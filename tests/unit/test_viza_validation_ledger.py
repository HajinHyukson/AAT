from __future__ import annotations

import zipfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology
from viza.file_format.container import write_viza_container
from viza.file_format.models import SectionStatus, VisibilityMode, VizaFileManifest, VizaSectionDescriptor
from viza.graph_schema import load_methodology_graph
from viza.project_store import get_project_store
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app
from viza.validation_ledger import (
    ValidationCompareRequest,
    ValidationRecordRequest,
    ValidationReplayRequest,
    compare_validation_records,
    create_validation_record,
    get_validation_ledger_store,
    read_validation_proof_from_viza,
    replay_validation_record,
    validate_validation_proof,
    validation_proof_for_export,
    validation_record_from_result,
)


client = TestClient(app)


def _graph():
    return load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)


def _result():
    return run_methodology(_graph(), load_attribute_registry())


def test_record_validation_from_run_and_fetch_by_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    result = _result()

    record = create_validation_record(ValidationRecordRequest(result=result))
    loaded = get_validation_ledger_store().require_record(record.validation_record_id)
    by_run = get_validation_ledger_store().list_by_run(result.run_id)

    assert loaded.result_checksum == result.result_checksum
    assert by_run[0].validation_record_id == record.validation_record_id
    assert loaded.performance_observation["status"] == "pending"
    assert loaded.outputs


def test_validation_compare_records_detects_checksum_changes(tmp_path) -> None:
    store = get_validation_ledger_store(tmp_path / "viza_projects.sqlite3")
    baseline = validation_record_from_result(_result())
    candidate = baseline.model_copy(
        update={
            "validation_record_id": "validation-candidate",
            "result_checksum": "changed-checksum",
        }
    )
    store.save_record(baseline)
    store.save_record(candidate)

    compared = compare_validation_records(
        ValidationCompareRequest(
            baseline_record_id=baseline.validation_record_id,
            candidate_record_id=candidate.validation_record_id,
        ),
        store,
    )

    assert compared.matching is False
    assert any(check.name == "result_checksum" and check.status == "mismatch" for check in compared.checks)


def test_validation_replay_compares_against_baseline(tmp_path) -> None:
    store = get_validation_ledger_store(tmp_path / "viza_projects.sqlite3")
    record = validation_record_from_result(_result())
    store.save_record(record)

    replay = replay_validation_record(
        ValidationReplayRequest(validation_record_id=record.validation_record_id, graph=_graph()),
        store,
    )

    assert replay.replayable is True
    assert replay.matching is True
    assert replay.result_checksum == record.result_checksum


def test_validation_service_endpoints_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    result_payload = _result().model_dump(mode="json")
    project = get_project_store().ensure_default_project()
    get_project_store().save_run_record(result_payload=result_payload, project_id=project.project_id)

    create_response = client.post("/viza/validation/record", json={"run_id": result_payload["run_id"]})
    record_id = create_response.json()["validation_record_id"]
    get_response = client.get(f"/viza/validation/{record_id}")
    by_run_response = client.get(f"/viza/validation/by-run/{result_payload['run_id']}")

    assert create_response.status_code == 200
    assert get_response.status_code == 200
    assert by_run_response.status_code == 200
    assert by_run_response.json()[0]["validation_record_id"] == record_id


def test_validation_proof_exports_and_imports_from_viza(tmp_path) -> None:
    record = validation_record_from_result(_result())
    proof = validation_proof_for_export(record)
    manifest = VizaFileManifest(
        schema="viza.document.v1",
        file_id="file-validation-proof-test",
        display_name="Validation Proof Test",
        object_kind="strategy_package",
        visibility=VisibilityMode.WHITE_BOX,
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        sections={"validation_proof": VizaSectionDescriptor(status=SectionStatus.INCLUDED)},
    )
    target = tmp_path / "validation-proof.viza"

    write_viza_container(target, manifest, {"validation_proof": proof})
    imported = read_validation_proof_from_viza(target)

    with zipfile.ZipFile(target) as archive:
        assert "proof/validation_manifest.json" in archive.namelist()
    assert imported["result_checksum"] == record.result_checksum
    assert imported["performance_observation"]["status"] == "pending"


def test_validation_proof_cannot_fake_missing_checksum() -> None:
    with pytest.raises(ValueError, match="evidence_checksum"):
        validate_validation_proof(
            {
                "run_id": "run-1",
                "graph_hash": "graph",
                "result_checksum": "result",
                "evidence_checksum": "",
            }
        )

    payload = _result().model_dump(mode="json")
    payload["manifest"].pop("evidence_checksum")
    with pytest.raises(ValueError, match="required checksums"):
        validation_record_from_result(payload)


def test_validation_proof_honors_source_rights_without_raw_evidence() -> None:
    proof = validation_proof_for_export(validation_record_from_result(_result()))

    assert proof["source_rights"]
    assert "evidence" not in proof
    assert "output_references" in proof
    assert proof["not_performance_claim"] is True

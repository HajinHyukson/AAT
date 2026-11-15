from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology
from viza.exports import ExportFormat, ExportRequest, export_payload
from viza.graph_schema import load_methodology_graph
from viza.insight_cards import build_insight_cards_from_result
from viza.project_store import get_project_store
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app


client = TestClient(app)


def _run_result_payload() -> dict:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    return run_methodology(graph, load_attribute_registry()).model_dump(mode="json")


def test_insight_card_payload_contains_translation_evidence_and_audit() -> None:
    result = _run_result_payload()

    cards = build_insight_cards_from_result(result)

    assert cards
    assert cards[0].translated_summary
    assert cards[0].missing_confirmations
    assert cards[0].invalidation_conditions
    assert cards[0].evidence
    assert cards[0].audit.run_id == result["run_id"]
    assert cards[0].audit.evidence_checksum == result["manifest"]["evidence_checksum"]


def test_run_insight_cards_endpoint_reads_saved_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    result = _run_result_payload()
    store = get_project_store()
    project = store.ensure_default_project()
    store.save_run_record(result_payload=result, project_id=project.project_id)

    response = client.get(f"/viza/runs/{result['run_id']}/insight-cards")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["insight_id"]
    assert payload[0]["translated_summary"]
    assert payload[0]["evidence"][0]["export_status"] in {"exportable", "redacted"}


def test_csv_export_includes_strategy_fit_columns_and_redactions() -> None:
    result = _run_result_payload()
    first_row = result["rows"][0]
    first_row["translated_summary"] = "restricted derived summary"
    first_row["source_restrictions"] = ["export_blocked"]

    exported = export_payload(
        ExportRequest(
            export_format=ExportFormat.CSV,
            result=result,
            selected_columns=["ticker", "strategy_fit_score", "translated_summary"],
        )
    )
    rows = list(csv.DictReader(io.StringIO(exported.payload)))

    assert rows[0]["strategy_fit_score"]
    assert rows[0]["translated_summary"] == "[redacted]"
    assert exported.redactions[0].path == "rows[0].translated_summary"


def test_json_export_carries_insights_translations_and_redacts_evidence_text() -> None:
    result = _run_result_payload()
    first_ref = result["rows"][0]["evidence_refs"][0]
    result["evidence"][first_ref]["entitlement"] = {"export_allowed": False}
    result["evidence"][first_ref]["entitlement_policy"] = "license_required"

    exported = export_payload(
        ExportRequest(
            export_format=ExportFormat.JSON,
            result=result,
            include_evidence=True,
        )
    )

    assert '"insights"' in exported.payload
    assert '"translations"' in exported.payload
    assert '"value": "[redacted]"' in exported.payload
    assert any(redaction.evidence_ref == first_ref for redaction in exported.redactions)

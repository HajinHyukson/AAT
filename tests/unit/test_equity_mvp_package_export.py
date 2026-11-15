from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from viza.file_format.container import read_viza_manifest, read_viza_section
from viza.project_store import get_project_store
from viza.service import app


client = TestClient(app)


def _set_flags(
    monkeypatch,
    tmp_path,
    *,
    persistence: bool = True,
    fmp: bool = False,
    fred: bool = False,
) -> None:
    monkeypatch.delenv("VIZA_ENGINE_TOKEN", raising=False)
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    monkeypatch.setenv("VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED", "true")
    monkeypatch.setenv("VIZA_EQUITY_SEC_WEDGE_ENABLED", "true")
    monkeypatch.setenv("VIZA_EQUITY_FMP_ENABLED", str(fmp).lower())
    monkeypatch.setenv("VIZA_EQUITY_FRED_ENABLED", str(fred).lower())
    monkeypatch.setenv("VIZA_EQUITY_LIVE_INTEGRATION_TESTS", "false")
    monkeypatch.setenv("VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED", str(persistence).lower())
    monkeypatch.setenv("VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED", "false")


def _persisted_run(monkeypatch, tmp_path, *, include_fmp: bool = False, include_fred: bool = False) -> str:
    _set_flags(monkeypatch, tmp_path, persistence=True, fmp=include_fmp, fred=include_fred)
    if include_fmp:
        monkeypatch.setenv("FMP_API_KEY", "TEST_FMP_SECRET_SHOULD_NOT_APPEAR")
        monkeypatch.setenv("FMP_PRODUCTION_LICENSE_CONFIRMED", "false")
    if include_fred:
        monkeypatch.setenv("FRED_API_KEY", "TEST_FRED_SECRET_SHOULD_NOT_APPEAR")
        monkeypatch.setenv("VIZA_FRED_USE_ALFRED_VINTAGES", "false")
    response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json={
            "target": {"cik": "320193", "ticker_alias": "AAPL"},
            "profile_id": "quality_value_long_only",
            "package_mode": "marketplace_draft",
            "include_fmp": include_fmp,
            "include_fred": include_fred,
            "use_live_connectors": False,
            "persist_run": True,
        },
    )
    assert response.status_code == 200
    return response.json()["run_id"]


def _export_package(run_id: str, target: Path, mode: str, *, project_id: str | None = None):
    response = client.post(
        f"/viza/equity/runtime-wedge/runs/{run_id}/package-draft",
        json={
            "package_mode": mode,
            "target_path": str(target),
            "project_id": project_id,
            "not_investment_advice_acknowledged": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_package_draft_endpoint_is_feature_flagged(monkeypatch, tmp_path) -> None:
    _set_flags(monkeypatch, tmp_path, persistence=False)
    run_response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json={
            "target": {"cik": "320193", "ticker_alias": "AAPL"},
            "profile_id": "quality_value_long_only",
            "package_mode": "marketplace_draft",
            "include_fmp": False,
            "include_fred": False,
            "use_live_connectors": False,
            "persist_run": True,
        },
    )
    assert run_response.status_code == 200
    assert run_response.json()["persisted"] is False

    blocked = client.post(
        "/viza/equity/runtime-wedge/runs/missing/package-draft",
        json={"package_mode": "marketplace_draft", "target_path": str(tmp_path / "blocked.viza")},
    )
    assert blocked.status_code == 403


def test_persisted_equity_run_exports_all_mvp_package_modes(monkeypatch, tmp_path) -> None:
    run_id = _persisted_run(monkeypatch, tmp_path)

    for mode in ("white_box", "output_only", "marketplace_draft"):
        target = tmp_path / f"{mode}.viza"
        payload = _export_package(run_id, target, mode)
        manifest = read_viza_manifest(target)
        radar = json.loads(read_viza_section(target, "radar_output").content)
        rights = json.loads(read_viza_section(target, "rights").content)
        proof = json.loads(read_viza_section(target, "validation_proof").content)

        assert payload["package_mode"] == mode
        assert payload["proof_checksum"]
        assert payload["pit_summary"]["observation_count"] > 0
        assert payload["rights_summary"]["policy_count"] > 0
        assert manifest.sections["radar_output"].status == "included"
        assert manifest.sections["validation_proof"].status == "included"
        assert manifest.sections["rights"].status == "included"
        assert radar["non_advice_boundary"]
        assert rights["source_rights_report"]["policies"]
        assert proof["proof_checksum"] == payload["proof_checksum"]
        if mode == "white_box":
            assert manifest.sections["methodology_graph"].status == "included"
        else:
            assert manifest.sections["methodology_graph"].status == "redacted"


def test_marketplace_draft_redacts_dev_only_fmp_and_preserves_fred_pit_warning(monkeypatch, tmp_path) -> None:
    fmp_secret = "TEST_FMP_SECRET_SHOULD_NOT_APPEAR"
    fred_secret = "TEST_FRED_SECRET_SHOULD_NOT_APPEAR"
    run_id = _persisted_run(monkeypatch, tmp_path, include_fmp=True, include_fred=True)
    target = tmp_path / "marketplace-draft.viza"

    payload = _export_package(run_id, target, "marketplace_draft")
    module_state = json.loads(read_viza_section(target, "module_state").content)
    rights = json.loads(read_viza_section(target, "rights").content)
    file_text = target.read_bytes().decode("latin1", errors="ignore")
    serialized = json.dumps({"payload": payload, "module_state": module_state, "rights": rights}, sort_keys=True)

    fmp_rows = [
        row
        for row in module_state["observations"]
        if row["connector_role"] == "licensed_market_data_connector"
    ]
    fred_rows = [row for row in module_state["observations"] if row["connector_role"] == "fred_macro"]

    assert fmp_rows
    assert all(row["value_redacted"] for row in fmp_rows)
    assert all(row["rights_policy"]["license_policy"] == "dev_only_unconfirmed" for row in fmp_rows)
    assert rights["rights_summary"]["redacted_count"] > 0
    assert rights["rights_summary"]["blocked_count"] > 0
    assert fred_rows
    assert payload["pit_summary"]["not_backtest_safe_count"] > 0
    assert fmp_secret not in serialized
    assert fred_secret not in serialized
    assert fmp_secret not in file_text
    assert fred_secret not in file_text


def test_package_export_records_to_existing_viza_file_export_store(monkeypatch, tmp_path) -> None:
    run_id = _persisted_run(monkeypatch, tmp_path)
    project = get_project_store(tmp_path / "viza_projects.sqlite3").ensure_default_project()
    payload = _export_package(
        run_id,
        tmp_path / "recorded-output-only.viza",
        "output_only",
        project_id=project.project_id,
    )

    assert payload["export_record"] is not None
    assert payload["export_record"]["file_id"] == payload["result"]["file_id"]
    assert payload["export_record"]["purpose"] == "equity_preview_package"

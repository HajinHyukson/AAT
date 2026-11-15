from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from viza.equity.persistence import get_equity_preview_store
from viza.service import app


client = TestClient(app)


def _set_flags(
    monkeypatch,
    tmp_path,
    *,
    persistence: bool = True,
    refresh: bool = False,
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
    monkeypatch.setenv("VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED", str(refresh).lower())
    monkeypatch.setenv("VIZA_SEC_USER_AGENT", "VIZA Equity Persistence Tests test@example.com")


def _preview_request(**overrides):
    request = {
        "target": {"cik": "320193", "ticker_alias": "AAPL"},
        "profile_id": "quality_value_long_only",
        "package_mode": "marketplace_draft",
        "include_fmp": False,
        "include_fred": False,
        "use_live_connectors": False,
        "persist_run": True,
    }
    request.update(overrides)
    return request


def test_persistence_flag_off_returns_disabled_without_durable_write(monkeypatch, tmp_path) -> None:
    _set_flags(monkeypatch, tmp_path, persistence=False)

    response = client.post("/viza/equity/runtime-wedge/preview", json=_preview_request())
    runs = client.get("/viza/equity/runtime-wedge/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted"] is False
    assert payload["persistence_status"] == "disabled"
    assert runs.status_code == 403


def test_persistence_flag_on_saves_run_record_and_links_reports(monkeypatch, tmp_path) -> None:
    _set_flags(monkeypatch, tmp_path, persistence=True)

    response = client.post("/viza/equity/runtime-wedge/preview", json=_preview_request())

    assert response.status_code == 200
    payload = response.json()
    run_id = payload["run_id"]
    assert payload["persisted"] is True
    assert payload["persistence_status"] == "persisted"
    assert run_id.startswith("eq-preview-run-")
    assert payload["history_url"].endswith(run_id)
    assert payload["target"]["cik"] == "0000320193"
    assert "ticker is alias only" in payload["target"]["primary_key_policy"].lower()

    list_response = client.get("/viza/equity/runtime-wedge/runs")
    detail_response = client.get(f"/viza/equity/runtime-wedge/runs/{run_id}")

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    summary = list_response.json()["runs"][0]
    assert summary["run_id"] == run_id
    assert summary["profile_id"] == "quality_value_long_only"
    assert summary["status"] in {"pass", "warn", "block"}
    assert summary["pit_status"] in {"pass", "warn", "block"}
    assert summary["rights_status"] in {"pass", "warn", "block"}
    assert summary["validation_status"] in {"pass", "warn", "block"}
    assert summary["proof_checksum"]

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["run_record"]["run_id"] == run_id
    assert detail["run_record"]["module_id"] == "viza.finance.equity_investment"
    assert detail["evidence_bundle"]["observation_ids"]
    assert detail["validation_report"]["rules"]
    assert detail["source_rights_report"]["policies"]
    assert detail["package_redaction_preview"]["package_mode"] == "marketplace_draft"
    assert "not personalized investment advice" in detail["output_preview"]["non_advice_boundary"]


def test_saved_sec_observations_have_pit_rights_and_source_lineage(monkeypatch, tmp_path) -> None:
    _set_flags(monkeypatch, tmp_path, persistence=True)

    run_id = client.post("/viza/equity/runtime-wedge/preview", json=_preview_request()).json()["run_id"]
    detail = client.get(f"/viza/equity/runtime-wedge/runs/{run_id}").json()

    sec_observations = [
        item for item in detail["observations"] if item["connector_role"] in {"sec_filings", "xbrl_facts"}
    ]
    assert sec_observations
    for observation in sec_observations:
        assert observation["run_id"] == run_id
        assert observation["source_id"]
        assert observation["observed_at"]
        assert observation["available_at"]
        assert observation["retrieved_at"]
        assert observation["rights_policy"]["license_policy"] == "public_official"
        assert observation["rights_policy"]["export_policy"] == "metadata_and_derived_allowed"
        assert "PIT_safe" in observation


def test_fmp_and_fred_observations_preserve_rights_and_pit_labels(monkeypatch, tmp_path) -> None:
    fmp_secret = "TEST_FMP_SECRET_SHOULD_NOT_APPEAR"
    fred_secret = "TEST_FRED_SECRET_SHOULD_NOT_APPEAR"
    _set_flags(monkeypatch, tmp_path, persistence=True, fmp=True, fred=True)
    monkeypatch.setenv("FMP_API_KEY", fmp_secret)
    monkeypatch.setenv("FRED_API_KEY", fred_secret)
    monkeypatch.setenv("FMP_PRODUCTION_LICENSE_CONFIRMED", "false")
    monkeypatch.setenv("VIZA_FRED_USE_ALFRED_VINTAGES", "false")

    response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json=_preview_request(include_fmp=True, include_fred=True),
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    detail = client.get(f"/viza/equity/runtime-wedge/runs/{run_id}").json()
    serialized = json.dumps(detail, sort_keys=True)
    fmp_observations = [
        item for item in detail["observations"] if item["connector_role"] == "licensed_market_data_connector"
    ]
    fred_observations = [item for item in detail["observations"] if item["connector_role"] == "fred_macro"]

    assert fmp_observations
    assert fred_observations
    for observation in fmp_observations:
        assert observation["rights_policy"]["license_policy"] == "dev_only_unconfirmed"
        assert observation["rights_policy"]["export_policy"] == "blocked"
        assert observation["rights_policy"]["marketplace_policy"] == "redacted"
    for observation in fred_observations:
        assert observation["PIT_safe"] is False
        assert observation["lookahead_risk"] in {
            "macro_revision_or_latest_only",
            "fred_latest_only_without_vintage_cutoff",
        }
    assert fmp_secret not in serialized
    assert fred_secret not in serialized


def test_replay_from_stored_observations_creates_linked_run_without_live_calls(monkeypatch, tmp_path) -> None:
    _set_flags(monkeypatch, tmp_path, persistence=True)

    original = client.post("/viza/equity/runtime-wedge/preview", json=_preview_request()).json()
    replay_response = client.post(
        f"/viza/equity/runtime-wedge/runs/{original['run_id']}/replay",
        json={"mode": "replay_from_stored_observations", "package_mode": "marketplace_draft"},
    )

    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert replay["mode"] == "replay_from_stored_observations"
    assert replay["parent_run_id"] == original["run_id"]
    assert replay["run_id"] != original["run_id"]
    assert replay["preview"]["audit"]["fixture_mode"] is True

    original_detail = client.get(f"/viza/equity/runtime-wedge/runs/{original['run_id']}").json()
    replay_detail = client.get(f"/viza/equity/runtime-wedge/runs/{replay['run_id']}").json()
    assert original_detail["run_record"]["parent_run_id"] is None
    assert replay_detail["run_record"]["parent_run_id"] == original["run_id"]
    assert original_detail["run_record"]["created_from"] == "api_preview"
    assert replay_detail["run_record"]["created_from"] == "replay_from_stored_observations"


def test_replay_with_refresh_is_feature_flagged_and_creates_linked_run(monkeypatch, tmp_path) -> None:
    _set_flags(monkeypatch, tmp_path, persistence=True, refresh=False)
    original = client.post("/viza/equity/runtime-wedge/preview", json=_preview_request()).json()

    blocked = client.post(
        f"/viza/equity/runtime-wedge/runs/{original['run_id']}/replay",
        json={"mode": "replay_with_refresh", "package_mode": "marketplace_draft"},
    )
    assert blocked.status_code == 403

    monkeypatch.setenv("VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED", "true")
    refreshed = client.post(
        f"/viza/equity/runtime-wedge/runs/{original['run_id']}/replay",
        json={"mode": "replay_with_refresh", "package_mode": "marketplace_draft"},
    )
    assert refreshed.status_code == 200
    payload = refreshed.json()
    assert payload["mode"] == "replay_with_refresh"
    assert payload["parent_run_id"] == original["run_id"]
    assert payload["run_id"] != original["run_id"]
    detail = client.get(f"/viza/equity/runtime-wedge/runs/{payload['run_id']}").json()
    assert detail["run_record"]["created_from"] == "replay_with_refresh"
    assert detail["run_record"]["parent_run_id"] == original["run_id"]


def test_persisted_records_do_not_contain_api_keys(monkeypatch, tmp_path) -> None:
    fmp_secret = "TEST_FMP_SECRET_SHOULD_NOT_APPEAR"
    fred_secret = "TEST_FRED_SECRET_SHOULD_NOT_APPEAR"
    _set_flags(monkeypatch, tmp_path, persistence=True, fmp=True, fred=True)
    monkeypatch.setenv("FMP_API_KEY", fmp_secret)
    monkeypatch.setenv("FRED_API_KEY", fred_secret)

    response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json=_preview_request(include_fmp=True, include_fred=True),
    )
    run_id = response.json()["run_id"]
    detail = client.get(f"/viza/equity/runtime-wedge/runs/{run_id}").json()
    replay = client.post(
        f"/viza/equity/runtime-wedge/runs/{run_id}/replay",
        json={"mode": "replay_from_stored_observations"},
    ).json()

    store_path = tmp_path / "viza_projects.sqlite3"
    with sqlite3.connect(store_path) as connection:
        rows = connection.execute(
            """
            SELECT persisted_payload_json FROM equity_preview_runs
            UNION ALL
            SELECT evidence_bundle_json FROM equity_preview_evidence_bundles
            UNION ALL
            SELECT report_json FROM equity_preview_report_records
            UNION ALL
            SELECT normalized_json FROM equity_preview_run_observations
            """
        ).fetchall()
    persisted_text = "\n".join(row[0] for row in rows)
    api_text = json.dumps({"response": response.json(), "detail": detail, "replay": replay}, sort_keys=True)

    assert fmp_secret not in persisted_text
    assert fred_secret not in persisted_text
    assert fmp_secret not in api_text
    assert fred_secret not in api_text


def test_store_detail_can_be_loaded_directly(monkeypatch, tmp_path) -> None:
    _set_flags(monkeypatch, tmp_path, persistence=True)

    run_id = client.post("/viza/equity/runtime-wedge/preview", json=_preview_request()).json()["run_id"]
    detail = get_equity_preview_store(tmp_path / "viza_projects.sqlite3").require_detail(run_id)

    assert detail.run_record["run_id"] == run_id
    assert detail.evidence_bundle["run_id"] == run_id
    assert detail.observations

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from viza.service import app


client = TestClient(app)


def _set_flags(
    monkeypatch,
    *,
    runtime: bool = True,
    sec: bool = True,
    fmp: bool = False,
    fred: bool = False,
    live: bool = False,
) -> None:
    monkeypatch.delenv("VIZA_ENGINE_TOKEN", raising=False)
    monkeypatch.setenv("VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED", str(runtime).lower())
    monkeypatch.setenv("VIZA_EQUITY_SEC_WEDGE_ENABLED", str(sec).lower())
    monkeypatch.setenv("VIZA_EQUITY_FMP_ENABLED", str(fmp).lower())
    monkeypatch.setenv("VIZA_EQUITY_FRED_ENABLED", str(fred).lower())
    monkeypatch.setenv("VIZA_EQUITY_LIVE_INTEGRATION_TESTS", str(live).lower())
    monkeypatch.setenv("VIZA_SEC_USER_AGENT", "VIZA Equity API Tests test@example.com")


def _preview_request(**overrides):
    request = {
        "target": {"cik": "320193", "ticker_alias": "AAPL"},
        "profile_id": "quality_value_long_only",
        "package_mode": "marketplace_draft",
        "include_fmp": False,
        "include_fred": False,
        "use_live_connectors": False,
        "cutoff_timestamp": None,
        "mock_fixture_id": "sec_fmp_fred_runtime_wedge_fixture",
    }
    request.update(overrides)
    return request


def test_feature_flag_off_disables_equity_preview_endpoint(monkeypatch) -> None:
    _set_flags(monkeypatch, runtime=False, sec=False)

    status = client.get("/viza/equity/runtime-wedge/status")
    preview = client.post("/viza/equity/runtime-wedge/preview", json=_preview_request())

    assert status.status_code == 200
    assert status.json()["enabled"] is False
    assert preview.status_code == 403


def test_flags_on_mock_preview_returns_required_contract_without_keys(monkeypatch) -> None:
    secret_fmp = "TEST_FMP_SECRET_SHOULD_NOT_APPEAR"
    secret_fred = "TEST_FRED_SECRET_SHOULD_NOT_APPEAR"
    _set_flags(monkeypatch)
    monkeypatch.setenv("FMP_API_KEY", secret_fmp)
    monkeypatch.setenv("FRED_API_KEY", secret_fred)

    response = client.post("/viza/equity/runtime-wedge/preview", json=_preview_request())

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["target"]["cik"] == "0000320193"
    assert payload["target"]["ticker_alias"] == "AAPL"
    assert "ticker is alias only" in payload["target"]["primary_key_policy"].lower()
    assert payload["profile"]["profile_id"] == "quality_value_long_only"
    assert payload["profile"]["compatibility_status"] in {"pass", "warn", "block"}
    assert payload["evidence_summary"]["source_count"] >= 3
    assert payload["evidence_summary"]["observed_at"]
    assert payload["evidence_summary"]["available_at"]
    assert payload["evidence_summary"]["retrieved_at"]
    assert payload["fundamental_attributes"]
    assert "not personalized investment advice" in payload["output_preview"]["non_advice_boundary"]
    assert payload["validation_report"]["rules"]
    assert payload["source_rights_report"]["policies"]
    assert payload["package_redaction_preview"]["package_mode"] == "marketplace_draft"
    assert payload["audit"]["fixture_mode"] is True
    assert secret_fmp not in serialized
    assert secret_fred not in serialized


def test_live_connectors_are_rejected_unless_live_flag_enabled(monkeypatch) -> None:
    _set_flags(monkeypatch, live=False)

    response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json=_preview_request(use_live_connectors=True),
    )

    assert response.status_code == 403
    assert "Live equity connector preview is disabled" in response.text


def test_ticker_alias_only_returns_block_without_primary_keying_on_ticker(monkeypatch) -> None:
    _set_flags(monkeypatch)

    response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json=_preview_request(target={"ticker_alias": "AAPL"}),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["compatibility_status"] == "block"
    assert payload["target"]["cik"] is None
    assert payload["target"]["entity_id"].startswith("viza:eq:entity:unresolved_alias_")
    assert payload["evidence_summary"]["source_count"] == 0


def test_include_fmp_flag_off_returns_disabled_context(monkeypatch) -> None:
    _set_flags(monkeypatch, fmp=False)
    monkeypatch.setenv("FMP_API_KEY", "TEST_FMP_SECRET_SHOULD_NOT_APPEAR")

    response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json=_preview_request(include_fmp=True),
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["optional_market_context"]["fmp"]["enabled"] is False
    assert payload["optional_market_context"]["fmp"]["status"] == "disabled"
    assert "TEST_FMP_SECRET_SHOULD_NOT_APPEAR" not in json.dumps(payload, sort_keys=True)


def test_fmp_mock_preview_is_dev_only_and_marketplace_redacted(monkeypatch) -> None:
    _set_flags(monkeypatch, fmp=True)
    monkeypatch.setenv("FMP_API_KEY", "TEST_FMP_SECRET_SHOULD_NOT_APPEAR")
    monkeypatch.setenv("FMP_PRODUCTION_LICENSE_CONFIRMED", "false")

    response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json=_preview_request(include_fmp=True, package_mode="marketplace_draft"),
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["optional_market_context"]["fmp"]["status"] == "dev_only"
    assert payload["optional_market_context"]["fmp"]["rights_status"] == "dev_only_unconfirmed"
    assert payload["optional_market_context"]["fmp"]["values_redacted"] is True
    assert any(row["source"] == "fmp" for row in payload["package_redaction_preview"]["blocked"])
    assert "TEST_FMP_SECRET_SHOULD_NOT_APPEAR" not in json.dumps(payload, sort_keys=True)


def test_fred_mock_preview_is_latest_only_not_true_pit(monkeypatch) -> None:
    _set_flags(monkeypatch, fred=True)
    monkeypatch.setenv("FRED_API_KEY", "TEST_FRED_SECRET_SHOULD_NOT_APPEAR")
    monkeypatch.setenv("VIZA_FRED_USE_ALFRED_VINTAGES", "false")

    response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json=_preview_request(include_fred=True),
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["optional_market_context"]["fred"]["status"] == "latest_only"
    assert payload["optional_market_context"]["fred"]["pit_status"] == "latest_only_or_ingestion_timestamped"
    assert "TEST_FRED_SECRET_SHOULD_NOT_APPEAR" not in json.dumps(payload, sort_keys=True)


def test_invalid_package_mode_returns_validation_error(monkeypatch) -> None:
    _set_flags(monkeypatch)

    response = client.post(
        "/viza/equity/runtime-wedge/preview",
        json=_preview_request(package_mode="black_box"),
    )

    assert response.status_code == 422

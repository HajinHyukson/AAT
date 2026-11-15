from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from viza.equity import DEFAULT_EQUITY_REGISTRIES_DIR, EQUITY_MODULE_ID
from viza.equity.config import EquityRuntimeConfig
from viza.equity.connectors import normalize_cik
from viza.equity.registry import EquityRegistryError
from viza.equity.runtime import (
    EquityRuntimeDisabled,
    build_sec_filing_evidence_bundle,
    derive_sec_public_fundamental_attributes,
    fetch_fmp_market_snapshot_optional,
    fetch_fred_macro_context_optional,
    fetch_sec_companyfacts,
    fetch_sec_submissions,
    load_equity_module_manifest,
    preview_package_redaction,
    render_equity_radar_preview,
    render_source_rights_report,
    render_validation_report,
    resolve_equity_identity,
    resolve_sec_company,
    run_quality_value_profile_compatibility,
    run_sec_quality_value_wedge,
)
from viza.modules import get_module_registry


NOW = datetime(2026, 5, 14, 14, 0, tzinfo=timezone.utc)


def _fact(value, fy, fp, end, filed):
    return {
        "val": value,
        "fy": fy,
        "fp": fp,
        "form": "10-K",
        "filed": filed,
        "end": end,
        "accn": f"accn-{fy}-{fp}",
    }


SEC_SUBMISSIONS = {
    "cik": "320193",
    "name": "Apple Inc.",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
    "filings": {
        "recent": {
            "form": ["10-K"],
            "accessionNumber": ["0000320193-23-000106"],
            "filingDate": ["2023-11-03"],
            "reportDate": ["2023-09-30"],
            "acceptanceDateTime": ["2023-11-02T18:08:27.000Z"],
            "primaryDocument": ["aapl-20230930.htm"],
        }
    },
}

SEC_COMPANYFACTS = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        _fact(394_328_000_000, 2022, "FY", "2022-09-24", "2022-10-28"),
                        _fact(383_285_000_000, 2023, "FY", "2023-09-30", "2023-11-03"),
                    ]
                }
            },
            "GrossProfit": {"units": {"USD": [_fact(169_148_000_000, 2023, "FY", "2023-09-30", "2023-11-03")]}},
            "OperatingIncomeLoss": {"units": {"USD": [_fact(114_301_000_000, 2023, "FY", "2023-09-30", "2023-11-03")]}},
            "NetIncomeLoss": {"units": {"USD": [_fact(96_995_000_000, 2023, "FY", "2023-09-30", "2023-11-03")]}},
            "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [_fact(110_543_000_000, 2023, "FY", "2023-09-30", "2023-11-03")]}},
            "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [_fact(10_959_000_000, 2023, "FY", "2023-09-30", "2023-11-03")]}},
            "Assets": {"units": {"USD": [_fact(352_583_000_000, 2023, "FY", "2023-09-30", "2023-11-03")]}},
            "Liabilities": {"units": {"USD": [_fact(290_437_000_000, 2023, "FY", "2023-09-30", "2023-11-03")]}},
            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                "units": {
                    "shares": [
                        _fact(16_325_819_000, 2022, "FY", "2022-09-24", "2022-10-28"),
                        _fact(15_812_547_000, 2023, "FY", "2023-09-30", "2023-11-03"),
                    ]
                }
            },
        }
    },
}


def _enabled_config(**overrides) -> EquityRuntimeConfig:
    values = {
        "runtime_handlers_enabled": True,
        "sec_wedge_enabled": True,
        "sec_user_agent": "VIZA Equity Tests test@example.com",
        "sec_max_rps": 5,
    }
    values.update(overrides)
    return EquityRuntimeConfig(**values)


def _sec_transport(calls: list[str]):
    def transport(url: str, headers: dict[str, str], _timeout: float):
        calls.append(url)
        assert headers["User-Agent"] == "VIZA Equity Tests test@example.com"
        if "submissions" in url:
            return SEC_SUBMISSIONS
        if "companyfacts" in url:
            return SEC_COMPANYFACTS
        raise AssertionError(f"unexpected SEC URL: {url}")

    return transport


def _sec_evidence_and_fundamentals():
    identity = resolve_sec_company(
        resolve_equity_identity("320193", retrieved_at=NOW),
        SEC_SUBMISSIONS,
        retrieved_at=NOW,
    )
    evidence = build_sec_filing_evidence_bundle(
        identity,
        SEC_SUBMISSIONS,
        SEC_COMPANYFACTS,
        retrieved_at=NOW,
    )
    fundamentals = derive_sec_public_fundamental_attributes(evidence)
    return identity, evidence, fundamentals


def test_feature_flag_disabled_leaves_module_registry_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED", "false")
    get_module_registry.cache_clear()

    module_ids = {module.module_id for module in get_module_registry().list_modules()}

    assert EQUITY_MODULE_ID not in module_ids
    with pytest.raises(EquityRuntimeDisabled):
        load_equity_module_manifest(config=EquityRuntimeConfig())

    get_module_registry.cache_clear()


def test_feature_flag_enabled_loads_equity_manifest(monkeypatch) -> None:
    monkeypatch.setenv("VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED", "true")
    get_module_registry.cache_clear()

    module = get_module_registry().get_module(EQUITY_MODULE_ID)
    manifest = load_equity_module_manifest(config=_enabled_config())

    assert module.module_id == EQUITY_MODULE_ID
    assert "viza.finance.equity_investment.sec_filing_evidence_bundle" in module.node_types
    assert manifest["module_id"] == EQUITY_MODULE_ID

    get_module_registry.cache_clear()


def test_invalid_manifest_fails_closed(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "registries"
    shutil.copytree(DEFAULT_EQUITY_REGISTRIES_DIR, fixture_dir)
    manifest_path = fixture_dir / "viza.finance.equity_investment.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["module_id"] = "viza.finance.not_equity"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(EquityRegistryError):
        load_equity_module_manifest(config=_enabled_config(), artifact_dir=fixture_dir)


def test_sec_cik_padding_and_mocked_evidence_bundle() -> None:
    calls: list[str] = []
    config = _enabled_config()

    submissions = fetch_sec_submissions("320193", config=config, transport=_sec_transport(calls))
    companyfacts = fetch_sec_companyfacts("320193", config=config, transport=_sec_transport(calls))
    identity = resolve_sec_company(
        resolve_equity_identity("320193", retrieved_at=NOW),
        submissions,
        retrieved_at=NOW,
    )
    evidence = build_sec_filing_evidence_bundle(identity, submissions, companyfacts, retrieved_at=NOW)

    assert normalize_cik("320193") == "0000320193"
    assert evidence["latest_periodic_filing"]["source_id"].startswith("sec:CIK0000320193")
    assert evidence["available_at"]
    assert evidence["retrieved_at"]
    assert evidence["rights_policy"]["license_policy"] == "public_official"
    assert evidence["PIT_policy"]["PIT_safe"] is True
    assert len(calls) == 2


def test_sec_fundamental_attributes_include_pit_and_rights() -> None:
    _, evidence, fundamentals = _sec_evidence_and_fundamentals()
    attributes_by_key = {attribute["key"]: attribute for attribute in fundamentals["attributes"]}

    assert evidence["pit_status"] == "pass"
    assert "revenue_latest_period" in attributes_by_key
    assert "free_cash_flow_or_cfo_capex_proxy_if_available" in attributes_by_key
    assert "filing_freshness_days" in attributes_by_key
    for attribute in fundamentals["attributes"]:
        assert attribute["source_ids"]
        assert attribute["observed_at"]
        assert attribute["available_at"]
        assert attribute["retrieved_at"]
        assert attribute["rights_policy"]["license_policy"] == "public_official"


def test_fmp_disabled_and_missing_key_do_not_call_transport() -> None:
    identity = resolve_equity_identity("320193", ticker_alias="AAPL", retrieved_at=NOW)
    calls: list[str] = []

    disabled = fetch_fmp_market_snapshot_optional(
        identity,
        config=_enabled_config(fmp_enabled=False, fmp_api_key="unused"),
        transport=lambda url, _headers, _timeout: calls.append(url) or {},
        retrieved_at=NOW,
    )
    missing_key = fetch_fmp_market_snapshot_optional(
        identity,
        config=_enabled_config(fmp_enabled=True, fmp_api_key=None),
        transport=lambda url, _headers, _timeout: calls.append(url) or {},
        retrieved_at=NOW,
    )

    assert disabled["status"] == "disabled"
    assert missing_key["status"] == "missing_credential"
    assert calls == []


def test_fmp_mocked_snapshot_is_dev_only_without_key_leak() -> None:
    secret = "unit-test-fmp-secret-value"
    identity = resolve_equity_identity("320193", ticker_alias="AAPL", retrieved_at=NOW)

    def transport(url: str, _headers: dict[str, str], _timeout: float):
        if "profile" in url:
            return [{"symbol": "AAPL", "cik": "320193", "companyName": "Apple Inc."}]
        if "quote" in url:
            return [{"symbol": "AAPL", "price": 195.12, "marketCap": 3_010_000_000_000, "timestamp": 1715600000}]
        if "market-capitalization" in url:
            return [{"symbol": "AAPL", "date": "2026-05-13", "marketCap": 3_010_000_000_000}]
        raise AssertionError(f"unexpected FMP URL: {url}")

    snapshot = fetch_fmp_market_snapshot_optional(
        identity,
        config=_enabled_config(fmp_enabled=True, fmp_api_key=secret),
        transport=transport,
        retrieved_at=NOW,
    )

    assert snapshot["status"] == "available"
    assert snapshot["rights_policy"]["license_policy"] == "dev_only_unconfirmed"
    assert snapshot["rights_policy"]["export_policy"] == "blocked"
    assert any(observation["field"] == "latest_price" for observation in snapshot["observations"])
    assert secret not in json.dumps(snapshot, sort_keys=True)


def test_fred_disabled_missing_key_and_mocked_latest_only_pit() -> None:
    calls: list[str] = []
    disabled = fetch_fred_macro_context_optional(
        config=_enabled_config(fred_enabled=False, fred_api_key="unused"),
        transport=lambda url, _headers, _timeout: calls.append(url) or {},
        retrieved_at=NOW,
    )
    missing_key = fetch_fred_macro_context_optional(
        config=_enabled_config(fred_enabled=True, fred_api_key=None),
        transport=lambda url, _headers, _timeout: calls.append(url) or {},
        retrieved_at=NOW,
    )

    assert disabled["status"] == "disabled"
    assert missing_key["status"] == "missing_credential"
    assert calls == []

    macro = fetch_fred_macro_context_optional(
        config=_enabled_config(fred_enabled=True, fred_api_key="unit-test-fred-secret"),
        series_ids=("DGS10",),
        transport=lambda _url, _headers, _timeout: {
            "observations": [
                {
                    "date": "2026-05-13",
                    "value": "4.12",
                    "realtime_start": "2026-05-14",
                    "realtime_end": "2026-05-14",
                }
            ]
        },
        retrieved_at=NOW,
    )

    assert macro["status"] == "available"
    assert macro["PIT_policy"]["PIT_safe"] is False
    assert macro["PIT_policy"]["pit_status"] == "latest_only_or_ingestion_timestamped"
    assert "unit-test-fred-secret" not in json.dumps(macro, sort_keys=True)


def test_quality_value_compatibility_pass_warn_and_block() -> None:
    identity, evidence, fundamentals = _sec_evidence_and_fundamentals()

    public_only = run_quality_value_profile_compatibility(
        identity=identity,
        evidence_bundle=evidence,
        fundamentals=fundamentals,
    )
    valuation_required = run_quality_value_profile_compatibility(
        identity=identity,
        evidence_bundle=evidence,
        fundamentals=fundamentals,
        require_market_price_for_valuation=True,
    )
    unresolved = run_quality_value_profile_compatibility(
        identity=resolve_equity_identity("AAPL", retrieved_at=NOW),
        evidence_bundle=None,
        fundamentals=None,
    )

    assert public_only["status"] == "warn"
    assert any(issue["code"] == "market_price_optional_missing" for issue in public_only["issues"])
    assert valuation_required["status"] == "block"
    assert any(issue["code"] == "market_price_required" for issue in valuation_required["issues"])
    assert unresolved["status"] == "block"


def test_outputs_and_package_redaction_include_non_advice_and_rights() -> None:
    identity, evidence, fundamentals = _sec_evidence_and_fundamentals()
    fmp = fetch_fmp_market_snapshot_optional(
        identity,
        config=_enabled_config(fmp_enabled=True, fmp_api_key="unit-secret"),
        transport=lambda _url, _headers, _timeout: [{"symbol": "AAPL", "price": 195.12, "timestamp": 1715600000}],
        retrieved_at=NOW,
    )
    compatibility = run_quality_value_profile_compatibility(
        identity=identity,
        evidence_bundle=evidence,
        fundamentals=fundamentals,
        market_snapshot=fmp,
    )

    radar = render_equity_radar_preview(
        identity=identity,
        evidence_bundle=evidence,
        fundamentals=fundamentals,
        market_snapshot=fmp,
        compatibility=compatibility,
    )
    validation = render_validation_report(
        compatibility=compatibility,
        evidence_bundle=evidence,
        fundamentals=fundamentals,
    )
    rights = render_source_rights_report(evidence, fundamentals, fmp)
    package_preview = preview_package_redaction(sources=rights["sources"])

    assert "not personalized investment advice" in radar["non_advice_boundary"]
    assert validation["status"] in {"pass", "warn"}
    assert rights["status"] == "block"
    assert package_preview["package_modes"]["white_box"]["status"] == "warn"
    assert package_preview["package_modes"]["output_only"]["status"] == "warn"
    assert package_preview["package_modes"]["marketplace_draft"]["status"] == "block"


def test_full_wedge_uses_mocks_and_does_not_expose_keys() -> None:
    secret = "unit-test-fmp-secret-value"
    calls: list[str] = []
    config = _enabled_config(
        fmp_enabled=True,
        fred_enabled=True,
        fmp_api_key=secret,
        fred_api_key="unit-test-fred-secret-value",
    )

    result = run_sec_quality_value_wedge(
        "320193",
        config=config,
        sec_transport=_sec_transport(calls),
        fmp_transport=lambda _url, _headers, _timeout: [{"symbol": "AAPL", "price": 195.12, "timestamp": 1715600000}],
        fred_transport=lambda _url, _headers, _timeout: {
            "observations": [{"date": "2026-05-13", "value": "4.12"}]
        },
        retrieved_at=NOW,
    )

    serialized = json.dumps(result, sort_keys=True)
    assert result["module_id"] == EQUITY_MODULE_ID
    assert result["outputs"]["source_rights_report"]["status"] == "block"
    assert "package_redaction_preview" in result["outputs"]
    assert secret not in serialized
    assert "unit-test-fred-secret-value" not in serialized


def test_unit_secret_values_do_not_appear_in_generated_docs() -> None:
    sentinel = "unit-test-secret-that-must-not-exist"
    roots = [
        Path("docs/equity_module/v0.1/fixtures"),
        Path("docs/equity_module/v0.1/reports"),
        Path("docs/equity_module/v0.1/proofs"),
    ]
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".json", ".md", ".csv", ".txt"}:
                assert sentinel not in path.read_text(encoding="utf-8")

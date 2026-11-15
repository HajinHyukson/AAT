from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from viza.equity.config import EquityRuntimeConfig
from viza.equity.connectors import normalize_cik
from viza.equity.persistence import (
    EquityPreviewReplayRequest,
    EquityPreviewReplayResult,
    EquityPreviewRunDetail,
    EquityPreviewRunList,
    get_equity_preview_store,
)
from viza.equity.registry import EQUITY_MODULE_ID, EQUITY_MODULE_VERSION, PackageMode
from viza.equity.runtime import (
    NON_ADVICE_BOUNDARY,
    QUALITY_VALUE_PROFILE_ID,
    run_sec_quality_value_wedge,
)


DESKTOP_PACKAGE_MODES = ("white_box", "output_only", "marketplace_draft")
MOCK_FIXTURE_ID = "sec_fmp_fred_runtime_wedge_fixture"


class EquityPreviewTarget(BaseModel):
    cik: str | None = None
    ticker_alias: str | None = None


class EquityRuntimeWedgePreviewRequest(BaseModel):
    target: EquityPreviewTarget = Field(default_factory=EquityPreviewTarget)
    profile_id: str = QUALITY_VALUE_PROFILE_ID
    package_mode: Literal["white_box", "output_only", "marketplace_draft"] = "marketplace_draft"
    include_fmp: bool = False
    include_fred: bool = False
    use_live_connectors: bool = False
    cutoff_timestamp: str | None = None
    mock_fixture_id: str = MOCK_FIXTURE_ID
    persist_run: bool = False


def equity_runtime_wedge_status_payload(
    *,
    config: EquityRuntimeConfig | None = None,
) -> dict[str, Any]:
    active_config = config or EquityRuntimeConfig.from_env()
    return {
        "module_id": EQUITY_MODULE_ID,
        "module_version": EQUITY_MODULE_VERSION,
        "enabled": active_config.runtime_handlers_enabled and active_config.sec_wedge_enabled,
        "feature_flags": _feature_flags(active_config),
        "mock_fixture_default": True,
        "mock_fixture_id": MOCK_FIXTURE_ID,
        "profile_id": QUALITY_VALUE_PROFILE_ID,
        "package_modes": list(DESKTOP_PACKAGE_MODES),
        "live_mode_allowed": active_config.live_integration_tests_enabled,
        "persistence_enabled": active_config.preview_persistence_enabled,
        "replay_refresh_enabled": active_config.preview_replay_refresh_enabled,
    }


def build_equity_runtime_wedge_preview(
    request: EquityRuntimeWedgePreviewRequest,
    *,
    config: EquityRuntimeConfig | None = None,
    created_from: str = "api_preview",
    parent_run_id: str | None = None,
) -> dict[str, Any]:
    active_config = config or EquityRuntimeConfig.from_env()
    if request.profile_id != QUALITY_VALUE_PROFILE_ID:
        raise ValueError("Only quality_value_long_only is supported by the packaged preview wedge.")
    if not active_config.runtime_handlers_enabled or not active_config.sec_wedge_enabled:
        raise PermissionError("Equity runtime wedge preview is feature-flag disabled.")
    if request.use_live_connectors and not active_config.live_integration_tests_enabled:
        raise PermissionError("Live equity connector preview is disabled unless live integration tests are enabled.")

    target_value = _request_target_value(request.target)
    retrieved_at = _parse_cutoff_timestamp(request.cutoff_timestamp)
    preview_config = replace(
        active_config,
        fmp_enabled=active_config.fmp_enabled and request.include_fmp,
        fred_enabled=active_config.fred_enabled and request.include_fred,
    )
    use_mocks = not request.use_live_connectors
    runtime_payload = run_sec_quality_value_wedge(
        target_value,
        config=preview_config,
        sec_transport=_mock_sec_transport if use_mocks else None,
        fmp_transport=_mock_fmp_transport if use_mocks else None,
        fred_transport=_mock_fred_transport if use_mocks else None,
        retrieved_at=retrieved_at,
        require_market_price_for_valuation=False,
    )
    response = _compact_runtime_payload(
        runtime_payload,
        request=request,
        config=preview_config,
        base_config=active_config,
        fixture_mode=use_mocks,
    )
    proof_checksum = _checksum(response)
    response["audit"] = {
        "run_id": f"eq-preview-{proof_checksum[:16].lower()}",
        "graph_hash": _checksum(
            {
                "target": response["target"],
                "evidence": response["evidence_summary"].get("sources", []),
                "profile": response["profile"],
            }
        ),
        "profile_hash": _checksum({"profile_id": request.profile_id})[:32],
        "proof_checksum": proof_checksum,
        "fixture_mode": use_mocks,
    }
    response["run_id"] = response["audit"]["run_id"]
    response["persisted"] = False
    response["persistence_status"] = "skipped"
    response["history_url"] = ""
    response["proof_checksum"] = proof_checksum
    if request.persist_run:
        if not active_config.preview_persistence_enabled:
            response["persistence_status"] = "disabled"
            response.setdefault("output_preview", {}).setdefault("missing_data_warnings", []).append(
                "Preview persistence is disabled by VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED."
            )
        else:
            persisted = get_equity_preview_store().persist_preview_run(
                request_payload=request.model_dump(mode="json"),
                response_payload=response,
                runtime_payload=runtime_payload,
                created_from=created_from,
                parent_run_id=parent_run_id,
            )
            response["run_id"] = persisted.run_id
            response["persisted"] = True
            response["persistence_status"] = "persisted"
            response["history_url"] = persisted.history_url
            response["proof_checksum"] = persisted.proof_checksum
            response["audit"]["run_id"] = persisted.run_id
            response["audit"]["proof_checksum"] = persisted.proof_checksum
    return response


def list_equity_preview_runs(
    *,
    config: EquityRuntimeConfig | None = None,
    limit: int = 25,
    offset: int = 0,
    target_entity_id: str | None = None,
    cik: str | None = None,
    ticker_alias: str | None = None,
    profile_id: str | None = None,
    status: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
) -> EquityPreviewRunList:
    active_config = config or EquityRuntimeConfig.from_env()
    _require_persistence_enabled(active_config)
    return get_equity_preview_store().list_runs(
        limit=limit,
        offset=offset,
        target_entity_id=target_entity_id,
        cik=cik,
        ticker_alias=ticker_alias,
        profile_id=profile_id,
        status=status,
        created_after=created_after,
        created_before=created_before,
    )


def get_equity_preview_run_detail(
    run_id: str,
    *,
    config: EquityRuntimeConfig | None = None,
) -> EquityPreviewRunDetail:
    active_config = config or EquityRuntimeConfig.from_env()
    _require_persistence_enabled(active_config)
    return get_equity_preview_store().require_detail(run_id)


def replay_equity_preview_run(
    run_id: str,
    request: EquityPreviewReplayRequest,
    *,
    config: EquityRuntimeConfig | None = None,
) -> EquityPreviewReplayResult:
    active_config = config or EquityRuntimeConfig.from_env()
    _require_persistence_enabled(active_config)
    store = get_equity_preview_store()
    if request.mode == "replay_from_stored_observations":
        return store.replay_from_stored_observations(run_id, request)
    if not active_config.preview_replay_refresh_enabled:
        raise PermissionError(
            "Replay with refresh is disabled unless VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED is true."
        )
    detail = store.require_detail(run_id)
    original_input = detail.run_record.get("input") if isinstance(detail.run_record, dict) else {}
    if not isinstance(original_input, dict):
        original_input = {}
    refresh_request = EquityRuntimeWedgePreviewRequest(
        target={
            "cik": original_input.get("cik") or detail.target.get("cik"),
            "ticker_alias": original_input.get("ticker_alias") or detail.target.get("ticker_alias"),
        },
        profile_id=QUALITY_VALUE_PROFILE_ID,
        package_mode=request.package_mode or original_input.get("package_mode") or "marketplace_draft",
        include_fmp=request.include_fmp,
        include_fred=request.include_fred,
        use_live_connectors=bool(original_input.get("use_live_connectors")),
        cutoff_timestamp=original_input.get("cutoff_timestamp"),
        mock_fixture_id=original_input.get("mock_fixture_id") or MOCK_FIXTURE_ID,
        persist_run=True,
    )
    preview = build_equity_runtime_wedge_preview(
        refresh_request,
        config=active_config,
        created_from="replay_with_refresh",
        parent_run_id=run_id,
    )
    differences = [
        {
            "field": "proof_checksum",
            "before": detail.audit.get("proof_checksum"),
            "after": preview.get("proof_checksum"),
            "status": "match" if detail.audit.get("proof_checksum") == preview.get("proof_checksum") else "changed",
        }
    ]
    return EquityPreviewReplayResult(
        mode="replay_with_refresh",
        parent_run_id=run_id,
        run_id=preview["run_id"],
        preview=preview,
        differences=differences,
    )


def _require_persistence_enabled(config: EquityRuntimeConfig) -> None:
    if not config.runtime_handlers_enabled or not config.sec_wedge_enabled:
        raise PermissionError("Equity runtime wedge preview is feature-flag disabled.")
    if not config.preview_persistence_enabled:
        raise PermissionError(
            "Equity preview persistence is disabled by VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED."
        )


def _compact_runtime_payload(
    payload: dict[str, Any],
    *,
    request: EquityRuntimeWedgePreviewRequest,
    config: EquityRuntimeConfig,
    base_config: EquityRuntimeConfig,
    fixture_mode: bool,
) -> dict[str, Any]:
    outputs = payload.get("outputs", {})
    radar = outputs.get("equity_radar", {})
    validation = outputs.get("validation_report", {})
    rights = outputs.get("source_rights_report", {})
    package_preview = outputs.get("package_redaction_preview", {})
    package_mode = request.package_mode
    mode_preview = package_preview.get("package_modes", {}).get(package_mode, {})
    compatibility_issues = list(validation.get("compatibility_issues", []))
    target = _target_payload(payload)
    evidence_summary = _evidence_summary(payload.get("evidence_bundle"))
    validation_rules = list(validation.get("checks", []))
    validation_rules.extend(
        {
            "rule_id": issue.get("code", "profile_compatibility"),
            "status": issue.get("severity", "warn"),
            "message": issue.get("message", ""),
        }
        for issue in compatibility_issues
    )

    return {
        "module_id": EQUITY_MODULE_ID,
        "module_version": payload.get("module_version") or EQUITY_MODULE_VERSION,
        "feature_flags": _feature_flags(base_config),
        "target": target,
        "profile": {
            "profile_id": request.profile_id,
            "compatibility_status": payload.get("status", "block"),
            "warnings": [issue for issue in compatibility_issues if issue.get("severity") == "warn"],
            "blocks": [issue for issue in compatibility_issues if issue.get("severity") == "block"],
        },
        "evidence_summary": evidence_summary,
        "fundamental_attributes": _fundamental_attributes(payload.get("fundamentals")),
        "optional_market_context": {
            "fmp": _fmp_context(
                payload.get("market_snapshot"),
                config=config,
                requested=request.include_fmp,
                package_mode=package_mode,
            ),
            "fred": _fred_context(
                payload.get("macro_context"),
                config=config,
                requested=request.include_fred,
            ),
        },
        "output_preview": {
            "view_id": radar.get("output_view", "equity_radar"),
            "non_advice_boundary": radar.get("non_advice_boundary") or NON_ADVICE_BOUNDARY,
            "summary_cards": _summary_cards(radar, payload.get("fundamentals")),
            "missing_data_warnings": list(radar.get("missing_data_warnings", [])),
        },
        "validation_report": {
            "status": validation.get("status", "block"),
            "rules": validation_rules,
        },
        "source_rights_report": {
            "status": rights.get("status", "block"),
            "policies": _rights_policies(rights),
        },
        "package_redaction_preview": {
            "package_mode": package_mode,
            "included": _decision_rows(mode_preview, "included"),
            "redacted": _decision_rows(mode_preview, "redacted"),
            "blocked": _decision_rows(mode_preview, "blocked"),
            "external_references": _external_reference_rows(rights),
            "entitlement_locked": _entitlement_locked_rows(mode_preview, rights),
        },
        "audit": {
            "run_id": "",
            "graph_hash": "",
            "profile_hash": "",
            "proof_checksum": "",
            "fixture_mode": fixture_mode,
        },
    }


def _request_target_value(target: EquityPreviewTarget) -> str:
    if target.cik and str(target.cik).strip():
        return normalize_cik(target.cik)
    if target.ticker_alias and target.ticker_alias.strip():
        return target.ticker_alias.strip().upper()
    return ""


def _parse_cutoff_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _feature_flags(config: EquityRuntimeConfig) -> dict[str, bool]:
    return {
        "runtime_handlers_enabled": config.runtime_handlers_enabled,
        "sec_wedge_enabled": config.sec_wedge_enabled,
        "fmp_enabled": config.fmp_enabled,
        "fred_enabled": config.fred_enabled,
        "live_integration_tests_enabled": config.live_integration_tests_enabled,
        "preview_persistence_enabled": config.preview_persistence_enabled,
        "preview_replay_refresh_enabled": config.preview_replay_refresh_enabled,
    }


def _target_payload(payload: dict[str, Any]) -> dict[str, Any]:
    identity = payload.get("identity") or {}
    evidence = payload.get("evidence_bundle") or {}
    company = evidence.get("company") if isinstance(evidence, dict) else {}
    return {
        "entity_id": identity.get("viza_entity_id"),
        "company_id": identity.get("company_id"),
        "security_id": identity.get("security_id"),
        "cik": identity.get("cik"),
        "ticker_alias": identity.get("ticker_alias"),
        "display_name": (company or {}).get("display_name") or "",
        "primary_key_policy": identity.get("primary_key_policy"),
    }


def _evidence_summary(evidence: dict[str, Any] | None) -> dict[str, Any]:
    if not evidence:
        return {
            "source_count": 0,
            "sources": [],
            "filing_refs": [],
            "observed_at": "",
            "available_at": "",
            "retrieved_at": "",
        }
    filing = evidence.get("latest_periodic_filing") or {}
    return {
        "source_count": len(evidence.get("source_refs", [])),
        "sources": list(evidence.get("source_refs", [])),
        "filing_refs": [filing] if filing else [],
        "observed_at": evidence.get("observed_at") or "",
        "available_at": evidence.get("available_at") or "",
        "retrieved_at": evidence.get("retrieved_at") or "",
    }


def _fundamental_attributes(fundamentals: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not fundamentals:
        return []
    rows = []
    for attribute in fundamentals.get("attributes", []):
        pit_policy = attribute.get("PIT_policy", {})
        rights_policy = attribute.get("rights_policy", {})
        rows.append(
            {
                "key": attribute.get("key"),
                "value": attribute.get("value"),
                "unit": attribute.get("unit"),
                "source_ids": list(attribute.get("source_ids", [])),
                "observed_at": attribute.get("observed_at"),
                "available_at": attribute.get("available_at"),
                "retrieved_at": attribute.get("retrieved_at"),
                "pit_status": "pass" if pit_policy.get("PIT_safe") else "warn",
                "rights_status": rights_policy.get("license_policy", "unknown"),
            }
        )
    return rows


def _fmp_context(
    market_snapshot: dict[str, Any] | None,
    *,
    config: EquityRuntimeConfig,
    requested: bool,
    package_mode: PackageMode,
) -> dict[str, Any]:
    snapshot = market_snapshot or {}
    rights = snapshot.get("rights_policy", {})
    license_policy = rights.get("license_policy", "")
    status = "disabled"
    if requested and not config.fmp_enabled:
        status = "disabled"
    elif config.fmp_enabled and snapshot.get("status") == "missing_credential":
        status = "missing_key"
    elif config.fmp_enabled and license_policy == "dev_only_unconfirmed":
        status = "dev_only"
    elif config.fmp_enabled and snapshot.get("status") == "available":
        status = "available"
    elif config.fmp_enabled:
        status = "blocked" if rights.get("export_policy") == "blocked" else snapshot.get("status", "blocked")
    return {
        "enabled": bool(config.fmp_enabled),
        "status": status,
        "rights_status": license_policy or "dev_only_unconfirmed",
        "values_redacted": (
            not config.fmp_enabled
            or license_policy == "dev_only_unconfirmed"
            or package_mode == "marketplace_draft"
        ),
        "warnings": list(snapshot.get("warnings", [])),
    }


def _fred_context(
    macro_context: dict[str, Any] | None,
    *,
    config: EquityRuntimeConfig,
    requested: bool,
) -> dict[str, Any]:
    macro = macro_context or {}
    pit = macro.get("PIT_policy", {})
    if requested and not config.fred_enabled:
        status = "disabled"
    elif config.fred_enabled and macro.get("status") == "missing_credential":
        status = "missing_key"
    elif config.fred_enabled and pit.get("PIT_safe"):
        status = "vintage_safe"
    elif config.fred_enabled and macro.get("status") == "available":
        status = "latest_only"
    elif config.fred_enabled:
        status = macro.get("status", "blocked")
    else:
        status = "disabled"
    return {
        "enabled": bool(config.fred_enabled),
        "status": status,
        "pit_status": pit.get("pit_status") or "latest_only_or_ingestion_timestamped",
        "values_redacted": False,
        "warnings": list(macro.get("warnings", [])),
    }


def _summary_cards(
    radar: dict[str, Any],
    fundamentals: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for row in radar.get("rows", []):
        cards.append(
            {
                "title": "Profile State",
                "status": row.get("profile_compatibility"),
                "body": row.get("research_state"),
                "detail": row.get("valuation_support"),
            }
        )
    if fundamentals:
        attrs = {item.get("key"): item for item in fundamentals.get("attributes", [])}
        for key in (
            "revenue_latest_period",
            "gross_margin_if_available",
            "free_cash_flow_or_cfo_capex_proxy_if_available",
            "filing_freshness_days",
        ):
            if key in attrs:
                item = attrs[key]
                cards.append(
                    {
                        "title": str(key).replace("_", " ").title(),
                        "status": "evidence",
                        "body": item.get("value"),
                        "detail": item.get("unit"),
                    }
                )
    return cards


def _rights_policies(rights_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for source in rights_report.get("sources", []):
        policy = source.get("rights_policy", {})
        rows.append(
            {
                "source": source.get("source"),
                "status": source.get("status"),
                "license_policy": policy.get("license_policy", "unknown"),
                "export_policy": policy.get("export_policy", "unknown"),
                "marketplace_policy": policy.get("marketplace_policy", "unknown"),
                "source_ids": list(source.get("source_ids", [])),
                "warnings": list(source.get("warnings", [])),
            }
        )
    return rows


def _decision_rows(mode_preview: dict[str, Any], field: str) -> list[dict[str, Any]]:
    return [
        {
            "source": decision.get("source"),
            "reason": decision.get("reason"),
            "warnings": list(decision.get("warnings", [])),
        }
        for decision in mode_preview.get("source_decisions", [])
        if decision.get(field)
    ]


def _external_reference_rows(rights_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for source in rights_report.get("sources", []):
        source_ids = list(source.get("source_ids", []))
        if source_ids:
            rows.append({"source": source.get("source"), "source_ids": source_ids})
    return rows


def _entitlement_locked_rows(
    mode_preview: dict[str, Any],
    rights_report: dict[str, Any],
) -> list[dict[str, Any]]:
    locked_sources = {
        source.get("source")
        for source in rights_report.get("sources", [])
        if source.get("rights_policy", {}).get("license_policy") == "dev_only_unconfirmed"
    }
    return [
        {
            "source": decision.get("source"),
            "reason": decision.get("reason"),
        }
        for decision in mode_preview.get("source_decisions", [])
        if decision.get("source") in locked_sources
    ]


def _checksum(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest().upper()


def _fact(value: float, fy: int, fp: str, end: str, filed: str) -> dict[str, Any]:
    return {
        "val": value,
        "fy": fy,
        "fp": fp,
        "form": "10-K",
        "filed": filed,
        "end": end,
        "accn": f"mock-accn-{fy}-{fp}",
    }


MOCK_SEC_SUBMISSIONS = {
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

MOCK_SEC_COMPANYFACTS = {
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


def _mock_sec_transport(url: str, headers: dict[str, str], _timeout: float) -> dict[str, Any]:
    if not headers.get("User-Agent"):
        raise AssertionError("SEC mock transport requires a User-Agent header.")
    if "submissions" in url:
        return MOCK_SEC_SUBMISSIONS
    if "companyfacts" in url:
        return MOCK_SEC_COMPANYFACTS
    raise AssertionError("Unexpected SEC mock URL.")


def _mock_fmp_transport(url: str, _headers: dict[str, str], _timeout: float) -> list[dict[str, Any]]:
    if "profile" in url:
        return [{"symbol": "AAPL", "cik": "320193", "companyName": "Apple Inc."}]
    if "quote" in url:
        return [
            {
                "symbol": "AAPL",
                "price": 195.12,
                "marketCap": 3_010_000_000_000,
                "timestamp": 1715600000,
            }
        ]
    if "market-capitalization" in url:
        return [{"symbol": "AAPL", "date": "2026-05-13", "marketCap": 3_010_000_000_000}]
    return []


def _mock_fred_transport(
    _url: str,
    _headers: dict[str, str],
    _timeout: float,
) -> dict[str, list[dict[str, str]]]:
    return {
        "observations": [
            {
                "date": "2026-05-13",
                "value": "4.12",
                "realtime_start": "2026-05-14",
                "realtime_end": "2026-05-14",
            }
        ]
    }

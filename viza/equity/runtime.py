from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from viza.equity.config import EquityRuntimeConfig
from viza.equity.connectors import (
    DEFAULT_FRED_SERIES,
    FmpMarketClient,
    FredMacroClient,
    JsonTransport,
    SecPublicClient,
    normalize_cik,
)
from viza.equity.registry import (
    EQUITY_MODULE_ID,
    EquityModule,
    EquityRegistryError,
    PackageMode,
    load_equity_module,
)


QUALITY_VALUE_PROFILE_ID = "quality_value_long_only"
NON_ADVICE_BOUNDARY = (
    "Research preview only. This output is not personalized investment advice, "
    "does not guarantee alpha, and does not make VIZA an investment adviser."
)

SEC_PUBLIC_RIGHTS_POLICY = {
    "license_policy": "public_official",
    "connector_roles": ["sec_filings", "xbrl_facts"],
    "display_policy": "allowed_with_attribution",
    "export_policy": "metadata_and_derived_allowed",
    "marketplace_policy": "metadata_and_derived_allowed_with_attribution",
    "redistribution_policy": "no_bulk_raw_filing_republication",
    "attribution_required": True,
    "redaction_required": False,
}


class EquityRuntimeDisabled(RuntimeError):
    pass


@dataclass(frozen=True)
class CompatibilityIssue:
    code: str
    severity: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "message": self.message}


def load_equity_module_manifest(
    *,
    config: EquityRuntimeConfig | None = None,
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    module = load_equity_registries(config=config, artifact_dir=artifact_dir)
    return module.manifest


def load_equity_registries(
    *,
    config: EquityRuntimeConfig | None = None,
    artifact_dir: str | Path | None = None,
) -> EquityModule:
    active_config = config or EquityRuntimeConfig.from_env()
    if not active_config.runtime_handlers_enabled:
        raise EquityRuntimeDisabled("equity runtime handlers are feature-flag disabled")
    module = load_equity_module(artifact_dir)
    module.validate().require_pass()
    return module


def resolve_equity_identity(
    target: str | int,
    *,
    ticker_alias: str | None = None,
    company_name: str | None = None,
    source_system: str = "runtime_input",
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = _iso_now(retrieved_at)
    target_text = str(target).strip()
    cik = normalize_cik(target_text) if any(ch.isdigit() for ch in target_text) and target_text.replace("-", "").isdigit() else None
    alias = ticker_alias.upper() if ticker_alias else None

    if cik:
        stable_suffix = f"cik_{cik}"
        source_id = f"sec:cik:{cik}"
        source_system = "sec_edgar"
        rights_policy = SEC_PUBLIC_RIGHTS_POLICY
        pit_policy = _pit_policy(
            observed_at_policy="sec_company_identity_record",
            available_at_policy="sec_public_api_available_at_retrieval",
            retrieved_at_policy="runtime_now",
            pit_safe=True,
            lookahead_risk="low_for_identity_not_observation",
        )
    else:
        alias = alias or target_text.upper()
        stable_suffix = f"unresolved_alias_{_stable_token(alias)}"
        source_id = f"runtime_alias_input:{_stable_token(alias)}"
        rights_policy = {
            "license_policy": "internal_research_only",
            "display_policy": "local_preview_only",
            "export_policy": "blocked_until_resolved",
            "marketplace_policy": "redacted",
            "redaction_required": True,
        }
        pit_policy = _pit_policy(
            observed_at_policy="user_or_runtime_alias_input",
            available_at_policy="runtime_now",
            retrieved_at_policy="runtime_now",
            pit_safe=False,
            lookahead_risk="alias_not_durable_identity",
        )

    return {
        "viza_entity_id": f"viza:eq:entity:{stable_suffix}",
        "company_id": f"viza:eq:company:{stable_suffix}",
        "issuer_id": f"viza:eq:issuer:{stable_suffix}",
        "security_id": f"viza:eq:security:{stable_suffix}",
        "listing_id": f"viza:eq:listing:{stable_suffix}",
        "cik": cik,
        "company_name": company_name,
        "ticker_alias": alias,
        "ticker_effective_range_if_available": None,
        "primary_key_policy": "CIK-backed internal VIZA IDs; ticker is alias only",
        "source_id": source_id,
        "source_system": source_system,
        "observed_at": timestamp,
        "available_at": timestamp,
        "retrieved_at": timestamp,
        "rights_policy": rights_policy,
        "PIT_policy": pit_policy,
        "warnings": [] if cik else ["Ticker/alias input is not a durable primary key until resolved to CIK."],
    }


def resolve_sec_company(
    identity: dict[str, Any],
    submissions_payload: dict[str, Any],
    *,
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    cik = normalize_cik(submissions_payload.get("cik") or identity.get("cik") or "")
    aliases = submissions_payload.get("tickers")
    ticker_alias = identity.get("ticker_alias")
    if isinstance(aliases, list) and aliases:
        ticker_alias = ticker_alias or str(aliases[0]).upper()
    resolved = resolve_equity_identity(
        cik,
        ticker_alias=ticker_alias,
        company_name=str(submissions_payload.get("name") or identity.get("company_name") or ""),
        retrieved_at=retrieved_at,
    )
    resolved["sec_aliases"] = {
        "tickers": aliases if isinstance(aliases, list) else [],
        "exchanges": submissions_payload.get("exchanges")
        if isinstance(submissions_payload.get("exchanges"), list)
        else [],
    }
    return resolved


def fetch_sec_submissions(
    cik: str | int,
    *,
    config: EquityRuntimeConfig | None = None,
    transport: JsonTransport | None = None,
) -> dict[str, Any]:
    active_config = config or EquityRuntimeConfig.from_env()
    if not active_config.sec_wedge_enabled:
        return {
            "source": "sec_public",
            "status": "disabled",
            "warnings": ["VIZA_EQUITY_SEC_WEDGE_ENABLED is false; SEC calls are disabled."],
        }
    return SecPublicClient(active_config, transport=transport).fetch_submissions(cik)


def fetch_sec_companyfacts(
    cik: str | int,
    *,
    config: EquityRuntimeConfig | None = None,
    transport: JsonTransport | None = None,
) -> dict[str, Any]:
    active_config = config or EquityRuntimeConfig.from_env()
    if not active_config.sec_wedge_enabled:
        return {
            "source": "sec_public",
            "status": "disabled",
            "warnings": ["VIZA_EQUITY_SEC_WEDGE_ENABLED is false; SEC calls are disabled."],
        }
    return SecPublicClient(active_config, transport=transport).fetch_companyfacts(cik)


def build_sec_filing_evidence_bundle(
    identity: dict[str, Any],
    submissions_payload: dict[str, Any],
    companyfacts_payload: dict[str, Any],
    *,
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = _iso_now(retrieved_at)
    cik = normalize_cik(identity.get("cik") or submissions_payload.get("cik") or companyfacts_payload.get("cik"))
    latest = _latest_periodic_filing(submissions_payload)
    accepted_at = _parse_sec_datetime(latest.get("acceptanceDateTime")) if latest else None
    filing_date = _parse_date(latest.get("filingDate")) if latest else None
    report_date = _parse_date(latest.get("reportDate")) if latest else None
    available_at = _iso_datetime(accepted_at) if accepted_at else _iso_date(filing_date) if filing_date else None
    pit_status = "pass" if accepted_at else "warn"
    warnings: list[str] = []
    if latest is None:
        warnings.append("No latest 10-K/10-Q filing was present in SEC submissions payload.")
        pit_status = "block"
    elif accepted_at is None:
        warnings.append(
            "SEC acceptance timestamp is missing or imprecise; filing date is used as availability warning."
        )

    accession_number = latest.get("accessionNumber") if latest else None
    filing_source_id = f"sec:CIK{cik}:{accession_number or 'latest-periodic-filing'}"
    return {
        "bundle_id": f"sec_filing_evidence_bundle_{cik}",
        "source": "sec_public",
        "connector_role": "sec_filings",
        "company": {
            "company_id": identity["company_id"],
            "display_name": submissions_payload.get("name") or identity.get("company_name"),
            "cik": cik,
        },
        "issuer_security_listing_aliases": {
            "issuer_id": identity["issuer_id"],
            "security_id": identity["security_id"],
            "listing_id": identity["listing_id"],
            "ticker_alias": identity.get("ticker_alias"),
            "ticker_alias_policy": "alias_only_never_primary_key",
        },
        "latest_periodic_filing": {
            "accession_number": accession_number,
            "form_type": latest.get("form") if latest else None,
            "filing_date": filing_date.isoformat() if filing_date else None,
            "report_date": report_date.isoformat() if report_date else None,
            "accepted_at": _iso_datetime(accepted_at) if accepted_at else None,
            "available_at": available_at,
            "primary_document": latest.get("primaryDocument") if latest else None,
            "source_id": filing_source_id,
        },
        "source_refs": [
            {
                "source_id": f"sec:CIK{cik}:submissions",
                "url": f"https://data.sec.gov/submissions/CIK{cik}.json",
                "source_type": "submissions_history",
            },
            {
                "source_id": f"sec:CIK{cik}:companyfacts",
                "url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                "source_type": "xbrl_companyfacts",
            },
            {
                "source_id": filing_source_id,
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{str(accession_number or '').replace('-', '')}/",
                "source_type": "filing_reference",
            },
        ],
        "observed_at": _iso_date(report_date) if report_date else available_at or timestamp,
        "available_at": available_at,
        "retrieved_at": timestamp,
        "rights_policy": SEC_PUBLIC_RIGHTS_POLICY,
        "PIT_policy": _pit_policy(
            observed_at_policy="fiscal_period_end_or_filing_event",
            available_at_policy="SEC accepted timestamp; filing date fallback is warning only",
            retrieved_at_policy="runtime_now",
            pit_safe=pit_status == "pass",
            lookahead_risk="low" if pit_status == "pass" else "accepted_timestamp_missing_precision",
        ),
        "pit_status": pit_status,
        "rights_status": "public_official",
        "raw_payloads": {
            "submissions": submissions_payload,
            "companyfacts": companyfacts_payload,
        },
        "warnings": warnings,
    }


def derive_sec_public_fundamental_attributes(
    evidence_bundle: dict[str, Any],
) -> dict[str, Any]:
    payload = evidence_bundle.get("raw_payloads", {}).get("companyfacts", {})
    cik = normalize_cik(evidence_bundle["company"]["cik"])
    retrieved_at = evidence_bundle["retrieved_at"]
    bundle_available_at = evidence_bundle.get("available_at") or retrieved_at
    attributes: list[dict[str, Any]] = []
    warnings: list[str] = []

    revenue_rows = _facts(
        payload,
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    )
    revenue_latest = _latest_fact(revenue_rows)
    if revenue_latest:
        _add_sec_attribute(
            attributes,
            "revenue_latest_period",
            revenue_latest,
            cik=cik,
            retrieved_at=retrieved_at,
            fallback_available_at=bundle_available_at,
        )
        previous_revenue = _previous_same_period(revenue_rows, revenue_latest)
        growth = _safe_ratio(
            revenue_latest["value"] - previous_revenue["value"],
            previous_revenue["value"],
        ) if previous_revenue else None
        if growth is not None:
            _add_derived_attribute(
                attributes,
                "revenue_growth_yoy_if_available",
                growth,
                source_ids=[
                    _fact_source_id(cik, revenue_latest),
                    _fact_source_id(cik, previous_revenue),
                ],
                observed_at=revenue_latest["observed_at"],
                available_at=revenue_latest.get("available_at") or bundle_available_at,
                retrieved_at=retrieved_at,
                unit="ratio",
            )
        else:
            warnings.append("Revenue YoY growth unavailable from comparable SEC companyfacts rows.")
    else:
        warnings.append("Revenue fact unavailable in SEC companyfacts.")

    gross_profit = _latest_fact(_facts(payload, ["GrossProfit"]))
    operating_income = _latest_fact(_facts(payload, ["OperatingIncomeLoss"]))
    net_income = _latest_fact(_facts(payload, ["NetIncomeLoss", "ProfitLoss"]))
    cfo = _latest_fact(
        _facts(payload, ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"])
    )
    capex = _latest_fact(_facts(payload, ["PaymentsToAcquirePropertyPlantAndEquipment"]))
    assets = _latest_fact(_facts(payload, ["Assets"]))
    liabilities = _latest_fact(_facts(payload, ["Liabilities"]))
    shares_rows = _facts(
        payload,
        ["WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"],
        preferred_units=("shares",),
    )
    shares_latest = _latest_fact(shares_rows)

    if revenue_latest and gross_profit:
        _ratio_attribute(attributes, "gross_margin_if_available", gross_profit, revenue_latest, cik, retrieved_at)
    else:
        warnings.append("Gross margin unavailable from SEC facts.")
    if revenue_latest and operating_income:
        _ratio_attribute(attributes, "operating_margin_if_available", operating_income, revenue_latest, cik, retrieved_at)
    else:
        warnings.append("Operating margin unavailable from SEC facts.")
    if revenue_latest and net_income:
        _ratio_attribute(attributes, "net_margin_if_available", net_income, revenue_latest, cik, retrieved_at)
    else:
        warnings.append("Net margin unavailable from SEC facts.")

    if cfo:
        capex_value = abs(capex["value"]) if capex else 0.0
        free_cash_flow = cfo["value"] - capex_value
        _add_derived_attribute(
            attributes,
            "free_cash_flow_or_cfo_capex_proxy_if_available",
            free_cash_flow,
            source_ids=[_fact_source_id(cik, cfo), *([_fact_source_id(cik, capex)] if capex else [])],
            observed_at=cfo["observed_at"],
            available_at=cfo.get("available_at") or bundle_available_at,
            retrieved_at=retrieved_at,
            unit="USD",
        )
        if revenue_latest:
            fcf_margin = _safe_ratio(free_cash_flow, revenue_latest["value"])
            if fcf_margin is not None:
                _add_derived_attribute(
                    attributes,
                    "fcf_margin_if_available",
                    fcf_margin,
                    source_ids=[_fact_source_id(cik, cfo), _fact_source_id(cik, revenue_latest)],
                    observed_at=cfo["observed_at"],
                    available_at=cfo.get("available_at") or bundle_available_at,
                    retrieved_at=retrieved_at,
                    unit="ratio",
                )
        if net_income:
            cash_conversion = _safe_ratio(cfo["value"], net_income["value"])
            if cash_conversion is not None:
                _add_derived_attribute(
                    attributes,
                    "cash_conversion_proxy",
                    cash_conversion,
                    source_ids=[_fact_source_id(cik, cfo), _fact_source_id(cik, net_income)],
                    observed_at=cfo["observed_at"],
                    available_at=cfo.get("available_at") or bundle_available_at,
                    retrieved_at=retrieved_at,
                    unit="ratio",
                )
    else:
        warnings.append("Cash-flow-from-operations fact unavailable; FCF proxy unavailable.")

    if assets and liabilities:
        leverage = _safe_ratio(liabilities["value"], assets["value"])
        if leverage is not None:
            _add_derived_attribute(
                attributes,
                "debt_to_assets_or_leverage_proxy",
                leverage,
                source_ids=[_fact_source_id(cik, liabilities), _fact_source_id(cik, assets)],
                observed_at=assets["observed_at"],
                available_at=assets.get("available_at") or bundle_available_at,
                retrieved_at=retrieved_at,
                unit="ratio",
            )
    else:
        warnings.append("Assets/liabilities unavailable; leverage proxy unavailable.")

    if shares_latest:
        previous_shares = _previous_same_period(shares_rows, shares_latest)
        share_growth = _safe_ratio(
            shares_latest["value"] - previous_shares["value"],
            previous_shares["value"],
        ) if previous_shares else None
        if share_growth is not None:
            _add_derived_attribute(
                attributes,
                "share_count_growth_if_available",
                share_growth,
                source_ids=[
                    _fact_source_id(cik, shares_latest),
                    _fact_source_id(cik, previous_shares),
                ],
                observed_at=shares_latest["observed_at"],
                available_at=shares_latest.get("available_at") or bundle_available_at,
                retrieved_at=retrieved_at,
                unit="ratio",
            )

    freshness_days = _freshness_days(bundle_available_at, retrieved_at)
    if freshness_days is not None:
        _add_derived_attribute(
            attributes,
            "filing_freshness_days",
            freshness_days,
            source_ids=[evidence_bundle["latest_periodic_filing"]["source_id"]],
            observed_at=evidence_bundle["observed_at"],
            available_at=bundle_available_at,
            retrieved_at=retrieved_at,
            unit="days",
        )

    _add_derived_attribute(
        attributes,
        "pit_status",
        evidence_bundle["pit_status"],
        source_ids=[evidence_bundle["latest_periodic_filing"]["source_id"]],
        observed_at=evidence_bundle["observed_at"],
        available_at=bundle_available_at,
        retrieved_at=retrieved_at,
        unit="label",
    )
    _add_derived_attribute(
        attributes,
        "rights_status",
        evidence_bundle["rights_status"],
        source_ids=[evidence_bundle["latest_periodic_filing"]["source_id"]],
        observed_at=evidence_bundle["observed_at"],
        available_at=bundle_available_at,
        retrieved_at=retrieved_at,
        unit="label",
    )

    return {
        "source": "sec_public",
        "connector_role": "xbrl_facts",
        "status": "available" if attributes else "unavailable",
        "attributes": attributes,
        "retrieved_at": retrieved_at,
        "rights_policy": SEC_PUBLIC_RIGHTS_POLICY,
        "PIT_policy": evidence_bundle["PIT_policy"],
        "pit_status": evidence_bundle["pit_status"],
        "rights_status": "public_official",
        "warnings": warnings,
    }


def fetch_fmp_market_snapshot_optional(
    identity: dict[str, Any],
    *,
    config: EquityRuntimeConfig | None = None,
    transport: JsonTransport | None = None,
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    active_config = config or EquityRuntimeConfig.from_env()
    if not active_config.fmp_enabled:
        return {
            "source": "fmp",
            "connector_role": "licensed_market_data_connector",
            "status": "disabled",
            "symbol": identity.get("ticker_alias"),
            "cik": identity.get("cik"),
            "observations": [],
            "retrieved_at": _iso_now(retrieved_at),
            "rights_policy": {
                "license_policy": "dev_only_unconfirmed",
                "export_policy": "blocked",
                "marketplace_policy": "redacted",
                "redaction_required": True,
            },
            "PIT_policy": {
                "observed_at_policy": "provider_timestamp_or_market_date",
                "available_at_policy": "retrieved_at_if_no_provider_timestamp",
                "retrieved_at_policy": "runtime_now",
                "PIT_safe": False,
            },
            "warnings": ["VIZA_EQUITY_FMP_ENABLED is false; optional FMP calls are disabled."],
        }
    return FmpMarketClient(active_config, transport=transport).fetch_market_snapshot(
        symbol=identity.get("ticker_alias"),
        cik=identity.get("cik"),
        retrieved_at=retrieved_at,
    )


def fetch_fred_macro_context_optional(
    *,
    config: EquityRuntimeConfig | None = None,
    transport: JsonTransport | None = None,
    series_ids: tuple[str, ...] = DEFAULT_FRED_SERIES,
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    active_config = config or EquityRuntimeConfig.from_env()
    if not active_config.fred_enabled:
        return {
            "source": "fred",
            "connector_role": "official_public_connector",
            "status": "disabled",
            "observations": [],
            "retrieved_at": _iso_now(retrieved_at),
            "rights_policy": {
                "license_policy": "public_official",
                "export_policy": "metadata_and_derived_allowed",
                "marketplace_policy": "metadata_and_derived_allowed_with_attribution",
                "redaction_required": False,
            },
            "PIT_policy": {
                "PIT_safe": False,
                "pit_status": "latest_only_or_ingestion_timestamped",
                "lookahead_risk": "macro_context_disabled",
            },
            "warnings": ["VIZA_EQUITY_FRED_ENABLED is false; optional FRED calls are disabled."],
        }
    return FredMacroClient(active_config, transport=transport).fetch_macro_context(
        series_ids=series_ids,
        retrieved_at=retrieved_at,
    )


def run_quality_value_profile_compatibility(
    *,
    identity: dict[str, Any] | None,
    evidence_bundle: dict[str, Any] | None,
    fundamentals: dict[str, Any] | None,
    market_snapshot: dict[str, Any] | None = None,
    macro_context: dict[str, Any] | None = None,
    require_market_price_for_valuation: bool = False,
) -> dict[str, Any]:
    issues: list[CompatibilityIssue] = []
    if not identity or not identity.get("cik"):
        issues.append(CompatibilityIssue("target_entity_resolved", "block", "Target entity must resolve to CIK-backed internal IDs."))
    if not evidence_bundle or evidence_bundle.get("pit_status") == "block":
        issues.append(CompatibilityIssue("sec_evidence_exists", "block", "SEC filing/XBRL evidence is required."))
    elif evidence_bundle.get("pit_status") == "warn":
        issues.append(CompatibilityIssue("sec_accepted_at_precision", "warn", "SEC accepted_at is missing or imprecise."))
    if not fundamentals or not fundamentals.get("attributes"):
        issues.append(CompatibilityIssue("basic_fundamentals_derived", "block", "Basic SEC fundamental attributes are required."))
    else:
        for warning in fundamentals.get("warnings", []):
            issues.append(CompatibilityIssue("fundamental_attribute_availability", "warn", warning))
    if evidence_bundle and not evidence_bundle.get("available_at"):
        issues.append(CompatibilityIssue("available_at_required", "block", "SEC evidence requires available_at."))
    if evidence_bundle and not evidence_bundle.get("retrieved_at"):
        issues.append(CompatibilityIssue("retrieved_at_required", "block", "SEC evidence requires retrieved_at."))
    if evidence_bundle and not evidence_bundle.get("rights_policy"):
        issues.append(CompatibilityIssue("rights_policy_required", "block", "SEC evidence requires rights policy."))

    price_available = _market_price_available(market_snapshot)
    if require_market_price_for_valuation and not price_available:
        issues.append(CompatibilityIssue("market_price_required", "block", "Market price is required for valuation/margin-of-safety output and is unavailable."))
    elif not price_available:
        issues.append(CompatibilityIssue("market_price_optional_missing", "warn", "Market price unavailable; valuation/margin-of-safety preview is downgraded."))
    if market_snapshot and market_snapshot.get("rights_policy", {}).get("license_policy") == "dev_only_unconfirmed":
        issues.append(CompatibilityIssue("fmp_dev_only_unconfirmed", "warn", "FMP observations are dev-only and export-blocked until production license is confirmed."))
    if macro_context and macro_context.get("status") == "available":
        pit_policy = macro_context.get("PIT_policy", {})
        if not pit_policy.get("PIT_safe"):
            issues.append(CompatibilityIssue("fred_latest_only_macro", "warn", "FRED macro context is not true PIT for backtests without enforced ALFRED vintages."))

    status = _issue_status(issues)
    return {
        "profile_id": QUALITY_VALUE_PROFILE_ID,
        "compatible": status != "block",
        "status": status,
        "issues": [issue.as_dict() for issue in issues],
        "required_output_views": [
            "equity_radar",
            "investment_memo",
            "validation_report",
            "source_rights_report",
            "package_redaction_preview",
        ],
        "non_advice_boundary_required": True,
        "non_advice_boundary": NON_ADVICE_BOUNDARY,
    }


def render_equity_radar_preview(
    *,
    identity: dict[str, Any],
    evidence_bundle: dict[str, Any] | None,
    fundamentals: dict[str, Any] | None,
    compatibility: dict[str, Any],
    market_snapshot: dict[str, Any] | None = None,
    macro_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": "viza.equity.output.equity_radar_preview.v1",
        "output_view": "equity_radar",
        "non_advice_boundary": NON_ADVICE_BOUNDARY,
        "target_entity": _public_identity(identity),
        "profile_id": QUALITY_VALUE_PROFILE_ID,
        "source_list": _source_list(evidence_bundle, fundamentals, market_snapshot, macro_context),
        "evidence_refs": evidence_bundle.get("source_refs", []) if evidence_bundle else [],
        "PIT_status": _pit_summary(evidence_bundle, fundamentals, market_snapshot, macro_context),
        "rights_status": _rights_summary(evidence_bundle, fundamentals, market_snapshot, macro_context),
        "validation_status": compatibility["status"],
        "missing_data_warnings": [
            issue["message"] for issue in compatibility["issues"] if issue["severity"] == "warn"
        ],
        "rows": [
            {
                "entity_id": identity.get("viza_entity_id"),
                "ticker_alias": identity.get("ticker_alias"),
                "research_state": "blocked" if compatibility["status"] == "block" else "research_preview",
                "profile_compatibility": compatibility["status"],
                "valuation_support": "market_snapshot_available"
                if _market_price_available(market_snapshot)
                else "market_snapshot_missing_or_locked",
                "action_translation": "non_advice_research_preview",
            }
        ],
        "package_behavior": preview_package_redaction(
            sources=_source_list(evidence_bundle, fundamentals, market_snapshot, macro_context)
        ),
    }


def render_validation_report(
    *,
    compatibility: dict[str, Any],
    evidence_bundle: dict[str, Any] | None,
    fundamentals: dict[str, Any] | None,
) -> dict[str, Any]:
    checks = [
        {
            "rule_id": "EQ-VAL-001",
            "status": "pass"
            if evidence_bundle
            and evidence_bundle.get("available_at")
            and evidence_bundle.get("retrieved_at")
            else "block",
            "message": "source_id / observed_at / available_at / retrieved_at required",
        },
        {
            "rule_id": "EQ-VAL-002",
            "status": "pass" if evidence_bundle and evidence_bundle.get("pit_status") != "block" else "block",
            "message": "reject future-revised or unavailable historical data",
        },
        {
            "rule_id": "EQ-VAL-003",
            "status": "pass",
            "message": "restricted raw data cannot export",
        },
        {
            "rule_id": "EQ-VAL-004",
            "status": "warn",
            "message": "Runtime wedge emits preview evidence; full thesis requires horizon, mechanism, and invalidation.",
        },
        {
            "rule_id": "EQ-VAL-005",
            "status": "warn" if not fundamentals else "pass",
            "message": "valuation requires assumptions and sensitivity; full DCF is intentionally out of scope.",
        },
        {
            "rule_id": "EQ-VAL-011",
            "status": "pass",
            "message": "output must redact restricted or unsupported claims",
        },
        {
            "rule_id": "EQ-VAL-012",
            "status": compatibility["status"],
            "message": "profile compatibility must pass before action translation",
        },
    ]
    return {
        "schema": "viza.equity.output.validation_report.v1",
        "output_view": "validation_report",
        "non_advice_boundary": NON_ADVICE_BOUNDARY,
        "profile_id": QUALITY_VALUE_PROFILE_ID,
        "status": _rule_status(checks),
        "summary_counts": _status_counts(checks),
        "checks": checks,
        "compatibility_issues": compatibility["issues"],
    }


def render_source_rights_report(*sources: dict[str, Any]) -> dict[str, Any]:
    source_rows = _source_list(*sources)
    return {
        "schema": "viza.equity.output.source_rights_report.v1",
        "output_view": "source_rights_report",
        "non_advice_boundary": NON_ADVICE_BOUNDARY,
        "status": "block"
        if any(_source_export_blocked(source) for source in source_rows)
        else "warn"
        if any(source.get("rights_policy", {}).get("redaction_required") for source in source_rows)
        else "pass",
        "sources": source_rows,
        "rules": {
            "unknown_rights": "export_blocked",
            "restricted_raw_provider_data": "marketplace_redacted",
            "fmp_dev_only_unconfirmed": "export_blocked",
            "sec_public_official": "metadata_and_derived_allowed",
            "fred_latest_macro": "metadata_and_derived_allowed_with_PIT_warning",
        },
    }


def preview_package_redaction(
    *,
    sources: list[dict[str, Any]],
    package_modes: tuple[PackageMode, ...] = ("white_box", "output_only", "marketplace_draft"),
) -> dict[str, Any]:
    modes: dict[str, Any] = {}
    for mode in package_modes:
        source_decisions = [_package_source_decision(source, mode) for source in sources]
        mode_status = "block" if any(item["blocked"] for item in source_decisions) else "warn" if any(
            item["redacted"] or item["warnings"] for item in source_decisions
        ) else "pass"
        modes[mode] = {
            "status": mode_status,
            "package_mode": mode,
            "non_advice_boundary": NON_ADVICE_BOUNDARY,
            "source_decisions": source_decisions,
            "sections": {
                "evidence": "included" if mode == "white_box" else "summary_only",
                "raw_provider_data": "redacted",
                "validation_report": "included",
                "source_rights_report": "included",
            },
            "marketplace_endpoint_supported": False if mode == "marketplace_draft" else None,
        }
    return {
        "schema": "viza.equity.package_redaction_preview.v1",
        "package_modes": modes,
    }


def run_sec_quality_value_wedge(
    target: str | int,
    *,
    config: EquityRuntimeConfig | None = None,
    sec_transport: JsonTransport | None = None,
    fmp_transport: JsonTransport | None = None,
    fred_transport: JsonTransport | None = None,
    retrieved_at: datetime | None = None,
    require_market_price_for_valuation: bool = False,
) -> dict[str, Any]:
    active_config = config or EquityRuntimeConfig.from_env()
    module = load_equity_registries(config=active_config)
    identity = resolve_equity_identity(target, retrieved_at=retrieved_at)
    if not identity.get("cik"):
        compatibility = run_quality_value_profile_compatibility(
            identity=identity,
            evidence_bundle=None,
            fundamentals=None,
            require_market_price_for_valuation=require_market_price_for_valuation,
        )
        return _wedge_payload(
            module=module,
            identity=identity,
            evidence_bundle=None,
            fundamentals=None,
            market_snapshot=None,
            macro_context=None,
            compatibility=compatibility,
        )

    submissions = fetch_sec_submissions(identity["cik"], config=active_config, transport=sec_transport)
    if submissions.get("status") == "disabled":
        compatibility = run_quality_value_profile_compatibility(
            identity=identity,
            evidence_bundle=None,
            fundamentals=None,
            require_market_price_for_valuation=require_market_price_for_valuation,
        )
        return _wedge_payload(
            module=module,
            identity=identity,
            evidence_bundle=None,
            fundamentals=None,
            market_snapshot=None,
            macro_context=None,
            compatibility=compatibility,
        )
    identity = resolve_sec_company(identity, submissions, retrieved_at=retrieved_at)
    companyfacts = fetch_sec_companyfacts(identity["cik"], config=active_config, transport=sec_transport)
    evidence = build_sec_filing_evidence_bundle(
        identity,
        submissions,
        companyfacts,
        retrieved_at=retrieved_at,
    )
    fundamentals = derive_sec_public_fundamental_attributes(evidence)
    market_snapshot = fetch_fmp_market_snapshot_optional(
        identity,
        config=active_config,
        transport=fmp_transport,
        retrieved_at=retrieved_at,
    )
    macro_context = fetch_fred_macro_context_optional(
        config=active_config,
        transport=fred_transport,
        retrieved_at=retrieved_at,
    )
    compatibility = run_quality_value_profile_compatibility(
        identity=identity,
        evidence_bundle=evidence,
        fundamentals=fundamentals,
        market_snapshot=market_snapshot,
        macro_context=macro_context,
        require_market_price_for_valuation=require_market_price_for_valuation,
    )
    return _wedge_payload(
        module=module,
        identity=identity,
        evidence_bundle=evidence,
        fundamentals=fundamentals,
        market_snapshot=market_snapshot,
        macro_context=macro_context,
        compatibility=compatibility,
    )


def _wedge_payload(
    *,
    module: EquityModule,
    identity: dict[str, Any],
    evidence_bundle: dict[str, Any] | None,
    fundamentals: dict[str, Any] | None,
    market_snapshot: dict[str, Any] | None,
    macro_context: dict[str, Any] | None,
    compatibility: dict[str, Any],
) -> dict[str, Any]:
    radar = render_equity_radar_preview(
        identity=identity,
        evidence_bundle=evidence_bundle,
        fundamentals=fundamentals,
        compatibility=compatibility,
        market_snapshot=market_snapshot,
        macro_context=macro_context,
    )
    validation = render_validation_report(
        compatibility=compatibility,
        evidence_bundle=evidence_bundle,
        fundamentals=fundamentals,
    )
    rights = render_source_rights_report(evidence_bundle or {}, fundamentals or {}, market_snapshot or {}, macro_context or {})
    package_preview = preview_package_redaction(sources=rights["sources"])
    return {
        "schema": "viza.equity.runtime.sec_quality_value_wedge.v1",
        "module_id": EQUITY_MODULE_ID,
        "module_version": module.manifest.get("module_version"),
        "profile_id": QUALITY_VALUE_PROFILE_ID,
        "status": compatibility["status"],
        "identity": _public_identity(identity),
        "evidence_bundle": _evidence_summary(evidence_bundle),
        "fundamentals": fundamentals,
        "market_snapshot": market_snapshot,
        "macro_context": macro_context,
        "outputs": {
            "equity_radar": radar,
            "validation_report": validation,
            "source_rights_report": rights,
            "package_redaction_preview": package_preview,
        },
    }


def _latest_periodic_filing(payload: dict[str, Any]) -> dict[str, Any] | None:
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    candidates: list[dict[str, Any]] = []
    for index, form in enumerate(forms):
        if form not in {"10-K", "10-Q"}:
            continue
        candidates.append(
            {
                "form": form,
                "accessionNumber": _indexed(recent.get("accessionNumber", []), index),
                "filingDate": _indexed(recent.get("filingDate", []), index),
                "reportDate": _indexed(recent.get("reportDate", []), index),
                "acceptanceDateTime": _indexed(recent.get("acceptanceDateTime", []), index),
                "primaryDocument": _indexed(recent.get("primaryDocument", []), index),
            }
        )
    if not candidates:
        return None
    candidates.sort(key=lambda row: row.get("acceptanceDateTime") or row.get("filingDate") or "")
    return candidates[-1]


def _facts(
    payload: dict[str, Any],
    tags: list[str],
    preferred_units: tuple[str, ...] = ("USD",),
) -> list[dict[str, Any]]:
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    rows: list[dict[str, Any]] = []
    for tag in tags:
        tag_payload = us_gaap.get(tag)
        if not isinstance(tag_payload, dict):
            continue
        units = tag_payload.get("units", {})
        unit_order = [unit for unit in preferred_units if unit in units]
        unit_order.extend(unit for unit in units if unit not in unit_order)
        for unit in unit_order:
            values = units.get(unit)
            if not isinstance(values, list):
                continue
            for row in values:
                if not isinstance(row, dict) or row.get("val") is None:
                    continue
                try:
                    numeric_value = float(row["val"])
                except (TypeError, ValueError):
                    continue
                form = row.get("form")
                if form and form not in {"10-K", "10-Q", "10-K/A", "10-Q/A"}:
                    continue
                rows.append(
                    {
                        "tag": tag,
                        "unit": unit,
                        "value": numeric_value,
                        "fy": _optional_int(row.get("fy")),
                        "fp": row.get("fp"),
                        "form": form,
                        "accn": row.get("accn"),
                        "filed": row.get("filed"),
                        "observed_at": _iso_date(_parse_date(row.get("end"))) if row.get("end") else None,
                        "available_at": _iso_date(_parse_date(row.get("filed"))) if row.get("filed") else None,
                    }
                )
    rows.sort(key=lambda row: (row.get("available_at") or "", row.get("observed_at") or ""))
    return rows


def _latest_fact(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[-1] if rows else None


def _previous_same_period(
    rows: list[dict[str, Any]],
    latest: dict[str, Any],
) -> dict[str, Any] | None:
    latest_fy = latest.get("fy")
    latest_fp = latest.get("fp")
    if latest_fy is None or latest_fp is None:
        return rows[-2] if len(rows) > 1 else None
    matches = [
        row
        for row in rows
        if row is not latest and row.get("fy") == latest_fy - 1 and row.get("fp") == latest_fp
    ]
    return matches[-1] if matches else rows[-2] if len(rows) > 1 else None


def _add_sec_attribute(
    attributes: list[dict[str, Any]],
    key: str,
    fact: dict[str, Any],
    *,
    cik: str,
    retrieved_at: str,
    fallback_available_at: str,
) -> None:
    attributes.append(
        _attribute_record(
            key=key,
            value=fact["value"],
            unit=fact["unit"],
            source_ids=[_fact_source_id(cik, fact)],
            observed_at=fact.get("observed_at") or fallback_available_at,
            available_at=fact.get("available_at") or fallback_available_at,
            retrieved_at=retrieved_at,
        )
    )


def _add_derived_attribute(
    attributes: list[dict[str, Any]],
    key: str,
    value: Any,
    *,
    source_ids: list[str],
    observed_at: str,
    available_at: str,
    retrieved_at: str,
    unit: str,
) -> None:
    attributes.append(
        _attribute_record(
            key=key,
            value=value,
            unit=unit,
            source_ids=source_ids,
            observed_at=observed_at,
            available_at=available_at,
            retrieved_at=retrieved_at,
        )
    )


def _ratio_attribute(
    attributes: list[dict[str, Any]],
    key: str,
    numerator: dict[str, Any],
    denominator: dict[str, Any],
    cik: str,
    retrieved_at: str,
) -> None:
    ratio = _safe_ratio(numerator["value"], denominator["value"])
    if ratio is None:
        return
    _add_derived_attribute(
        attributes,
        key,
        ratio,
        source_ids=[_fact_source_id(cik, numerator), _fact_source_id(cik, denominator)],
        observed_at=numerator.get("observed_at") or denominator.get("observed_at"),
        available_at=numerator.get("available_at") or denominator.get("available_at"),
        retrieved_at=retrieved_at,
        unit="ratio",
    )


def _attribute_record(
    *,
    key: str,
    value: Any,
    unit: str,
    source_ids: list[str],
    observed_at: str,
    available_at: str,
    retrieved_at: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "value": value,
        "unit": unit,
        "source_ids": source_ids,
        "observed_at": observed_at,
        "available_at": available_at,
        "retrieved_at": retrieved_at,
        "rights_policy": SEC_PUBLIC_RIGHTS_POLICY,
        "PIT_policy": _pit_policy(
            observed_at_policy="SEC XBRL fact period end",
            available_at_policy="SEC filed/accepted availability timestamp",
            retrieved_at_policy="runtime_now",
            pit_safe=bool(available_at and retrieved_at),
            lookahead_risk="low_if_accepted_at_available_else_filing_date_warning",
        ),
    }


def _fact_source_id(cik: str, fact: dict[str, Any]) -> str:
    return f"sec:companyfacts:CIK{cik}:{fact.get('tag')}:{fact.get('accn') or fact.get('filed') or 'unknown'}"


def _market_price_available(snapshot: dict[str, Any] | None) -> bool:
    if not snapshot or snapshot.get("status") != "available":
        return False
    return any(
        observation.get("field") == "latest_price" and observation.get("value") is not None
        for observation in snapshot.get("observations", [])
    )


def _source_list(*sources: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources:
        if not source:
            continue
        rights = source.get("rights_policy") or {}
        pit = source.get("PIT_policy") or {}
        rows.append(
            {
                "source": source.get("source", "unknown"),
                "connector_role": source.get("connector_role"),
                "status": source.get("status", "available"),
                "source_ids": _source_ids(source),
                "rights_policy": rights,
                "PIT_policy": pit,
                "warnings": source.get("warnings", []),
            }
        )
    return rows


def _source_ids(source: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for ref in source.get("source_refs", []):
        if isinstance(ref, dict) and ref.get("source_id"):
            ids.append(str(ref["source_id"]))
    for attribute in source.get("attributes", []):
        ids.extend(str(item) for item in attribute.get("source_ids", []))
    for observation in source.get("observations", []):
        if observation.get("source_id"):
            ids.append(str(observation["source_id"]))
    return list(dict.fromkeys(ids))


def _pit_summary(*sources: dict[str, Any] | None) -> dict[str, Any]:
    source_rows = _source_list(*sources)
    return {
        "status": "block"
        if any(not source.get("PIT_policy") for source in source_rows)
        else "warn"
        if any(not source.get("PIT_policy", {}).get("PIT_safe", True) for source in source_rows)
        else "pass",
        "sources": [
            {
                "source": source["source"],
                "pit_policy": source.get("PIT_policy"),
                "warnings": source.get("warnings", []),
            }
            for source in source_rows
        ],
    }


def _rights_summary(*sources: dict[str, Any] | None) -> dict[str, Any]:
    source_rows = _source_list(*sources)
    return {
        "status": "block"
        if any(_source_export_blocked(source) for source in source_rows)
        else "warn"
        if any(source.get("rights_policy", {}).get("redaction_required") for source in source_rows)
        else "pass",
        "sources": [
            {
                "source": source["source"],
                "rights_policy": source.get("rights_policy"),
                "warnings": source.get("warnings", []),
            }
            for source in source_rows
        ],
    }


def _source_export_blocked(source: dict[str, Any]) -> bool:
    policy = source.get("rights_policy", {})
    return policy.get("export_policy") in {"blocked", "blocked_until_resolved"} or policy.get(
        "license_policy"
    ) in {"unknown", "restricted_or_unclear"}


def _package_source_decision(source: dict[str, Any], mode: PackageMode) -> dict[str, Any]:
    rights = source.get("rights_policy", {})
    license_policy = rights.get("license_policy", "unknown")
    export_policy = rights.get("export_policy", "unknown")
    marketplace_policy = rights.get("marketplace_policy", "unknown")
    source_name = source.get("source", "unknown")
    warnings = list(source.get("warnings", []))

    if license_policy == "public_official":
        return {
            "source": source_name,
            "included": True,
            "redacted": mode == "marketplace_draft",
            "blocked": False,
            "reason": "public official metadata and derived values allowed; bulk raw data not reproduced",
            "warnings": warnings,
        }
    if license_policy == "dev_only_unconfirmed":
        return {
            "source": source_name,
            "included": mode == "white_box",
            "redacted": mode != "white_box",
            "blocked": mode == "marketplace_draft",
            "reason": "FMP data is dev-only until production display/licensing is confirmed",
            "warnings": warnings,
        }
    if "blocked" in str(export_policy) or "redacted" in str(marketplace_policy) or license_policy == "unknown":
        return {
            "source": source_name,
            "included": False,
            "redacted": True,
            "blocked": mode in {"output_only", "marketplace_draft"} or license_policy == "unknown",
            "reason": "restricted or unclear rights fail closed for export/package previews",
            "warnings": warnings,
        }
    return {
        "source": source_name,
        "included": mode == "white_box",
        "redacted": mode != "white_box",
        "blocked": False,
        "reason": "source included according to declared rights policy",
        "warnings": warnings,
    }


def _public_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "viza_entity_id": identity.get("viza_entity_id"),
        "company_id": identity.get("company_id"),
        "issuer_id": identity.get("issuer_id"),
        "security_id": identity.get("security_id"),
        "listing_id": identity.get("listing_id"),
        "cik": identity.get("cik"),
        "ticker_alias": identity.get("ticker_alias"),
        "primary_key_policy": identity.get("primary_key_policy"),
    }


def _evidence_summary(evidence_bundle: dict[str, Any] | None) -> dict[str, Any] | None:
    if evidence_bundle is None:
        return None
    return {
        key: value
        for key, value in evidence_bundle.items()
        if key != "raw_payloads"
    }


def _rule_status(checks: list[dict[str, Any]]) -> str:
    if any(check.get("status") == "block" for check in checks):
        return "block"
    if any(check.get("status") == "warn" for check in checks):
        return "warn"
    return "pass"


def _issue_status(issues: list[CompatibilityIssue]) -> str:
    if any(issue.severity == "block" for issue in issues):
        return "block"
    if any(issue.severity == "warn" for issue in issues):
        return "warn"
    return "pass"


def _status_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "block": 0}
    for check in checks:
        status = check.get("status", "block")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _pit_policy(
    *,
    observed_at_policy: str,
    available_at_policy: str,
    retrieved_at_policy: str,
    pit_safe: bool,
    lookahead_risk: str,
) -> dict[str, Any]:
    return {
        "observed_at_policy": observed_at_policy,
        "available_at_policy": available_at_policy,
        "retrieved_at_policy": retrieved_at_policy,
        "source_version_policy": "source_payload_version_at_retrieval",
        "data_version_policy": "runtime_ingestion_payload",
        "model_version_policy": "viza.equity.runtime.sec_quality_value_wedge.v1",
        "vintage_required": False,
        "PIT_safe": pit_safe,
        "lookahead_risk": lookahead_risk,
    }


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator in {0, 0.0}:
        return None
    return numerator / denominator


def _freshness_days(available_at: str, retrieved_at: str) -> int | None:
    available = _parse_any_datetime(available_at)
    retrieved = _parse_any_datetime(retrieved_at)
    if not available or not retrieved:
        return None
    return max(0, (retrieved.date() - available.date()).days)


def _indexed(values: list[Any], index: int) -> Any:
    return values[index] if isinstance(values, list) and index < len(values) else None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_sec_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if "T" not in text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_any_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if len(text) == 10:
        text = f"{text}T00:00:00+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _iso_date(value: date | None) -> str | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc).isoformat()


def _iso_now(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat()


def _stable_token(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return digest

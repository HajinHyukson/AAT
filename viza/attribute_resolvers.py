from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from viza.attribute_registry import AttributeRegistry
from viza.assets import resolve_static_asset_identity
from viza.connectors import (
    EntitlementPolicy,
    connector_id_for_attribute,
    entitlement_for_attribute,
)
from viza.observations import TECHNICAL_OBSERVATION_KEYS, VizaObservation, get_observation_store
from viza.universes import UniverseSecurity


class AttributeValue(BaseModel):
    attribute_key: str
    value: float | str | bool | None
    unit: str
    source: str
    source_record_id: str | None = None
    event_time: str | None = None
    timestamp_available: str | None = None
    data_version: str
    model_version: str
    contribution_stage: str
    connector_id: str
    license_policy: str
    cache_policy: str
    entitlement_policy: str
    entitlement: EntitlementPolicy
    limitations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    missing_reason: str | None = None
    is_prototype: bool = False
    entity_id: str | None = None
    asset_id: str | None = None
    observation_id: str | None = None
    observed_at: str | None = None
    available_at: str | None = None
    retrieved_at: str | None = None
    rights_policy: dict[str, Any] = Field(default_factory=dict)
    PIT_status: str | None = None


LOCAL_UNIVERSE_ATTRIBUTES = {"sector", "industry", "subindustry", "run_status"}


def resolve_attribute_values(
    security: UniverseSecurity,
    attribute_keys: list[str],
    registry: AttributeRegistry,
    *,
    timestamp_cutoff: datetime | None = None,
) -> dict[str, AttributeValue]:
    return {
        key: resolve_attribute_value(
            security=security,
            attribute_key=key,
            registry=registry,
            timestamp_cutoff=timestamp_cutoff,
        )
        for key in attribute_keys
    }


def resolve_attribute_value(
    security: UniverseSecurity,
    attribute_key: str,
    registry: AttributeRegistry,
    *,
    timestamp_cutoff: datetime | None = None,
) -> AttributeValue:
    definition = registry.require(attribute_key)
    entity_id, asset_id = resolve_static_asset_identity(security.ticker)
    observation = _latest_observation_for_attribute(
        entity_id,
        attribute_key,
        timestamp_cutoff or datetime.now(timezone.utc),
    )
    if observation is not None:
        return _attribute_value_from_observation(
            observation=observation,
            security=security,
            registry=registry,
        )

    value = _attribute_value(security, attribute_key)
    missing_reason = _missing_reason(attribute_key, value)
    is_local_value = attribute_key in LOCAL_UNIVERSE_ATTRIBUTES
    connector_id = "local_viza_workspace" if is_local_value else connector_id_for_attribute(definition)
    entitlement = entitlement_for_attribute(definition)
    is_phase_13_value = definition.model_version.startswith("phase_13_")
    source = (
        "local_universe"
        if is_local_value
        else "phase_13_deterministic_fallback"
        if is_phase_13_value
        else "phase_4_prototype_fallback"
    )
    data_version = (
        "local_universe_current_snapshot"
        if is_local_value
        else definition.data_version
        if is_phase_13_value
        else "deterministic_prototype_v0"
    )
    model_version = (
        "source_value"
        if is_local_value
        else definition.model_version
        if is_phase_13_value
        else "phase_4_deterministic_resolver_v0"
    )

    return AttributeValue(
        attribute_key=attribute_key,
        value=value,
        unit=definition.unit,
        source=source,
        source_record_id=f"universe_security:{security.ticker}",
        data_version=data_version,
        model_version=model_version,
        contribution_stage=definition.contribution_stage,
        connector_id=connector_id,
        license_policy=definition.license_policy,
        cache_policy=definition.cache_policy,
        entitlement_policy=definition.entitlement_policy,
        entitlement=entitlement,
        limitations=definition.limitations,
        confidence=0.9 if is_local_value and missing_reason is None else 0.45,
        diagnostics={
            "family": definition.family,
            "point_in_time_status": definition.point_in_time_status,
            "license_policy": definition.license_policy,
            "entitlement_policy": definition.entitlement_policy,
            "cache_policy": definition.cache_policy,
            "connector_id": connector_id,
            "entitlement": entitlement.model_dump(mode="json"),
            "prototype_fallback": not is_local_value,
            "resolver_family": "phase_13" if is_phase_13_value else "phase_4",
        },
        missing_reason=missing_reason,
        is_prototype=not is_local_value,
        entity_id=entity_id,
        asset_id=asset_id,
        rights_policy=entitlement.model_dump(mode="json"),
        PIT_status=definition.point_in_time_status,
    )


def _latest_observation_for_attribute(
    entity_id: str,
    attribute_key: str,
    cutoff: datetime,
) -> VizaObservation | None:
    if attribute_key not in TECHNICAL_OBSERVATION_KEYS:
        return None
    try:
        return get_observation_store().get_latest_observation_as_of(
            entity_id,
            attribute_key,
            cutoff,
        )
    except Exception:
        return None


def _attribute_value_from_observation(
    *,
    observation: VizaObservation,
    security: UniverseSecurity,
    registry: AttributeRegistry,
) -> AttributeValue:
    definition = registry.require(observation.attribute_key)
    entitlement = entitlement_for_attribute(definition)
    rights_policy = observation.rights_policy or entitlement.model_dump(mode="json")
    rights_policy = _complete_source_rights_policy(
        rights_policy=rights_policy,
        connector_id=observation.connector_id,
        source_id=observation.source_id,
        definition_license=definition.license_policy,
        definition_cache=definition.cache_policy,
        entitlement=entitlement,
    )
    return AttributeValue(
        attribute_key=observation.attribute_key,
        value=observation.value,
        unit=observation.unit or definition.unit,
        source=observation.source_id,
        source_record_id=observation.source_record or f"observation:{observation.observation_id}",
        event_time=observation.observed_at.isoformat(),
        timestamp_available=observation.available_at.isoformat(),
        data_version=observation.data_version or definition.data_version,
        model_version=observation.model_version or "source_backed_observation_v0",
        contribution_stage=definition.contribution_stage,
        connector_id=observation.connector_id,
        license_policy=definition.license_policy,
        cache_policy=definition.cache_policy,
        entitlement_policy=definition.entitlement_policy,
        entitlement=entitlement,
        limitations=definition.limitations,
        confidence=observation.confidence or 0.85,
        diagnostics={
            "family": definition.family,
            "point_in_time_status": definition.point_in_time_status,
            "license_policy": definition.license_policy,
            "entitlement_policy": definition.entitlement_policy,
            "cache_policy": definition.cache_policy,
            "connector_id": observation.connector_id,
            "source_id": observation.source_id,
            "display_policy": rights_policy["display_policy"],
            "export_policy": rights_policy["export_policy"],
            "derived_value_policy": rights_policy["derived_value_policy"],
            "redistribution_policy": rights_policy["redistribution_policy"],
            "retention_policy": rights_policy["retention_policy"],
            "entitlement": entitlement.model_dump(mode="json"),
            "prototype_fallback": False,
            "resolver_family": "observation_store",
            "observation_id": observation.observation_id,
            "observation_checksum": observation.checksum,
            "source_ticker": security.ticker,
        },
        is_prototype=False,
        entity_id=observation.entity_id,
        asset_id=observation.asset_id,
        observation_id=observation.observation_id,
        observed_at=observation.observed_at.isoformat(),
        available_at=observation.available_at.isoformat(),
        retrieved_at=observation.retrieved_at.isoformat(),
        rights_policy=rights_policy,
        PIT_status="point_in_time",
    )


def _attribute_value(security: UniverseSecurity, attribute_key: str) -> float | str | bool | None:
    values: dict[str, float | str | bool | None] = {
        "sector": security.sector or None,
        "industry": security.industry or None,
        "subindustry": security.subindustry or None,
        "latest_price": round(20 + _stable_unit(security.ticker, "latest_price") * 480, 2),
        "price_bar_count": 220 + int(_stable_unit(security.ticker, "price_bar_count") * 540),
        "run_status": "available",
    }
    values["observed_return_bps"] = _signed_bps(security.ticker, "observed_return_bps", 520)
    values["unexplained_residual_bps"] = _signed_bps(
        security.ticker,
        "unexplained_residual_bps",
        190,
    )
    observed_return = _read_float(values["observed_return_bps"])
    values["residual_share_stable"] = abs(observed_return) >= 15
    values["french_market_contribution_bps"] = _signed_bps(
        security.ticker,
        "french_market_contribution_bps",
        260,
    )
    values["french_smb_contribution_bps"] = _signed_bps(
        security.ticker,
        "french_smb_contribution_bps",
        95,
    )
    values["french_hml_contribution_bps"] = _signed_bps(
        security.ticker,
        "french_hml_contribution_bps",
        95,
    )
    values["french_rmw_contribution_bps"] = _signed_bps(
        security.ticker,
        "french_rmw_contribution_bps",
        80,
    )
    values["french_cma_contribution_bps"] = _signed_bps(
        security.ticker,
        "french_cma_contribution_bps",
        80,
    )
    values["market_contribution_bps"] = _signed_bps(
        security.ticker,
        "market_contribution_bps",
        280,
    )
    values["industry_contribution_bps"] = _industry_contribution(security)
    values["subindustry_basket_contribution_bps"] = _subindustry_contribution(security)
    values["custom_peer_basket_contribution_bps"] = _signed_bps(
        security.ticker,
        "custom_peer_basket_contribution_bps",
        125,
    )
    values["peer_residual_spread_bps"] = _signed_bps(
        security.ticker,
        "peer_residual_spread_bps",
        160,
    )
    values["sector_contribution_bps"] = _sector_contribution(security)
    values["peer_contribution_bps"] = _signed_bps(security.ticker, "peer_contribution_bps", 120)
    values["macro_contribution_bps"] = _macro_contribution(security)
    values["beta_market"] = round(0.55 + _stable_unit(security.ticker, "beta_market") * 1.15, 4)
    values["momentum"] = round(_stable_unit(security.ticker, "momentum"), 4)
    values["short_term_reversal"] = round(_stable_unit(security.ticker, "short_term_reversal"), 4)
    values["realized_volatility"] = round(0.05 + _stable_unit(security.ticker, "vol") * 0.85, 4)
    values["liquidity"] = round(_stable_unit(security.ticker, "liquidity"), 4)
    values["event_count"] = int(_stable_unit(security.ticker, "event_count") * 7)
    values["event_materiality"] = round(_stable_unit(security.ticker, "event_materiality"), 4)
    values["event_novelty"] = round(_stable_unit(security.ticker, "event_novelty"), 4)
    values.update(_macro_values(security))
    values.update(_event_values(security))
    values.update(_fundamental_values(security))
    values.update(_positioning_values(security))

    return values.get(attribute_key)


def _complete_source_rights_policy(
    *,
    rights_policy: dict[str, Any],
    connector_id: str,
    source_id: str,
    definition_license: str,
    definition_cache: str,
    entitlement: EntitlementPolicy,
) -> dict[str, Any]:
    completed = dict(rights_policy)
    completed.setdefault("connector_id", connector_id)
    completed.setdefault("source_id", source_id)
    completed.setdefault("license_policy", definition_license)
    completed.setdefault("cache_policy", definition_cache)
    completed.setdefault("display_policy", "derived_values_allowed")
    completed.setdefault(
        "export_policy",
        "derived_values_allowed" if entitlement.export_allowed else "restricted",
    )
    completed.setdefault("derived_value_policy", "allowed")
    completed.setdefault(
        "redistribution_policy",
        "allowed" if entitlement.redistribution_allowed else "restricted",
    )
    completed.setdefault("attribution_required", entitlement.attribution_required)
    completed.setdefault("retention_policy", "local_project_store")
    return completed


def _missing_reason(attribute_key: str, value: float | str | bool | None) -> str | None:
    if value is not None and value != "":
        return None
    if attribute_key in {"sector", "industry", "subindustry"}:
        return "missing_local_universe_classification"
    return "missing_prototype_value"


def _sector_contribution(security: UniverseSecurity) -> float:
    sector_bias = {
        "Information Technology": 35.0,
        "Communication Services": 20.0,
        "Consumer Discretionary": 12.0,
        "Financials": -8.0,
        "Energy": 18.0,
        "Health Care": -4.0,
        "Industrials": 6.0,
    }.get(security.sector, 0.0)
    return round(sector_bias + _signed_bps(security.ticker, "sector_contribution_bps", 45), 2)


def _industry_contribution(security: UniverseSecurity) -> float:
    industry_anchor = _stable_unit(security.industry or security.ticker, "industry_anchor") * 90 - 45
    return round(industry_anchor + _signed_bps(security.ticker, "industry_contribution_bps", 55), 2)


def _subindustry_contribution(security: UniverseSecurity) -> float:
    subindustry_anchor = (
        _stable_unit(security.subindustry or security.industry or security.ticker, "subindustry")
        * 80
        - 40
    )
    return round(
        subindustry_anchor + _signed_bps(security.ticker, "subindustry_basket_contribution_bps", 45),
        2,
    )


def _macro_contribution(security: UniverseSecurity) -> float:
    if not security.exposures:
        return _signed_bps(security.ticker, "macro_contribution_bps", 65)
    exposure_signal = sum(security.exposures.values()) / len(security.exposures)
    sign = -1 if _stable_unit(security.ticker, "macro_direction") < 0.45 else 1
    return round(sign * exposure_signal * 95, 2)


def _macro_values(security: UniverseSecurity) -> dict[str, float]:
    scales = {
        "yield_2y_change_bps": 42,
        "yield_10y_change_bps": 36,
        "curve_2s10s_change_bps": 28,
        "dollar_index_change_bps": 85,
        "wti_change_bps": 170,
        "natural_gas_change_bps": 260,
        "high_yield_spread_change_bps": 52,
        "investment_grade_spread_change_bps": 30,
        "vix_change_bps": 210,
        "inflation_expectations_change_bps": 24,
    }
    return {
        key: _signed_bps(security.ticker, key, scale)
        for key, scale in scales.items()
    }


def _event_values(security: UniverseSecurity) -> dict[str, float | str | int]:
    category = _stable_choice(
        security.ticker,
        "event_category",
        ["earnings", "guidance", "product", "regulatory", "macro", "industry"],
    )
    subtype_by_category = {
        "earnings": ["beat", "miss", "margin", "revenue_mix"],
        "guidance": ["raise", "cut", "reaffirm", "withdrawn"],
        "product": ["launch", "delay", "pricing", "capacity"],
        "regulatory": ["approval", "investigation", "rule_change", "litigation"],
        "macro": ["rates", "fx", "commodity", "credit"],
        "industry": ["peer_readthrough", "supply_chain", "demand", "pricing"],
    }
    return {
        "event_category": category,
        "event_subtype": _stable_choice(
            security.ticker,
            "event_subtype",
            subtype_by_category[category],
        ),
        "event_direction": _stable_choice(
            security.ticker,
            "event_direction",
            ["positive", "negative", "mixed", "neutral"],
        ),
        "event_surprise": round(_stable_unit(security.ticker, "event_surprise"), 4),
        "event_relevance": round(_stable_unit(security.ticker, "event_relevance"), 4),
        "source_credibility": round(0.45 + _stable_unit(security.ticker, "source_credibility") * 0.5, 4),
        "exposure_match": round(_stable_unit(security.ticker, "exposure_match"), 4),
        "evidence_span_days": 1 + int(_stable_unit(security.ticker, "evidence_span_days") * 20),
    }


def _fundamental_values(security: UniverseSecurity) -> dict[str, float]:
    base_keys = [
        "size",
        "value",
        "growth",
        "quality",
        "leverage",
        "dividend_yield",
        "geographic_revenue_exposure",
        "segment_revenue_exposure",
        "customer_concentration",
        "supplier_concentration",
        "commodity_input_exposure",
        "interest_rate_exposure",
        "credit_exposure",
        "regulatory_exposure",
        "product_cycle_exposure",
        "fx_exposure",
    ]
    values = {key: round(_stable_unit(security.ticker, key), 4) for key in base_keys}
    if security.exposures:
        values["interest_rate_exposure"] = round(security.exposures.get("rates", values["interest_rate_exposure"]), 4)
        values["credit_exposure"] = round(security.exposures.get("credit", values["credit_exposure"]), 4)
        values["fx_exposure"] = round(security.exposures.get("broad_usd", values["fx_exposure"]), 4)
    return values


def _positioning_values(security: UniverseSecurity) -> dict[str, float]:
    return {
        key: round(_stable_unit(security.ticker, key), 4)
        for key in [
            "short_interest",
            "days_to_cover",
            "borrow_cost",
            "atm_implied_volatility",
            "iv_change",
            "put_call_skew",
            "options_volume_open_interest",
            "dealer_gamma_exposure",
            "etf_flow_exposure",
        ]
    }


def _signed_bps(ticker: str, key: str, scale: float) -> float:
    return round((_stable_unit(ticker, key) * 2 - 1) * scale, 2)


def _stable_choice(ticker: str, key: str, values: list[str]) -> str:
    index = int(_stable_unit(ticker, key) * len(values))
    return values[min(index, len(values) - 1)]


def _stable_unit(ticker: str, key: str) -> float:
    digest = hashlib.sha256(f"{ticker}:{key}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def _read_float(value: Any, fallback: float = 0.0) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return fallback
    return fallback

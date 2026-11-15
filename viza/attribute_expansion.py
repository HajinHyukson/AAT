from __future__ import annotations

from typing import Any


PHASE_13_REGISTRY_VERSION = "1.1.0"


def phase_13_attribute_definitions() -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    definitions.extend(_baseline_attributes())
    definitions.extend(_macro_attributes())
    definitions.extend(_event_attributes())
    definitions.extend(_fundamental_and_exposure_attributes())
    definitions.extend(_positioning_and_options_attributes())
    return definitions


def _baseline_attributes() -> list[dict[str, Any]]:
    return [
        _attribute(
            "market_contribution_bps",
            "Market Contribution",
            "attribution",
            "Broad market contribution from the active attribution model.",
            unit="basis_points",
            source="aat_contributions",
            availability_function="has_market_contribution",
            contribution_stage="production",
            evidence_policy="contribution_reference",
            diagnostics={"phase_13_category": "baseline"},
        ),
        _attribute(
            "industry_contribution_bps",
            "Industry Contribution",
            "attribution",
            "Industry basket contribution where a point-in-time industry proxy is available.",
            unit="basis_points",
            source="aat_contributions",
            availability_function="has_industry_contribution",
            contribution_stage="shadow",
            evidence_policy="contribution_reference",
            diagnostics={"phase_13_category": "baseline"},
        ),
        _attribute(
            "subindustry",
            "Subindustry",
            "classification",
            "Current subindustry label for the company from the local universe snapshot.",
            unit="label",
            source="aat_universe_classification",
            availability_function="has_company_classification",
            point_in_time_status="latest_snapshot",
            contribution_stage="evidence_only",
            evidence_policy="classification_reference",
            diagnostics={"phase_13_category": "baseline"},
        ),
        _attribute(
            "subindustry_basket_contribution_bps",
            "Subindustry Basket Contribution",
            "attribution",
            "Subindustry basket contribution using the best available local proxy.",
            unit="basis_points",
            source="aat_contributions",
            availability_function="has_subindustry_basket_contribution",
            contribution_stage="research",
            evidence_policy="contribution_reference",
            diagnostics={"phase_13_category": "baseline"},
        ),
        _attribute(
            "custom_peer_basket_contribution_bps",
            "Custom Peer Basket Contribution",
            "attribution",
            "User-defined peer basket contribution derived from visible peer relationships.",
            unit="basis_points",
            source="aat_peer_model",
            availability_function="has_custom_peer_basket",
            contribution_stage="research",
            evidence_policy="peer_basket_reference",
            diagnostics={"phase_13_category": "baseline"},
        ),
        _attribute(
            "peer_residual_spread_bps",
            "Peer Residual Spread",
            "attribution",
            "Residual spread between the company and its visible peer basket.",
            unit="basis_points",
            source="aat_peer_model",
            availability_function="has_peer_residual_spread",
            contribution_stage="research",
            evidence_policy="peer_basket_reference",
            diagnostics={"phase_13_category": "baseline"},
        ),
        _attribute(
            "beta_market",
            "Market Beta",
            "style",
            "Point-in-time estimated beta to the broad market factor.",
            unit="score",
            source="aat_factor_exposures",
            availability_function="has_factor_exposure",
            contribution_stage="shadow",
            evidence_policy="exposure_reference",
            diagnostics={"phase_13_category": "baseline"},
        ),
    ]


def _macro_attributes() -> list[dict[str, Any]]:
    return [
        _macro("yield_2y_change_bps", "2Y Yield Change", "Two-year Treasury yield move over the attribution window."),
        _macro("yield_10y_change_bps", "10Y Yield Change", "Ten-year Treasury yield move over the attribution window."),
        _macro("curve_2s10s_change_bps", "2s10s Curve Change", "Change in the 2Y-10Y Treasury curve slope."),
        _macro("dollar_index_change_bps", "Dollar Index Change", "Dollar index move mapped into basis points for screening."),
        _macro("wti_change_bps", "WTI Change", "WTI crude oil move mapped into basis points for screening."),
        _macro("natural_gas_change_bps", "Natural Gas Change", "Natural gas move mapped into basis points for screening."),
        _macro("high_yield_spread_change_bps", "High-Yield Spread Change", "High-yield credit spread move."),
        _macro("investment_grade_spread_change_bps", "Investment-Grade Spread Change", "Investment-grade credit spread move."),
        _macro("vix_change_bps", "VIX Change", "VIX move mapped into basis points for screening."),
        _macro("inflation_expectations_change_bps", "Inflation Expectations Change", "Inflation expectations move over the attribution window."),
    ]


def _event_attributes() -> list[dict[str, Any]]:
    return [
        _event("event_category", "Event Category", "Primary visible event category.", unit="label"),
        _event("event_subtype", "Event Subtype", "Primary visible event subtype.", unit="label"),
        _event("event_direction", "Event Direction", "Directional interpretation of the visible event.", unit="label"),
        _event("event_surprise", "Event Surprise", "Visible event surprise score."),
        _event("event_relevance", "Event Relevance", "Relevance of visible events to the company move."),
        _event("source_credibility", "Source Credibility", "Credibility score of the visible event source mix."),
        _event("exposure_match", "Exposure Match", "How closely the event matches known company exposures."),
        _event("evidence_span_days", "Evidence Span Days", "Calendar span covered by visible event evidence.", unit="count"),
    ]


def _fundamental_and_exposure_attributes() -> list[dict[str, Any]]:
    specs = [
        ("size", "Size", "Market-cap size descriptor."),
        ("value", "Value", "Value descriptor derived from available fundamentals."),
        ("growth", "Growth", "Growth descriptor derived from available fundamentals."),
        ("quality", "Quality", "Quality descriptor derived from available fundamentals."),
        ("leverage", "Leverage", "Balance-sheet leverage descriptor."),
        ("dividend_yield", "Dividend Yield", "Dividend yield descriptor."),
        ("geographic_revenue_exposure", "Geographic Revenue Exposure", "Geographic revenue concentration score."),
        ("segment_revenue_exposure", "Segment Revenue Exposure", "Business segment concentration score."),
        ("customer_concentration", "Customer Concentration", "Customer concentration risk score."),
        ("supplier_concentration", "Supplier Concentration", "Supplier concentration risk score."),
        ("commodity_input_exposure", "Commodity Input Exposure", "Commodity input cost exposure score."),
        ("interest_rate_exposure", "Interest-Rate Exposure", "Interest-rate sensitivity score."),
        ("credit_exposure", "Credit Exposure", "Credit spread sensitivity score."),
        ("regulatory_exposure", "Regulatory Exposure", "Regulatory sensitivity score."),
        ("product_cycle_exposure", "Product-Cycle Exposure", "Product-cycle sensitivity score."),
        ("fx_exposure", "FX Exposure", "Foreign-exchange sensitivity score."),
    ]
    return [
        _attribute(
            key,
            display_name,
            "fundamental" if "exposure" not in key and "concentration" not in key else "exposure",
            description,
            unit="score",
            source="aat_fundamental_features",
            availability_function="has_fundamental_or_exposure_feature",
            point_in_time_status="timestamp_available",
            contribution_stage="research",
            evidence_policy="fundamental_feature_reference",
            diagnostics={"phase_13_category": "fundamentals_and_exposures"},
        )
        for key, display_name, description in specs
    ]


def _positioning_and_options_attributes() -> list[dict[str, Any]]:
    specs = [
        ("short_interest", "Short Interest", "Short interest as a percent-like score."),
        ("days_to_cover", "Days To Cover", "Estimated days-to-cover descriptor."),
        ("borrow_cost", "Borrow Cost", "Borrow-cost pressure descriptor."),
        ("atm_implied_volatility", "ATM Implied Volatility", "At-the-money implied volatility descriptor."),
        ("iv_change", "IV Change", "Change in implied volatility."),
        ("put_call_skew", "Put-Call Skew", "Put-call skew descriptor."),
        ("options_volume_open_interest", "Options Volume/Open Interest", "Options activity versus open interest."),
        ("dealer_gamma_exposure", "Dealer Gamma Exposure", "Dealer gamma exposure descriptor."),
        ("etf_flow_exposure", "ETF Flow Exposure", "ETF flow exposure descriptor."),
    ]
    return [
        _attribute(
            key,
            display_name,
            "positioning",
            description,
            unit="score",
            source="fmp_or_licensed_positioning_source",
            source_type="fmp_paid_api",
            availability_function="has_positioning_or_options_feature",
            point_in_time_status="timestamp_available",
            contribution_stage="evidence_only",
            evidence_policy="licensed_source_reference",
            license_policy="paid_or_licensed_source_terms",
            entitlement_policy="query_only_no_export_credential_required",
            cache_policy="provider_terms_required",
            limitations=[
                "Registered for methodology design only until a licensed point-in-time source is configured.",
                "Exports are redacted by entitlement policy.",
            ],
            diagnostics={"phase_13_category": "positioning_and_options"},
        )
        for key, display_name, description in specs
    ]


def _macro(key: str, display_name: str, description: str) -> dict[str, Any]:
    return _attribute(
        key,
        display_name,
        "macro",
        description,
        unit="basis_points",
        source="fred_or_public_macro_proxy",
        source_type="public_api",
        availability_function="has_macro_series",
        point_in_time_status="timestamp_available",
        contribution_stage="research",
        evidence_policy="macro_series_reference",
        license_policy="public_source_attribution_required",
        entitlement_policy="public_source",
        diagnostics={"phase_13_category": "macro"},
    )


def _event(
    key: str,
    display_name: str,
    description: str,
    *,
    unit: str = "score",
) -> dict[str, Any]:
    return _attribute(
        key,
        display_name,
        "event",
        description,
        unit=unit,
        source="aat_event_features",
        availability_function="has_event_features",
        point_in_time_status="timestamp_available",
        contribution_stage="evidence_only",
        evidence_policy="event_reference",
        diagnostics={"phase_13_category": "event_intelligence"},
    )


def _attribute(
    key: str,
    display_name: str,
    family: str,
    description: str,
    *,
    unit: str,
    source: str,
    availability_function: str,
    point_in_time_status: str = "point_in_time",
    contribution_stage: str,
    evidence_policy: str,
    license_policy: str = "internal_aat",
    source_type: str = "internal_aat",
    entitlement_policy: str = "internal",
    cache_policy: str = "local_cache_allowed",
    limitations: list[str] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    phase_limitations = limitations or [
        "Phase 13 deterministic prototype value; replace with source-backed resolver before production decisions."
    ]
    return {
        "key": key,
        "display_name": display_name,
        "family": family,
        "description": description,
        "unit": unit,
        "source": source,
        "source_type": source_type,
        "frequency": "daily_or_event",
        "coverage": "phase_13_expansion",
        "coverage_universe": "local_viza_starter_universes",
        "freshness": "prototype_snapshot",
        "timestamp_policy": "timestamp_available",
        "availability_function": availability_function,
        "point_in_time_status": point_in_time_status,
        "contribution_stage": contribution_stage,
        "evidence_policy": evidence_policy,
        "license_policy": license_policy,
        "entitlement_policy": entitlement_policy,
        "cache_policy": cache_policy,
        "diagnostics": {
            "implementation_status": "deterministic_prototype",
            "promotion_requires": [
                "source definition",
                "point-in-time validation",
                "confidence thresholds",
                "versioned resolver",
            ],
            **(diagnostics or {}),
        },
        "limitations": phase_limitations,
        "model_version": "phase_13_deterministic_resolver_v0",
        "data_version": "phase_13_prototype_v0",
    }

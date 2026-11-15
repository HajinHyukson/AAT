from __future__ import annotations

from viza.attribute_registry import load_attribute_registry
from viza.attribute_resolvers import resolve_attribute_values
from viza.execution import run_methodology
from viza.graph_schema import load_methodology_graph
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.universes import load_universe_definition


def test_attribute_resolver_uses_local_universe_values_where_available() -> None:
    registry = load_attribute_registry()
    universe = load_universe_definition("pilot_sp500_static")
    security = universe.securities[0]

    values = resolve_attribute_values(security, ["sector", "momentum"], registry)

    assert values["sector"].source == "local_universe"
    assert values["sector"].connector_id == "local_viza_workspace"
    assert values["sector"].is_prototype is False
    assert values["sector"].missing_reason is None
    assert values["momentum"].source == "phase_4_prototype_fallback"
    assert values["momentum"].entitlement.query_allowed is True
    assert values["momentum"].is_prototype is True


def test_phase_13_expanded_attributes_resolve_with_stage_metadata() -> None:
    registry = load_attribute_registry()
    universe = load_universe_definition("mvp_50")
    security = universe.securities[0]

    values = resolve_attribute_values(
        security,
        [
            "market_contribution_bps",
            "subindustry",
            "yield_10y_change_bps",
            "event_category",
            "quality",
            "short_interest",
        ],
        registry,
    )

    assert isinstance(values["market_contribution_bps"].value, float)
    assert values["subindustry"].source == "local_universe"
    assert values["yield_10y_change_bps"].connector_id == "fred"
    assert values["yield_10y_change_bps"].data_version == "phase_13_prototype_v0"
    assert isinstance(values["event_category"].value, str)
    assert 0 <= values["quality"].value <= 1
    assert values["short_interest"].entitlement.export_allowed is False
    assert values["short_interest"].limitations


def test_run_evidence_labels_prototype_fallbacks_and_local_values() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()

    result = run_methodology(graph, registry)
    first_ticker = result.rows[0].ticker
    momentum_evidence = result.evidence[f"attr:{first_ticker}:momentum"]
    sector_evidence = result.evidence[f"attr:{first_ticker}:sector"]

    assert momentum_evidence["source"] == "phase_4_prototype_fallback"
    assert momentum_evidence["connector_id"] == "local_viza_workspace"
    assert momentum_evidence["evidence_ref"] == f"attr:{first_ticker}:momentum"
    assert momentum_evidence["calculation"]["attribute_key"] == "momentum"
    assert "license_policy" in momentum_evidence
    assert momentum_evidence["entitlement"]["query_allowed"] is True
    assert momentum_evidence["is_prototype"] is True
    assert momentum_evidence["data_version"] == "deterministic_prototype_v0"
    assert sector_evidence["source"] == "local_universe"
    assert sector_evidence["is_prototype"] is False
    assert any(warning.code == "prototype_attribute_values" for warning in result.warnings)

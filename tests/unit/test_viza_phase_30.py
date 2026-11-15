"""Phase-30 tests: FIBO mappings, asset → FiboIdentity projection,
compile_decisions fibo_identity_resolver wiring, event type FIBO IRIs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from viza.commands import CommandMapping, SizingExpression
from viza.config_paths import resolve_config_path
from viza.decisions import compile_decisions
from viza.events import load_event_registry
from viza.fibo import (
    FiboIdentity,
    asset_to_fibo_identity,
    fibo_instrument_class_for_asset_class,
    fibo_iri_for_event_type,
    fibo_iri_for_identifier_scheme,
    get_fibo_mappings,
    reset_fibo_mappings_cache,
)
from viza.observations import ObservationInput, VizaObservation, observation_from_input
from viza.strategy_profiles import (
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    VizaStrategyProfile,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_fibo_mappings_cache()
    yield
    reset_fibo_mappings_cache()


# ---- Mappings load + accessors ------------------------------------------


def test_mappings_load_with_expected_us_eq_class() -> None:
    mappings = get_fibo_mappings()
    assert mappings.schema_name == "viza.fibo_mappings.v1"
    us_eq_iri = fibo_instrument_class_for_asset_class("US_EQ")
    assert us_eq_iri is not None
    assert "CommonStock" in us_eq_iri


def test_mappings_resolve_identifier_schemes() -> None:
    cik_iri = fibo_iri_for_identifier_scheme("cik")
    assert cik_iri is not None
    assert "SecCikIdentifier" in cik_iri
    figi_iri = fibo_iri_for_identifier_scheme("figi")
    assert figi_iri is not None
    assert "FinancialInstrumentIdentifier" in figi_iri


def test_mappings_resolve_confirmed_mna_event_to_fibo_cae() -> None:
    iri = fibo_iri_for_event_type("confirmed_mna")
    assert iri is not None
    assert "MergerEvent" in iri


def test_mappings_unknown_event_returns_null() -> None:
    iri = fibo_iri_for_event_type("acquisition_rumor")
    assert iri is None  # Intentionally null — no direct FIBO equivalent.


# ---- asset_to_fibo_identity ---------------------------------------------


def test_asset_to_fibo_identity_projects_us_equity() -> None:
    from viza.assets import VizaAsset, apply_fibo_mappings

    asset = VizaAsset(
        entity_id="entity-us-equity-AAPL",
        asset_id="asset-us-equity-AAPL",
        asset_class="US_EQ",
        primary_symbol="AAPL",
        current_name="Apple Inc.",
        identifiers={"ticker": "AAPL", "cik": "0000320193"},
        created_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
    )
    asset = apply_fibo_mappings(asset)
    identity = asset_to_fibo_identity(asset)
    assert identity.instrument_class_iri is not None
    assert "CommonStock" in identity.instrument_class_iri
    assert identity.legal_entity_iri == "entity-us-equity-AAPL"
    assert identity.instrument_iri == "asset-us-equity-AAPL"
    schemes = {ident.scheme_iri for ident in identity.identifier_set}
    assert any("SecCikIdentifier" in iri for iri in schemes)
    assert any("ExchangeTicker" in iri for iri in schemes)


def test_apply_fibo_mappings_populates_asset_iris() -> None:
    from viza.assets import VizaAsset, apply_fibo_mappings

    asset = VizaAsset(
        entity_id="entity-us-equity-MSFT",
        asset_id="asset-us-equity-MSFT",
        asset_class="US_EQ",
        primary_symbol="MSFT",
        current_name="Microsoft Corp.",
        identifiers={"ticker": "MSFT"},
        created_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
    )
    populated = apply_fibo_mappings(asset)
    assert populated.fibo_instrument_iri == "asset-us-equity-MSFT"
    assert populated.fibo_legal_entity_iri == "entity-us-equity-MSFT"
    assert populated.fibo_instrument_class_iri is not None
    assert "CommonStock" in populated.fibo_instrument_class_iri
    assert populated.fibo_legal_entity_class_iri is not None


# ---- compile_decisions accepts a fibo_identity_resolver -----------------


def _observation(
    *,
    entity_id: str = "eq_aapl",
    attribute_key: str,
    value: float,
    moment: datetime,
    asset_id: str | None = None,
) -> VizaObservation:
    item = ObservationInput(
        entity_id=entity_id,
        asset_id=asset_id,
        attribute_key=attribute_key,
        value=value,
        observed_at=moment,
        available_at=moment,
        retrieved_at=moment,
    )
    return observation_from_input(item)


def _profile() -> VizaStrategyProfile:
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_buy",
        label="RSI oversold",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(
                    attribute_key="rsi_14d", operator="lte", threshold=30.0
                )
            ]
        ),
        action_template="Open small position.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    return VizaStrategyProfile(
        strategy_profile_id="phase-30-test",
        display_name="Phase 30 test",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        created_at=now,
        updated_at=now,
    )


def test_command_target_carries_fibo_iris_when_resolver_provided() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    profile = _profile()
    observations = [
        _observation(
            attribute_key="rsi_14d", value=27.0, moment=cutoff, asset_id="asset-us-equity-AAPL"
        )
    ]

    def resolver(asset_id: str) -> FiboIdentity | None:
        if asset_id != "asset-us-equity-AAPL":
            return None
        return FiboIdentity(
            legal_entity_iri="https://spec.edmcouncil.org/fibo/ontology/BE/LegalEntities/CorporateBodies/Corporation#AAPL",
            instrument_iri="https://spec.edmcouncil.org/fibo/ontology/SEC/Equities/EquityInstruments/CommonStock#AAPL",
            instrument_class_iri="https://spec.edmcouncil.org/fibo/ontology/SEC/Equities/EquityInstruments/CommonStock",
        )

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-phase-30",
        graph_hash="g",
        profile_version="v",
        fibo_identity_resolver=resolver,
    )
    assert len(decisions) == 1
    command = decisions[0].command
    assert command is not None
    assert command.target.fibo_legal_entity_iri is not None
    assert "Corporation" in command.target.fibo_legal_entity_iri
    assert command.target.fibo_instrument_iri is not None
    assert "CommonStock" in command.target.fibo_instrument_iri


def test_command_target_fibo_iris_null_when_no_resolver() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    profile = _profile()
    observations = [
        _observation(attribute_key="rsi_14d", value=27.0, moment=cutoff, asset_id="asset-us-equity-AAPL")
    ]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-phase-30",
        graph_hash="g",
        profile_version="v",
    )
    assert len(decisions) == 1
    command = decisions[0].command
    assert command is not None
    assert command.target.fibo_legal_entity_iri is None
    assert command.target.fibo_instrument_iri is None


def test_default_fibo_identity_resolver_via_asset_store(tmp_path) -> None:
    """The default resolver looks up the local AssetStore. A seeded asset
    returns a populated FiboIdentity; unknown assets return None so the
    caller leaves CommandTarget.fibo_*_iri null."""
    from viza.assets import get_asset_store, asset_id_for_ticker
    from viza.fibo import default_fibo_identity_resolver
    from viza.universes import load_universe_definition

    store_path = tmp_path / "viza_projects.sqlite3"
    store = get_asset_store(store_path)
    seeded = store.seed_local_universe(load_universe_definition("pilot_sp500_static"))
    assert seeded, "fixture universe should seed at least one asset"
    seeded_asset_id = seeded[0].asset_id

    import viza.assets as assets_module

    original = assets_module.get_asset_store
    try:
        assets_module.get_asset_store = lambda path=None: store
        resolver = default_fibo_identity_resolver()
        identity = resolver(seeded_asset_id)
        assert identity is not None
        assert identity.instrument_iri == seeded_asset_id
        assert identity.instrument_class_iri is not None
        assert "CommonStock" in identity.instrument_class_iri
        # Unknown asset returns None — caller leaves CommandTarget.fibo_*_iri None.
        assert resolver("asset-us-equity-MISSING") is None
    finally:
        assets_module.get_asset_store = original


# ---- Event registry FIBO IRIs --------------------------------------------


def test_event_registry_now_carries_fibo_iri_for_confirmed_mna() -> None:
    registry = load_event_registry()
    by_type = {entry.event_type: entry for entry in registry.event_types}
    assert by_type["confirmed_mna"].fibo_iri is not None
    assert "MergerEvent" in by_type["confirmed_mna"].fibo_iri
    # Acquisition_rumor remains null intentionally.
    assert by_type["acquisition_rumor"].fibo_iri is None


def test_event_registry_concept_iris_resolve_via_concept_scheme() -> None:
    """The Phase-26 SKOS concepts and Phase-30 fibo mappings agree on event
    families: every event type's family_concept_iri resolves to a concept
    in `config/viza_concepts.json`."""
    registry = load_event_registry()
    from viza.concepts import get_concept_scheme

    scheme = get_concept_scheme()
    for entry in registry.event_types:
        assert entry.family_concept_iri is not None
        assert scheme.get(entry.family_concept_iri) is not None

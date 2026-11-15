"""Phase-32 tests: event-pattern grammar.

Coverage:

* Pattern AST validates and round-trips through Pydantic.
* Single `event_match` with confidence + source-credibility + PIT filters.
* `sequence` with `within` window bounds first-to-last span.
* `all` / `any` / `not` combinators.
* Allen relations (`before`, `equals`).
* `compile_decisions` event_pattern leg fires alongside observation predicates.
* `counter_event` defeater triggers via the registry FIBO-IRI lookup.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from viza.argumentation import (
    apply_argumentation,
    evaluate_defeaters_for_decision,
)
from viza.commands import (
    CommandMapping,
    CommandTarget,
    Defeater,
    InvestmentCommandPayload,
    PositionAxes,
    SizingExpression,
)
from viza.decisions import DecisionAudit, DecisionFrame, compile_decisions
from viza.event_patterns import (
    AllenRelation,
    Conjunction,
    Disjunction,
    EventMatch,
    EventPattern,
    Negation,
    Sequence,
    evaluate_pattern,
)
from viza.events import VizaEvent
from viza.observations import ObservationInput, VizaObservation, observation_from_input
from viza.strategy_profiles import (
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    VizaStrategyProfile,
)


# ---- Helpers -------------------------------------------------------------


def _event(
    *,
    event_type: str,
    event_id: str,
    affected_entity_ids: list[str],
    observed_at: datetime,
    available_at: datetime | None = None,
    confidence: float = 0.8,
    source_credibility: float = 0.7,
    point_in_time_safe: bool = True,
) -> VizaEvent:
    return VizaEvent(
        event_id=event_id,
        event_type=event_type,
        affected_entity_ids=affected_entity_ids,
        observed_at=observed_at,
        available_at=available_at or observed_at,
        source={"kind": "manual"},
        confidence=confidence,
        source_credibility=source_credibility,
        point_in_time_safe=point_in_time_safe,
    )


def _observation(
    *,
    entity_id: str,
    attribute_key: str,
    value: float,
    moment: datetime,
) -> VizaObservation:
    item = ObservationInput(
        entity_id=entity_id,
        attribute_key=attribute_key,
        value=value,
        observed_at=moment,
        available_at=moment,
        retrieved_at=moment,
    )
    return observation_from_input(item)


# ---- Pattern AST validation --------------------------------------------


def test_event_pattern_round_trips_through_pydantic() -> None:
    pattern = EventPattern(
        name="rumor_then_volume",
        pattern=Sequence(
            steps=[
                EventMatch(event_type="acquisition_rumor", min_confidence=0.5),
                EventMatch(event_type="unusual_volume", min_confidence=0.7),
            ],
            within="P3D",
        ),
    )
    payload = pattern.model_dump(mode="json", by_alias=True)
    reloaded = EventPattern.model_validate(payload)
    assert reloaded.pattern.kind == "sequence"
    assert isinstance(reloaded.pattern, Sequence)
    assert reloaded.pattern.within == "P3D"
    assert reloaded.pattern.steps[0].event_type == "acquisition_rumor"


# ---- Single event_match --------------------------------------------------


def test_event_match_by_type() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    events = [
        _event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment),
    ]
    match = evaluate_pattern(EventMatch(event_type="acquisition_rumor"), events)
    assert match is not None
    assert match.matched_event_ids == ["e1"]


def test_event_match_respects_min_confidence() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    events = [_event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment, confidence=0.3)]
    assert evaluate_pattern(EventMatch(event_type="acquisition_rumor", min_confidence=0.5), events) is None
    assert evaluate_pattern(EventMatch(event_type="acquisition_rumor", min_confidence=0.2), events) is not None


def test_event_match_respects_pit_safe_filter() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    events = [_event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment, point_in_time_safe=False)]
    assert evaluate_pattern(EventMatch(event_type="acquisition_rumor", require_point_in_time_safe=True), events) is None


def test_event_match_filters_by_cutoff_available_at() -> None:
    t0 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    later = t0 + timedelta(days=2)
    events = [_event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=later, available_at=later)]
    assert evaluate_pattern(EventMatch(event_type="acquisition_rumor"), events, cutoff_timestamp=t0) is None
    assert evaluate_pattern(EventMatch(event_type="acquisition_rumor"), events, cutoff_timestamp=later) is not None


# ---- Sequence ------------------------------------------------------------


def test_sequence_matches_when_steps_in_order_and_within_window() -> None:
    t0 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=12)
    events = [
        _event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=t0),
        _event(event_type="unusual_volume", event_id="e2", affected_entity_ids=["eq_aapl"], observed_at=t1),
    ]
    pattern = Sequence(
        steps=[
            EventMatch(event_type="acquisition_rumor"),
            EventMatch(event_type="unusual_volume"),
        ],
        within="P3D",
    )
    match = evaluate_pattern(pattern, events)
    assert match is not None
    assert match.matched_event_ids == ["e1", "e2"]


def test_sequence_fails_when_window_exceeded() -> None:
    t0 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    far = t0 + timedelta(days=10)
    events = [
        _event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=t0),
        _event(event_type="unusual_volume", event_id="e2", affected_entity_ids=["eq_aapl"], observed_at=far),
    ]
    pattern = Sequence(
        steps=[
            EventMatch(event_type="acquisition_rumor"),
            EventMatch(event_type="unusual_volume"),
        ],
        within="P3D",
    )
    assert evaluate_pattern(pattern, events) is None


def test_sequence_fails_when_steps_reversed() -> None:
    t0 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=12)
    events = [
        _event(event_type="unusual_volume", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=t0),
        _event(event_type="acquisition_rumor", event_id="e2", affected_entity_ids=["eq_aapl"], observed_at=t1),
    ]
    pattern = Sequence(
        steps=[
            EventMatch(event_type="acquisition_rumor"),
            EventMatch(event_type="unusual_volume"),
        ]
    )
    assert evaluate_pattern(pattern, events) is None


# ---- Combinators --------------------------------------------------------


def test_conjunction_requires_all_to_match() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    events = [
        _event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment),
        _event(event_type="unusual_volume", event_id="e2", affected_entity_ids=["eq_aapl"], observed_at=moment),
    ]
    match = evaluate_pattern(
        Conjunction(
            patterns=[
                EventMatch(event_type="acquisition_rumor"),
                EventMatch(event_type="unusual_volume"),
            ]
        ),
        events,
    )
    assert match is not None
    assert sorted(match.matched_event_ids) == ["e1", "e2"]


def test_disjunction_passes_if_any_matches() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    events = [
        _event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment),
    ]
    match = evaluate_pattern(
        Disjunction(
            patterns=[
                EventMatch(event_type="confirmed_mna"),
                EventMatch(event_type="acquisition_rumor"),
            ]
        ),
        events,
    )
    assert match is not None
    assert match.matched_event_ids == ["e1"]


def test_negation_succeeds_when_inner_does_not_match() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    events = [_event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment)]
    match = evaluate_pattern(
        Negation(pattern=EventMatch(event_type="regulatory_action")),
        events,
    )
    assert match is not None  # No regulatory_action present → negation passes.
    assert match.matched_event_ids == []


def test_negation_fails_when_inner_matches() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    events = [_event(event_type="regulatory_action", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment)]
    assert (
        evaluate_pattern(
            Negation(pattern=EventMatch(event_type="regulatory_action")), events
        )
        is None
    )


# ---- Allen relations ----------------------------------------------------


def test_allen_before_holds_when_left_strictly_before_right() -> None:
    t0 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=1)
    events = [
        _event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=t0),
        _event(event_type="confirmed_mna", event_id="e2", affected_entity_ids=["eq_aapl"], observed_at=t1),
    ]
    pattern = AllenRelation(
        relation="before",
        left=EventMatch(event_type="acquisition_rumor"),
        right=EventMatch(event_type="confirmed_mna"),
    )
    match = evaluate_pattern(pattern, events)
    assert match is not None


def test_allen_equals_uses_tolerance() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    events = [
        _event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment),
        _event(event_type="unusual_volume", event_id="e2", affected_entity_ids=["eq_aapl"], observed_at=moment + timedelta(seconds=30)),
    ]
    pattern = AllenRelation(
        relation="equals",
        left=EventMatch(event_type="acquisition_rumor"),
        right=EventMatch(event_type="unusual_volume"),
        tolerance="PT1M",
    )
    assert evaluate_pattern(pattern, events) is not None
    pattern_strict = AllenRelation(
        relation="equals",
        left=EventMatch(event_type="acquisition_rumor"),
        right=EventMatch(event_type="unusual_volume"),
        tolerance="PT1S",
    )
    assert evaluate_pattern(pattern_strict, events) is None


# ---- compile_decisions integration --------------------------------------


def _profile_with_event_trigger() -> VizaStrategyProfile:
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="catalyst_then_volume",
        label="Acquisition rumor followed by volume spike",
        trigger=DecisionTrigger(
            event_pattern=EventPattern(
                pattern=Sequence(
                    steps=[
                        EventMatch(event_type="acquisition_rumor", min_confidence=0.4),
                        EventMatch(event_type="unusual_volume", min_confidence=0.5),
                    ],
                    within="P3D",
                )
            )
        ),
        action_template="open small position.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    return VizaStrategyProfile(
        strategy_profile_id="phase-32-test",
        display_name="Phase 32",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        created_at=now,
        updated_at=now,
    )


def test_compile_decisions_fires_on_event_pattern() -> None:
    t0 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=6)
    cutoff = t1 + timedelta(hours=1)
    profile = _profile_with_event_trigger()
    observations = [
        _observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, moment=cutoff),
    ]
    events = [
        _event(event_type="acquisition_rumor", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=t0),
        _event(event_type="unusual_volume", event_id="e2", affected_entity_ids=["eq_aapl"], observed_at=t1),
    ]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        events=events,
        cutoff_timestamp=cutoff,
        run_id="run-32",
        graph_hash="g",
        profile_version="v",
    )
    assert len(decisions) == 1
    assert decisions[0].command is not None
    assert decisions[0].command.command_iri == "viza:cmd/buy_to_open"


def test_compile_decisions_does_not_fire_without_events_for_event_trigger() -> None:
    t0 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    profile = _profile_with_event_trigger()
    observations = [_observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, moment=t0)]
    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        events=[],
        cutoff_timestamp=t0,
        run_id="run-32-empty",
        graph_hash="g",
        profile_version="v",
    )
    assert decisions == []


# ---- counter_event defeater (Phase-32 wire-up) --------------------------


def _decision_with_counter_event_defeater(
    entity_id: str = "eq_aapl",
) -> DecisionFrame:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    command = InvestmentCommandPayload(
        command_iri="viza:cmd/buy_to_open",
        command_pref_label="BUY_TO_OPEN",
        kind="PositionCommand",
        target=CommandTarget(entity_id=entity_id),
        position_axes=PositionAxes(
            direction="BUY",
            position_change="OPEN",
            side="LONG",
            default_sizing_method="TARGET_WEIGHT",
        ),
        sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        resolved_sizing_value=0.02,
        defeaters=[
            Defeater(
                defeater_kind="counter_event",
                countering_event_iris=["regulatory_action"],
                rationale="Block when regulator intervenes.",
            )
        ],
    )
    return DecisionFrame(
        decision_id="d-counter",
        strategy_profile_id="phase-32-test",
        rule_id="r1",
        entity_id=entity_id,
        action_template="(test)",
        rule_text="r1: test",
        cutoff_timestamp=cutoff,
        emitted_at=cutoff,
        audit=DecisionAudit(
            graph_hash="g", profile_version="v", run_id="run-X", evidence_checksum="e"
        ),
        command=command,
        trigger_observation_ids=["obs-1"],
    )


def test_counter_event_defeater_triggers_on_regulatory_action() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    decision = _decision_with_counter_event_defeater()
    events = [
        _event(event_type="regulatory_action", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment),
    ]
    triggered = evaluate_defeaters_for_decision(decision, events=events)
    assert len(triggered) == 1
    assert triggered[0].defeater_kind == "counter_event"


def test_counter_event_defeater_does_not_trigger_when_unrelated_events() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    decision = _decision_with_counter_event_defeater()
    events = [
        _event(event_type="news_sentiment_shift", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment),
    ]
    assert evaluate_defeaters_for_decision(decision, events=events) == []


def test_counter_event_defeater_scoped_to_target_entity() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    decision = _decision_with_counter_event_defeater(entity_id="eq_aapl")
    events = [
        _event(event_type="regulatory_action", event_id="e1", affected_entity_ids=["eq_msft"], observed_at=moment),
    ]
    assert evaluate_defeaters_for_decision(decision, events=events) == []


def test_apply_argumentation_threads_events_through() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    decision = _decision_with_counter_event_defeater()
    events = [
        _event(event_type="regulatory_action", event_id="e1", affected_entity_ids=["eq_aapl"], observed_at=moment),
    ]
    result = apply_argumentation([decision], events=events)
    assert result[0].argumentation_status == "rejected"
    assert "counter_event" in (result[0].argumentation_reason or "")


def test_counter_event_defeater_matches_fibo_iri_from_event_registry() -> None:
    """`countering_event_iris` may contain FIBO IRIs (e.g.
    `fibo-cae-mer:MergerEvent`); the evaluator looks up the event_type's
    fibo_iri from the registry to test the match."""
    from viza.events import load_event_registry

    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    registry = load_event_registry()
    by_type = {entry.event_type: entry for entry in registry.event_types}
    merger_fibo_iri = by_type["confirmed_mna"].fibo_iri
    assert merger_fibo_iri is not None  # Phase-30 wired this.

    # Defeater names the FIBO IRI; the event_type "confirmed_mna" maps to it.
    decision = _decision_with_counter_event_defeater()
    decision = decision.model_copy(
        update={
            "command": decision.command.model_copy(
                update={
                    "defeaters": [
                        Defeater(
                            defeater_kind="counter_event",
                            countering_event_iris=[merger_fibo_iri],
                        )
                    ]
                }
            )
        }
    )
    events = [
        _event(event_type="confirmed_mna", event_id="e-mna", affected_entity_ids=["eq_aapl"], observed_at=moment),
    ]
    triggered = evaluate_defeaters_for_decision(decision, events=events)
    assert len(triggered) == 1
    assert "counter_event" in triggered[0].reason

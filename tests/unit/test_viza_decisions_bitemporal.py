"""Phase-28 integration tests: compile_decisions respects the
transaction_time_cutoff parameter, so that a re-compile after corrections
reproduces the original DecisionFrames bit-for-bit.

This is the central correctness story Phase 28 buys: backtesting and
marketplace claims become defensible because "what did the strategy say at
T?" is answerable independent of subsequent data revisions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from viza.commands import CommandMapping, SizingExpression
from viza.decisions import compile_decisions
from viza.observations import (
    ObservationInput,
    ObservationStore,
    VizaObservation,
    observation_from_input,
)
from viza.strategy_profiles import (
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    VizaStrategyProfile,
)


def _store(tmp_path: Path) -> ObservationStore:
    return ObservationStore(tmp_path / "obs.db")


def _profile_with_buy_rule(profile_id: str = "test-profile") -> VizaStrategyProfile:
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
        action_template="open small position.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    return VizaStrategyProfile(
        strategy_profile_id=profile_id,
        display_name="test profile",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        created_at=now,
        updated_at=now,
    )


def _observation(
    *,
    entity_id: str = "eq_aapl",
    attribute_key: str = "rsi_14d",
    value: float,
    moment: datetime,
    valid_time_start: datetime | None = None,
) -> VizaObservation:
    item = ObservationInput(
        entity_id=entity_id,
        attribute_key=attribute_key,
        value=value,
        observed_at=moment,
        available_at=moment,
        retrieved_at=moment,
    )
    obs = observation_from_input(item)
    if valid_time_start is not None:
        obs = obs.model_copy(update={"valid_time_start": valid_time_start})
    return obs


# ---- Core back-compat path: no corrections, no behavior change -----------


def test_compile_decisions_default_behavior_unchanged_without_corrections(
    tmp_path: Path,
) -> None:
    """A clean observation set with no corrections gives the same decisions
    whether or not `transaction_time_cutoff` is set."""
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    profile = _profile_with_buy_rule()
    obs = _observation(value=27.0, moment=cutoff)

    decisions_default = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-0",
        graph_hash="g",
        profile_version="v",
    )
    decisions_with_ttx = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-0",
        graph_hash="g",
        profile_version="v",
        transaction_time_cutoff=cutoff + timedelta(seconds=1),
    )

    assert len(decisions_default) == 1
    assert [d.decision_id for d in decisions_default] == [
        d.decision_id for d in decisions_with_ttx
    ]
    assert decisions_default[0].command is not None
    assert decisions_default[0].command.command_iri == "viza:cmd/buy_to_open"


# ---- The Phase-28 correctness story --------------------------------------


def test_replay_after_correction_returns_original_command(tmp_path: Path) -> None:
    """At t0 the system sees RSI=27 → BUY_TO_OPEN fires.
    A correction at t1 revises RSI to 35 (still trustable, but ABOVE the
    threshold). Recompiling at the original transaction time must still
    yield BUY_TO_OPEN; recompiling under the corrected belief must NOT."""
    store = _store(tmp_path)
    valid_moment = datetime(2026, 5, 21, 9, 0, tzinfo=timezone.utc)
    t0 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    profile = _profile_with_buy_rule()

    # Original observation: RSI=27 at t0.
    original = _observation(value=27.0, moment=t0, valid_time_start=valid_moment)
    store.upsert_observation(original)

    # Original compile produces a BUY_TO_OPEN.
    original_decisions = compile_decisions(
        profile=profile,
        observations=[original],
        cutoff_timestamp=valid_moment + timedelta(hours=4),
        run_id="run-original",
        graph_hash="g",
        profile_version="v",
        emitted_at=t0,
    )
    assert len(original_decisions) == 1
    assert original_decisions[0].command is not None
    assert (
        original_decisions[0].command.command_iri == "viza:cmd/buy_to_open"
    )

    # A correction lands at t1 revising RSI upward, past the trigger threshold.
    corrected = _observation(value=35.0, moment=t1, valid_time_start=valid_moment)
    store.correct_observation(
        prior_observation_id=original.observation_id,
        new_observation=corrected,
        correction_time=t1,
    )

    # Sanity: the store now has TWO rows for the same logical fact.
    raw_rows = store.get_as_of_transaction_time(transaction_time=t1 - timedelta(seconds=1))
    assert len(raw_rows) == 1
    assert raw_rows[0].value == 27.0

    raw_now = store.get_as_of_transaction_time(transaction_time=t1 + timedelta(seconds=1))
    assert len(raw_now) == 1
    assert raw_now[0].value == 35.0

    # Recompile under the CURRENT belief: nothing fires (RSI=35 above threshold).
    obs_set_now = store.get_as_of_transaction_time(
        transaction_time=t1 + timedelta(seconds=1)
    )
    decisions_under_current_belief = compile_decisions(
        profile=profile,
        observations=obs_set_now,
        cutoff_timestamp=valid_moment + timedelta(hours=4),
        run_id="run-now",
        graph_hash="g",
        profile_version="v",
        emitted_at=t1 + timedelta(seconds=1),
    )
    assert decisions_under_current_belief == []

    # Recompile AS-OF the original transaction time: BUY_TO_OPEN fires again.
    obs_set_then = store.get_as_of_transaction_time(transaction_time=t0)
    decisions_under_old_belief = compile_decisions(
        profile=profile,
        observations=obs_set_then,
        cutoff_timestamp=valid_moment + timedelta(hours=4),
        run_id="run-original",
        graph_hash="g",
        profile_version="v",
        emitted_at=t0,
        transaction_time_cutoff=t0,
    )
    assert len(decisions_under_old_belief) == 1
    assert (
        decisions_under_old_belief[0].command.command_iri == "viza:cmd/buy_to_open"
    )
    # The replay reproduces the decision_id deterministically — the same
    # (rule_id, entity_id, cutoff_timestamp, run_id) inputs hash to the
    # same id.
    assert (
        decisions_under_old_belief[0].decision_id
        == original_decisions[0].decision_id
    )


def test_transaction_time_cutoff_drops_observations_recorded_after_ttx(
    tmp_path: Path,
) -> None:
    """A new observation recorded at t2 must not influence a recompile at
    transaction_time_cutoff=t1<t2."""
    valid_moment = datetime(2026, 5, 21, 9, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    profile = _profile_with_buy_rule()
    later_observation = _observation(
        value=27.0, moment=t2, valid_time_start=valid_moment
    )

    decisions = compile_decisions(
        profile=profile,
        observations=[later_observation],
        cutoff_timestamp=valid_moment + timedelta(hours=4),
        run_id="run-replay",
        graph_hash="g",
        profile_version="v",
        emitted_at=t1,
        transaction_time_cutoff=t1,
    )
    # The later observation has transaction_time_start = t2 > t1, so it must
    # be filtered out by the AS-OF transaction-time predicate.
    assert decisions == []

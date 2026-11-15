"""Pin-5 look-ahead audit gate for the VIZA decision executor.

THREE REQUIRED ASSERTIONS (any failure must fail CI):

  A. Persistence integrity:
       For every persisted DecisionFrame,
         decision.pit_state["max_observation_available_at"]
       equals the actual available_at of the latest triggering observation.
       The executor never substitutes retrieved_at, observed_at, or now() for
       available_at.

  B. Replay PIT correctness:
       For replay_decisions_from_store(run_id, cutoff_timestamp=T):
       every returned decision satisfies
         pit_state["max_observation_available_at"] <= T
       AND decision.cutoff_timestamp <= T.

  C. Rule-effective-from gate (sandbox analog of pin-5 C):
       A DecisionRule with effective_from > cutoff_timestamp does NOT fire.
       Sandbox replay must not fabricate decisions for a rule that did not yet
       exist at the cutoff. Phase C will extend this to a hard block in live
       mode; Phase A enforces non-firing in sandbox replay.

This file lives in tests/lookahead_audit/ (NOT tests/unit/) because it gates
CI separately as a look-ahead safety check. See
docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md and tests/lookahead_audit/test_finbert_observation_pit.py
for the pattern this file mirrors.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from viza.decisions import (
    DecisionStore,
    compile_decisions,
    replay_decisions_from_store,
)
from viza.observations import ObservationInput, observation_from_input
from viza.strategy_profiles import (
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    VizaStrategyProfile,
)


CUTOFF = datetime(2026, 5, 20, tzinfo=timezone.utc)
OBS_AVAILABLE_AT = CUTOFF - timedelta(hours=2)
OBS_RETRIEVED_AT = CUTOFF + timedelta(hours=5)  # intentionally later than CUTOFF


def _observation():
    item = ObservationInput(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        observed_at=OBS_AVAILABLE_AT,
        available_at=OBS_AVAILABLE_AT,
        retrieved_at=OBS_RETRIEVED_AT,
        source_id="pit_audit",
        connector_id="pit_audit_connector",
        rights_policy={"export_allowed": True, "raw_snapshot_allowed": True},
    )
    return observation_from_input(item)


def _rule(*, effective_from: datetime | None = None) -> DecisionRule:
    return DecisionRule(
        rule_id="rsi-deep-oversold-v1",
        label="Deep oversold",
        enabled=True,
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(
                    attribute_key="rsi_14d",
                    operator="lte",
                    threshold=30.0,
                )
            ]
        ),
        action_template="Flag for analyst review: RSI deep-oversold reading.",
        effective_from=effective_from,
    )


def _profile(rule: DecisionRule) -> VizaStrategyProfile:
    return VizaStrategyProfile(
        strategy_profile_id="pit-audit-profile",
        display_name="PIT Audit Profile",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        created_at=CUTOFF - timedelta(days=30),
        updated_at=CUTOFF - timedelta(days=1),
    )


# ---- Assertion A: persistence integrity ------------------------------------


def test_persisted_decision_max_available_at_equals_observation_available_at(
    tmp_path: Path,
) -> None:
    """pit_state['max_observation_available_at'] must equal the triggering
    observation's available_at, never retrieved_at, observed_at, or emitted_at."""
    obs = _observation()
    decisions = compile_decisions(
        profile=_profile(_rule()),
        observations=[obs],
        cutoff_timestamp=CUTOFF,
        run_id="run-pit-a",
        graph_hash="h",
        profile_version="v",
    )
    assert len(decisions) == 1
    decision = decisions[0]

    max_avail = decision.pit_state["max_observation_available_at"]
    assert max_avail == OBS_AVAILABLE_AT.isoformat()
    assert max_avail != OBS_RETRIEVED_AT.isoformat()
    assert max_avail != decision.emitted_at.isoformat()
    assert decision.pit_state["lookahead_risk"] == "low"

    store = DecisionStore(tmp_path / "pit_a.sqlite3")
    store.upsert_decision(decision)
    persisted = store.list_decisions_by_run("run-pit-a")
    assert len(persisted) == 1
    assert (
        persisted[0].pit_state["max_observation_available_at"]
        == OBS_AVAILABLE_AT.isoformat()
    )


# ---- Assertion B: replay PIT correctness -----------------------------------


def test_replay_never_returns_post_cutoff_decisions(tmp_path: Path) -> None:
    """replay_decisions_from_store with cutoff T returns only decisions whose
    triggering observations had available_at <= T AND whose own
    cutoff_timestamp was <= T."""
    obs = _observation()
    decisions = compile_decisions(
        profile=_profile(_rule()),
        observations=[obs],
        cutoff_timestamp=CUTOFF,
        run_id="run-pit-b",
        graph_hash="h",
        profile_version="v",
    )
    store = DecisionStore(tmp_path / "pit_b.sqlite3")
    for decision in decisions:
        store.upsert_decision(decision)

    pre_cutoff = OBS_AVAILABLE_AT - timedelta(seconds=1)
    pre_replay = replay_decisions_from_store(
        store=store,
        run_id="run-pit-b",
        cutoff_timestamp=pre_cutoff,
    )
    for decision in pre_replay:
        assert decision.pit_state["max_observation_available_at"] is not None
        max_dt = datetime.fromisoformat(
            decision.pit_state["max_observation_available_at"]
        )
        assert max_dt <= pre_cutoff
    assert pre_replay == []

    full_replay = replay_decisions_from_store(
        store=store,
        run_id="run-pit-b",
        cutoff_timestamp=CUTOFF,
    )
    for decision in full_replay:
        max_dt = datetime.fromisoformat(
            decision.pit_state["max_observation_available_at"]
        )
        assert max_dt <= CUTOFF
        assert decision.cutoff_timestamp <= CUTOFF
    assert len(full_replay) == 1


# ---- Assertion C: rule-effective-from gate ---------------------------------


def test_rule_effective_after_cutoff_does_not_fire() -> None:
    """A rule whose effective_from is later than the cutoff must not fire.

    Sandbox replay cannot fabricate decisions for a rule that did not yet exist
    as of the replay cutoff. Phase C will extend this to a hard block in live
    mode; Phase A enforces non-firing in sandbox replay.
    """
    rule = _rule(effective_from=CUTOFF + timedelta(days=1))
    decisions = compile_decisions(
        profile=_profile(rule),
        observations=[_observation()],
        cutoff_timestamp=CUTOFF,
        run_id="run-pit-c",
        graph_hash="h",
        profile_version="v",
    )
    assert decisions == []


def test_rule_effective_at_or_before_cutoff_fires() -> None:
    """The dual of the above: a rule whose effective_from is at or before the
    cutoff fires normally."""
    rule = _rule(effective_from=CUTOFF - timedelta(days=30))
    decisions = compile_decisions(
        profile=_profile(rule),
        observations=[_observation()],
        cutoff_timestamp=CUTOFF,
        run_id="run-pit-c-dual",
        graph_hash="h",
        profile_version="v",
    )
    assert len(decisions) == 1


def test_rule_without_effective_from_fires_under_sandbox_replay() -> None:
    """A rule without a declared effective_from is tolerated under sandbox
    replay (Phase A default). Phase C will tighten this for live mode."""
    decisions = compile_decisions(
        profile=_profile(_rule(effective_from=None)),
        observations=[_observation()],
        cutoff_timestamp=CUTOFF,
        run_id="run-pit-c-null",
        graph_hash="h",
        profile_version="v",
    )
    assert len(decisions) == 1


# ---- Schema invariant: replay must not silently swallow corruption ---------


def test_replay_raises_on_malformed_pit_state(tmp_path: Path) -> None:
    """Every Phase A decision persisted by compile_decisions carries a valid
    pit_state.max_observation_available_at ISO string. A row missing or
    corrupting that field must fail replay loudly, not silently disappear."""
    import sqlite3

    store = DecisionStore(tmp_path / "pit_corrupt.sqlite3")
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            """
            INSERT INTO decisions(
                decision_id, strategy_profile_id, rule_id, entity_id, asset_id,
                action_template, rule_text, trigger_observation_ids_json,
                pit_state_json, source_rights_state_json,
                cutoff_timestamp, mode, emitted_at,
                graph_hash, profile_version, run_id, evidence_checksum,
                not_investment_advice
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', '{}', '{}', ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                "decision-corrupt",
                "profile-1",
                "rule-1",
                "AAPL",
                None,
                "test action",
                "rule-1: test",
                CUTOFF.isoformat(),
                "sandbox_replay",
                CUTOFF.isoformat(),
                "h",
                "v",
                "run-corrupt",
                "c",
            ),
        )

    import pytest

    with pytest.raises(ValueError, match="malformed pit_state"):
        replay_decisions_from_store(
            store=store,
            run_id="run-corrupt",
            cutoff_timestamp=CUTOFF,
        )

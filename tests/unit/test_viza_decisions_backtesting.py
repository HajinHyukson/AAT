"""Phase D backtesting evaluator tests for VIZA decisions.

See docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from viza.decisions_backtesting import (
    BacktestRequest,
    run_decisions_backtest,
)
from viza.observations import ObservationInput, observation_from_input
from viza.strategy_profiles import (
    CooldownPolicy,
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    VizaStrategyProfile,
)


def _observation(
    *,
    entity_id: str,
    attribute_key: str,
    value: float,
    available_at: datetime,
):
    return observation_from_input(
        ObservationInput(
            entity_id=entity_id,
            attribute_key=attribute_key,
            value=value,
            observed_at=available_at,
            available_at=available_at,
            retrieved_at=available_at + timedelta(hours=1),
            source_id="bt",
            connector_id="bt-connector",
            rights_policy={"export_allowed": True, "raw_snapshot_allowed": True},
        )
    )


def _rsi_rule(cooldown: CooldownPolicy | None = None) -> DecisionRule:
    return DecisionRule(
        rule_id="bt-rsi-rule",
        label="BT: RSI deep oversold",
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
        action_template="Flag for analyst review: deep-oversold RSI.",
        cooldown_policy=cooldown or CooldownPolicy(),
    )


def _profile(rule: DecisionRule) -> VizaStrategyProfile:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return VizaStrategyProfile(
        strategy_profile_id="bt-profile",
        display_name="BT",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        created_at=now,
        updated_at=now,
    )


def test_backtest_returns_empty_report_when_no_cutoffs() -> None:
    report = run_decisions_backtest(
        BacktestRequest(
            profile=_profile(_rsi_rule()),
            observations=[],
            cutoffs=[],
            graph_hash="h",
            profile_version="v",
        )
    )
    assert report.cutoff_count == 0
    assert report.total_decisions == 0
    assert report.by_rule == []
    assert report.by_entity == []
    assert report.decisions == []
    assert report.not_investment_advice is True


def test_backtest_fires_once_per_qualifying_cutoff_without_cooldown() -> None:
    cutoffs = [
        datetime(2026, 1, 10, tzinfo=timezone.utc),
        datetime(2026, 2, 10, tzinfo=timezone.utc),
        datetime(2026, 3, 10, tzinfo=timezone.utc),
    ]
    observations = [
        _observation(
            entity_id="AAPL",
            attribute_key="rsi_14d",
            value=25.0,
            available_at=cutoff - timedelta(hours=1),
        )
        for cutoff in cutoffs
    ]
    report = run_decisions_backtest(
        BacktestRequest(
            profile=_profile(_rsi_rule()),
            observations=observations,
            cutoffs=cutoffs,
            graph_hash="h",
            profile_version="v",
        )
    )
    assert report.cutoff_count == 3
    assert report.total_decisions == 3
    assert len(report.by_rule) == 1
    rule_summary = report.by_rule[0]
    assert rule_summary.rule_id == "bt-rsi-rule"
    assert rule_summary.fire_count == 3
    assert rule_summary.entities_fired == ["AAPL"]
    assert rule_summary.fires_by_entity == {"AAPL": 3}
    assert len(rule_summary.fires_by_cutoff) == 3
    assert rule_summary.earliest_fire_at == cutoffs[0]
    assert rule_summary.latest_fire_at == cutoffs[-1]


def test_backtest_cooldown_suppresses_subsequent_fires_within_window() -> None:
    cutoffs = [
        datetime(2026, 1, 10, tzinfo=timezone.utc),
        datetime(2026, 1, 15, tzinfo=timezone.utc),  # within 7-day window
        datetime(2026, 2, 10, tzinfo=timezone.utc),  # outside window
    ]
    observations = [
        _observation(
            entity_id="AAPL",
            attribute_key="rsi_14d",
            value=25.0,
            available_at=cutoff - timedelta(hours=1),
        )
        for cutoff in cutoffs
    ]
    cooldown = CooldownPolicy(
        max_fires_per_entity_per_window=1,
        window_seconds=7 * 24 * 3600,
    )
    report = run_decisions_backtest(
        BacktestRequest(
            profile=_profile(_rsi_rule(cooldown=cooldown)),
            observations=observations,
            cutoffs=cutoffs,
            graph_hash="h",
            profile_version="v",
        )
    )
    # Cutoff #1 fires; #2 suppressed by cooldown; #3 fires again (out of window).
    assert report.total_decisions == 2


def test_backtest_aggregates_by_entity() -> None:
    cutoffs = [
        datetime(2026, 1, 10, tzinfo=timezone.utc),
        datetime(2026, 2, 10, tzinfo=timezone.utc),
    ]
    observations: list = []
    for cutoff in cutoffs:
        observations.append(
            _observation(
                entity_id="AAPL",
                attribute_key="rsi_14d",
                value=25.0,
                available_at=cutoff - timedelta(hours=1),
            )
        )
        observations.append(
            _observation(
                entity_id="MSFT",
                attribute_key="rsi_14d",
                value=28.0,
                available_at=cutoff - timedelta(hours=1),
            )
        )
    report = run_decisions_backtest(
        BacktestRequest(
            profile=_profile(_rsi_rule()),
            observations=observations,
            cutoffs=cutoffs,
            graph_hash="h",
            profile_version="v",
        )
    )
    assert report.total_decisions == 4  # 2 entities * 2 cutoffs
    by_entity = {entry.entity_id: entry for entry in report.by_entity}
    assert by_entity["AAPL"].fire_count == 2
    assert by_entity["MSFT"].fire_count == 2
    assert by_entity["AAPL"].rules_fired == ["bt-rsi-rule"]


def test_backtest_does_not_fire_when_predicate_fails() -> None:
    cutoffs = [datetime(2026, 1, 10, tzinfo=timezone.utc)]
    observations = [
        _observation(
            entity_id="AAPL",
            attribute_key="rsi_14d",
            value=55.0,  # above threshold
            available_at=cutoffs[0] - timedelta(hours=1),
        )
    ]
    report = run_decisions_backtest(
        BacktestRequest(
            profile=_profile(_rsi_rule()),
            observations=observations,
            cutoffs=cutoffs,
            graph_hash="h",
            profile_version="v",
        )
    )
    assert report.total_decisions == 0
    assert report.by_rule == []
    assert report.by_entity == []


def test_backtest_decisions_carry_sandbox_replay_mode() -> None:
    """Backtesting is sandbox-only by construction; every emitted decision
    must carry mode='sandbox_replay' regardless of any caller intent."""
    cutoffs = [datetime(2026, 1, 10, tzinfo=timezone.utc)]
    observations = [
        _observation(
            entity_id="AAPL",
            attribute_key="rsi_14d",
            value=25.0,
            available_at=cutoffs[0] - timedelta(hours=1),
        )
    ]
    report = run_decisions_backtest(
        BacktestRequest(
            profile=_profile(_rsi_rule()),
            observations=observations,
            cutoffs=cutoffs,
            graph_hash="h",
            profile_version="v",
        )
    )
    assert len(report.decisions) == 1
    assert report.decisions[0].mode == "sandbox_replay"
    assert report.decisions[0].not_investment_advice is True


def test_backtest_pit_safety_observations_after_cutoff_are_ignored() -> None:
    """A backtest at cutoff T must not use observations whose available_at > T,
    even if those observations exist in the input set."""
    cutoff_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    observations = [
        _observation(
            entity_id="AAPL",
            attribute_key="rsi_14d",
            value=25.0,
            available_at=cutoff_at + timedelta(days=5),  # after the cutoff
        )
    ]
    report = run_decisions_backtest(
        BacktestRequest(
            profile=_profile(_rsi_rule()),
            observations=observations,
            cutoffs=[cutoff_at],
            graph_hash="h",
            profile_version="v",
        )
    )
    assert report.total_decisions == 0

"""Phase-27 integration tests: compile_decisions emits structured commands,
argumentation gate, package redaction.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from viza.commands import CommandMapping, SizingExpression
from viza.decisions import (
    DecisionFrame,
    DecisionStore,
    compile_decisions,
    emit_and_persist_decisions,
)
from viza.decisions_redaction import (
    command_axis_counts,
    redact_decisions_for_package,
    PackageRedactionBlocked,
)
from viza.observations import ObservationInput, VizaObservation, observation_from_input
from viza.strategy_profiles import (
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    VizaStrategyProfile,
)


# ---- Helpers -------------------------------------------------------------


def _observation(
    *,
    entity_id: str,
    attribute_key: str,
    value: float,
    available_at: datetime,
    asset_id: str | None = None,
    rights_policy: dict | None = None,
) -> VizaObservation:
    item = ObservationInput(
        entity_id=entity_id,
        asset_id=asset_id,
        attribute_key=attribute_key,
        value=value,
        observed_at=available_at,
        available_at=available_at,
        retrieved_at=available_at,
        rights_policy=rights_policy or {"export_allowed": True, "raw_snapshot_allowed": True},
    )
    return observation_from_input(item)


def _profile_with_rule(
    *,
    rule: DecisionRule,
    profile_id: str = "test-profile",
) -> VizaStrategyProfile:
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    return VizaStrategyProfile(
        strategy_profile_id=profile_id,
        display_name="test profile",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        created_at=now,
        updated_at=now,
    )


# ---- Tests ---------------------------------------------------------------


def test_rule_without_command_mapping_emits_no_command() -> None:
    """Pre-Phase-27 rules continue to work: a DecisionFrame is emitted with
    command=None and the verbatim action_template intact."""
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_oversold",
        label="RSI oversold",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="Investigate this candidate.",
    )
    profile = _profile_with_rule(rule=rule)
    observations = [_observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, available_at=cutoff, asset_id="AAPL")]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-1",
        graph_hash="graph-hash",
        profile_version="v1",
    )

    assert len(decisions) == 1
    assert decisions[0].command is None
    assert decisions[0].action_template == "Investigate this candidate."


def test_rule_with_command_mapping_emits_structured_buy_to_open() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_catalyst_entry",
        label="RSI oversold + catalyst",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="Open small starter position pending confirmation.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    profile = _profile_with_rule(rule=rule)
    observations = [_observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, available_at=cutoff, asset_id="AAPL")]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-2",
        graph_hash="graph-hash",
        profile_version="v1",
    )

    assert len(decisions) == 1
    command = decisions[0].command
    assert command is not None
    assert command.command_iri == "viza:cmd/buy_to_open"
    assert command.kind == "PositionCommand"
    assert command.position_axes is not None
    assert command.position_axes.direction == "BUY"
    assert command.position_axes.position_change == "OPEN"
    assert command.resolved_sizing_value == pytest.approx(0.02)
    assert command.execution_routing == "none"
    assert command.not_investment_advice is True


def test_rule_with_dynamic_sizing_expression_evaluates_against_observations() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_dynamic_size",
        label="RSI oversold + conviction-weighted entry",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="Open dynamic-sized position.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(
                method="TARGET_WEIGHT",
                expression="min(0.05, max(0.005, conviction_score / 50))",
            ),
        ),
    )
    profile = _profile_with_rule(rule=rule)
    observations = [
        _observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, available_at=cutoff),
        _observation(entity_id="eq_aapl", attribute_key="conviction_score", value=2.0, available_at=cutoff),
    ]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-3",
        graph_hash="graph-hash",
        profile_version="v1",
    )

    assert len(decisions) == 1
    command = decisions[0].command
    assert command is not None
    # 2.0 / 50 = 0.04, clamped between 0.005 and 0.05.
    assert command.resolved_sizing_value == pytest.approx(0.04)


def test_rights_blocked_observation_converts_command_to_block_export() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_oversold_export_blocked",
        label="RSI oversold (export-restricted source)",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="Open starter position.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    profile = _profile_with_rule(rule=rule)
    observations = [
        _observation(
            entity_id="eq_aapl",
            attribute_key="rsi_14d",
            value=27.0,
            available_at=cutoff,
            rights_policy={"export_allowed": False, "raw_snapshot_allowed": True},
        ),
    ]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-4",
        graph_hash="graph-hash",
        profile_version="v1",
    )

    assert len(decisions) == 1
    command = decisions[0].command
    assert command is not None
    assert command.command_iri == "viza:cmd/block_export"
    assert command.kind == "SystemCommand"


def test_block_action_command_rejects_other_commands_on_same_target() -> None:
    """Phase-27 minimal argumentation: a BLOCK_ACTION on entity X tags every
    other co-firing command on X as argumentation_status='rejected'."""
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    buy_rule = DecisionRule(
        rule_id="rsi_buy",
        label="RSI oversold",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="Open position.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    block_rule = DecisionRule(
        rule_id="regulatory_veto",
        label="Regulatory action: block all positions",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(
                    attribute_key="regulatory_action_severity",
                    operator="gte",
                    threshold=0.9,
                )
            ]
        ),
        action_template="Halt due to regulatory action.",
        command_mapping=CommandMapping(command_iri="viza:cmd/block_action"),
    )
    profile = _profile_with_rule(rule=buy_rule)
    profile.decision_rules.append(block_rule)
    observations = [
        _observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, available_at=cutoff),
        _observation(
            entity_id="eq_aapl",
            attribute_key="regulatory_action_severity",
            value=1.0,
            available_at=cutoff,
        ),
    ]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-5",
        graph_hash="graph-hash",
        profile_version="v1",
    )

    assert len(decisions) == 2
    buy_decision = next(d for d in decisions if d.rule_id == "rsi_buy")
    block_decision = next(d for d in decisions if d.rule_id == "regulatory_veto")

    assert block_decision.argumentation_status == "accepted"
    assert buy_decision.argumentation_status == "rejected"
    assert buy_decision.command is not None
    assert buy_decision.command.argumentation_status == "rejected"


def test_provenance_block_populated_with_prov_iris() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_oversold",
        label="RSI oversold",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="Open position.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    profile = _profile_with_rule(rule=rule)
    observations = [_observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, available_at=cutoff)]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-6",
        graph_hash="g",
        profile_version="v",
    )

    provenance = decisions[0].provenance
    assert provenance is not None
    assert provenance.was_generated_by_run_iri == "viza:activity/run/run-6"
    assert provenance.was_attributed_to_agent_iri.startswith("viza:agent/")
    assert provenance.decision_entity_iri.startswith("viza:entity/decision/")
    assert all(iri.startswith("viza:entity/observation/") for iri in provenance.used_observation_iris)


def test_command_axis_counts_aggregates_by_axis() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rules = [
        DecisionRule(
            rule_id="buy_rule",
            label="buy",
            trigger=DecisionTrigger(
                observation_predicates=[
                    ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
                ]
            ),
            action_template="open.",
            command_mapping=CommandMapping(
                command_iri="viza:cmd/buy_to_open",
                sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
            ),
        ),
        DecisionRule(
            rule_id="trim_rule",
            label="trim",
            trigger=DecisionTrigger(
                observation_predicates=[
                    ObservationPredicate(attribute_key="momentum", operator="lte", threshold=-0.05)
                ]
            ),
            action_template="trim.",
            command_mapping=CommandMapping(
                command_iri="viza:cmd/trim_long",
                sizing=SizingExpression(method="DELTA_WEIGHT", expression="0.005"),
            ),
        ),
    ]
    profile = _profile_with_rule(rule=rules[0])
    profile.decision_rules.append(rules[1])

    observations = [
        _observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, available_at=cutoff),
        _observation(entity_id="eq_msft", attribute_key="momentum", value=-0.10, available_at=cutoff),
    ]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-7",
        graph_hash="g",
        profile_version="v",
    )

    counts = command_axis_counts(decisions)
    assert counts["by_direction"].get("BUY") == 1
    assert counts["by_direction"].get("SELL") == 1
    assert counts["by_position_change"].get("OPEN") == 1
    assert counts["by_position_change"].get("REDUCE") == 1
    assert counts["by_side"].get("LONG") == 2
    assert counts["by_command_iri"]["viza:cmd/buy_to_open"] == 1
    assert counts["by_command_iri"]["viza:cmd/trim_long"] == 1


def test_marketplace_redaction_strips_targets_and_keeps_axis_counts() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="buy_rule",
        label="buy",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="open.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    profile = _profile_with_rule(rule=rule)
    observations = [_observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, available_at=cutoff)]
    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-8",
        graph_hash="g",
        profile_version="v",
    )

    payload = redact_decisions_for_package(decisions, mode="marketplace_draft")
    assert payload["decisions"] == []
    assert "eq_aapl" not in str(payload)
    assert payload["command_axis_counts"]["by_command_iri"]["viza:cmd/buy_to_open"] == 1


def test_output_only_redaction_redacts_sizing_expression() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="buy_rule",
        label="buy",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="open.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.0234567"),
        ),
    )
    profile = _profile_with_rule(rule=rule)
    observations = [_observation(entity_id="eq_aapl", attribute_key="rsi_14d", value=27.0, available_at=cutoff)]
    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-9",
        graph_hash="g",
        profile_version="v",
    )

    payload = redact_decisions_for_package(decisions, mode="output_only")
    decision_payload = payload["decisions"][0]
    assert decision_payload["command"]["sizing"]["expression"] == "[redacted]"
    assert decision_payload["command"]["resolved_sizing_value"] is None
    # The sizing method itself remains visible so consumers know it WAS a
    # target-weight command without learning the formula.
    assert decision_payload["command"]["sizing"]["method"] == "TARGET_WEIGHT"


def test_export_blocked_observation_makes_redaction_raise() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="buy_rule",
        label="buy",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="open.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    profile = _profile_with_rule(rule=rule)
    observations = [
        _observation(
            entity_id="eq_aapl",
            attribute_key="rsi_14d",
            value=27.0,
            available_at=cutoff,
            rights_policy={"export_allowed": False, "raw_snapshot_allowed": False},
        )
    ]
    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="run-10",
        graph_hash="g",
        profile_version="v",
    )

    # The decision was emitted but with source_rights_state.export_allowed=False.
    assert decisions[0].source_rights_state["export_allowed"] is False

    # The package redaction layer refuses to export it.
    with pytest.raises(PackageRedactionBlocked):
        redact_decisions_for_package(decisions, mode="output_only")

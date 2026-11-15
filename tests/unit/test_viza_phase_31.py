"""Phase-31 tests: ASPIC+ argumentation over commands.

Coverage:

* Defeater evaluators (evidence_absent, time_decay, pit_unsafe, rights_blocked).
* Attack graph construction from `viza_command_conflicts.json`.
* Preference-resolved symmetric attacks (command_confidence * command_priority).
* Grounded-extension fixed point: BLOCK_ACTION defeats every position
  command; mutual `attacks` edges resolve in favor of the higher-preference
  command.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from viza.argumentation import (
    apply_argumentation,
    apply_preferences,
    build_attack_graph,
    compute_grounded_extension,
    evaluate_defeaters_for_decision,
)
from viza.commands import (
    AttentionAxes,
    CommandTarget,
    Defeater,
    InvestmentCommandPayload,
    PositionAxes,
    SizingExpression,
    SystemAxes,
)
from viza.decisions import DecisionAudit, DecisionFrame


def _decision(
    *,
    decision_id: str,
    entity_id: str,
    command: InvestmentCommandPayload | None,
    pit_state: dict | None = None,
    source_rights_state: dict | None = None,
    trigger_observation_ids: list[str] | None = None,
    cutoff_timestamp: datetime | None = None,
) -> DecisionFrame:
    cutoff = cutoff_timestamp or datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    return DecisionFrame(
        decision_id=decision_id,
        strategy_profile_id="test-profile",
        rule_id=f"rule-{decision_id}",
        entity_id=entity_id,
        action_template="(test)",
        rule_text="test rule",
        cutoff_timestamp=cutoff,
        emitted_at=cutoff,
        audit=DecisionAudit(
            graph_hash="g", profile_version="v", run_id="run-X", evidence_checksum="e"
        ),
        command=command,
        pit_state=pit_state or {"lookahead_risk": "low"},
        source_rights_state=source_rights_state or {"export_allowed": True},
        trigger_observation_ids=trigger_observation_ids or ["obs-1"],
    )


def _buy_to_open(
    *,
    entity_id: str = "eq_aapl",
    confidence: float = 0.8,
    priority: int = 70,
    defeaters: list[Defeater] | None = None,
) -> InvestmentCommandPayload:
    return InvestmentCommandPayload(
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
        command_confidence=confidence,
        command_priority=priority,
        defeaters=defeaters or [],
    )


def _avoid(
    *,
    entity_id: str = "eq_aapl",
    confidence: float = 0.9,
    priority: int = 50,
) -> InvestmentCommandPayload:
    return InvestmentCommandPayload(
        command_iri="viza:cmd/avoid",
        command_pref_label="AVOID",
        kind="AttentionCommand",
        target=CommandTarget(entity_id=entity_id),
        attention_axes=AttentionAxes(urgency="EXCLUDE"),
        command_confidence=confidence,
        command_priority=priority,
    )


def _block_action(
    entity_id: str = "eq_aapl",
) -> InvestmentCommandPayload:
    return InvestmentCommandPayload(
        command_iri="viza:cmd/block_action",
        command_pref_label="BLOCK_ACTION",
        kind="SystemCommand",
        target=CommandTarget(entity_id=entity_id),
        system_axes=SystemAxes(veto_kind="EMIT_BLOCKED"),
        command_confidence=1.0,
        command_priority=100,
    )


# ---- Defeater evaluation -------------------------------------------------


def test_evidence_absent_defeater_triggers_when_too_few_observations() -> None:
    defeater = Defeater(
        defeater_kind="evidence_absent",
        required_evidence_keys=["rsi_14d", "volume_spike", "sec_filing_novelty"],
    )
    decision = _decision(
        decision_id="d1",
        entity_id="eq_aapl",
        command=_buy_to_open(defeaters=[defeater]),
        trigger_observation_ids=["obs-rsi"],  # only one of three required.
    )
    triggered = evaluate_defeaters_for_decision(decision)
    assert len(triggered) == 1
    assert triggered[0].defeater_kind == "evidence_absent"


def test_evidence_absent_defeater_does_not_trigger_with_enough_observations() -> None:
    defeater = Defeater(
        defeater_kind="evidence_absent",
        required_evidence_keys=["rsi_14d"],
    )
    decision = _decision(
        decision_id="d1",
        entity_id="eq_aapl",
        command=_buy_to_open(defeaters=[defeater]),
        trigger_observation_ids=["obs-rsi"],
    )
    assert evaluate_defeaters_for_decision(decision) == []


def test_time_decay_defeater_triggers_when_evidence_older_than_window() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    old_evidence = (cutoff - timedelta(days=10)).isoformat()
    defeater = Defeater(defeater_kind="time_decay", window="P3D")
    decision = _decision(
        decision_id="d1",
        entity_id="eq_aapl",
        command=_buy_to_open(defeaters=[defeater]),
        pit_state={"lookahead_risk": "low", "max_observation_available_at": old_evidence},
        cutoff_timestamp=cutoff,
    )
    triggered = evaluate_defeaters_for_decision(decision)
    assert len(triggered) == 1
    assert triggered[0].defeater_kind == "time_decay"


def test_time_decay_defeater_passes_when_evidence_inside_window() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    recent = (cutoff - timedelta(hours=12)).isoformat()
    defeater = Defeater(defeater_kind="time_decay", window="P3D")
    decision = _decision(
        decision_id="d1",
        entity_id="eq_aapl",
        command=_buy_to_open(defeaters=[defeater]),
        pit_state={"lookahead_risk": "low", "max_observation_available_at": recent},
        cutoff_timestamp=cutoff,
    )
    assert evaluate_defeaters_for_decision(decision) == []


def test_pit_unsafe_defeater_triggers_when_risk_elevated() -> None:
    defeater = Defeater(defeater_kind="pit_unsafe")
    decision = _decision(
        decision_id="d1",
        entity_id="eq_aapl",
        command=_buy_to_open(defeaters=[defeater]),
        pit_state={"lookahead_risk": "high"},
    )
    triggered = evaluate_defeaters_for_decision(decision)
    assert len(triggered) == 1
    assert triggered[0].defeater_kind == "pit_unsafe"


def test_rights_blocked_defeater_triggers_when_export_disallowed() -> None:
    defeater = Defeater(defeater_kind="rights_blocked")
    decision = _decision(
        decision_id="d1",
        entity_id="eq_aapl",
        command=_buy_to_open(defeaters=[defeater]),
        source_rights_state={"export_allowed": False},
    )
    triggered = evaluate_defeaters_for_decision(decision)
    assert len(triggered) == 1


# ---- Attack graph --------------------------------------------------------


def test_attack_graph_has_block_action_edge_against_position_command() -> None:
    block = _decision(decision_id="block", entity_id="eq_aapl", command=_block_action())
    buy = _decision(decision_id="buy", entity_id="eq_aapl", command=_buy_to_open())
    edges = build_attack_graph([block, buy])
    block_edges = [e for e in edges if e.attacker_decision_id == "block"]
    assert any(e.target_decision_id == "buy" for e in block_edges)
    # And no self-attack on block.
    self_attack = [
        e for e in edges if e.attacker_decision_id == "block" and e.target_decision_id == "block"
    ]
    assert self_attack == []


def test_attack_graph_per_target_only() -> None:
    """Conflict edges are scoped per target — a BLOCK_ACTION on AAPL does
    not reach a BUY_TO_OPEN on MSFT."""
    block = _decision(decision_id="block", entity_id="eq_aapl", command=_block_action("eq_aapl"))
    buy = _decision(decision_id="buy", entity_id="eq_msft", command=_buy_to_open(entity_id="eq_msft"))
    edges = build_attack_graph([block, buy])
    assert all(e.target_decision_id != "buy" for e in edges)


# ---- Grounded extension --------------------------------------------------


def test_grounded_extension_block_action_defeats_buy() -> None:
    block = _decision(decision_id="block", entity_id="eq_aapl", command=_block_action())
    buy = _decision(decision_id="buy", entity_id="eq_aapl", command=_buy_to_open())
    result = apply_argumentation([block, buy])
    by_id = {d.decision_id: d for d in result}
    assert by_id["block"].argumentation_status == "accepted"
    assert by_id["buy"].argumentation_status == "rejected"
    assert by_id["buy"].command is not None
    assert by_id["buy"].command.argumentation_status == "rejected"
    assert "block" in (by_id["buy"].argumentation_reason or "").lower()


def test_grounded_extension_preference_breaks_mutual_attack_avoid_vs_buy() -> None:
    """AVOID and BUY_TO_OPEN are mutually attacking via the conflict
    registry. The AVOID has higher (confidence × priority) than the BUY,
    so AVOID's attack succeeds and BUY's reverse attack is dropped."""
    avoid = _decision(
        decision_id="avoid",
        entity_id="eq_aapl",
        command=_avoid(confidence=0.9, priority=70),
    )
    buy = _decision(
        decision_id="buy",
        entity_id="eq_aapl",
        command=_buy_to_open(confidence=0.6, priority=50),
    )
    result = apply_argumentation([avoid, buy])
    by_id = {d.decision_id: d for d in result}
    assert by_id["avoid"].argumentation_status == "accepted"
    assert by_id["buy"].argumentation_status == "rejected"


def test_grounded_extension_one_way_attack_unaffected_by_preference() -> None:
    """The shipped conflict registry edges are one-way (AVOID → BUY_TO_OPEN
    has no reverse). Preference resolution only applies to mutual attacks,
    so a one-way attack from a lower-priority AVOID still rejects the
    higher-priority BUY. Equal-preference symmetric attacks are exercised
    directly by `test_apply_preferences_drops_lower_preference_reverse_edge`."""
    avoid = _decision(
        decision_id="avoid",
        entity_id="eq_aapl",
        command=_avoid(confidence=0.5, priority=40),
    )
    buy = _decision(
        decision_id="buy",
        entity_id="eq_aapl",
        command=_buy_to_open(confidence=0.9, priority=80),
    )
    result = apply_argumentation([avoid, buy])
    by_id = {d.decision_id: d for d in result}
    # The AVOID attack against BUY is the only edge; AVOID is unattacked.
    assert by_id["avoid"].argumentation_status == "accepted"
    assert by_id["buy"].argumentation_status == "rejected"


def test_grounded_extension_evidence_absent_self_defeats() -> None:
    """A command whose own defeater triggers is rejected even with no
    external attacker."""
    defeater = Defeater(
        defeater_kind="evidence_absent",
        required_evidence_keys=["rsi_14d", "volume_spike"],
    )
    buy = _decision(
        decision_id="buy",
        entity_id="eq_aapl",
        command=_buy_to_open(defeaters=[defeater]),
        trigger_observation_ids=["obs-rsi"],
    )
    result = apply_argumentation([buy])
    assert result[0].argumentation_status == "rejected"
    assert "evidence_absent" in (result[0].argumentation_reason or "")


def test_grounded_extension_unattacked_command_accepted() -> None:
    """No attackers and no triggered defeaters → accepted."""
    buy = _decision(decision_id="buy", entity_id="eq_aapl", command=_buy_to_open())
    result = apply_argumentation([buy])
    assert result[0].argumentation_status == "accepted"


def test_grounded_extension_legacy_decision_without_command_is_accepted() -> None:
    """A pre-Phase-27 DecisionFrame (command=None) is not part of the
    attack graph — defaults to accepted with no rationale."""
    decision = _decision(decision_id="legacy", entity_id="eq_aapl", command=None)
    result = apply_argumentation([decision])
    assert result[0].argumentation_status == "accepted"


# ---- Preference helper ---------------------------------------------------


def test_apply_preferences_drops_lower_preference_reverse_edge() -> None:
    """Setup: AVOID (higher pref) ⇄ BUY (lower pref). After preference
    resolution only AVOID→BUY survives."""
    from viza.argumentation import AttackEdge

    avoid = _decision(
        decision_id="avoid",
        entity_id="eq_aapl",
        command=_avoid(confidence=0.9, priority=70),
    )
    buy = _decision(
        decision_id="buy",
        entity_id="eq_aapl",
        command=_buy_to_open(confidence=0.6, priority=50),
    )
    raw_edges = [
        AttackEdge(
            attacker_decision_id="avoid",
            target_decision_id="buy",
            rationale="avoid→buy",
            edge_kind="preference_resolved",
        ),
        AttackEdge(
            attacker_decision_id="buy",
            target_decision_id="avoid",
            rationale="buy→avoid",
            edge_kind="preference_resolved",
        ),
    ]
    resolved = apply_preferences([avoid, buy], raw_edges)
    pairs = {(e.attacker_decision_id, e.target_decision_id) for e in resolved}
    assert ("avoid", "buy") in pairs
    assert ("buy", "avoid") not in pairs

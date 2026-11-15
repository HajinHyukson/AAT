"""Phase-27 unit tests: RadarItem adapters and assemble_output_radar."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from viza.commands import (
    AttentionAxes,
    CommandTarget,
    InvestmentCommandPayload,
    PositionAxes,
    SizingExpression,
    SystemAxes,
)
from viza.decisions import DecisionAudit, DecisionFrame
from viza.execution import RadarRow
from viza.radar import (
    DecisionRadarFilters,
    OutputRadarConfig,
    assemble_output_radar,
    decision_frame_to_radar_item,
    parse_output_radar_config,
    ranking_result_to_radar_item,
)


# ---- Helpers -------------------------------------------------------------


def _buy_to_open_command(entity_id: str = "eq_aapl") -> InvestmentCommandPayload:
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
        command_confidence=0.85,
        command_priority=70,
    )


def _block_action_command(entity_id: str = "eq_aapl") -> InvestmentCommandPayload:
    return InvestmentCommandPayload(
        command_iri="viza:cmd/block_action",
        command_pref_label="BLOCK_ACTION",
        kind="SystemCommand",
        target=CommandTarget(entity_id=entity_id),
        system_axes=SystemAxes(veto_kind="EMIT_BLOCKED"),
        command_confidence=1.0,
        command_priority=100,
    )


def _watch_command(entity_id: str = "eq_msft") -> InvestmentCommandPayload:
    return InvestmentCommandPayload(
        command_iri="viza:cmd/watch_closely",
        command_pref_label="WATCH_CLOSELY",
        kind="AttentionCommand",
        target=CommandTarget(entity_id=entity_id),
        attention_axes=AttentionAxes(urgency="ELEVATED"),
        command_confidence=0.7,
        command_priority=40,
    )


def _decision(
    *,
    decision_id: str,
    entity_id: str,
    command: InvestmentCommandPayload | None,
    argumentation_status: str = "undecided",
) -> DecisionFrame:
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    return DecisionFrame(
        decision_id=decision_id,
        strategy_profile_id="test-profile",
        rule_id="r1",
        entity_id=entity_id,
        action_template="(test)",
        rule_text="r1: test rule",
        cutoff_timestamp=now,
        emitted_at=now,
        audit=DecisionAudit(
            graph_hash="g",
            profile_version="v",
            run_id="run-X",
            evidence_checksum="e",
        ),
        command=command,
        argumentation_status=argumentation_status,
    )


# ---- Adapters ------------------------------------------------------------


def test_ranking_row_adapts_to_ranking_result_item() -> None:
    row = RadarRow(ticker="AAPL", entity_id="eq_aapl", score=0.81, rank=1)
    item = ranking_result_to_radar_item(row)
    assert item.item_kind == "ranking_result"
    assert item.entity_id == "eq_aapl"
    assert item.radar_score == pytest.approx(0.81)
    assert item.render_component == "RankingCard"


def test_position_command_adapts_to_decision_command_item() -> None:
    decision = _decision(
        decision_id="d1", entity_id="eq_aapl", command=_buy_to_open_command()
    )
    item = decision_frame_to_radar_item(decision)
    assert item.item_kind == "decision_command"
    assert item.render_component == "DecisionCommandCard"
    assert item.command is not None
    assert item.command.command_iri == "viza:cmd/buy_to_open"
    assert item.display_group == "Investment Commands"


def test_system_command_adapts_to_blocked_command_item() -> None:
    decision = _decision(
        decision_id="d2", entity_id="eq_aapl", command=_block_action_command()
    )
    item = decision_frame_to_radar_item(decision)
    assert item.item_kind == "blocked_command"
    assert item.render_component == "BlockedCommandCard"
    assert item.display_group == "Blocked"
    assert item.priority == "high"


def test_attention_command_adapts_to_watch_command_item() -> None:
    decision = _decision(
        decision_id="d3", entity_id="eq_msft", command=_watch_command()
    )
    item = decision_frame_to_radar_item(decision)
    assert item.item_kind == "watch_command"
    assert item.render_component == "WatchCommandCard"
    assert item.display_group == "Watch / Attention"


# ---- Config parsing ------------------------------------------------------


def test_parse_output_radar_config_defaults_when_empty() -> None:
    config = parse_output_radar_config(None)
    assert config.mode == "mixed"
    assert config.hit_policy == "COLLECT"
    assert "ranking_results" in config.sources
    assert "decision_frames" in config.sources


def test_quota_then_score_requires_quotas() -> None:
    with pytest.raises(ValueError):
        OutputRadarConfig(hit_policy="QUOTA_THEN_SCORE")


# ---- Assembly ------------------------------------------------------------


def test_ranking_only_mode_drops_decisions() -> None:
    row = RadarRow(ticker="AAPL", entity_id="eq_aapl", score=0.81, rank=1)
    decision = _decision(
        decision_id="d1", entity_id="eq_aapl", command=_buy_to_open_command()
    )
    config = OutputRadarConfig(mode="ranking_only", sources=["ranking_results"])
    view = assemble_output_radar(
        config=config, ranking_rows=[row], decisions=[decision]
    )
    assert view.item_counts_by_kind.get("decision_command") is None
    assert view.item_counts_by_kind.get("ranking_result") == 1


def test_decisions_only_mode_drops_rankings() -> None:
    row = RadarRow(ticker="AAPL", entity_id="eq_aapl", score=0.81, rank=1)
    decision = _decision(
        decision_id="d1", entity_id="eq_aapl", command=_buy_to_open_command()
    )
    config = OutputRadarConfig(mode="decisions_only", sources=["decision_frames"])
    view = assemble_output_radar(
        config=config, ranking_rows=[row], decisions=[decision]
    )
    assert view.item_counts_by_kind.get("ranking_result") is None
    assert view.item_counts_by_kind.get("decision_command") == 1


def test_mixed_mode_carries_both_kinds() -> None:
    row = RadarRow(ticker="AAPL", entity_id="eq_aapl", score=0.81, rank=1)
    decision = _decision(
        decision_id="d1", entity_id="eq_msft", command=_buy_to_open_command("eq_msft")
    )
    config = OutputRadarConfig(mode="mixed")
    view = assemble_output_radar(
        config=config, ranking_rows=[row], decisions=[decision]
    )
    assert view.item_counts_by_kind.get("ranking_result") == 1
    assert view.item_counts_by_kind.get("decision_command") == 1


def test_rejected_decisions_hidden_by_default() -> None:
    decision = _decision(
        decision_id="d1",
        entity_id="eq_aapl",
        command=_buy_to_open_command(),
        argumentation_status="rejected",
    )
    config = OutputRadarConfig(mode="decisions_only", sources=["decision_frames"])
    view = assemble_output_radar(config=config, decisions=[decision])
    assert view.items == []


def test_rejected_decisions_visible_when_include_rejected_true() -> None:
    decision = _decision(
        decision_id="d1",
        entity_id="eq_aapl",
        command=_buy_to_open_command(),
        argumentation_status="rejected",
    )
    config = OutputRadarConfig(
        mode="decisions_only",
        sources=["decision_frames"],
        decision_filters=DecisionRadarFilters(include_rejected=True),
    )
    view = assemble_output_radar(config=config, decisions=[decision])
    assert len(view.items) == 1
    assert view.items[0].argumentation_status == "rejected"


def test_quota_then_score_respects_per_kind_budget() -> None:
    rows = [
        RadarRow(ticker=f"T{i}", entity_id=f"eq_{i}", score=0.9 - i * 0.01, rank=i + 1)
        for i in range(5)
    ]
    decisions = [
        _decision(
            decision_id=f"d{i}",
            entity_id=f"eq_d{i}",
            command=_buy_to_open_command(entity_id=f"eq_d{i}"),
        )
        for i in range(5)
    ]
    config = OutputRadarConfig(
        mode="mixed",
        hit_policy="QUOTA_THEN_SCORE",
        quotas={"ranking_result": 2, "decision_command": 3},
        max_items=10,
    )
    view = assemble_output_radar(
        config=config, ranking_rows=rows, decisions=decisions
    )
    assert view.item_counts_by_kind.get("ranking_result") == 2
    assert view.item_counts_by_kind.get("decision_command") == 3
    assert len(view.items) == 5


def test_max_items_truncates() -> None:
    rows = [
        RadarRow(ticker=f"T{i}", entity_id=f"eq_{i}", score=0.9 - i * 0.01, rank=i + 1)
        for i in range(10)
    ]
    config = OutputRadarConfig(mode="ranking_only", sources=["ranking_results"], max_items=3)
    view = assemble_output_radar(config=config, ranking_rows=rows, decisions=[])
    assert len(view.items) == 3


def test_block_command_surfaced_to_blocked_group() -> None:
    decision = _decision(
        decision_id="d1", entity_id="eq_aapl", command=_block_action_command()
    )
    config = OutputRadarConfig(mode="decisions_only", sources=["decision_frames"])
    view = assemble_output_radar(config=config, decisions=[decision])
    assert view.item_counts_by_group.get("Blocked") == 1

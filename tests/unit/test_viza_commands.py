"""Phase-27 unit tests: command taxonomy, payload validation, FEEL-Lite."""

from __future__ import annotations

import pytest

from viza.commands import (
    AttentionAxes,
    CommandConflictRegistry,
    CommandTarget,
    CommandTaxonomy,
    Defeater,
    InvestmentCommandPayload,
    PositionAxes,
    SizingExpression,
    SystemAxes,
    build_command_from_concept,
    get_command_conflicts,
    get_command_taxonomy,
    load_command_conflicts,
    load_command_taxonomy,
    reset_command_caches,
)
from viza.feel_lite import FeelLiteError, evaluate


@pytest.fixture(autouse=True)
def _clear_caches():
    reset_command_caches()
    yield
    reset_command_caches()


def test_command_taxonomy_validates_with_mvp_commands() -> None:
    taxonomy = load_command_taxonomy()
    assert isinstance(taxonomy, CommandTaxonomy)
    iris = {concept.iri for concept in taxonomy.commands}
    expected = {
        "viza:cmd/buy_to_open",
        "viza:cmd/add_long",
        "viza:cmd/hold",
        "viza:cmd/trim_long",
        "viza:cmd/sell_to_close",
        "viza:cmd/watch_closely",
        "viza:cmd/avoid",
        "viza:cmd/block_action",
        "viza:cmd/block_export",
    }
    assert expected.issubset(iris)


def test_command_conflicts_includes_block_action_wildcard() -> None:
    registry = load_command_conflicts()
    assert isinstance(registry, CommandConflictRegistry)
    has_wildcard = any(
        edge.left_command_iri == "viza:cmd/block_action"
        and edge.right_command_iri == "*"
        and edge.relation == "defeats_unconditionally"
        for edge in registry.conflicts
    )
    assert has_wildcard


def test_block_action_defeats_a_specific_command_via_registry() -> None:
    registry = get_command_conflicts()
    defeaters_of_buy = registry.unconditional_defeaters_of("viza:cmd/buy_to_open")
    iris = {edge.left_command_iri for edge in defeaters_of_buy}
    assert "viza:cmd/block_action" in iris


def test_build_position_command_with_target_weight_sizing() -> None:
    taxonomy = get_command_taxonomy()
    concept = taxonomy.require("viza:cmd/buy_to_open")
    command = build_command_from_concept(
        concept=concept,
        target=CommandTarget(entity_id="eq_aapl", instrument_id="sec_aapl_common"),
        sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        resolved_sizing_value=0.02,
        command_confidence=0.8,
    )
    assert command.kind == "PositionCommand"
    assert command.position_axes is not None
    assert command.position_axes.direction == "BUY"
    assert command.position_axes.position_change == "OPEN"
    assert command.position_axes.side == "LONG"
    assert command.sizing is not None
    assert command.resolved_sizing_value == 0.02
    assert command.execution_routing == "none"


def test_position_command_rejects_attention_axes() -> None:
    with pytest.raises(ValueError):
        InvestmentCommandPayload(
            command_iri="viza:cmd/buy_to_open",
            command_pref_label="BUY_TO_OPEN",
            kind="PositionCommand",
            target=CommandTarget(entity_id="eq_aapl"),
            position_axes=PositionAxes(
                direction="BUY",
                position_change="OPEN",
                side="LONG",
                default_sizing_method="TARGET_WEIGHT",
            ),
            attention_axes=AttentionAxes(urgency="ELEVATED"),
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        )


def test_position_command_requires_sizing_when_explicit_method() -> None:
    with pytest.raises(ValueError):
        InvestmentCommandPayload(
            command_iri="viza:cmd/buy_to_open",
            command_pref_label="BUY_TO_OPEN",
            kind="PositionCommand",
            target=CommandTarget(entity_id="eq_aapl"),
            position_axes=PositionAxes(
                direction="BUY",
                position_change="OPEN",
                side="LONG",
                default_sizing_method="TARGET_WEIGHT",
            ),
        )


def test_attention_command_cannot_carry_sizing() -> None:
    with pytest.raises(ValueError):
        InvestmentCommandPayload(
            command_iri="viza:cmd/watch_closely",
            command_pref_label="WATCH_CLOSELY",
            kind="AttentionCommand",
            target=CommandTarget(entity_id="eq_aapl"),
            attention_axes=AttentionAxes(urgency="ELEVATED"),
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        )


def test_system_command_requires_veto_kind() -> None:
    with pytest.raises(ValueError):
        InvestmentCommandPayload(
            command_iri="viza:cmd/block_action",
            command_pref_label="BLOCK_ACTION",
            kind="SystemCommand",
            target=CommandTarget(entity_id="eq_aapl"),
        )

    # Valid construction succeeds.
    command = InvestmentCommandPayload(
        command_iri="viza:cmd/block_action",
        command_pref_label="BLOCK_ACTION",
        kind="SystemCommand",
        target=CommandTarget(entity_id="eq_aapl"),
        system_axes=SystemAxes(veto_kind="EMIT_BLOCKED"),
    )
    assert command.execution_routing == "none"


def test_defeater_can_be_attached() -> None:
    defeater = Defeater(
        defeater_kind="evidence_absent",
        required_evidence_keys=["sec_filing_novelty"],
        rationale="No SEC filing in PIT window",
    )
    assert defeater.defeater_kind == "evidence_absent"


# ---- FEEL-Lite -----------------------------------------------------------


def test_feel_lite_evaluates_literal() -> None:
    assert evaluate("0.02", {}) == 0.02
    assert evaluate("42", {}) == 42


def test_feel_lite_evaluates_min_max() -> None:
    context = {"conviction_score": 30}
    assert evaluate("min(0.02, conviction_score / 50)", context) == pytest.approx(0.02)
    assert evaluate(
        "max(0.01, conviction_score / 50)", {"conviction_score": 25}
    ) == pytest.approx(0.5)


def test_feel_lite_evaluates_dotted_path() -> None:
    context = {"technical": {"rsi_14": 27}}
    assert evaluate("technical.rsi_14", context) == 27
    assert evaluate("technical.rsi_14 < 30", context) is True


def test_feel_lite_clamp_and_abs() -> None:
    assert evaluate("clamp(0.07, 0.01, 0.05)", {}) == 0.05
    assert evaluate("abs(-3.14)", {}) == pytest.approx(3.14)


def test_feel_lite_rejects_unknown_identifier() -> None:
    with pytest.raises(FeelLiteError):
        evaluate("undefined_score", {})


def test_feel_lite_rejects_unsafe_call() -> None:
    with pytest.raises(FeelLiteError):
        evaluate("__import__('os')", {})


def test_feel_lite_rejects_division_by_zero() -> None:
    with pytest.raises(FeelLiteError):
        evaluate("1 / 0", {})


def test_feel_lite_rejects_attribute_call() -> None:
    with pytest.raises(FeelLiteError):
        evaluate("obj.method(1)", {"obj": object()})

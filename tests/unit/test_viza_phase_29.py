"""Phase-29 unit tests: FEEL-Lite S-FEEL extensions, DecisionTrigger
feel_expression, DecisionTable, BKM registry, DMN XML export.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import pytest

from viza.commands import CommandMapping, SizingExpression
from viza.config_paths import resolve_config_path
from viza.decision_tables import (
    DecisionTable,
    DecisionTableRule,
    action_threshold_table_from_dict,
)
from viza.decisions import compile_decisions
from viza.dmn_export import export_strategy_profile_as_dmn, trigger_to_feel
from viza.feel_lite import FeelLiteError, evaluate
from viza.observations import ObservationInput, VizaObservation, observation_from_input
from viza.strategy_profiles import (
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    VizaStrategyProfile,
)


# ---- FEEL-Lite S-FEEL extensions ----------------------------------------


def test_feel_lite_supports_list_literals() -> None:
    assert evaluate("[1, 2, 3]", {}) == [1, 2, 3]


def test_feel_lite_supports_in_operator() -> None:
    assert evaluate("3 in [1, 2, 3]", {}) is True
    assert evaluate("4 in [1, 2, 3]", {}) is False


def test_feel_lite_supports_not_in_operator() -> None:
    assert evaluate("4 not in [1, 2, 3]", {}) is True


def test_feel_lite_supports_days_between_two_dates() -> None:
    # 5 calendar days exactly.
    expression = 'days(date("2026-05-16"), date("2026-05-21"))'
    assert evaluate(expression, {}) == pytest.approx(5.0)


def test_feel_lite_supports_date_function_on_bound_identifier() -> None:
    context = {"observed": "2026-05-16T00:00:00Z", "cutoff": "2026-05-21T00:00:00Z"}
    expression = "days(date(observed), date(cutoff)) < 5"
    assert evaluate(expression, context) is False
    context_close = {"observed": "2026-05-19T00:00:00Z", "cutoff": "2026-05-21T00:00:00Z"}
    assert evaluate("days(date(observed), date(cutoff)) < 5", context_close) is True


def test_feel_lite_duration_parses_iso() -> None:
    delta = evaluate('duration("P30D")', {})
    assert delta == timedelta(days=30)
    delta = evaluate('duration("PT5H30M")', {})
    assert delta == timedelta(hours=5, minutes=30)


def test_feel_lite_year_month_duration_rejected() -> None:
    with pytest.raises(FeelLiteError):
        evaluate('duration("P1Y")', {})


def test_feel_lite_in_rejects_non_collection() -> None:
    with pytest.raises(FeelLiteError):
        evaluate("3 in 5", {})


# ---- DecisionTrigger.feel_expression integration ------------------------


def _observation(
    *,
    entity_id: str = "eq_aapl",
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


def test_feel_expression_trigger_fires_on_compound_condition() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_volume_compound",
        label="Oversold + volume confirmation",
        trigger=DecisionTrigger(
            feel_expression="rsi_14d <= 30 and volume_spike > 2.0",
        ),
        action_template="surface candidate.",
    )
    profile = VizaStrategyProfile(
        strategy_profile_id="test-profile",
        display_name="test",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        created_at=cutoff,
        updated_at=cutoff,
    )
    observations = [
        _observation(attribute_key="rsi_14d", value=27.0, moment=cutoff),
        _observation(attribute_key="volume_spike", value=2.6, moment=cutoff),
    ]

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="r-1",
        graph_hash="g",
        profile_version="v",
    )
    assert len(decisions) == 1
    # Both attribute keys should be in the triggering observation set.
    assert len(decisions[0].trigger_observation_ids) == 2


def test_feel_expression_trigger_does_not_fire_when_volume_low() -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_volume_compound",
        label="Oversold + volume confirmation",
        trigger=DecisionTrigger(
            feel_expression="rsi_14d <= 30 and volume_spike > 2.0",
        ),
        action_template="surface candidate.",
    )
    profile = VizaStrategyProfile(
        strategy_profile_id="test-profile",
        display_name="test",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        created_at=cutoff,
        updated_at=cutoff,
    )
    observations = [
        _observation(attribute_key="rsi_14d", value=27.0, moment=cutoff),
        _observation(attribute_key="volume_spike", value=1.0, moment=cutoff),
    ]
    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff,
        run_id="r-2",
        graph_hash="g",
        profile_version="v",
    )
    assert decisions == []


def test_referenced_attribute_keys_combines_structured_and_feel() -> None:
    trigger = DecisionTrigger(
        observation_predicates=[
            ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
        ],
        feel_expression="rsi_14d <= 30 and volume_spike > 2.0",
    )
    keys = trigger.referenced_attribute_keys()
    assert "rsi_14d" in keys
    assert "volume_spike" in keys


# ---- DecisionTable ------------------------------------------------------


def test_action_threshold_table_picks_first_matching_rule() -> None:
    table = action_threshold_table_from_dict(
        {"alert_threshold": 0.75, "research_threshold": 0.65, "watchlist_threshold": 0.55},
        input_expression="score",
    )
    # FIRST after descending-threshold sort means the highest crossed
    # threshold wins.
    result = table.evaluate({"score": 0.66})
    assert result.outputs["action"] == "research"
    assert result.matched_rule_ids == ["research_threshold"]

    result = table.evaluate({"score": 0.80})
    assert result.outputs["action"] == "alert"

    result = table.evaluate({"score": 0.20})
    assert result.matched_rule_ids == []
    assert result.outputs == {}


def test_decision_table_collect_hit_policy() -> None:
    table = DecisionTable(
        name="multi_alert",
        hit_policy="COLLECT",
        inputs=["score"],
        outputs=["channel"],
        rules=[
            DecisionTableRule(rule_id="email", input_cells=["score >= 0.5"], output_cells={"channel": "email"}),
            DecisionTableRule(rule_id="dashboard", input_cells=["score >= 0.7"], output_cells={"channel": "dashboard"}),
            DecisionTableRule(rule_id="alert", input_cells=["score >= 0.9"], output_cells={"channel": "alert"}),
        ],
    )
    result = table.evaluate({"score": 0.95})
    channels = [row["channel"] for row in result.collected_outputs]
    assert channels == ["email", "dashboard", "alert"]


def test_decision_table_rejects_mismatched_input_cell_count() -> None:
    with pytest.raises(ValueError):
        DecisionTable(
            name="bad",
            inputs=["a", "b"],
            outputs=["x"],
            rules=[DecisionTableRule(rule_id="r1", input_cells=["a >= 1"], output_cells={"x": "y"})],
        )


def test_decision_table_unique_hit_policy_raises_on_two_matches() -> None:
    table = DecisionTable(
        name="unique_table",
        hit_policy="UNIQUE",
        inputs=["score"],
        outputs=["action"],
        rules=[
            DecisionTableRule(rule_id="r1", input_cells=["score >= 0.5"], output_cells={"action": "a"}),
            DecisionTableRule(rule_id="r2", input_cells=["score >= 0.6"], output_cells={"action": "b"}),
        ],
    )
    with pytest.raises(ValueError):
        table.evaluate({"score": 0.8})


# ---- BKM registry -------------------------------------------------------


def test_bkm_registry_loads_with_expected_indicators() -> None:
    payload = json.loads(resolve_config_path("viza_bkm_registry.json").read_text("utf-8"))
    assert payload["schema"] == "viza.bkm_registry.v1"
    bkm_names = {entry["name"] for entry in payload["business_knowledge_models"]}
    assert {"rsi_14", "volume_spike", "momentum_21", "moving_average_trend"}.issubset(bkm_names)


# ---- DMN XML export -----------------------------------------------------


def _example_profile() -> VizaStrategyProfile:
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_volume_compound",
        label="Oversold + volume confirmation",
        trigger=DecisionTrigger(
            feel_expression="rsi_14d <= 30 and volume_spike > 2.0",
        ),
        action_template="Surface candidate for review.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    table = action_threshold_table_from_dict(
        {"alert_threshold": 0.75, "watchlist_threshold": 0.55},
        input_expression="score",
    )
    return VizaStrategyProfile(
        strategy_profile_id="phase-29-example",
        display_name="Phase 29 example profile",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        action_thresholds_table=table.model_dump(mode="json", by_alias=True),
        created_at=now,
        updated_at=now,
    )


def test_dmn_export_includes_decision_input_and_bkm_elements() -> None:
    xml_text = export_strategy_profile_as_dmn(_example_profile())
    assert xml_text.startswith("<?xml")
    root = ET.fromstring(xml_text)
    ns = {"dmn": "https://www.omg.org/spec/DMN/20211108/MODEL/"}
    decisions = root.findall("dmn:decision", ns)
    input_datas = root.findall("dmn:inputData", ns)
    bkms = root.findall("dmn:businessKnowledgeModel", ns)
    assert len(decisions) >= 1
    assert {elem.get("name") for elem in input_datas} >= {"rsi_14d", "volume_spike"}
    # BKM registry seeds at least 5 indicators.
    assert len(bkms) >= 5


def test_trigger_to_feel_translates_double_equals() -> None:
    trigger = DecisionTrigger(feel_expression='status == "open" and score >= 0.5')
    feel = trigger_to_feel(trigger)
    assert feel.count("==") == 0
    assert "status =" in feel
    assert "true" not in feel or "false" not in feel  # no spurious booleans inserted


def test_trigger_to_feel_renders_structured_predicate_as_and_chain() -> None:
    trigger = DecisionTrigger(
        observation_predicates=[
            ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0),
            ObservationPredicate(attribute_key="volume_spike", operator="gt", threshold=2.0),
        ]
    )
    feel = trigger_to_feel(trigger)
    assert "rsi_14d <= 30" in feel
    assert "volume_spike > 2" in feel
    assert " and " in feel


def test_dmn_export_carries_command_mapping_in_extension() -> None:
    xml_text = export_strategy_profile_as_dmn(_example_profile())
    assert "commandMapping" in xml_text
    assert "viza:cmd/buy_to_open" in xml_text
    # The sizing block rides inside the command-mapping extension.
    assert "TARGET_WEIGHT" in xml_text


def test_dmn_export_emits_action_threshold_decision_table() -> None:
    xml_text = export_strategy_profile_as_dmn(_example_profile())
    root = ET.fromstring(xml_text)
    ns = {"dmn": "https://www.omg.org/spec/DMN/20211108/MODEL/"}
    decision_tables = root.findall(".//dmn:decisionTable", ns)
    assert len(decision_tables) == 1
    assert decision_tables[0].get("hitPolicy") == "FIRST"

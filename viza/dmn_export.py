"""DMN 1.5 XML export for VIZA strategy profiles.

Phase 29 of `docs/viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`.
Emits a single-file DMN definitions document containing:

* One `<dmn:decision>` per DecisionRule. Its expression body is the rule's
  trigger as FEEL (translated from FEEL-Lite syntax).
* One `<dmn:inputData>` per referenced attribute key.
* One `<dmn:businessKnowledgeModel>` per BKM declared in
  `config/viza_bkm_registry.json`.
* `<dmn:decisionTable>` for the strategy profile's `action_thresholds_table`
  when present.

The export is *lossy by design* in two places: VIZA-specific metadata
(strategy_profile_id, command_mapping, cooldown_policy, live-mode opt-in) is
preserved only inside `<dmn:extensionElements>` blocks so external DMN
engines that ignore extensions still load the rules. Round-trip back into
VIZA is supported by `viza.dmn_import` (left as Phase-30/31 follow-up: this
module is export-only for the MVP).
"""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from viza.commands import CommandMapping
from viza.decision_tables import DecisionTable, DecisionTableRule
from viza.strategy_profiles import DecisionRule, DecisionTrigger, VizaStrategyProfile


DMN_NS = "https://www.omg.org/spec/DMN/20211108/MODEL/"
DMNDI_NS = "https://www.omg.org/spec/DMN/20211108/DMNDI/"
DC_NS = "http://www.omg.org/spec/DMN/20180521/DC/"
VIZA_EXT_NS = "http://viza.local/dmn/extensions/v1"

ET.register_namespace("dmn", DMN_NS)
ET.register_namespace("dmndi", DMNDI_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("viza", VIZA_EXT_NS)


def export_strategy_profile_as_dmn(profile: VizaStrategyProfile) -> str:
    """Return a DMN 1.5 XML document representing the strategy profile."""
    root = ET.Element(
        f"{{{DMN_NS}}}definitions",
        attrib={
            "id": f"viza-profile-{profile.strategy_profile_id}",
            "name": profile.display_name,
            "namespace": f"http://viza.local/profiles/{profile.strategy_profile_id}",
            "exporter": "viza",
            "exporterVersion": "phase-29",
        },
    )

    referenced_attributes = _collect_referenced_attributes(profile)
    for attribute_key in sorted(referenced_attributes):
        _append_input_data(root, attribute_key)

    _append_bkm_stubs(root)

    for rule in profile.decision_rules:
        _append_decision(root, profile=profile, rule=rule)

    if profile.action_thresholds_table:
        _append_action_threshold_table(root, profile)

    return _serialize(root)


# ---- Element builders ----------------------------------------------------


def _append_input_data(root: ET.Element, attribute_key: str) -> None:
    input_data = ET.SubElement(
        root,
        f"{{{DMN_NS}}}inputData",
        attrib={"id": f"input-{attribute_key}", "name": attribute_key},
    )
    type_ref = ET.SubElement(input_data, f"{{{DMN_NS}}}variable")
    type_ref.set("id", f"variable-{attribute_key}")
    type_ref.set("name", attribute_key)
    type_ref.set("typeRef", "number")


def _append_bkm_stubs(root: ET.Element) -> None:
    """Emit one BKM stub per indicator in the registry. The function body is
    declared but left empty — the BKM points at its Python implementation
    via a VIZA extension element."""
    try:
        from viza.config_paths import resolve_config_path

        with resolve_config_path("viza_bkm_registry.json").open(
            "r", encoding="utf-8"
        ) as handle:
            payload = json.load(handle)
    except Exception:
        return
    for bkm in payload.get("business_knowledge_models", []):
        bkm_element = ET.SubElement(
            root,
            f"{{{DMN_NS}}}businessKnowledgeModel",
            attrib={"id": _safe_id(bkm["iri"]), "name": bkm["name"]},
        )
        variable = ET.SubElement(bkm_element, f"{{{DMN_NS}}}variable")
        variable.set("id", f"variable-{bkm['name']}")
        variable.set("name", bkm["name"])
        variable.set("typeRef", "number")
        encapsulated = ET.SubElement(
            bkm_element, f"{{{DMN_NS}}}encapsulatedLogic"
        )
        for parameter in bkm.get("inputs", []):
            formal = ET.SubElement(encapsulated, f"{{{DMN_NS}}}formalParameter")
            formal.set("id", f"param-{bkm['name']}-{parameter['name']}")
            formal.set("name", parameter["name"])
            formal.set("typeRef", parameter.get("type", "Any"))
        # The implementation pointer rides in an extension element so an
        # external engine that doesn't host the Python implementation still
        # loads the BKM but knows where to look.
        extensions = ET.SubElement(
            bkm_element, f"{{{DMN_NS}}}extensionElements"
        )
        impl = ET.SubElement(
            extensions, f"{{{VIZA_EXT_NS}}}implementationRef"
        )
        impl.text = bkm.get("implementation_ref", "")


def _append_decision(
    root: ET.Element,
    *,
    profile: VizaStrategyProfile,
    rule: DecisionRule,
) -> None:
    decision = ET.SubElement(
        root,
        f"{{{DMN_NS}}}decision",
        attrib={"id": f"decision-{rule.rule_id}", "name": rule.label},
    )

    variable = ET.SubElement(decision, f"{{{DMN_NS}}}variable")
    variable.set("id", f"variable-decision-{rule.rule_id}")
    variable.set("name", rule.rule_id)
    variable.set("typeRef", "boolean")

    for attribute_key in rule.trigger.referenced_attribute_keys():
        requirement = ET.SubElement(
            decision, f"{{{DMN_NS}}}informationRequirement"
        )
        required = ET.SubElement(requirement, f"{{{DMN_NS}}}requiredInput")
        required.set("href", f"#input-{attribute_key}")

    feel_body = trigger_to_feel(rule.trigger)
    literal_expression = ET.SubElement(
        decision, f"{{{DMN_NS}}}literalExpression"
    )
    literal_expression.set("id", f"expr-{rule.rule_id}")
    text = ET.SubElement(literal_expression, f"{{{DMN_NS}}}text")
    text.text = feel_body

    # VIZA-specific metadata for round-trip / audit.
    extensions = ET.SubElement(decision, f"{{{DMN_NS}}}extensionElements")
    profile_ext = ET.SubElement(extensions, f"{{{VIZA_EXT_NS}}}profile")
    profile_ext.set("strategy_profile_id", profile.strategy_profile_id)
    if rule.effective_from is not None:
        profile_ext.set("effective_from", rule.effective_from.isoformat())
    if rule.command_mapping is not None:
        _append_command_mapping_ext(extensions, rule.command_mapping)
    if rule.action_template:
        action_ext = ET.SubElement(extensions, f"{{{VIZA_EXT_NS}}}actionTemplate")
        action_ext.text = rule.action_template


def _append_command_mapping_ext(
    extensions: ET.Element, mapping: CommandMapping
) -> None:
    command = ET.SubElement(extensions, f"{{{VIZA_EXT_NS}}}commandMapping")
    command.set("command_iri", mapping.command_iri)
    if mapping.else_command_iri:
        command.set("else_command_iri", mapping.else_command_iri)
    if mapping.sizing is not None:
        sizing = ET.SubElement(command, f"{{{VIZA_EXT_NS}}}sizing")
        sizing.set("method", mapping.sizing.method)
        sizing.set("units", mapping.sizing.units)
        sizing.text = mapping.sizing.expression


def _append_action_threshold_table(
    root: ET.Element, profile: VizaStrategyProfile
) -> None:
    table = DecisionTable.model_validate(profile.action_thresholds_table)
    decision = ET.SubElement(
        root,
        f"{{{DMN_NS}}}decision",
        attrib={
            "id": f"decision-action-threshold-{profile.strategy_profile_id}",
            "name": table.name,
        },
    )
    variable = ET.SubElement(decision, f"{{{DMN_NS}}}variable")
    variable.set("id", f"variable-action-threshold-{profile.strategy_profile_id}")
    variable.set("name", "action")
    variable.set("typeRef", "string")

    decision_table = ET.SubElement(decision, f"{{{DMN_NS}}}decisionTable")
    decision_table.set("id", f"dt-{profile.strategy_profile_id}")
    decision_table.set("hitPolicy", table.hit_policy)

    for index, input_expression in enumerate(table.inputs):
        input_elem = ET.SubElement(decision_table, f"{{{DMN_NS}}}input")
        input_elem.set("id", f"input-col-{index}")
        input_elem.set("label", input_expression)
        input_expr = ET.SubElement(input_elem, f"{{{DMN_NS}}}inputExpression")
        input_expr.set("id", f"input-expr-{index}")
        input_expr.set("typeRef", "number")
        text = ET.SubElement(input_expr, f"{{{DMN_NS}}}text")
        text.text = input_expression

    for output_name in table.outputs:
        output_elem = ET.SubElement(decision_table, f"{{{DMN_NS}}}output")
        output_elem.set("id", f"output-col-{output_name}")
        output_elem.set("name", output_name)
        output_elem.set("typeRef", "string")

    for rule in table.rules:
        rule_elem = ET.SubElement(decision_table, f"{{{DMN_NS}}}rule")
        rule_elem.set("id", f"dt-rule-{rule.rule_id}")
        for cell_index, cell in enumerate(rule.input_cells):
            entry = ET.SubElement(rule_elem, f"{{{DMN_NS}}}inputEntry")
            entry.set("id", f"dt-rule-{rule.rule_id}-in-{cell_index}")
            text = ET.SubElement(entry, f"{{{DMN_NS}}}text")
            text.text = _feel_translate(cell)
        for output_name in table.outputs:
            entry = ET.SubElement(rule_elem, f"{{{DMN_NS}}}outputEntry")
            entry.set("id", f"dt-rule-{rule.rule_id}-out-{output_name}")
            text = ET.SubElement(entry, f"{{{DMN_NS}}}text")
            value = rule.output_cells.get(output_name)
            text.text = _feel_literal(value)
        if rule.annotation:
            description = ET.SubElement(rule_elem, f"{{{DMN_NS}}}description")
            description.text = rule.annotation


# ---- FEEL-Lite → FEEL translation ----------------------------------------


def trigger_to_feel(trigger: DecisionTrigger) -> str:
    """Render a DecisionTrigger as a FEEL boolean expression."""
    if trigger.has_feel_expression():
        return _feel_translate(trigger.feel_expression)
    if not trigger.observation_predicates:
        return "true"
    parts: list[str] = []
    for predicate in trigger.observation_predicates:
        parts.append(_predicate_to_feel(predicate))
    return " and ".join(parts)


def _predicate_to_feel(predicate: "ObservationPredicate") -> str:  # type: ignore[name-defined]
    """Render a structured predicate as a FEEL atom."""
    op = predicate.operator
    key = predicate.attribute_key
    if op == "between":
        return (
            f"({key} >= {predicate.range_min} and {key} <= {predicate.range_max})"
        )
    symbol = {
        "lte": "<=",
        "gte": ">=",
        "lt": "<",
        "gt": ">",
        "eq": "=",
    }[op]
    return f"{key} {symbol} {predicate.threshold}"


def _feel_translate(expression: str | None) -> str:
    """Translate FEEL-Lite Python-flavored syntax into FEEL syntax.

    The transforms are intentionally textual and conservative:

    * `==` becomes `=` (FEEL equality is single `=`).
    * Identifier-level `and` / `or` / `not` are already FEEL-shaped, so they
      pass through.
    * `True` / `False` literals become `true` / `false`.
    * Other constructs (`min`, `max`, comparison operators) are valid in both
      syntaxes so they pass through unchanged.

    Round-trip back into FEEL-Lite is the job of `viza.dmn_import` (out of
    scope for the Phase-29 MVP).
    """
    if not expression:
        return "true"
    out = expression
    out = out.replace("==", "=")
    out = out.replace("True", "true").replace("False", "false")
    return out


def _feel_literal(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    return json.dumps(value, default=str)


# ---- Helpers -------------------------------------------------------------


def _collect_referenced_attributes(profile: VizaStrategyProfile) -> set[str]:
    attributes: set[str] = set()
    for rule in profile.decision_rules:
        attributes.update(rule.trigger.referenced_attribute_keys())
    return attributes


def _safe_id(iri: str) -> str:
    """DMN element IDs must be NCName. Map IRIs onto a flat hyphenated form."""
    return iri.replace(":", "_").replace("/", "-").replace(" ", "_")


def _serialize(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(root, encoding="unicode")
    )

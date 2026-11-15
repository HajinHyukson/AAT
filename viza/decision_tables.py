"""DMN-shaped decision tables for VIZA strategy profiles.

Phase 29 of `docs/viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`.
Lifts `action_thresholds: dict[str, float]` (the dict on every strategy
profile mapping `watchlist_threshold`/`research_threshold`/`alert_threshold`
to a numeric cutoff) from an ad-hoc dict to a real DMN decision table with a
declared hit policy. The dict form continues to work for legacy profiles; new
profiles can carry the typed table instead and gain:

* Explicit input columns (`score`, `confidence`, …).
* A declared hit policy (`FIRST` is the natural default for thresholded
  routing — first matching rule wins).
* Rule cells authored as FEEL-Lite expressions, evaluated by the same engine
  that runs decision rule triggers.

The evaluator is small (~80 lines) because it delegates every cell to
`viza.feel_lite`. DMN XML export (`viza/dmn_export.py`) consumes this typed
form to emit `<dmn:decisionTable>` elements.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.feel_lite import FeelLiteError, evaluate as feel_evaluate


HitPolicy = Literal["UNIQUE", "ANY", "PRIORITY", "FIRST", "COLLECT", "RULE_ORDER"]


class DecisionTableRule(BaseModel):
    """One row of a decision table.

    `input_cells` carries one FEEL-Lite expression per input column. Each cell
    is evaluated as a boolean predicate over the context augmented with the
    input value bound by the table; conventionally cells use `_` (or the
    input's declared name) to reference the input value, e.g. `_ >= 0.75` or
    `score >= 0.75`.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    input_cells: list[str] = Field(default_factory=list)
    output_cells: dict[str, Any] = Field(default_factory=dict)
    annotation: str | None = None


class DecisionTable(BaseModel):
    """A DMN-style decision table.

    Inputs are named expressions (typically just bare attribute keys, but any
    FEEL-Lite expression is accepted). The evaluator computes each input
    value once per evaluation, then walks the rules in order applying the
    declared hit policy.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.decision_table.v1", alias="schema")
    name: str
    hit_policy: HitPolicy = "FIRST"
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    rules: list[DecisionTableRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rules_against_inputs(self) -> "DecisionTable":
        for rule in self.rules:
            if len(rule.input_cells) != len(self.inputs):
                raise ValueError(
                    f"rule {rule.rule_id!r} has {len(rule.input_cells)} input "
                    f"cells but the table declares {len(self.inputs)} inputs"
                )
            extra_outputs = set(rule.output_cells.keys()) - set(self.outputs)
            if extra_outputs:
                raise ValueError(
                    f"rule {rule.rule_id!r} declares output columns not on "
                    f"the table: {sorted(extra_outputs)}"
                )
        return self

    def evaluate(self, context: dict[str, Any]) -> "DecisionTableResult":
        """Run the table against `context`. The evaluator never mutates
        `context`. The result records the matching rule(s) and the merged
        outputs per the hit policy."""
        input_values: dict[str, Any] = {}
        for index, expression in enumerate(self.inputs):
            try:
                input_values[expression] = feel_evaluate(expression, context)
            except FeelLiteError as exc:
                raise FeelLiteError(
                    f"input #{index} {expression!r} on table {self.name!r}: {exc}"
                ) from exc

        eval_context = {**context, **input_values, "_inputs": input_values}

        matches: list[DecisionTableRule] = []
        for rule in self.rules:
            satisfied = True
            for cell_index, cell in enumerate(rule.input_cells):
                cell_text = (cell or "").strip()
                if cell_text in {"-", "", "_"}:
                    # `-` is the DMN "don't care" marker; treat the cell as a
                    # trivial pass-through so single-axis thresholds need
                    # only carry one cell.
                    continue
                try:
                    result = feel_evaluate(cell_text, eval_context)
                except FeelLiteError as exc:
                    raise FeelLiteError(
                        f"rule {rule.rule_id!r} cell #{cell_index} "
                        f"{cell_text!r}: {exc}"
                    ) from exc
                if not isinstance(result, bool):
                    raise ValueError(
                        f"rule {rule.rule_id!r} cell #{cell_index} "
                        f"{cell_text!r} returned non-boolean: {result!r}"
                    )
                if not result:
                    satisfied = False
                    break
            if satisfied:
                matches.append(rule)
                if self.hit_policy == "FIRST":
                    break

        return _build_result(self.hit_policy, matches, self.outputs)


class DecisionTableResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hit_policy: HitPolicy
    matched_rule_ids: list[str] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    collected_outputs: list[dict[str, Any]] = Field(default_factory=list)


def _build_result(
    hit_policy: HitPolicy,
    matches: list[DecisionTableRule],
    declared_outputs: list[str],
) -> DecisionTableResult:
    matched_ids = [rule.rule_id for rule in matches]
    if not matches:
        return DecisionTableResult(hit_policy=hit_policy, matched_rule_ids=[])

    if hit_policy in ("FIRST", "UNIQUE", "PRIORITY", "ANY"):
        if hit_policy == "UNIQUE" and len(matches) > 1:
            raise ValueError(
                f"UNIQUE hit policy violated: {len(matches)} rules matched "
                f"({matched_ids})"
            )
        if hit_policy == "ANY" and len({tuple(sorted(rule.output_cells.items())) for rule in matches}) > 1:
            raise ValueError(
                "ANY hit policy violated: matched rules disagree on outputs"
            )
        chosen = matches[0]
        outputs = {column: chosen.output_cells.get(column) for column in declared_outputs}
        return DecisionTableResult(
            hit_policy=hit_policy,
            matched_rule_ids=matched_ids,
            outputs=outputs,
        )

    if hit_policy in ("COLLECT", "RULE_ORDER"):
        collected = [
            {column: rule.output_cells.get(column) for column in declared_outputs}
            for rule in matches
        ]
        return DecisionTableResult(
            hit_policy=hit_policy,
            matched_rule_ids=matched_ids,
            outputs={},
            collected_outputs=collected,
        )

    raise ValueError(f"unsupported hit policy: {hit_policy!r}")


def action_threshold_table_from_dict(
    action_thresholds: dict[str, float],
    *,
    name: str = "action_threshold_router",
    input_expression: str = "score",
) -> DecisionTable:
    """Build a DMN-shaped DecisionTable from a legacy `action_thresholds` dict.

    The legacy dict carries entries like
    `{"alert_threshold": 0.75, "research_threshold": 0.65, "watchlist_threshold": 0.55}`.
    The generated table fires the action whose threshold is the highest one
    still satisfied by the input — hence `FIRST` hit policy after sorting
    rules in descending threshold order.
    """
    ordered = sorted(
        action_thresholds.items(), key=lambda kv: kv[1], reverse=True
    )
    rules: list[DecisionTableRule] = []
    for action_key, threshold in ordered:
        rules.append(
            DecisionTableRule(
                rule_id=action_key,
                input_cells=[f"{input_expression} >= {threshold}"],
                output_cells={
                    "action": action_key.replace("_threshold", ""),
                    "threshold": threshold,
                },
                annotation=(
                    f"Surface the {action_key.replace('_threshold', '')} "
                    f"action when {input_expression} ≥ {threshold}."
                ),
            )
        )
    return DecisionTable(
        name=name,
        hit_policy="FIRST",
        inputs=[input_expression],
        outputs=["action", "threshold"],
        rules=rules,
    )

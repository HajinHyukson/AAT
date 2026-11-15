"""Package-redaction rules for VIZA decision-bearing exports.

Phase C of docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md. Mirrors the existing
viza/equity/text/package_redaction.py pattern. Three modes:

  white_box:
    * Full DecisionFrame payload (action_template, rule_text,
      trigger_observation_ids, audit chain, PIT/rights state).
    * Suitable for the user's own analyst view inside the VIZA app.

  output_only:
    * Per-decision payload included so a downstream consumer can see WHICH
      entities were flagged and WHAT action template the rule emitted.
    * rule_text REDACTED and trigger_observation_ids REDACTED so the
      receiver cannot reverse-engineer the rule's identity or trigger
      semantics from the export. trigger_observation_count is retained for
      shape-only audit.

  marketplace_draft:
    * Per-decision payload entirely stripped — no entity_ids, no
      action_templates, no trigger semantics.
    * Only schema/shape: decision_count, entity_count, rule_count,
      audit-chain summary, mode label, non-advice boundary.
    * Proves "this profile, on this data, emitted N decisions" without
      exposing the user's strategy IP.

Cross-mode rule: if any DecisionFrame's source_rights_state.export_allowed
is False, the export is BLOCKED regardless of mode. The PackageRedactionBlocked
exception carries the offending decision_id so the caller can route the user
to a rights remediation flow.
"""

from __future__ import annotations

from typing import Any, Literal

from viza.decisions import DecisionFrame


PackageMode = Literal["white_box", "output_only", "marketplace_draft"]


class PackageRedactionBlocked(RuntimeError):
    """Raised when redaction policy blocks the requested package mode."""

    def __init__(self, *, mode: str, reason: str) -> None:
        super().__init__(f"package_mode={mode} blocked: {reason}")
        self.mode = mode
        self.reason = reason


def redact_decisions_for_package(
    decisions: list[DecisionFrame],
    *,
    mode: PackageMode,
) -> dict[str, Any]:
    """Return a dict payload ready for inclusion in a .viza package preview.

    The function never mutates the originals; it returns a fresh dict with
    redacted fields and explicit absence markers. Caller serializes into the
    package manifest.
    """
    _enforce_export_rights(decisions, mode)

    base: dict[str, Any] = {
        "schema": "viza.decisions_redaction.v1",
        "package_mode": mode,
        "decision_count": len(decisions),
        "runtime_mode": "sandbox_replay",
        "non_advice_boundary": True,
        "redactions": [],
        "audit": _audit_summary(decisions),
    }

    if mode == "white_box":
        base["decisions"] = [decision.model_dump(mode="json") for decision in decisions]
        base["command_axis_counts"] = command_axis_counts(decisions)
        return base

    if mode == "output_only":
        base["decisions"] = [
            _output_only_decision_payload(decision) for decision in decisions
        ]
        base["command_axis_counts"] = command_axis_counts(decisions)
        base["redactions"].extend(
            [
                {"field": "rule_text", "reason": "output_only_hides_rule_identity"},
                {
                    "field": "trigger_observation_ids",
                    "reason": "output_only_hides_trigger_semantics",
                },
                {
                    "field": "command.sizing.expression",
                    "reason": "output_only_hides_sizing_formula",
                },
                {
                    "field": "command.resolved_sizing_value",
                    "reason": "output_only_hides_resolved_sizing",
                },
            ]
        )
        return base

    if mode == "marketplace_draft":
        base["decisions"] = []
        base["entity_count"] = len({decision.entity_id for decision in decisions})
        base["rule_count"] = len({decision.rule_id for decision in decisions})
        # Aggregate axis counts only — the count of decisions of each command
        # shape is shape-only and does not reveal the strategy parameters.
        base["command_axis_counts"] = command_axis_counts(decisions)
        base["redactions"].extend(
            [
                {
                    "field": "per_decision_payload",
                    "reason": "marketplace_redacts_per_decision_content",
                },
                {"field": "rule_text", "reason": "marketplace_redacts_rule_identity"},
                {
                    "field": "action_template",
                    "reason": "marketplace_redacts_action_template",
                },
                {
                    "field": "trigger_observation_ids",
                    "reason": "marketplace_redacts_trigger_semantics",
                },
                {
                    "field": "entity_ids",
                    "reason": "marketplace_redacts_per_entity_identity",
                },
                {
                    "field": "command.target.entity_id",
                    "reason": "marketplace_redacts_target_entity",
                },
                {
                    "field": "command.sizing",
                    "reason": "marketplace_redacts_sizing_entirely",
                },
            ]
        )
        return base

    raise ValueError(f"unknown package_mode={mode!r}")


def _enforce_export_rights(
    decisions: list[DecisionFrame], mode: PackageMode
) -> None:
    for decision in decisions:
        export_allowed = decision.source_rights_state.get("export_allowed")
        if export_allowed is False:
            raise PackageRedactionBlocked(
                mode=mode,
                reason=(
                    f"decision {decision.decision_id!r}: "
                    "source_rights_state.export_allowed=False — at least one "
                    "triggering observation forbids export under its source rights"
                ),
            )


def _output_only_decision_payload(decision: DecisionFrame) -> dict[str, Any]:
    payload = {
        "decision_id": decision.decision_id,
        "strategy_profile_id": decision.strategy_profile_id,
        "rule_id": decision.rule_id,
        "entity_id": decision.entity_id,
        "asset_id": decision.asset_id,
        "action_template": decision.action_template,
        "rule_text": "[redacted]",
        "trigger_observation_ids": [],
        "trigger_observation_count": len(decision.trigger_observation_ids),
        "pit_state": decision.pit_state,
        "source_rights_state": decision.source_rights_state,
        "cutoff_timestamp": decision.cutoff_timestamp.isoformat(),
        "mode": decision.mode,
        "emitted_at": decision.emitted_at.isoformat(),
        "audit": decision.audit.model_dump(mode="json"),
        "not_investment_advice": decision.not_investment_advice,
        "argumentation_status": decision.argumentation_status,
    }
    if decision.command is not None:
        # Phase-27 extension: emit a redacted shape of the command (the IRI,
        # axes, sizing method) while withholding the sizing expression and
        # resolved value (which encode the strategy's parameter choices).
        payload["command"] = _output_only_command_payload(decision.command)
    return payload


def _output_only_command_payload(command) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Output-only mode strips sizing internals but preserves the command
    shape so a downstream consumer can render what kind of command was
    emitted without learning the sizing formula."""
    return {
        "schema": command.schema_name,
        "command_iri": command.command_iri,
        "command_pref_label": command.command_pref_label,
        "kind": command.kind,
        "target": command.target.model_dump(mode="json"),
        "position_axes": (
            command.position_axes.model_dump(mode="json")
            if command.position_axes is not None
            else None
        ),
        "attention_axes": (
            command.attention_axes.model_dump(mode="json")
            if command.attention_axes is not None
            else None
        ),
        "system_axes": (
            command.system_axes.model_dump(mode="json")
            if command.system_axes is not None
            else None
        ),
        "sizing": (
            {"method": command.sizing.method, "expression": "[redacted]"}
            if command.sizing is not None
            else None
        ),
        "resolved_sizing_value": None,
        "command_confidence": command.command_confidence,
        "command_priority": command.command_priority,
        "argumentation_status": command.argumentation_status,
        "execution_routing": "none",
        "not_investment_advice": True,
    }


def command_axis_counts(decisions: list[DecisionFrame]) -> dict[str, Any]:
    """Aggregate decision counts by command axis without leaking any
    per-decision identity. Phase 27.

    Returns a dict shaped like:

        {
          "by_kind": {"PositionCommand": 4, "AttentionCommand": 1, "SystemCommand": 1},
          "by_direction": {"BUY": 2, "SELL": 2, "NONE": 1},
          "by_position_change": {"OPEN": 1, "INCREASE": 1, "REDUCE": 1, "CLOSE": 1, "MAINTAIN": 0},
          "by_side": {"LONG": 4, "SHORT": 0},
          "by_command_iri": {"viza:cmd/buy_to_open": 1, ...},
          "by_argumentation_status": {"accepted": 3, "rejected": 2, "undecided": 1}
        }
    """
    counts: dict[str, dict[str, int]] = {
        "by_kind": {},
        "by_direction": {},
        "by_position_change": {},
        "by_side": {},
        "by_command_iri": {},
        "by_argumentation_status": {},
    }
    for decision in decisions:
        counts["by_argumentation_status"][decision.argumentation_status] = (
            counts["by_argumentation_status"].get(decision.argumentation_status, 0) + 1
        )
        command = decision.command
        if command is None:
            continue
        counts["by_kind"][command.kind] = counts["by_kind"].get(command.kind, 0) + 1
        counts["by_command_iri"][command.command_iri] = (
            counts["by_command_iri"].get(command.command_iri, 0) + 1
        )
        if command.position_axes is not None:
            direction = command.position_axes.direction
            position_change = command.position_axes.position_change
            side = command.position_axes.side
            counts["by_direction"][direction] = (
                counts["by_direction"].get(direction, 0) + 1
            )
            counts["by_position_change"][position_change] = (
                counts["by_position_change"].get(position_change, 0) + 1
            )
            counts["by_side"][side] = counts["by_side"].get(side, 0) + 1
    return counts


def _audit_summary(decisions: list[DecisionFrame]) -> dict[str, Any]:
    if not decisions:
        return {"runs": [], "graph_hashes": [], "profile_versions": []}
    return {
        "runs": sorted({decision.audit.run_id for decision in decisions}),
        "graph_hashes": sorted({decision.audit.graph_hash for decision in decisions}),
        "profile_versions": sorted(
            {decision.audit.profile_version for decision in decisions}
        ),
    }

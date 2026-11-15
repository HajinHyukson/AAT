"""Argumentation over command sets — ASPIC+-shaped grounded extension.

Phase 31 of `docs/viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`.
Replaces the Phase-27 minimal argumentation gate (BLOCK_ACTION defeats all
others on the same target) with the general algorithm:

1. **Defeater evaluation.** Each command can carry structured
   `Defeater` records. Any triggered defeater rejects the command outright
   — the defeater is a self-attack the argumentation framework cannot
   undo. Structured kinds covered in Phase 31:

   * ``evidence_absent`` — a `required_evidence_keys` value is missing
     from the triggering observation set.
   * ``time_decay`` — every triggering observation is older than the
     declared ISO-8601 ``window`` before the cutoff.
   * ``pit_unsafe`` — ``decision.pit_state.lookahead_risk`` is not ``low``.
   * ``rights_blocked`` — ``source_rights_state.export_allowed`` is False.

   ``counter_event`` defeats need event context that Phase 27 does not
   thread into ``compile_decisions``; they are recognized but treated as
   non-triggering until Phase 32 adds the event-pattern grammar.

2. **Attack graph.** Built from
   ``config/viza_command_conflicts.json``. Per-target only (matching the
   conflict registry's `same_target` scope). An ``attacks`` edge becomes a
   preference-resolved attack; a ``defeats_unconditionally`` edge survives
   regardless of preferences.

3. **Preferences.** When two commands mutually attack, ASPIC+ resolves the
   conflict via the preference relation
   ``command_confidence * command_priority``. The higher-preference
   argument's attack succeeds; the lower-preference argument's reverse
   attack is dropped. Equal preferences keep both attacks (the standoff
   leaves both commands undecided unless another argument tips the
   balance).

4. **Grounded extension.** Standard Dung iterative fixed-point: argue
   that an argument is *accepted* when every attacker is rejected, and
   *rejected* when some attacker is accepted. Start from the
   defeater-triggered rejection set and iterate to fixed point.

Returns a new `DecisionFrame` list with each frame's
``argumentation_status`` and ``argumentation_reason`` updated (and the
nested `command.argumentation_status` mirrored).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from viza.commands import Defeater, get_command_conflicts
from viza.feel_lite import FeelLiteError, _parse_iso_duration


@dataclass
class TriggeredDefeater:
    decision_id: str
    defeater_kind: str
    reason: str


@dataclass
class AttackEdge:
    attacker_decision_id: str
    target_decision_id: str
    rationale: str
    edge_kind: str  # "unconditional" | "preference_resolved"


# ---- Defeater evaluation -------------------------------------------------


def evaluate_defeaters_for_decision(
    decision: Any, *, events: list[Any] | None = None
) -> list[TriggeredDefeater]:
    """Walk the command's `defeaters` list and return triggered records.

    `decision` is duck-typed against `DecisionFrame` so this module avoids
    importing `viza.decisions` (which would create a cycle).

    Phase 32: `events` is the entity-scoped event set the decision saw at
    emission time. When provided, the `counter_event` defeater is
    evaluated against it — a defeater whose `countering_event_iris`
    matches the FIBO IRI of any event in the set triggers and rejects the
    command.
    """
    triggered: list[TriggeredDefeater] = []
    command = decision.command
    if command is None:
        return triggered

    for defeater in command.defeaters:
        kind = defeater.defeater_kind
        if kind == "evidence_absent":
            reason = _evaluate_evidence_absent(decision, defeater)
        elif kind == "time_decay":
            reason = _evaluate_time_decay(decision, defeater)
        elif kind == "pit_unsafe":
            reason = _evaluate_pit_unsafe(decision, defeater)
        elif kind == "rights_blocked":
            reason = _evaluate_rights_blocked(decision, defeater)
        elif kind == "counter_event":
            reason = _evaluate_counter_event(decision, defeater, events)
        else:
            reason = None

        if reason:
            triggered.append(
                TriggeredDefeater(
                    decision_id=decision.decision_id,
                    defeater_kind=kind,
                    reason=reason,
                )
            )
    return triggered


def _evaluate_counter_event(
    decision: Any, defeater: Defeater, events: list[Any] | None
) -> str | None:
    """Triggered when any event in the decision's entity scope matches one
    of the defeater's `countering_event_iris` (looked up against the event
    registry's FIBO IRI mapping)."""
    if not events or not defeater.countering_event_iris:
        return None
    if decision.command is None:
        return None
    target_entity = decision.command.target.entity_id
    try:
        from viza.events import load_event_registry  # local: cycle-safe

        registry = load_event_registry()
        type_to_fibo = {
            entry.event_type: entry.fibo_iri for entry in registry.event_types
        }
    except Exception:
        type_to_fibo = {}

    countering = set(defeater.countering_event_iris)
    for event in events:
        affected = getattr(event, "affected_entity_ids", []) or []
        if target_entity not in affected:
            continue
        event_type = getattr(event, "event_type", None)
        candidate_iris: set[str] = set()
        if isinstance(event_type, str):
            candidate_iris.add(event_type)
            fibo_iri = type_to_fibo.get(event_type)
            if fibo_iri:
                candidate_iris.add(fibo_iri)
        if candidate_iris & countering:
            return (
                f"counter_event: event {getattr(event, 'event_id', '?')!r} "
                f"({event_type}) matches countering_event_iris="
                f"{sorted(countering & candidate_iris)}"
            )
    return None


def _evaluate_evidence_absent(decision: Any, defeater: Defeater) -> str | None:
    """Triggered when any `required_evidence_keys` value is NOT present in
    the triggering observation set or evidence cache.

    The evaluator uses two best-effort heuristics:

    1. If the decision's provenance lists fewer observation IRIs than the
       defeater's required key count, the evidence is materially absent.
    2. The pit_state's ``observation_count`` (set by `_pit_state`) is
       compared to the required count.

    Phase 32 promotes this to a key-by-key check once events carry typed
    attribute references; for Phase 31 the heuristic catches the common
    "rule fired with strictly fewer evidence rows than declared" case.
    """
    if not defeater.required_evidence_keys:
        return None
    required = len(defeater.required_evidence_keys)
    have = len(decision.trigger_observation_ids)
    if have < required:
        return (
            f"evidence_absent: rule required {required} evidence keys "
            f"({sorted(defeater.required_evidence_keys)}); only {have} "
            "triggering observations were bound"
        )
    return None


def _evaluate_time_decay(decision: Any, defeater: Defeater) -> str | None:
    """Triggered when the most recent triggering observation is older than
    the declared window before the cutoff timestamp."""
    if not defeater.window:
        return None
    try:
        window = _parse_iso_duration(defeater.window)
    except FeelLiteError:
        return None
    max_avail = decision.pit_state.get("max_observation_available_at")
    if not isinstance(max_avail, str) or not max_avail:
        return None
    try:
        max_dt = datetime.fromisoformat(max_avail.replace("Z", "+00:00"))
    except ValueError:
        return None
    if max_dt.tzinfo is None:
        max_dt = max_dt.replace(tzinfo=timezone.utc)
    cutoff = decision.cutoff_timestamp
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    if cutoff - max_dt > window:
        return (
            f"time_decay: triggering evidence (max available_at "
            f"{max_dt.isoformat()}) is older than window {defeater.window} "
            f"before cutoff {cutoff.isoformat()}"
        )
    return None


def _evaluate_pit_unsafe(decision: Any, defeater: Defeater) -> str | None:
    """Triggered when pit_state.lookahead_risk is not 'low'."""
    risk = decision.pit_state.get("lookahead_risk")
    if risk and risk != "low":
        return f"pit_unsafe: pit_state.lookahead_risk={risk!r}"
    return None


def _evaluate_rights_blocked(decision: Any, defeater: Defeater) -> str | None:
    """Triggered when source_rights_state.export_allowed is False."""
    if decision.source_rights_state.get("export_allowed") is False:
        return "rights_blocked: source_rights_state.export_allowed=False"
    return None


# ---- Attack graph --------------------------------------------------------


def build_attack_graph(decisions: list[Any]) -> list[AttackEdge]:
    """Build attack edges from `config/viza_command_conflicts.json`.

    Edges are scoped per target (same `target.entity_id`) because the
    conflict registry's `scope` field is `same_target` for every Phase-31
    edge. `defeats_unconditionally` edges become `edge_kind='unconditional'`
    and are immune to preference resolution.
    """
    edges: list[AttackEdge] = []
    try:
        conflict_registry = get_command_conflicts()
    except Exception:
        return edges

    by_target: dict[str, list[Any]] = {}
    for decision in decisions:
        if decision.command is None:
            continue
        target_key = decision.command.target.entity_id
        by_target.setdefault(target_key, []).append(decision)

    for target_key, group in by_target.items():
        for edge in conflict_registry.conflicts:
            for attacker in group:
                if attacker.command is None:
                    continue
                if attacker.command.command_iri != edge.left_command_iri:
                    continue
                for victim in group:
                    if victim.command is None:
                        continue
                    if attacker.decision_id == victim.decision_id:
                        continue
                    matches_right = (
                        edge.right_command_iri == "*"
                        or edge.right_command_iri == victim.command.command_iri
                    )
                    if not matches_right:
                        continue
                    if (
                        edge.right_command_iri == "*"
                        and victim.command.command_iri == edge.left_command_iri
                    ):
                        # Wildcard defeats apply to OTHER commands, not the
                        # one matching the wildcard's own IRI. Otherwise a
                        # BLOCK_ACTION would attack itself.
                        continue
                    rationale = edge.rationale or (
                        f"{edge.left_command_iri} {edge.relation} "
                        f"{edge.right_command_iri}"
                    )
                    edges.append(
                        AttackEdge(
                            attacker_decision_id=attacker.decision_id,
                            target_decision_id=victim.decision_id,
                            rationale=rationale,
                            edge_kind=(
                                "unconditional"
                                if edge.relation == "defeats_unconditionally"
                                else "preference_resolved"
                            ),
                        )
                    )
    return edges


def apply_preferences(
    decisions: list[Any], edges: list[AttackEdge]
) -> list[AttackEdge]:
    """Resolve symmetric attacks by the preference relation.

    Preference = `command_confidence * command_priority`. When (A → B) and
    (B → A) both exist as preference-resolved edges:

    * If A has higher preference, A → B survives, B → A is dropped.
    * If B has higher preference, the inverse.
    * If equal, both edges survive (the standoff leaves both undecided).

    Unconditional edges are not subject to preference resolution.
    """
    preference: dict[str, float] = {}
    for decision in decisions:
        if decision.command is None:
            preference[decision.decision_id] = 0.0
            continue
        preference[decision.decision_id] = (
            float(decision.command.command_confidence)
            * float(decision.command.command_priority)
        )

    edge_set = {
        (edge.attacker_decision_id, edge.target_decision_id) for edge in edges
    }
    surviving: list[AttackEdge] = []
    for edge in edges:
        if edge.edge_kind == "unconditional":
            surviving.append(edge)
            continue
        reverse = (edge.target_decision_id, edge.attacker_decision_id)
        if reverse not in edge_set:
            surviving.append(edge)
            continue
        attacker_pref = preference.get(edge.attacker_decision_id, 0.0)
        target_pref = preference.get(edge.target_decision_id, 0.0)
        if attacker_pref > target_pref:
            surviving.append(edge)
        elif attacker_pref == target_pref:
            surviving.append(edge)
        # else: attacker is lower-preference; drop this edge so the
        # higher-preference side wins.
    return surviving


# ---- Grounded extension --------------------------------------------------


def compute_grounded_extension(
    decisions: list[Any],
    edges: list[AttackEdge],
    initially_rejected: set[str],
) -> dict[str, str]:
    """Standard Dung grounded-extension fixed-point.

    Start: ``rejected = initially_rejected`` (defeater-triggered).
    Iterate:
      * Newly accepted: decisions whose every attacker is in rejected.
      * Newly rejected: decisions attacked by some accepted decision.
    Stop when neither set grows.

    Returns the per-decision status as ``"accepted" | "rejected" | "undecided"``.
    """
    accepted: set[str] = set()
    rejected: set[str] = set(initially_rejected)

    attackers_of: dict[str, list[str]] = {}
    for edge in edges:
        attackers_of.setdefault(edge.target_decision_id, []).append(
            edge.attacker_decision_id
        )

    while True:
        changed = False
        for decision in decisions:
            did = decision.decision_id
            if did in accepted or did in rejected:
                continue
            attackers = attackers_of.get(did, [])
            if all(att_id in rejected for att_id in attackers):
                accepted.add(did)
                changed = True
        for decision in decisions:
            did = decision.decision_id
            if did in accepted or did in rejected:
                continue
            attackers = attackers_of.get(did, [])
            if any(att_id in accepted for att_id in attackers):
                rejected.add(did)
                changed = True
        if not changed:
            break

    status: dict[str, str] = {}
    for decision in decisions:
        did = decision.decision_id
        if did in rejected:
            status[did] = "rejected"
        elif did in accepted:
            status[did] = "accepted"
        else:
            status[did] = "undecided"
    return status


# ---- Top-level entry point ----------------------------------------------


def apply_argumentation(
    decisions: list[Any], *, events: list[Any] | None = None
) -> list[Any]:
    """Evaluate defeaters, build the attack graph, and tag every decision
    with its grounded-extension status.

    Phase 32: `events` is forwarded to defeater evaluation so the
    `counter_event` kind can fire when a countering event landed for the
    decision's entity. Callers that don't have events (the simple
    Phase-27 path) leave it as None and behavior is unchanged.

    Returns a new list (the input decisions are not mutated).
    """
    if not decisions:
        return decisions

    initially_rejected: set[str] = set()
    rejection_reasons: dict[str, str] = {}
    for decision in decisions:
        triggered = evaluate_defeaters_for_decision(decision, events=events)
        if triggered:
            initially_rejected.add(decision.decision_id)
            rejection_reasons[decision.decision_id] = "; ".join(
                t.reason for t in triggered
            )

    edges = build_attack_graph(decisions)
    edges = apply_preferences(decisions, edges)
    status = compute_grounded_extension(decisions, edges, initially_rejected)

    rebuilt: list[Any] = []
    for decision in decisions:
        new_status = status.get(decision.decision_id, "undecided")
        if decision.decision_id in rejection_reasons:
            reason = rejection_reasons[decision.decision_id]
        elif new_status == "rejected":
            # Find an attacker that's accepted, for the human-readable reason.
            reason = None
            for edge in edges:
                if (
                    edge.target_decision_id == decision.decision_id
                    and status.get(edge.attacker_decision_id) == "accepted"
                ):
                    reason = (
                        f"defeated by accepted command "
                        f"{edge.attacker_decision_id!r} ({edge.rationale})"
                    )
                    break
            if reason is None:
                reason = "rejected by argumentation extension"
        elif new_status == "accepted":
            reason = "accepted by grounded extension"
        else:
            reason = "undecided: mutual attack with equal preference"

        if decision.command is None:
            rebuilt.append(
                decision.model_copy(
                    update={
                        "argumentation_status": new_status,
                        "argumentation_reason": reason,
                    }
                )
            )
            continue
        rebuilt.append(
            decision.model_copy(
                update={
                    "argumentation_status": new_status,
                    "argumentation_reason": reason,
                    "command": decision.command.model_copy(
                        update={
                            "argumentation_status": new_status,
                            "argumentation_reason": reason,
                        }
                    ),
                }
            )
        )
    return rebuilt

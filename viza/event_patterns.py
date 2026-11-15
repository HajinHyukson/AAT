"""Event-pattern grammar for VIZA — Phase 32.

The compliance plan (`docs/viza_end_product/VIZA_KR_COMPLIANCE_REPORT.md` §6
and `VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md` §3 Phase 32) calls for
multi-event temporal patterns expressed as data, not Python. The plan said:
"declare the pattern in YAML/JSON, evaluate batch over a bounded event store,
no streaming engine."

This module is that grammar and evaluator. The pattern AST is a Pydantic
discriminated union; the evaluator is a small recursive matcher that walks
the event list per entity and returns either ``None`` (no match) or a
``PatternMatch`` record carrying the chosen events for downstream provenance.

Operators
---------

* ``event_match`` — single event matching by type, optional confidence
  threshold, optional source-credibility floor, optional `point_in_time_safe`
  flag.
* ``sequence`` — ordered list of sub-patterns; each step's match must
  follow the previous step's match in `observed_at`. `within` (ISO-8601
  duration) bounds the total span.
* ``conjunction`` (``all``) — every sub-pattern must match (order-free).
* ``disjunction`` (``any``) — at least one sub-pattern must match.
* ``negation`` — the sub-pattern must NOT match. Used in compound patterns:
  e.g. `sequence [A, not(B), C]` says "A then C with no B in between".
* Allen interval relations on event pairs: ``before``, ``after``, ``during``,
  ``overlaps``, ``meets``, ``starts``, ``finishes``, ``equals``. Each relates
  two named sub-patterns by their `observed_at` intervals (treated as
  instants when end-times are absent).

The grammar is deliberately small — it covers VIZA's `counter_event`
defeater, the hardcoded `acquisition_rumor_with_technical_reversal_context`
extractor in `viza/insights.py`, and the "regulatory_action invalidates
acquisition_rumor within 30 days" insight reaction without inventing the
full Esper EPL surface.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from viza.feel_lite import FeelLiteError, _parse_iso_duration


# ---- Pattern AST nodes ---------------------------------------------------


class EventMatch(BaseModel):
    """Match a single event by type, optionally filtered."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["event_match"] = "event_match"
    event_type: str
    name: str | None = None  # Bind the matched event for later Allen-relation refs.
    min_confidence: float | None = None
    min_source_credibility: float | None = None
    require_point_in_time_safe: bool | None = None
    fibo_iri: str | None = None  # When set, also match events whose registry FIBO IRI equals this.


class Sequence(BaseModel):
    """Ordered match: each step matches an event whose `observed_at` is >=
    the previous step's match. `within` bounds first-to-last span."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["sequence"] = "sequence"
    steps: list["PatternNode"] = Field(min_length=1)
    within: str | None = None


class Conjunction(BaseModel):
    """All sub-patterns must match (order-free)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["all"] = "all"
    patterns: list["PatternNode"] = Field(min_length=1)


class Disjunction(BaseModel):
    """At least one sub-pattern must match."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["any"] = "any"
    patterns: list["PatternNode"] = Field(min_length=1)


class Negation(BaseModel):
    """The sub-pattern must NOT match.

    For use inside `Conjunction` or to express "no countering event occurred."
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["not"] = "not"
    pattern: "PatternNode"


AllenRelationName = Literal[
    "before",
    "after",
    "during",
    "overlaps",
    "meets",
    "starts",
    "finishes",
    "equals",
]


class AllenRelation(BaseModel):
    """Constrain two named sub-patterns by an Allen interval relation.

    `left` and `right` are inline sub-patterns (typically `EventMatch`
    with a `name`); the constraint is evaluated on their matched events'
    `observed_at` instants (treated as zero-length intervals).
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["allen"] = "allen"
    relation: AllenRelationName
    left: "PatternNode"
    right: "PatternNode"
    tolerance: str | None = None  # ISO-8601 duration; gives the relation slack.


PatternNode = Annotated[
    Union[EventMatch, Sequence, Conjunction, Disjunction, Negation, AllenRelation],
    Field(discriminator="kind"),
]

Sequence.model_rebuild()
Conjunction.model_rebuild()
Disjunction.model_rebuild()
Negation.model_rebuild()
AllenRelation.model_rebuild()


class EventPattern(BaseModel):
    """Top-level pattern wrapper. Carries the AST plus pattern metadata
    (name, description) for UI and audit."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.event_pattern.v1", alias="schema")
    name: str | None = None
    description: str | None = None
    pattern: PatternNode


# ---- Match result --------------------------------------------------------


class PatternMatch(BaseModel):
    """The events the matcher bound on a successful evaluation. Returned to
    callers so the matching events can be threaded into provenance and
    evidence checksums."""

    model_config = ConfigDict(extra="forbid")

    matched_event_ids: list[str] = Field(default_factory=list)
    bindings: dict[str, str] = Field(default_factory=dict)


# ---- Evaluator -----------------------------------------------------------


def evaluate_pattern(
    pattern: EventPattern | PatternNode,
    events: list[Any],
    *,
    cutoff_timestamp: datetime | None = None,
) -> PatternMatch | None:
    """Match `pattern` against `events` (an event list, e.g.
    `list[VizaEvent]`). `cutoff_timestamp` enforces a PIT filter — events
    whose `available_at` exceeds the cutoff are removed before matching.

    Returns the bound match record on success, `None` on failure.
    """
    node: PatternNode
    if isinstance(pattern, EventPattern):
        node = pattern.pattern
    else:
        node = pattern  # type: ignore[assignment]

    candidates = _filter_by_cutoff(events, cutoff_timestamp)
    candidates = sorted(candidates, key=_event_observed_at)
    return _match_node(node, candidates)


def _match_node(node: PatternNode, events: list[Any]) -> PatternMatch | None:
    if isinstance(node, EventMatch):
        return _match_event(node, events)
    if isinstance(node, Sequence):
        return _match_sequence(node, events)
    if isinstance(node, Conjunction):
        return _match_conjunction(node, events)
    if isinstance(node, Disjunction):
        return _match_disjunction(node, events)
    if isinstance(node, Negation):
        return _match_negation(node, events)
    if isinstance(node, AllenRelation):
        return _match_allen(node, events)
    raise ValueError(f"unsupported pattern node: {type(node).__name__}")


def _match_event(node: EventMatch, events: list[Any]) -> PatternMatch | None:
    for event in events:
        if not _event_passes_filter(event, node):
            continue
        bindings = {node.name: event.event_id} if node.name else {}
        return PatternMatch(matched_event_ids=[event.event_id], bindings=bindings)
    return None


def _match_sequence(node: Sequence, events: list[Any]) -> PatternMatch | None:
    if not node.steps:
        return None
    within = _parse_duration_or_none(node.within)
    matched_ids: list[str] = []
    bindings: dict[str, str] = {}
    cursor_index = 0
    first_observed: datetime | None = None

    for step in node.steps:
        # Match each step against the events still ahead of the cursor.
        if not isinstance(step, EventMatch):
            # Sub-patterns inside sequences are restricted to event_match
            # for MVP — nested sequences/disjunctions could be added later
            # without changing the protocol. Skip non-event_match steps.
            return None
        found = False
        for index in range(cursor_index, len(events)):
            event = events[index]
            if not _event_passes_filter(event, step):
                continue
            observed = _event_observed_at(event)
            if first_observed is None:
                first_observed = observed
            elif within is not None and observed - first_observed > within:
                # The sequence span has overshot the window — no match.
                return None
            matched_ids.append(event.event_id)
            if step.name:
                bindings[step.name] = event.event_id
            cursor_index = index + 1
            found = True
            break
        if not found:
            return None
    return PatternMatch(matched_event_ids=matched_ids, bindings=bindings)


def _match_conjunction(node: Conjunction, events: list[Any]) -> PatternMatch | None:
    merged_ids: list[str] = []
    merged_bindings: dict[str, str] = {}
    for sub in node.patterns:
        match = _match_node(sub, events)
        if match is None:
            return None
        merged_ids.extend(match.matched_event_ids)
        merged_bindings.update(match.bindings)
    deduped = list(dict.fromkeys(merged_ids))
    return PatternMatch(matched_event_ids=deduped, bindings=merged_bindings)


def _match_disjunction(node: Disjunction, events: list[Any]) -> PatternMatch | None:
    for sub in node.patterns:
        match = _match_node(sub, events)
        if match is not None:
            return match
    return None


def _match_negation(node: Negation, events: list[Any]) -> PatternMatch | None:
    inner = _match_node(node.pattern, events)
    if inner is None:
        # Negation succeeds when the inner pattern does NOT match. The match
        # has no bound events because nothing was matched — provenance for
        # negation is the absence proof, recorded by the caller.
        return PatternMatch(matched_event_ids=[], bindings={})
    return None


def _match_allen(node: AllenRelation, events: list[Any]) -> PatternMatch | None:
    left_match = _match_node(node.left, events)
    if left_match is None or not left_match.matched_event_ids:
        return None
    right_match = _match_node(node.right, events)
    if right_match is None or not right_match.matched_event_ids:
        return None
    left_event = _event_by_id(events, left_match.matched_event_ids[0])
    right_event = _event_by_id(events, right_match.matched_event_ids[0])
    if left_event is None or right_event is None:
        return None
    tolerance = _parse_duration_or_none(node.tolerance) or timedelta(0)
    if not _allen_holds(node.relation, _event_observed_at(left_event), _event_observed_at(right_event), tolerance):
        return None
    merged_ids = list(dict.fromkeys(left_match.matched_event_ids + right_match.matched_event_ids))
    bindings = {**left_match.bindings, **right_match.bindings}
    return PatternMatch(matched_event_ids=merged_ids, bindings=bindings)


# ---- Helpers -------------------------------------------------------------


def _event_passes_filter(event: Any, node: EventMatch) -> bool:
    if node.event_type and getattr(event, "event_type", None) != node.event_type:
        return False
    if node.min_confidence is not None:
        confidence = getattr(event, "confidence", None)
        if confidence is None or confidence < node.min_confidence:
            return False
    if node.min_source_credibility is not None:
        cred = getattr(event, "source_credibility", None)
        if cred is None or cred < node.min_source_credibility:
            return False
    if node.require_point_in_time_safe is True:
        pit = getattr(event, "point_in_time_safe", None)
        if pit is not True:
            return False
    if node.fibo_iri is not None:
        # Late-binding lookup: import here to avoid a top-level cycle.
        try:
            from viza.events import load_event_registry

            registry = load_event_registry()
            definition = next(
                (
                    item
                    for item in registry.event_types
                    if item.event_type == getattr(event, "event_type", None)
                ),
                None,
            )
        except Exception:
            return False
        if definition is None or definition.fibo_iri != node.fibo_iri:
            return False
    return True


def _filter_by_cutoff(
    events: list[Any], cutoff: datetime | None
) -> list[Any]:
    if cutoff is None:
        return list(events)
    out: list[Any] = []
    for event in events:
        available = getattr(event, "available_at", None)
        if available is None:
            out.append(event)
            continue
        if available <= cutoff:
            out.append(event)
    return out


def _event_observed_at(event: Any) -> datetime:
    value = getattr(event, "observed_at", None)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.min.replace(tzinfo=timezone.utc)


def _event_by_id(events: list[Any], event_id: str) -> Any | None:
    for event in events:
        if getattr(event, "event_id", None) == event_id:
            return event
    return None


def _parse_duration_or_none(value: str | None) -> timedelta | None:
    if not value:
        return None
    try:
        return _parse_iso_duration(value)
    except FeelLiteError:
        return None


def _allen_holds(
    relation: AllenRelationName,
    left: datetime,
    right: datetime,
    tolerance: timedelta,
) -> bool:
    """Apply an Allen interval relation to two instants (treating each as a
    zero-length interval). The full 13 Allen relations collapse to the
    obvious instant-level comparisons:

    * `before` / `after` — strict temporal ordering (with tolerance).
    * `equals` — same instant (within tolerance).
    * `meets` — same as `equals` for zero-length intervals.
    * `during`, `overlaps`, `starts`, `finishes` — degenerate to `equals`
      at the instant level (each is satisfied when left == right within
      tolerance).
    """
    delta = right - left
    if relation == "before":
        return delta > tolerance
    if relation == "after":
        return delta < -tolerance
    if relation in ("equals", "meets", "during", "overlaps", "starts", "finishes"):
        return abs(delta) <= tolerance
    raise ValueError(f"unknown Allen relation: {relation!r}")

"""Investment-command schemas for VIZA's output_radar.

Phase 27 of `docs/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`. The proposal
in this session asked for `BUY_TO_OPEN`, `ADD_LONG`, `HOLD`, `TRIM_LONG`,
`SELL_TO_CLOSE`, `WATCH_CLOSELY`, `AVOID`, `BLOCK_ACTION` as a flat enum; the
compliance audit decomposed those into three command kinds and four orthogonal
axes so the schema does not encode policy in the label. The taxonomy lives in
`config/viza_command_taxonomy.json` as SKOS concepts; this module supplies the
Pydantic shapes that the decision executor produces and the radar consumes.

Identity is FIBO-aligned (CommandTarget carries `fibo_legal_entity_iri` and
`fibo_instrument_iri`). The fields are nullable in MVP because the canonical
asset master is seeded in Phase 30; new commands written by Phase 27 set them
to `None` and are forward-compatible.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.config_paths import resolve_config_path


COMMAND_TAXONOMY_FILE_NAME = "viza_command_taxonomy.json"
COMMAND_CONFLICTS_FILE_NAME = "viza_command_conflicts.json"


# ---- Axes ----------------------------------------------------------------

CommandKind = Literal["PositionCommand", "AttentionCommand", "SystemCommand"]
Direction = Literal["BUY", "SELL", "NONE"]
PositionChange = Literal["OPEN", "INCREASE", "MAINTAIN", "REDUCE", "CLOSE", "REBALANCE"]
Side = Literal["LONG", "SHORT", "FLAT"]
SizingMethod = Literal[
    "TARGET_WEIGHT",
    "DELTA_WEIGHT",
    "TARGET_NOTIONAL",
    "DELTA_NOTIONAL",
    "SHARES",
    "IMPLICIT",
]
Urgency = Literal["ELEVATED", "EXCLUDE"]
VetoKind = Literal["EMIT_BLOCKED", "EXPORT_BLOCKED", "LIVE_MODE_BLOCKED"]


class PositionAxes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: Direction
    position_change: PositionChange
    side: Side
    default_sizing_method: SizingMethod = "IMPLICIT"


class AttentionAxes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urgency: Urgency


class SystemAxes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    veto_kind: VetoKind


# ---- Identity ------------------------------------------------------------


class CanonicalIdentifier(BaseModel):
    """A FIBO-style typed identifier. Phase 30 populates `scheme_iri` from
    fibo-fbc-fct-ra:* concepts; in Phase 27 we use VIZA-local schemes
    (e.g. `viza:scheme/local_entity_id`) that are migrated mechanically later."""

    model_config = ConfigDict(extra="forbid")

    scheme_iri: str
    value: str


class CommandTarget(BaseModel):
    """What the command operates on.

    `entity_id` and `instrument_id` are local VIZA identifiers that the
    project store understands today. `fibo_legal_entity_iri` and
    `fibo_instrument_iri` are populated in Phase 30 from the canonical asset
    master; they are nullable here so a Phase-27 command remains valid before
    that work lands.
    """

    model_config = ConfigDict(extra="forbid")

    entity_id: str
    instrument_id: str | None = None
    ticker_alias: str | None = None
    fibo_legal_entity_iri: str | None = None
    fibo_instrument_iri: str | None = None
    identifier_set: list[CanonicalIdentifier] = Field(default_factory=list)


# ---- Sizing --------------------------------------------------------------


class SizingExpression(BaseModel):
    """The numeric size of a position command, expressed as a FEEL-Lite
    expression evaluated against the trigger's observation context.

    Phase 27 ships a deliberately small evaluator (see `viza/feel_lite.py`)
    that handles literals, dotted identifier access, the arithmetic
    operators, and `min` / `max` / `abs`. Phase 29 replaces this with the
    full S-FEEL subset of DMN.
    """

    model_config = ConfigDict(extra="forbid")

    method: SizingMethod
    expression: str
    units: Literal["weight", "notional_usd", "shares"] = "weight"


# ---- Defeaters (structured invalidation) ---------------------------------


class Defeater(BaseModel):
    """A structured defeater for a command (or insight).

    Replaces unstructured `invalidation_conditions: list[str]`. A defeater
    that triggers tags the command `argumentation_status="rejected"` without
    manual conflict configuration.
    """

    model_config = ConfigDict(extra="forbid")

    defeater_kind: Literal[
        "evidence_absent",
        "counter_event",
        "time_decay",
        "rights_blocked",
        "pit_unsafe",
    ]
    window: str | None = None  # ISO-8601 duration, e.g. "P30D"
    required_evidence_keys: list[str] = Field(default_factory=list)
    countering_event_iris: list[str] = Field(default_factory=list)
    rationale: str | None = None


# ---- Command payload -----------------------------------------------------


class InvestmentCommandPayload(BaseModel):
    """The structured shape of an investment command emitted by a strategy.

    `command_iri` references a SKOS concept in `viza_command_taxonomy.json`.
    The axes are denormalized onto the payload for query convenience and to
    let downstream consumers reason without re-loading the registry.

    `sizing` is required for `PositionCommand` instances whose
    `default_sizing_method` is not `IMPLICIT`, and forbidden for
    `AttentionCommand` and `SystemCommand` instances.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["viza.investment_command.v1"] = Field(
        default="viza.investment_command.v1", alias="schema"
    )
    command_iri: str
    command_pref_label: str
    kind: CommandKind
    target: CommandTarget
    position_axes: PositionAxes | None = None
    attention_axes: AttentionAxes | None = None
    system_axes: SystemAxes | None = None
    sizing: SizingExpression | None = None
    resolved_sizing_value: float | None = None
    command_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    command_priority: int = Field(default=50, ge=0, le=100)
    defeaters: list[Defeater] = Field(default_factory=list)
    argumentation_status: Literal["accepted", "rejected", "undecided"] = "undecided"
    argumentation_reason: str | None = None
    execution_routing: Literal["none"] = "none"
    not_investment_advice: bool = True

    @model_validator(mode="after")
    def validate_kind_axes(self) -> "InvestmentCommandPayload":
        if self.kind == "PositionCommand":
            if self.position_axes is None:
                raise ValueError("PositionCommand requires position_axes")
            if self.attention_axes is not None or self.system_axes is not None:
                raise ValueError("PositionCommand cannot also carry attention/system axes")
            if (
                self.sizing is None
                and self.position_axes.default_sizing_method != "IMPLICIT"
            ):
                raise ValueError(
                    f"PositionCommand with default_sizing_method="
                    f"{self.position_axes.default_sizing_method!r} requires a sizing block"
                )
        elif self.kind == "AttentionCommand":
            if self.attention_axes is None:
                raise ValueError("AttentionCommand requires attention_axes")
            if self.position_axes is not None or self.system_axes is not None:
                raise ValueError("AttentionCommand cannot also carry position/system axes")
            if self.sizing is not None:
                raise ValueError("AttentionCommand cannot carry sizing")
        elif self.kind == "SystemCommand":
            if self.system_axes is None:
                raise ValueError("SystemCommand requires system_axes")
            if self.position_axes is not None or self.attention_axes is not None:
                raise ValueError("SystemCommand cannot also carry position/attention axes")
            if self.sizing is not None:
                raise ValueError("SystemCommand cannot carry sizing")
        return self


# ---- Command-mapping spec on rules ---------------------------------------


class CommandMapping(BaseModel):
    """How a DecisionRule binds its firing to a structured command.

    A rule whose trigger fires emits the command identified by `command_iri`.
    If the rule's trigger does not fire and `else_command_iri` is set, that
    alternative command is emitted instead (the typical pattern: trigger ⇒
    BUY_TO_OPEN, otherwise WATCH_CLOSELY).
    """

    model_config = ConfigDict(extra="forbid")

    command_iri: str
    sizing: SizingExpression | None = None
    else_command_iri: str | None = None
    else_sizing: SizingExpression | None = None


# ---- Command taxonomy registry (loaded from JSON) ------------------------


class CommandConceptAxes(BaseModel):
    model_config = ConfigDict(extra="allow")

    direction: Direction | None = None
    position_change: PositionChange | None = None
    side: Side | None = None
    default_sizing_method: SizingMethod | None = None
    urgency: Urgency | None = None
    veto_kind: VetoKind | None = None


class CommandConcept(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    iri: str
    skos_pref_label: str
    skos_alt_labels: list[str] = Field(default_factory=list)
    skos_broader: list[str] = Field(default_factory=list)
    kind: CommandKind
    axes: CommandConceptAxes
    command_priority: int = 50
    fibo_related_iri: str | None = None
    description: str | None = None


class CommandTaxonomy(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["viza.command_taxonomy.v1"] = Field(
        default="viza.command_taxonomy.v1", alias="schema"
    )
    registry_version: str = "0.1.0"
    concept_scheme: str
    description: str | None = None
    commands: list[CommandConcept] = Field(default_factory=list)

    def get(self, iri: str) -> CommandConcept | None:
        return next((concept for concept in self.commands if concept.iri == iri), None)

    def require(self, iri: str) -> CommandConcept:
        concept = self.get(iri)
        if concept is None:
            raise KeyError(f"unknown VIZA command concept: {iri}")
        return concept


class CommandConflictEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_command_iri: str
    right_command_iri: str
    relation: Literal["attacks", "defeats_unconditionally"]
    scope: Literal["same_target", "any_target"] = "same_target"
    preference_basis: str | None = None
    rationale: str | None = None


class CommandConflictRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["viza.command_conflicts.v1"] = Field(
        default="viza.command_conflicts.v1", alias="schema"
    )
    registry_version: str = "0.1.0"
    description: str | None = None
    conflicts: list[CommandConflictEdge] = Field(default_factory=list)

    def unconditional_defeaters_of(self, command_iri: str) -> list[CommandConflictEdge]:
        """Return edges whose `left` defeats this `command_iri` unconditionally."""
        result: list[CommandConflictEdge] = []
        for edge in self.conflicts:
            if edge.relation != "defeats_unconditionally":
                continue
            if edge.right_command_iri == command_iri or edge.right_command_iri == "*":
                if edge.left_command_iri != command_iri:
                    result.append(edge)
        return result


def load_command_taxonomy(path: str | Path | None = None) -> CommandTaxonomy:
    target = (
        Path(path)
        if path is not None
        else resolve_config_path(COMMAND_TAXONOMY_FILE_NAME)
    )
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return CommandTaxonomy.model_validate(payload)


def load_command_conflicts(path: str | Path | None = None) -> CommandConflictRegistry:
    target = (
        Path(path)
        if path is not None
        else resolve_config_path(COMMAND_CONFLICTS_FILE_NAME)
    )
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return CommandConflictRegistry.model_validate(payload)


@lru_cache(maxsize=1)
def get_command_taxonomy() -> CommandTaxonomy:
    return load_command_taxonomy()


@lru_cache(maxsize=1)
def get_command_conflicts() -> CommandConflictRegistry:
    return load_command_conflicts()


def reset_command_caches() -> None:
    get_command_taxonomy.cache_clear()
    get_command_conflicts.cache_clear()


# ---- Construction helpers ------------------------------------------------


def build_command_from_concept(
    *,
    concept: CommandConcept,
    target: CommandTarget,
    sizing: SizingExpression | None,
    resolved_sizing_value: float | None,
    command_confidence: float,
    defeaters: list[Defeater] | None = None,
) -> InvestmentCommandPayload:
    """Construct an `InvestmentCommandPayload` from a taxonomy concept.

    Pure-function helper so tests can build commands without invoking the full
    decisions pipeline.
    """
    position_axes: PositionAxes | None = None
    attention_axes: AttentionAxes | None = None
    system_axes: SystemAxes | None = None
    effective_sizing = sizing
    effective_resolved = resolved_sizing_value

    if concept.kind == "PositionCommand":
        if (
            concept.axes.direction is None
            or concept.axes.position_change is None
            or concept.axes.side is None
        ):
            raise ValueError(
                f"PositionCommand concept {concept.iri!r} is missing required axes"
            )
        method = concept.axes.default_sizing_method or "IMPLICIT"
        position_axes = PositionAxes(
            direction=concept.axes.direction,
            position_change=concept.axes.position_change,
            side=concept.axes.side,
            default_sizing_method=method,
        )
        if method == "IMPLICIT" and sizing is None:
            # Implicit-sizing commands like HOLD / SELL_TO_CLOSE may omit sizing.
            effective_sizing = None
            effective_resolved = None
    elif concept.kind == "AttentionCommand":
        if concept.axes.urgency is None:
            raise ValueError(
                f"AttentionCommand concept {concept.iri!r} is missing `urgency` axis"
            )
        attention_axes = AttentionAxes(urgency=concept.axes.urgency)
        effective_sizing = None
        effective_resolved = None
    elif concept.kind == "SystemCommand":
        if concept.axes.veto_kind is None:
            raise ValueError(
                f"SystemCommand concept {concept.iri!r} is missing `veto_kind` axis"
            )
        system_axes = SystemAxes(veto_kind=concept.axes.veto_kind)
        effective_sizing = None
        effective_resolved = None

    return InvestmentCommandPayload(
        command_iri=concept.iri,
        command_pref_label=concept.skos_pref_label,
        kind=concept.kind,
        target=target,
        position_axes=position_axes,
        attention_axes=attention_axes,
        system_axes=system_axes,
        sizing=effective_sizing,
        resolved_sizing_value=effective_resolved,
        command_confidence=command_confidence,
        command_priority=concept.command_priority,
        defeaters=defeaters or [],
    )

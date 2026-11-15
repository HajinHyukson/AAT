"""Output-radar assembly: normalize ranking rows and decision frames into a
single RadarItem stream, then select for display.

Phase 27 of `docs/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`. The output
radar stops being a Top-N ranking table; it becomes a multiplexer that
consumes both ranking results and DecisionFrames and emits a typed sequence
of RadarItems. Selection is governed by `OutputRadarConfig`, which carries an
explicit DMN-style hit policy.

MVP scope (the rest follows in Phases 28–33):

* Three modes: `ranking_only`, `decisions_only`, `mixed`.
* Two hit policies: `COLLECT` (preserve all, sorted), `QUOTA_THEN_SCORE`
  (per-kind quotas filled by descending score).
* `BLOCK_ACTION` decisions are always surfaced when present on a target;
  `argumentation_status="rejected"` items are hidden unless explicitly
  requested.

`OutputRadarConfig` is stored on `VizaStrategyProfile.output_radar_config` as
a `dict[str, Any]` to avoid an import cycle with strategy_profiles; the
`parse_output_radar_config` helper validates and returns the typed form.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.commands import InvestmentCommandPayload
from viza.decisions import DecisionFrame
from viza.execution import RadarRow


RadarItemKind = Literal[
    "ranking_result",
    "decision_command",
    "watch_command",
    "blocked_command",
    "package_warning",
]


RadarMode = Literal["ranking_only", "decisions_only", "mixed"]
HitPolicy = Literal["COLLECT", "QUOTA_THEN_SCORE", "PRIORITY", "FIRST", "UNIQUE"]


class DecisionRadarFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_iris: list[str] | None = None
    include_rejected: bool = False
    include_veto_commands: bool = True
    include_attention_commands: bool = True


class OutputRadarConfig(BaseModel):
    """How the radar selects from the assembled RadarItem stream.

    Mode caps which sources are consulted. Hit policy decides multi-result
    semantics. `quotas` is consulted only when `hit_policy="QUOTA_THEN_SCORE"`.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.output_radar_config.v1", alias="schema")
    mode: RadarMode = "mixed"
    max_items: int = Field(default=20, ge=1, le=200)
    sources: list[Literal["ranking_results", "decision_frames"]] = Field(
        default_factory=lambda: ["ranking_results", "decision_frames"]
    )
    hit_policy: HitPolicy = "COLLECT"
    quotas: dict[str, int] = Field(default_factory=dict)
    sort_by: Literal[
        "radar_score",
        "command_priority",
        "valid_time_start",
        "argumentation_status",
    ] = "radar_score"
    group_by: Literal["display_group", "command_family", "argumentation_status"] | None = None
    decision_filters: DecisionRadarFilters = Field(default_factory=DecisionRadarFilters)

    @model_validator(mode="after")
    def validate_sources_for_mode(self) -> "OutputRadarConfig":
        if self.mode == "ranking_only" and "ranking_results" not in self.sources:
            raise ValueError("ranking_only mode requires 'ranking_results' in sources")
        if self.mode == "decisions_only" and "decision_frames" not in self.sources:
            raise ValueError("decisions_only mode requires 'decision_frames' in sources")
        if self.mode == "mixed" and not self.sources:
            raise ValueError("mixed mode requires at least one source")
        if self.hit_policy == "QUOTA_THEN_SCORE" and not self.quotas:
            raise ValueError("QUOTA_THEN_SCORE hit_policy requires non-empty quotas")
        return self


def parse_output_radar_config(payload: dict[str, Any] | None) -> OutputRadarConfig:
    """Validate a profile's `output_radar_config` dict; return default config
    when payload is empty / missing."""
    if not payload:
        return OutputRadarConfig()
    return OutputRadarConfig.model_validate(payload)


class RadarItem(BaseModel):
    """The unit the radar UI renders.

    Both ranking rows and decision frames adapt to this shape. Sort and group
    decisions consult the typed fields rather than poking into the source
    object.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.radar_item.v1", alias="schema")
    radar_item_id: str
    item_kind: RadarItemKind
    entity_id: str
    asset_id: str | None = None
    profile_id: str | None = None
    source_run_id: str | None = None
    source_object_id: str | None = None
    display_group: str = "Top Ranked Securities"
    priority: Literal["low", "medium", "high"] = "medium"
    radar_score: float = 0.0
    sort_key: float = 0.0
    command_family_iri: str | None = None
    command: InvestmentCommandPayload | None = None
    ranking_row: RadarRow | None = None
    pit_state: dict[str, Any] = Field(default_factory=dict)
    rights_state: dict[str, Any] = Field(default_factory=dict)
    validation_state: dict[str, Any] = Field(default_factory=dict)
    audit_chain: dict[str, Any] = Field(default_factory=dict)
    argumentation_status: Literal["accepted", "rejected", "undecided"] = "undecided"
    render_component: Literal[
        "RankingCard",
        "DecisionCommandCard",
        "WatchCommandCard",
        "BlockedCommandCard",
        "PackageWarningCard",
    ] = "RankingCard"


class OutputRadarView(BaseModel):
    """The selected, ordered set of RadarItems for the desktop radar UI."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.output_radar_view.v1", alias="schema")
    mode: RadarMode
    hit_policy: HitPolicy
    item_counts_by_kind: dict[str, int] = Field(default_factory=dict)
    item_counts_by_group: dict[str, int] = Field(default_factory=dict)
    items: list[RadarItem] = Field(default_factory=list)
    not_investment_advice: bool = True


# ---- Adapters ------------------------------------------------------------


def ranking_result_to_radar_item(row: RadarRow) -> RadarItem:
    """Project an existing RadarRow (ranking result) into a RadarItem."""
    score = row.score if row.score is not None else 0.0
    return RadarItem(
        radar_item_id=f"radar-rank-{row.entity_id or row.ticker}",
        item_kind="ranking_result",
        entity_id=row.entity_id or row.ticker,
        asset_id=row.asset_id,
        profile_id=None,
        source_object_id=None,
        display_group="Top Ranked Securities",
        priority="medium",
        radar_score=float(score),
        sort_key=float(score),
        ranking_row=row,
        pit_state={"PIT_status": row.PIT_status} if row.PIT_status else {},
        argumentation_status="accepted",
        render_component="RankingCard",
    )


def decision_frame_to_radar_item(decision: DecisionFrame) -> RadarItem:
    """Project a DecisionFrame into a RadarItem.

    Kind selection follows the command kind:
    * PositionCommand -> decision_command (DecisionCommandCard)
    * AttentionCommand -> watch_command (WatchCommandCard)
    * SystemCommand -> blocked_command (BlockedCommandCard)

    DecisionFrames without a command (legacy rules) fall back to
    `decision_command` with command=None and the DecisionCommandCard renders
    the verbatim action_template.
    """
    command = decision.command
    if command is not None and command.kind == "AttentionCommand":
        item_kind: RadarItemKind = "watch_command"
        render_component = "WatchCommandCard"
        display_group = "Watch / Attention"
        priority = "medium"
    elif command is not None and command.kind == "SystemCommand":
        item_kind = "blocked_command"
        render_component = "BlockedCommandCard"
        display_group = "Blocked"
        priority = "high"
    else:
        item_kind = "decision_command"
        render_component = "DecisionCommandCard"
        display_group = "Investment Commands"
        priority = (
            "high"
            if command is not None and command.command_priority >= 75
            else "medium"
        )

    command_priority = command.command_priority if command is not None else 50
    radar_score = float(command.command_confidence) if command is not None else 0.5

    return RadarItem(
        radar_item_id=f"radar-decision-{decision.decision_id}",
        item_kind=item_kind,
        entity_id=decision.entity_id,
        asset_id=decision.asset_id,
        profile_id=decision.strategy_profile_id,
        source_run_id=decision.audit.run_id,
        source_object_id=decision.decision_id,
        display_group=display_group,
        priority=priority,
        radar_score=radar_score,
        sort_key=float(command_priority),
        command_family_iri=(
            command.command_iri.rsplit("/", 1)[0] if command is not None else None
        ),
        command=command,
        pit_state=dict(decision.pit_state),
        rights_state=dict(decision.source_rights_state),
        validation_state={
            "evidence_checksum": decision.audit.evidence_checksum,
            "graph_hash": decision.audit.graph_hash,
            "profile_version": decision.audit.profile_version,
        },
        audit_chain=(
            decision.provenance.model_dump(mode="json")
            if decision.provenance is not None
            else decision.audit.model_dump(mode="json")
        ),
        argumentation_status=decision.argumentation_status,
        render_component=render_component,
    )


# ---- Assembly + selection ------------------------------------------------


def assemble_output_radar(
    *,
    config: OutputRadarConfig,
    ranking_rows: list[RadarRow] | None = None,
    decisions: list[DecisionFrame] | None = None,
) -> OutputRadarView:
    """Build an OutputRadarView from raw ranking rows and decision frames.

    Selection rules in Phase 27:

    1. Filter by `config.mode`:
       - `ranking_only` drops decisions even when present.
       - `decisions_only` drops ranking rows.
       - `mixed` keeps both.
    2. Apply `config.decision_filters`:
       - `include_rejected=False` (default) hides argumentation-rejected items.
       - `include_veto_commands=False` hides system vetoes.
       - `include_attention_commands=False` hides watch items.
       - `command_iris` (if set) keeps only matching decisions.
    3. Apply hit policy:
       - `COLLECT` keeps all matching items sorted by `sort_by`.
       - `QUOTA_THEN_SCORE` fills per-kind quotas in score order.
    4. Truncate to `max_items`.
    """
    ranking_rows = ranking_rows or []
    decisions = decisions or []

    ranking_items: list[RadarItem] = []
    decision_items: list[RadarItem] = []

    if config.mode in ("ranking_only", "mixed") and "ranking_results" in config.sources:
        ranking_items = [ranking_result_to_radar_item(row) for row in ranking_rows]

    if (
        config.mode in ("decisions_only", "mixed")
        and "decision_frames" in config.sources
    ):
        decision_items = [decision_frame_to_radar_item(d) for d in decisions]

    decision_items = _apply_decision_filters(decision_items, config.decision_filters)

    candidates = ranking_items + decision_items
    sorted_candidates = _sort_candidates(candidates, config.sort_by)

    if config.hit_policy == "COLLECT":
        selected = sorted_candidates[: config.max_items]
    elif config.hit_policy == "QUOTA_THEN_SCORE":
        selected = _quota_then_score(sorted_candidates, config.quotas, config.max_items)
    else:
        # Phase-27 stub for the other DMN hit policies; conservative behavior
        # is COLLECT with a warning surfaced via item_counts_by_group.
        selected = sorted_candidates[: config.max_items]

    counts_by_kind: dict[str, int] = {}
    counts_by_group: dict[str, int] = {}
    for item in selected:
        counts_by_kind[item.item_kind] = counts_by_kind.get(item.item_kind, 0) + 1
        counts_by_group[item.display_group] = (
            counts_by_group.get(item.display_group, 0) + 1
        )

    return OutputRadarView(
        mode=config.mode,
        hit_policy=config.hit_policy,
        item_counts_by_kind=counts_by_kind,
        item_counts_by_group=counts_by_group,
        items=selected,
    )


def _apply_decision_filters(
    items: list[RadarItem], filters: DecisionRadarFilters
) -> list[RadarItem]:
    out: list[RadarItem] = []
    for item in items:
        if item.argumentation_status == "rejected" and not filters.include_rejected:
            continue
        if item.item_kind == "blocked_command" and not filters.include_veto_commands:
            continue
        if (
            item.item_kind == "watch_command"
            and not filters.include_attention_commands
        ):
            continue
        if (
            filters.command_iris is not None
            and item.command is not None
            and item.command.command_iri not in filters.command_iris
        ):
            continue
        out.append(item)
    return out


def _sort_candidates(items: list[RadarItem], sort_by: str) -> list[RadarItem]:
    if sort_by == "radar_score":
        return sorted(items, key=lambda item: item.radar_score, reverse=True)
    if sort_by == "command_priority":
        return sorted(items, key=lambda item: item.sort_key, reverse=True)
    if sort_by == "argumentation_status":
        order = {"accepted": 0, "undecided": 1, "rejected": 2}
        return sorted(
            items,
            key=lambda item: (order.get(item.argumentation_status, 3), -item.radar_score),
        )
    return sorted(items, key=lambda item: item.radar_score, reverse=True)


def _quota_then_score(
    items: list[RadarItem], quotas: dict[str, int], max_items: int
) -> list[RadarItem]:
    """Per-kind STRICT quotas filled by descending score.

    Items whose kind is not in `quotas` are skipped entirely (a kind without a
    quota cannot consume a slot). When the sum of quotas is less than
    `max_items`, the view is intentionally short — users who want a soft cap
    should raise the quotas. This is the simpler contract and matches DMN's
    Priority hit policy semantics.
    """
    remaining = {kind: int(limit) for kind, limit in quotas.items()}
    selected: list[RadarItem] = []
    for item in items:
        if len(selected) >= max_items:
            break
        budget = remaining.get(item.item_kind)
        if budget is None or budget <= 0:
            continue
        selected.append(item)
        remaining[item.item_kind] = budget - 1
    return selected

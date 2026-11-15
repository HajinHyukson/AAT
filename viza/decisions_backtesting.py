"""Backtesting evaluator for VIZA decision rules.

Phase D of docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md. Replays a strategy
profile's DecisionRules across a series of historical cutoffs and emits a
summary of fires per rule, per entity, and per cutoff. Cooldown and
dead-band suppression are applied across cutoffs by feeding earlier
emissions back in as ``prior_emissions``.

Sandbox-only by design — backtesting against historical observations is
inherently a sandbox-replay activity. The evaluator refuses ``mode='live'``
and any other mode by relying on ``compile_decisions``'s own mode validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.decisions import DecisionFrame, PriorEmission, compile_decisions
from viza.observations import VizaObservation
from viza.strategy_profiles import VizaStrategyProfile


class BacktestRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    profile: VizaStrategyProfile
    observations: list[VizaObservation] = Field(default_factory=list)
    cutoffs: list[datetime] = Field(default_factory=list)
    graph_hash: str
    profile_version: str
    run_id_prefix: str = "backtest"


class BacktestRuleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    fire_count: int
    entities_fired: list[str]
    fires_by_entity: dict[str, int]
    fires_by_cutoff: dict[str, int]
    earliest_fire_at: datetime | None
    latest_fire_at: datetime | None


class BacktestEntitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    fire_count: int
    rules_fired: list[str]
    cutoffs_with_fires: list[str]


class BacktestReport(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(
        default="viza.decisions_backtest_report.v1", alias="schema"
    )
    profile_id: str
    cutoff_count: int
    total_decisions: int
    by_rule: list[BacktestRuleSummary] = Field(default_factory=list)
    by_entity: list[BacktestEntitySummary] = Field(default_factory=list)
    by_command_axis: dict[str, dict[str, int]] = Field(default_factory=dict)
    decisions: list[DecisionFrame] = Field(default_factory=list)
    not_investment_advice: bool = True


def run_decisions_backtest(request: BacktestRequest) -> BacktestReport:
    """Run the strategy profile's DecisionRules across ``request.cutoffs``.

    For each cutoff (sorted ascending), compile decisions against the full
    observation set with the cutoff applied, then feed the emitted decisions
    forward as prior emissions for subsequent cutoffs so cooldown / dead-band
    bookkeeping crosses the cutoff boundary correctly.
    """
    sorted_cutoffs = sorted(request.cutoffs)
    all_decisions: list[DecisionFrame] = []
    prior_emissions: list[PriorEmission] = []
    obs_by_id: dict[str, VizaObservation] = {
        obs.observation_id: obs for obs in request.observations
    }

    for cutoff in sorted_cutoffs:
        decisions = compile_decisions(
            profile=request.profile,
            observations=request.observations,
            cutoff_timestamp=cutoff,
            run_id=f"{request.run_id_prefix}-{cutoff.isoformat()}",
            graph_hash=request.graph_hash,
            profile_version=request.profile_version,
            mode="sandbox_replay",
            prior_emissions=prior_emissions,
        )
        all_decisions.extend(decisions)
        prior_emissions = prior_emissions + [
            _prior_emission_from_decision(decision, obs_by_id)
            for decision in decisions
        ]

    by_rule = _summarize_by_rule(all_decisions)
    by_entity = _summarize_by_entity(all_decisions)
    # Phase 27: aggregate counts by command axis so a backtest answers
    # questions like "how many BUY_TO_OPEN firings did this strategy produce
    # across these cutoffs?" without callers walking every DecisionFrame.
    from viza.decisions_redaction import command_axis_counts  # local: cycle-safe

    by_command_axis = command_axis_counts(all_decisions)

    return BacktestReport(
        profile_id=request.profile.strategy_profile_id,
        cutoff_count=len(sorted_cutoffs),
        total_decisions=len(all_decisions),
        by_rule=by_rule,
        by_entity=by_entity,
        by_command_axis=by_command_axis,
        decisions=all_decisions,
    )


def _prior_emission_from_decision(
    decision: DecisionFrame,
    obs_by_id: dict[str, VizaObservation],
) -> PriorEmission:
    trigger_values: dict[str, float] = {}
    for observation_id in decision.trigger_observation_ids:
        observation = obs_by_id.get(observation_id)
        if observation is None:
            continue
        try:
            trigger_values[observation.attribute_key] = float(observation.value)
        except (TypeError, ValueError):
            continue
    return PriorEmission(
        rule_id=decision.rule_id,
        entity_id=decision.entity_id,
        cutoff_timestamp=decision.cutoff_timestamp,
        trigger_values=trigger_values,
    )


def _summarize_by_rule(decisions: list[DecisionFrame]) -> list[BacktestRuleSummary]:
    grouped: dict[str, list[DecisionFrame]] = {}
    for decision in decisions:
        grouped.setdefault(decision.rule_id, []).append(decision)
    summaries: list[BacktestRuleSummary] = []
    for rule_id, group in grouped.items():
        entities = sorted({decision.entity_id for decision in group})
        fires_by_entity = {
            entity_id: sum(
                1 for decision in group if decision.entity_id == entity_id
            )
            for entity_id in entities
        }
        cutoffs_present = sorted(
            {decision.cutoff_timestamp.isoformat() for decision in group}
        )
        fires_by_cutoff = {
            cutoff_iso: sum(
                1
                for decision in group
                if decision.cutoff_timestamp.isoformat() == cutoff_iso
            )
            for cutoff_iso in cutoffs_present
        }
        summaries.append(
            BacktestRuleSummary(
                rule_id=rule_id,
                fire_count=len(group),
                entities_fired=entities,
                fires_by_entity=fires_by_entity,
                fires_by_cutoff=fires_by_cutoff,
                earliest_fire_at=min(decision.cutoff_timestamp for decision in group),
                latest_fire_at=max(decision.cutoff_timestamp for decision in group),
            )
        )
    summaries.sort(key=lambda summary: summary.rule_id)
    return summaries


def _summarize_by_entity(
    decisions: list[DecisionFrame],
) -> list[BacktestEntitySummary]:
    grouped: dict[str, list[DecisionFrame]] = {}
    for decision in decisions:
        grouped.setdefault(decision.entity_id, []).append(decision)
    summaries: list[BacktestEntitySummary] = []
    for entity_id, group in grouped.items():
        summaries.append(
            BacktestEntitySummary(
                entity_id=entity_id,
                fire_count=len(group),
                rules_fired=sorted({decision.rule_id for decision in group}),
                cutoffs_with_fires=sorted(
                    {decision.cutoff_timestamp.isoformat() for decision in group}
                ),
            )
        )
    summaries.sort(key=lambda summary: summary.entity_id)
    return summaries


def report_for_export(report: BacktestReport) -> dict[str, Any]:
    """Return a serialization-safe dict of the report for inclusion in a
    ``.viza`` package or HTTP response. Includes the non-advice marker."""
    payload = report.model_dump(mode="json", by_alias=True)
    payload["not_investment_advice"] = True
    return payload

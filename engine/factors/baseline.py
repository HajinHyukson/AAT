from __future__ import annotations

from datetime import datetime
from uuid import UUID

from engine.attribution.hierarchy import assert_systematic_before_events, sort_factor_inputs
from engine.contracts import (
    AttributionContribution,
    AttributionResult,
    ConfidenceLevel,
    DriverType,
    FactorContributionInput,
    TimeWindow,
)
from engine.time import is_point_in_time_visible


MODEL_VERSION = "factor-baseline-v0"


def build_factor_baseline_result(
    *,
    security_id: UUID,
    window: TimeWindow,
    attribution_cutoff: datetime,
    observed_return_bps: float,
    factor_inputs: list[FactorContributionInput],
) -> AttributionResult:
    visible_inputs = [
        item
        for item in factor_inputs
        if item.security_id == security_id
        and window.start <= item.event_time <= window.end
        and is_point_in_time_visible(item, attribution_cutoff)
        and item.driver != DriverType.UNEXPLAINED_RESIDUAL
    ]
    visible_inputs = sort_factor_inputs(visible_inputs)
    assert_systematic_before_events(visible_inputs)

    contributions = [
        AttributionContribution(
            driver=item.driver,
            name=item.name,
            contribution_bps=item.contribution_bps,
            share_of_move=_share_of_move(item.contribution_bps, observed_return_bps),
            confidence=item.confidence,
            evidence=item.evidence,
            contribution_stage=item.contribution_stage,
            evidence_payload=item.evidence_payload,
        )
        for item in visible_inputs
    ]

    explained = sum(item.contribution_bps for item in contributions)
    residual = observed_return_bps - explained
    contributions.append(
        AttributionContribution(
            driver=DriverType.UNEXPLAINED_RESIDUAL,
            name="Unexplained residual",
            contribution_bps=residual,
            share_of_move=_share_of_move(residual, observed_return_bps),
            confidence=ConfidenceLevel.LOW if abs(residual) > abs(observed_return_bps) * 0.5 else ConfidenceLevel.MEDIUM,
            evidence=[],
        )
    )

    return AttributionResult(
        security_id=security_id,
        window=window,
        attribution_cutoff=attribution_cutoff,
        observed_return_bps=observed_return_bps,
        contributions=contributions,
        unexplained_residual_bps=residual,
        model_version=MODEL_VERSION,
    )


def _share_of_move(contribution_bps: float, observed_return_bps: float) -> float | None:
    if observed_return_bps == 0:
        return None
    return contribution_bps / observed_return_bps

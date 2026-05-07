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
from engine.attribution.diagnostics import (
    build_share_diagnostics,
    legacy_share_of_move,
    residual_confidence,
    safe_share_of_move,
)
from engine.time import is_point_in_time_visible


MODEL_VERSION = "factor-baseline-v0"
RESIDUAL_SAFETY_MODEL_VERSION = "factor-baseline-residual-safety-v1"


def build_factor_baseline_result(
    *,
    security_id: UUID,
    window: TimeWindow,
    attribution_cutoff: datetime,
    observed_return_bps: float,
    factor_inputs: list[FactorContributionInput],
    share_policy: str = "legacy",
    model_version: str = MODEL_VERSION,
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

    use_safety = share_policy == "residual_safety_v1"
    contributions = [
        AttributionContribution(
            driver=item.driver,
            name=item.name,
            contribution_bps=item.contribution_bps,
            share_of_move=_contribution_share(
                contribution_bps=item.contribution_bps,
                observed_return_bps=observed_return_bps,
                use_safety=use_safety,
            ),
            confidence=item.confidence,
            evidence=item.evidence,
            contribution_stage=item.contribution_stage,
            evidence_payload=item.evidence_payload,
        )
        for item in visible_inputs
    ]

    explained = sum(item.contribution_bps for item in contributions)
    residual = observed_return_bps - explained
    diagnostics = build_share_diagnostics(
        observed_return_bps=observed_return_bps,
        non_residual_contribution_bps=[item.contribution_bps for item in contributions],
        residual_bps=residual,
    )
    if use_safety:
        contributions = [
            item.model_copy(
                update={
                    "evidence_payload": {
                        **item.evidence_payload,
                        **diagnostics.as_payload(),
                    }
                }
            )
            for item in contributions
        ]
    contributions.append(
        AttributionContribution(
            driver=DriverType.UNEXPLAINED_RESIDUAL,
            name="Unexplained residual",
            contribution_bps=residual,
            share_of_move=_contribution_share(
                contribution_bps=residual,
                observed_return_bps=observed_return_bps,
                use_safety=use_safety,
            ),
            confidence=(
                residual_confidence(
                    residual_bps=residual,
                    observed_return_bps=observed_return_bps,
                )
                if use_safety
                else ConfidenceLevel.LOW
                if abs(residual) > abs(observed_return_bps) * 0.5
                else ConfidenceLevel.MEDIUM
            ),
            evidence=[],
            evidence_payload=diagnostics.as_payload() if use_safety else {},
        )
    )

    return AttributionResult(
        security_id=security_id,
        window=window,
        attribution_cutoff=attribution_cutoff,
        observed_return_bps=observed_return_bps,
        contributions=contributions,
        unexplained_residual_bps=residual,
        model_version=model_version,
    )


def _contribution_share(
    *,
    contribution_bps: float,
    observed_return_bps: float,
    use_safety: bool,
) -> float | None:
    if use_safety:
        return safe_share_of_move(
            contribution_bps=contribution_bps,
            observed_return_bps=observed_return_bps,
        )
    return legacy_share_of_move(
        contribution_bps=contribution_bps,
        observed_return_bps=observed_return_bps,
    )

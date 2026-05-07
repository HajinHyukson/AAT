from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import numpy as np

from engine.attribution.diagnostics import finite_bps
from engine.confidence.scoring import confidence_from_penalties, standard_factor_penalties
from engine.contracts import ConfidenceLevel, DriverType, FactorContributionInput, PriceBar, TimeWindow
from engine.factors.regression import attribution_factor_move, paired_estimation_returns, simple_beta, visible_stock_returns


MODEL_VERSION = "hierarchical-market-first-v1"


@dataclass(frozen=True)
class HierarchicalFactorSpec:
    factor_name: str
    driver: DriverType
    display_name: str
    raw_returns: dict[datetime, float]
    gate: float = 1.0


def build_hierarchical_residualized_inputs(
    *,
    security_id: UUID,
    price_bars: list[PriceBar],
    prior_factor_returns_by_name: dict[str, dict[datetime, float]],
    factor_specs: list[HierarchicalFactorSpec],
    estimation_window: TimeWindow,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
    min_observations: int = 60,
) -> list[FactorContributionInput]:
    stock_returns = visible_stock_returns(
        security_id=security_id,
        price_bars=price_bars,
        estimation_window=estimation_window,
        attribution_window=attribution_window,
        attribution_cutoff=attribution_cutoff,
    )
    prior_series = [series for series in prior_factor_returns_by_name.values() if series]
    inputs: list[FactorContributionInput] = []

    for spec in factor_specs:
        gate = max(0.0, min(1.0, spec.gate))
        if gate == 0:
            continue
        residual_returns, condition_number, residualized_against = residualize_factor_returns(
            target_returns=spec.raw_returns,
            prior_returns=prior_series,
            estimation_window=estimation_window,
        )
        paired = paired_estimation_returns(
            stock_returns=stock_returns,
            factor_returns=residual_returns,
            estimation_window=estimation_window,
        )
        if len(paired) < min_observations:
            prior_series.append(residual_returns)
            continue
        beta = simple_beta(y=[item[0] for item in paired], x=[item[1] for item in paired])
        factor_move = attribution_factor_move(
            factor_returns=residual_returns,
            attribution_window=attribution_window,
        )
        contribution_bps = float(beta * factor_move * gate)
        if not finite_bps(contribution_bps) or not math.isfinite(beta) or not math.isfinite(factor_move):
            prior_series.append(residual_returns)
            continue
        confidence = confidence_from_penalties(
            penalties=standard_factor_penalties(
                observations=len(paired),
                min_observations=min_observations,
            )
        )
        if condition_number > 30:
            confidence = ConfidenceLevel.LOW_MEDIUM
        inputs.append(
            FactorContributionInput(
                security_id=security_id,
                driver=spec.driver,
                name=spec.display_name,
                contribution_bps=contribution_bps,
                confidence=confidence,
                factor_move=factor_move,
                factor_move_unit="residualized_bps",
                exposure_value=beta,
                exposure_unit="beta",
                evidence=[
                    f"beta={beta:.4f}",
                    f"residualized_factor_return_bps={factor_move:.4f}",
                    f"observations={len(paired)}",
                    f"condition_number={condition_number:.4f}",
                    f"model={MODEL_VERSION}",
                ],
                evidence_payload={
                    "factor_name": spec.factor_name,
                    "raw_factor_name": spec.factor_name,
                    "residualized_against": residualized_against,
                    "hierarchy_version": MODEL_VERSION,
                    "beta": beta,
                    "factor_move_bps": factor_move,
                    "observations": len(paired),
                    "condition_number": condition_number,
                    "exposure_gate": gate,
                    "model_version": MODEL_VERSION,
                },
                event_time=attribution_window.end,
                ingestion_time=attribution_cutoff,
                timestamp_available=attribution_cutoff,
            )
        )
        prior_series.append(residual_returns)
    return inputs


def residualize_factor_returns(
    *,
    target_returns: dict[datetime, float],
    prior_returns: list[dict[datetime, float]],
    estimation_window: TimeWindow,
) -> tuple[dict[datetime, float], float, list[str]]:
    if not prior_returns:
        return dict(target_returns), 0.0, []

    estimation_dates = [
        event_time
        for event_time in sorted(target_returns)
        if estimation_window.start <= event_time < estimation_window.end
        and all(event_time in series for series in prior_returns)
    ]
    if len(estimation_dates) <= len(prior_returns) + 1:
        return dict(target_returns), 0.0, []

    y = np.array([target_returns[event_time] for event_time in estimation_dates], dtype=float)
    x = np.array(
        [[series[event_time] for series in prior_returns] for event_time in estimation_dates],
        dtype=float,
    )
    design = np.column_stack([np.ones(len(estimation_dates)), x])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    condition_number = float(np.linalg.cond(x)) if x.size else 0.0

    residualized: dict[datetime, float] = {}
    for event_time, target_value in target_returns.items():
        if all(event_time in series for series in prior_returns):
            vector = np.array([1.0, *[series[event_time] for series in prior_returns]], dtype=float)
            residualized[event_time] = float(target_value - vector.dot(coefficients))
    return residualized, condition_number, [f"prior_layer_{index}" for index in range(len(prior_returns))]

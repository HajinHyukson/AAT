from __future__ import annotations

from datetime import datetime
from uuid import UUID

from engine.confidence.scoring import confidence_from_penalties, standard_factor_penalties
from engine.contracts import DriverType, FactorContributionInput, PriceBar, TimeWindow
from engine.factors.regression import (
    attribution_factor_move,
    paired_estimation_returns,
    simple_beta,
    visible_stock_returns,
)


MODEL_VERSION = "macro-factor-v0"


def level_changes_by_date(values_by_date: dict[datetime, float], multiplier: float = 1.0) -> dict[datetime, float]:
    dates = sorted(values_by_date)
    changes: dict[datetime, float] = {}
    for previous, current in zip(dates, dates[1:], strict=False):
        changes[current] = (values_by_date[current] - values_by_date[previous]) * multiplier
    return changes


def spread_by_date(
    *,
    long_values_by_date: dict[datetime, float],
    short_values_by_date: dict[datetime, float],
) -> dict[datetime, float]:
    return {
        event_time: long_values_by_date[event_time] - short_values_by_date[event_time]
        for event_time in long_values_by_date
        if event_time in short_values_by_date
    }


def percent_returns_by_date(values_by_date: dict[datetime, float]) -> dict[datetime, float]:
    dates = sorted(values_by_date)
    returns: dict[datetime, float] = {}
    for previous, current in zip(dates, dates[1:], strict=False):
        previous_value = values_by_date[previous]
        if previous_value != 0:
            returns[current] = ((values_by_date[current] / previous_value) - 1.0) * 10_000
    return returns


def build_macro_factor_inputs(
    *,
    security_id: UUID,
    price_bars: list[PriceBar],
    macro_factor_moves_by_name: dict[str, dict[datetime, float]],
    estimation_window: TimeWindow,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
    exposure_gate_by_name: dict[str, float] | None = None,
    min_observations: int = 20,
) -> list[FactorContributionInput]:
    stock_returns = visible_stock_returns(
        security_id=security_id,
        price_bars=price_bars,
        estimation_window=estimation_window,
        attribution_window=attribution_window,
        attribution_cutoff=attribution_cutoff,
    )
    exposure_gate_by_name = exposure_gate_by_name or {}
    inputs: list[FactorContributionInput] = []
    for factor_name, factor_moves in macro_factor_moves_by_name.items():
        paired = paired_estimation_returns(
            stock_returns=stock_returns,
            factor_returns=factor_moves,
            estimation_window=estimation_window,
        )
        if len(paired) < min_observations:
            continue
        gate = max(0.0, min(1.0, exposure_gate_by_name.get(factor_name, 1.0)))
        if gate == 0:
            continue
        beta = simple_beta(y=[item[0] for item in paired], x=[item[1] for item in paired])
        factor_move = attribution_factor_move(
            factor_returns=factor_moves,
            attribution_window=attribution_window,
        )
        contribution_bps = beta * factor_move * gate
        confidence = confidence_from_penalties(
            penalties=standard_factor_penalties(
                observations=len(paired),
                min_observations=min_observations,
            )
        )
        inputs.append(
            FactorContributionInput(
                security_id=security_id,
                driver=DriverType.MACRO,
                name=f"Macro factor ({factor_name})",
                contribution_bps=contribution_bps,
                confidence=confidence,
                factor_move=factor_move,
                factor_move_unit="factor_units",
                exposure_value=beta,
                exposure_unit="beta",
                evidence=[
                    f"beta={beta:.4f}",
                    f"factor_move={factor_move:.4f}",
                    f"exposure_gate={gate:.4f}",
                    f"observations={len(paired)}",
                    f"model={MODEL_VERSION}",
                ],
                evidence_payload={
                    "factor_name": factor_name,
                    "beta": beta,
                    "factor_move": factor_move,
                    "exposure_gate": gate,
                    "observations": len(paired),
                    "model_version": MODEL_VERSION,
                },
                event_time=attribution_window.end,
                ingestion_time=attribution_cutoff,
                timestamp_available=attribution_cutoff,
            )
        )
    return inputs

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


MODEL_VERSION = "sector-factor-v0"


def build_sector_factor_inputs(
    *,
    security_id: UUID,
    price_bars: list[PriceBar],
    factor_returns_by_name: dict[str, dict[datetime, float]],
    estimation_window: TimeWindow,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
    min_observations: int = 10,
) -> list[FactorContributionInput]:
    stock_returns = visible_stock_returns(
        security_id=security_id,
        price_bars=price_bars,
        estimation_window=estimation_window,
        attribution_window=attribution_window,
        attribution_cutoff=attribution_cutoff,
    )
    inputs: list[FactorContributionInput] = []
    for factor_name, factor_returns in factor_returns_by_name.items():
        paired = paired_estimation_returns(
            stock_returns=stock_returns,
            factor_returns=factor_returns,
            estimation_window=estimation_window,
        )
        if len(paired) < min_observations:
            continue
        beta = simple_beta(y=[item[0] for item in paired], x=[item[1] for item in paired])
        factor_move = attribution_factor_move(
            factor_returns=factor_returns,
            attribution_window=attribution_window,
        )
        contribution_bps = beta * factor_move
        confidence = confidence_from_penalties(
            penalties=standard_factor_penalties(
                observations=len(paired),
                min_observations=min_observations,
            )
        )
        inputs.append(
            FactorContributionInput(
                security_id=security_id,
                driver=DriverType.SECTOR,
                name=f"Sector/industry factor ({factor_name})",
                contribution_bps=contribution_bps,
                confidence=confidence,
                factor_move=factor_move,
                factor_move_unit="bps",
                exposure_value=beta,
                exposure_unit="beta",
                evidence=[
                    f"beta={beta:.4f}",
                    f"factor_return_bps={factor_move:.4f}",
                    f"observations={len(paired)}",
                    f"model={MODEL_VERSION}",
                ],
                evidence_payload={
                    "factor_name": factor_name,
                    "beta": beta,
                    "factor_move_bps": factor_move,
                    "observations": len(paired),
                    "model_version": MODEL_VERSION,
                },
                event_time=attribution_window.end,
                ingestion_time=attribution_cutoff,
                timestamp_available=attribution_cutoff,
            )
        )
    return inputs

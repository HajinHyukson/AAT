from __future__ import annotations

from datetime import datetime
from uuid import UUID

import numpy as np

from engine.contracts import ConfidenceLevel, DriverType, FactorContributionInput, PriceBar, TimeWindow
from engine.factors.market_model import _daily_returns_bps
from engine.time import is_point_in_time_visible


FRENCH_FACTOR_NAMES = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")
FACTOR_DRIVER_MAP = {
    "Mkt-RF": DriverType.MARKET,
    "SMB": DriverType.STYLE,
    "HML": DriverType.STYLE,
    "RMW": DriverType.STYLE,
    "CMA": DriverType.STYLE,
}


def build_french_factor_inputs(
    *,
    security_id: UUID,
    price_bars: list[PriceBar],
    factor_returns_by_name: dict[str, dict[datetime, float]],
    estimation_window: TimeWindow,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
    factor_names: tuple[str, ...] = FRENCH_FACTOR_NAMES,
    min_observations: int | None = None,
) -> list[FactorContributionInput]:
    visible_bars = [
        bar
        for bar in price_bars
        if bar.security_id == security_id
        and estimation_window.start <= bar.event_time <= attribution_window.end
        and is_point_in_time_visible(bar, attribution_cutoff)
    ]
    visible_bars.sort(key=lambda bar: bar.event_time)
    if len(visible_bars) < len(factor_names) + 2:
        return []

    stock_returns = _daily_returns_bps(visible_bars)
    paired_dates = [
        event_time
        for event_time in stock_returns
        if estimation_window.start <= event_time < attribution_window.start
        and all(event_time in factor_returns_by_name.get(name, {}) for name in factor_names)
    ]
    required_observations = min_observations or max(10, len(factor_names) * 2)
    if len(paired_dates) < required_observations:
        return []

    y = np.array([stock_returns[event_time] for event_time in paired_dates], dtype=float)
    x = np.array(
        [
            [factor_returns_by_name[name][event_time] for name in factor_names]
            for event_time in paired_dates
        ],
        dtype=float,
    )
    design = np.column_stack([np.ones(len(paired_dates)), x])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    betas = coefficients[1:]

    condition_number = float(np.linalg.cond(x)) if x.size else 0.0
    confidence = ConfidenceLevel.LOW_MEDIUM if condition_number > 30 else ConfidenceLevel.MEDIUM

    inputs: list[FactorContributionInput] = []
    for factor_name, beta in zip(factor_names, betas, strict=True):
        attribution_factor_return = sum(
            factor_return
            for event_time, factor_return in factor_returns_by_name.get(factor_name, {}).items()
            if attribution_window.start < event_time <= attribution_window.end
        )
        contribution_bps = float(beta * attribution_factor_return)
        inputs.append(
            FactorContributionInput(
                security_id=security_id,
                driver=FACTOR_DRIVER_MAP[factor_name],
                name=f"French factor ({factor_name})",
                contribution_bps=contribution_bps,
                confidence=confidence,
                evidence=[
                    f"beta={beta:.4f}",
                    f"factor_return_bps={attribution_factor_return:.4f}",
                    f"observations={len(paired_dates)}",
                    f"condition_number={condition_number:.4f}",
                ],
                event_time=attribution_window.end,
                ingestion_time=attribution_cutoff,
                timestamp_available=attribution_cutoff,
            )
        )
    return inputs

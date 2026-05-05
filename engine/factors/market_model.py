from __future__ import annotations

from datetime import datetime
from statistics import mean
from uuid import UUID

from engine.contracts import ConfidenceLevel, DriverType, FactorContributionInput, PriceBar, TimeWindow
from engine.time import is_point_in_time_visible


def build_market_factor_input(
    *,
    security_id: UUID,
    price_bars: list[PriceBar],
    market_factor_returns: dict[datetime, float],
    estimation_window: TimeWindow,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
    factor_name: str = "Mkt-RF",
) -> FactorContributionInput | None:
    visible_bars = [
        bar
        for bar in price_bars
        if bar.security_id == security_id
        and estimation_window.start <= bar.event_time <= attribution_window.end
        and is_point_in_time_visible(bar, attribution_cutoff)
    ]
    visible_bars.sort(key=lambda bar: bar.event_time)
    if len(visible_bars) < 3:
        return None

    stock_returns = _daily_returns_bps(visible_bars)
    paired = [
        (stock_return, market_factor_returns[event_time])
        for event_time, stock_return in stock_returns.items()
        if estimation_window.start <= event_time < attribution_window.start
        and event_time in market_factor_returns
    ]
    if len(paired) < 5:
        return None

    beta = _ols_beta(y=[item[0] for item in paired], x=[item[1] for item in paired])
    attribution_factor_return = sum(
        factor_return
        for event_time, factor_return in market_factor_returns.items()
        if attribution_window.start < event_time <= attribution_window.end
    )
    contribution_bps = beta * attribution_factor_return

    return FactorContributionInput(
        security_id=security_id,
        driver=DriverType.MARKET,
        name=f"Market factor ({factor_name})",
        contribution_bps=contribution_bps,
        confidence=ConfidenceLevel.MEDIUM,
        evidence=[
            f"beta={beta:.4f}",
            f"factor_return_bps={attribution_factor_return:.4f}",
            f"observations={len(paired)}",
        ],
        event_time=attribution_window.end,
        ingestion_time=attribution_cutoff,
        timestamp_available=attribution_cutoff,
    )


def _daily_returns_bps(bars: list[PriceBar]) -> dict[datetime, float]:
    returns: dict[datetime, float] = {}
    for previous, current in zip(bars, bars[1:], strict=False):
        returns[current.event_time] = ((current.adjusted_close / previous.adjusted_close) - 1.0) * 10_000
    return returns


def _ols_beta(*, y: list[float], x: list[float]) -> float:
    x_mean = mean(x)
    y_mean = mean(y)
    variance = sum((value - x_mean) ** 2 for value in x)
    if variance == 0:
        return 0.0
    covariance = sum(
        (x_value - x_mean) * (y_value - y_mean)
        for x_value, y_value in zip(x, y, strict=True)
    )
    return covariance / variance

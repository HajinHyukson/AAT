from __future__ import annotations

from datetime import datetime
from statistics import mean

from engine.contracts import PriceBar, TimeWindow
from engine.factors.market_model import _daily_returns_bps
from engine.time import is_point_in_time_visible


def visible_stock_returns(
    *,
    security_id,
    price_bars: list[PriceBar],
    estimation_window: TimeWindow,
    attribution_window: TimeWindow,
    attribution_cutoff: datetime,
) -> dict[datetime, float]:
    visible_bars = [
        bar
        for bar in price_bars
        if bar.security_id == security_id
        and estimation_window.start <= bar.event_time <= attribution_window.end
        and is_point_in_time_visible(bar, attribution_cutoff)
    ]
    visible_bars.sort(key=lambda bar: bar.event_time)
    return _daily_returns_bps(visible_bars)


def simple_beta(*, y: list[float], x: list[float]) -> float:
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


def paired_estimation_returns(
    *,
    stock_returns: dict[datetime, float],
    factor_returns: dict[datetime, float],
    estimation_window: TimeWindow,
) -> list[tuple[float, float]]:
    return [
        (stock_return, factor_returns[event_time])
        for event_time, stock_return in stock_returns.items()
        if estimation_window.start <= event_time < estimation_window.end
        and event_time in factor_returns
    ]


def attribution_factor_move(
    *,
    factor_returns: dict[datetime, float],
    attribution_window: TimeWindow,
) -> float:
    return sum(
        factor_return
        for event_time, factor_return in factor_returns.items()
        if attribution_window.start < event_time <= attribution_window.end
    )

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from engine.contracts import DriverType, PriceBar, TimeWindow
from engine.factors.market_model import build_market_factor_input


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_market_factor_input_estimates_beta_and_contribution() -> None:
    security_id = uuid4()
    bars = []
    price = 100.0
    market_returns = {}
    for offset, market_bps in enumerate([10, -5, 20, -10, 15, 5, 7, -3], start=1):
        event_time = dt(offset)
        if offset > 1:
            price *= 1 + (2 * market_bps) / 10_000
            market_returns[event_time] = market_bps
        bars.append(
            PriceBar(
                security_id=security_id,
                event_time=event_time,
                ingestion_time=event_time,
                timestamp_available=event_time,
                close=price,
                adjusted_close=price,
            )
        )

    result = build_market_factor_input(
        security_id=security_id,
        price_bars=bars,
        market_factor_returns=market_returns,
        estimation_window=TimeWindow(start=dt(1), end=dt(7)),
        attribution_window=TimeWindow(start=dt(7), end=dt(8)),
        attribution_cutoff=dt(9),
    )

    assert result is not None
    assert result.driver == DriverType.MARKET
    assert result.contribution_bps == pytest.approx(-6)

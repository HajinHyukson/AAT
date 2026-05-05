from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from engine.contracts import DriverType, PriceBar, TimeWindow
from engine.factors.french_model import FRENCH_FACTOR_NAMES, build_french_factor_inputs


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_french_factor_inputs_estimate_multiple_factor_contributions() -> None:
    security_id = uuid4()
    bars = []
    price = 100.0
    factor_returns = {name: {} for name in FRENCH_FACTOR_NAMES}
    coefficients = {
        "Mkt-RF": 1.2,
        "SMB": 0.5,
        "HML": -0.25,
        "RMW": 0.1,
        "CMA": -0.4,
    }
    factor_rows = [
        (10, 2, -3, 1, 4),
        (-8, 1, 2, -2, 0),
        (12, -4, 1, 3, -2),
        (-3, 5, 4, -1, 2),
        (7, -2, -5, 2, 1),
        (2, 3, 0, -3, -1),
        (-6, -1, 3, 4, 2),
        (9, 0, -2, 1, -4),
        (4, -5, 5, 2, 3),
        (-2, 4, -1, -2, 1),
        (6, 1, 2, 3, -3),
        (5, -2, 1, 0, 2),
        (5, 1, -1, 2, 0),
    ]
    for offset, row in enumerate(factor_rows, start=1):
        event_time = dt(offset)
        for name, value in zip(FRENCH_FACTOR_NAMES, row, strict=True):
            factor_returns[name][event_time] = value
        if offset > 1:
            stock_return = sum(coefficients[name] * value for name, value in zip(FRENCH_FACTOR_NAMES, row, strict=True))
            price *= 1 + stock_return / 10_000
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

    inputs = build_french_factor_inputs(
        security_id=security_id,
        price_bars=bars,
        factor_returns_by_name=factor_returns,
        estimation_window=TimeWindow(start=dt(1), end=dt(12)),
        attribution_window=TimeWindow(start=dt(12), end=dt(13)),
        attribution_cutoff=dt(14),
    )

    assert len(inputs) == 5
    assert {item.driver for item in inputs} == {DriverType.MARKET, DriverType.STYLE}
    market_input = next(item for item in inputs if item.name.endswith("(Mkt-RF)"))
    assert market_input.contribution_bps == pytest.approx(6.0, abs=0.2)

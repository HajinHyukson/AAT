from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from engine.contracts import PriceBar, TimeWindow
from engine.returns.accounting import close_to_close_return_bps


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_close_to_close_return_uses_adjusted_prices() -> None:
    security_id = uuid4()
    result = close_to_close_return_bps(
        security_id=security_id,
        window=TimeWindow(start=dt(1), end=dt(2)),
        attribution_cutoff=dt(3),
        bars=[
            PriceBar(
                security_id=security_id,
                event_time=dt(1),
                ingestion_time=dt(1),
                timestamp_available=dt(1),
                close=100,
                adjusted_close=50,
            ),
            PriceBar(
                security_id=security_id,
                event_time=dt(2),
                ingestion_time=dt(2),
                timestamp_available=dt(2),
                close=120,
                adjusted_close=60,
            ),
        ],
    )

    assert result == pytest.approx(2_000)


def test_close_to_close_return_excludes_future_available_bars() -> None:
    security_id = uuid4()

    with pytest.raises(ValueError, match="at least two"):
        close_to_close_return_bps(
            security_id=security_id,
            window=TimeWindow(start=dt(1), end=dt(2)),
            attribution_cutoff=dt(2),
            bars=[
                PriceBar(
                    security_id=security_id,
                    event_time=dt(1),
                    ingestion_time=dt(1),
                    timestamp_available=dt(1),
                    close=100,
                    adjusted_close=100,
                ),
                PriceBar(
                    security_id=security_id,
                    event_time=dt(2),
                    ingestion_time=dt(2),
                    timestamp_available=dt(3),
                    close=101,
                    adjusted_close=101,
                ),
            ],
        )

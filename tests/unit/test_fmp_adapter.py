from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from adapters.fmp.client import parse_historical_prices


def test_parse_historical_prices_sorts_and_maps_adjusted_close() -> None:
    payload = [
        {
            "date": "2026-01-03",
            "open": 102,
            "high": 103,
            "low": 101,
            "close": 102,
            "adjClose": 101.5,
            "volume": 2_000,
        },
        {
            "date": "2026-01-02",
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "adjClose": 99.5,
            "volume": 1_000,
        },
    ]
    ingestion_time = datetime(2026, 1, 4, tzinfo=timezone.utc)

    bars = parse_historical_prices(payload, ticker="aapl", ingestion_time=ingestion_time)

    assert [bar.event_time.day for bar in bars] == [2, 3]
    assert bars[0].ticker == "AAPL"
    assert bars[0].adjusted_close == Decimal("99.5")
    assert bars[0].timestamp_available == ingestion_time

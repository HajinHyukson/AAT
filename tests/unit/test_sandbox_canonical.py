from __future__ import annotations

import polars as pl
from datetime import date, datetime, timezone

from viza_sandbox.canonical import (
    InMemoryCanonicalSource,
    PostgresCanonicalSource,
    price_bar_t,
    security_t,
    security_ticker_history_t,
    faustcalc_company_t,
)


def _prices():
    return pl.DataFrame(
        {
            "security_id": ["a", "a", "b"],
            "event_date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 2)],
            "close": [10.0, 11.0, 5.0],
            "adjusted_close": [10.0, 11.0, 5.0],
            "volume": [100, 110, 50],
            "currency": ["USD"] * 3,
            "ingestion_time": [datetime(2024, 5, 1, tzinfo=timezone.utc)] * 3,
        }
    )


def test_in_memory_filters_range_and_reports_snapshot():
    src = InMemoryCanonicalSource(
        pl.DataFrame(
            {
                "security_id": ["a", "b"],
                "ticker": ["AAA", "BBB"],
                "exchange": ["NYSE"] * 2,
                "currency": ["USD"] * 2,
                "sector": [None, "Tech"],
                "industry": [None, "Chips"],
                "classification_as_of": [None, None],
            }
        ),
        _prices(),
    )
    out = src.price_bars(date(2024, 1, 3), date(2024, 1, 3))
    assert out["security_id"].to_list() == ["a"]
    assert src.snapshot_id() == "2024-05-01T00:00:00+00:00"


def test_lightweight_tables_match_canonical_column_names():
    from db import models

    for table, model in [
        (price_bar_t, models.PriceBar),
        (security_t, models.Security),
        (security_ticker_history_t, models.SecurityTickerHistory),
        (faustcalc_company_t, models.FaustcalcCompany),
    ]:
        assert set(table.c.keys()) <= set(model.__table__.c.keys())


def test_postgres_source_reads_through_sqlite_schema(tmp_path):
    url = f"sqlite:///{tmp_path/'canon.db'}"
    src = PostgresCanonicalSource(url)
    src.create_tables_for_tests()
    src.insert_for_tests(
        security_t,
        [
            {
                "security_id": "a",
                "company_id": "c",
                "exchange": "NYSE",
                "active_from": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "active_to": None,
            }
        ],
    )
    src.insert_for_tests(
        security_ticker_history_t,
        [
            {
                "ticker_history_id": "t1",
                "security_id": "a",
                "ticker": "AAA",
                "active_from": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "active_to": None,
            }
        ],
    )
    src.insert_for_tests(
        faustcalc_company_t,
        [
            {
                "faustcalc_company_id": "f1",
                "source_ticker": "AAA",
                "canonical_ticker": "AAA",
                "sector": "Tech",
                "industry": "Chips",
                "source_last_updated": datetime(2024, 5, 1, tzinfo=timezone.utc),
            }
        ],
    )
    src.insert_for_tests(
        price_bar_t,
        [
            {
                "price_bar_id": "p1",
                "security_id": "a",
                "event_time": datetime(2024, 1, 2, tzinfo=timezone.utc),
                "ingestion_time": datetime(2024, 5, 1, tzinfo=timezone.utc),
                "timestamp_available": datetime(2024, 5, 1, tzinfo=timezone.utc),
                "close": 10.0,
                "adjusted_close": 10.0,
                "volume": 100,
                "currency": "USD",
                "source": "faustcalc_fmp_snapshot",
            }
        ],
    )
    secs = src.securities()
    first = secs.row(0, named=True)
    assert first["ticker"] == "AAA" and first["sector"] == "Tech"
    bars = src.price_bars(date(2024, 1, 1), date(2024, 1, 31))
    assert bars["event_date"].to_list() == [date(2024, 1, 2)]

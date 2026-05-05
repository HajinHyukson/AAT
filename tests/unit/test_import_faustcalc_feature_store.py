from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from jobs.import_faustcalc_feature_store import (
    build_asset_value,
    build_price_value,
    month_chunks,
    run_feature_store_import,
)


def test_build_asset_value_normalizes_ticker_and_currency_defaults() -> None:
    value = build_asset_value(
        import_run_id=uuid4(),
        row={
            "ticker": "brk-b",
            "ticker_local": None,
            "company_name_en": "Berkshire Hathaway Inc.",
            "company_name_ko": None,
            "ticker_display": "BRK-B",
            "asset_type": "equity",
            "exchange": "NYSE",
            "market": "US",
            "currency": None,
            "is_active": True,
            "created_at": None,
            "last_updated": None,
        },
    )

    assert value["source_ticker"] == "BRK-B"
    assert value["canonical_ticker"] == "BRK.B"
    assert value["currency"] == "USD"


def test_build_price_value_preserves_granularity_and_rejects_invalid_prices() -> None:
    value = build_price_value(
        import_run_id=uuid4(),
        row={
            "id": 101,
            "ticker": "brk-b",
            "date": "2026-04-03",
            "close": Decimal("356.12"),
            "volume": 1234567,
        },
    )

    assert value["source_price_id"] == 101
    assert value["source_ticker"] == "BRK-B"
    assert value["canonical_ticker"] == "BRK.B"
    assert value["price_date"] == date(2026, 4, 3)
    assert value["close"] == 356.12
    assert value["volume"] == 1234567
    assert value["currency"] == "USD"

    with pytest.raises(ValueError, match="non-positive"):
        build_price_value(
            import_run_id=uuid4(),
            row={"id": 102, "ticker": "AAPL", "date": "2026-04-03", "close": 0},
        )


def test_dry_run_inventory_reads_source_counts_without_aat_writes() -> None:
    source_engine = create_engine("sqlite+pysqlite:///:memory:")
    with source_engine.begin() as conn:
        conn.execute(text("CREATE TABLE assets (id INTEGER PRIMARY KEY, ticker TEXT)"))
        conn.execute(text("INSERT INTO assets (id, ticker) VALUES (1, 'AAPL')"))
        conn.execute(
            text("CREATE TABLE prices (id INTEGER PRIMARY KEY, ticker TEXT, date TEXT, close REAL)")
        )
        conn.execute(
            text(
                "INSERT INTO prices (id, ticker, date, close) "
                "VALUES (1, 'AAPL', '2026-04-02', 100.0), "
                "(2, 'MSFT', '2026-04-03', 200.0)"
            )
        )

    report = run_feature_store_import(
        source_engine=source_engine,
        tables=("assets", "prices"),
        dry_run=True,
    )

    assert report.import_run_id is None
    assert report.staged_counts == {}
    assert report.source_counts["assets"]["rows"] == 1
    assert report.source_counts["prices"] == {
        "rows": 2,
        "min_date": "2026-04-02",
        "max_date": "2026-04-03",
        "tickers": 2,
    }


def test_month_chunks_cover_inclusive_source_date_range() -> None:
    assert list(month_chunks(date(2026, 1, 30), date(2026, 3, 1))) == [
        (date(2026, 1, 1), date(2026, 2, 1)),
        (date(2026, 2, 1), date(2026, 3, 1)),
        (date(2026, 3, 1), date(2026, 4, 1)),
    ]

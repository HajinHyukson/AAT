from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from jobs.import_acquin_snapshot import (
    TABLE_SPECS,
    _map_flow,
    _map_index,
    _map_price,
    _map_stock,
    import_acquin_snapshot,
)
from jobs.run_attribution import DEFAULT_MARKET_FACTOR_NAME, market_factor_basket_version


RUN_ID = uuid.uuid4()
CREATED = datetime(2026, 6, 9, 7, 22, 3)


def test_map_stock_normalizes_ticker_and_keeps_raw_payload() -> None:
    mapped = _map_stock(
        {
            "ticker": " 005930 ",
            "market": "KOSPI",
            "is_preferred": False,
            "is_active": True,
            "created_at": CREATED,
            "updated_at": CREATED,
        },
        RUN_ID,
    )

    assert mapped["ticker"] == "005930"
    assert mapped["source_created_at"].tzinfo == timezone.utc
    assert mapped["raw_payload"]["market"] == "KOSPI"


def test_map_price_carries_staging_only_columns() -> None:
    mapped = _map_price(
        {
            "ticker": "005930",
            "date": date(2026, 6, 9),
            "open": 310000.0,
            "high": 323000.0,
            "low": 309500.0,
            "close": 322000.0,
            "adj_close": 322000.0,
            "volume": 28989253.0,
            "trading_value": 9334539466000.0,
            "market_cap": 1882501711776000.0,
            "shares_outstanding": 5969782550.0,
            "return_1d": 0.0897,
            "source": "pykrx",
            "freshness_state": "FINAL_EOD",
            "created_at": CREATED,
            "updated_at": CREATED,
        },
        RUN_ID,
    )

    assert mapped["price_date"] == date(2026, 6, 9)
    assert mapped["market_cap"] == 1882501711776000.0
    assert mapped["acquin_import_run_id"] == RUN_ID


def test_map_flow_and_index_use_natural_keys() -> None:
    flow = _map_flow(
        {
            "ticker": "005930",
            "date": date(2026, 6, 9),
            "investor_group": "foreign",
            "buy_volume": 1.0,
            "sell_volume": 2.0,
            "net_buy_volume": -1.0,
            "buy_amount": 100.0,
            "sell_amount": 200.0,
            "net_buy_amount": -100.0,
            "source": "pykrx",
            "freshness_state": "FINAL_EOD",
            "created_at": CREATED,
            "updated_at": CREATED,
        },
        RUN_ID,
    )
    index = _map_index(
        {
            "index_code": "1001",
            "date": date(2026, 6, 9),
            "name": "코스피",
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "return_1d": 0.01,
            "source": "pykrx",
            "freshness_state": "FINAL_EOD",
            "created_at": CREATED,
            "updated_at": CREATED,
        },
        RUN_ID,
    )

    assert flow["investor_group"] == "foreign"
    assert flow["flow_date"] == date(2026, 6, 9)
    assert index["index_code"] == "1001"
    assert index["index_date"] == date(2026, 6, 9)


def test_table_specs_cover_all_acquin_source_tables() -> None:
    assert [spec.name for spec in TABLE_SPECS] == [
        "dim_stock",
        "fact_price_daily",
        "fact_investor_flow_daily",
        "fact_foreign_holding_daily",
        "fact_index_daily",
    ]


def test_import_fails_closed_in_production_without_license(monkeypatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ACQUIN_PYKRX_PRODUCTION_LICENSE_CONFIRMED", raising=False)

    with pytest.raises(RuntimeError, match="ACQUIN_PYKRX_PRODUCTION_LICENSE_CONFIRMED"):
        import_acquin_snapshot(dry_run=True)


def test_market_factor_basket_version_is_backward_compatible() -> None:
    assert market_factor_basket_version(DEFAULT_MARKET_FACTOR_NAME) == "french_market_v0"
    assert market_factor_basket_version("kospi_market") == "market_kospi_market_v0"

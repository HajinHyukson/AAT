from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from engine.contracts import TimeWindow


SECTOR_PROXY_TICKERS = {
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Information Technology": "XLK",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}

INDUSTRY_PROXY_TICKERS = {
    "Semiconductors": "SMH",
    "Banks": "KBE",
    "Biotechnology": "XBI",
    "Pharmaceuticals": "XLV",
    "Software": "IGV",
    "Broadline Retail": "XRT",
    "Specialty Retail": "XRT",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build sector/industry factor returns from proxy price bars")
    parser.add_argument("--from", dest="start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    window = TimeWindow(
        start=_date_to_utc_datetime(date.fromisoformat(args.start)),
        end=_date_to_utc_datetime(date.fromisoformat(args.end)),
    )
    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        count = build_proxy_factor_returns(session=session, window=window)

    print(f"built {count} proxy factor return rows")


def build_proxy_factor_returns(*, session, window: TimeWindow) -> int:
    count = 0
    for sector, ticker in SECTOR_PROXY_TICKERS.items():
        count += _upsert_proxy_returns(
            session=session,
            ticker=ticker,
            factor_name=f"sector:{sector}",
            factor_family="sector",
            window=window,
        )
    for industry, ticker in INDUSTRY_PROXY_TICKERS.items():
        count += _upsert_proxy_returns(
            session=session,
            ticker=ticker,
            factor_name=f"industry:{industry}",
            factor_family="sector",
            window=window,
        )
    return count


def _upsert_proxy_returns(*, session, ticker: str, factor_name: str, factor_family: str, window: TimeWindow) -> int:
    security_id = session.execute(
        select(models.Security.security_id)
        .join(models.SecurityTickerHistory, models.Security.security_id == models.SecurityTickerHistory.security_id)
        .where(models.SecurityTickerHistory.ticker == ticker)
        .where(models.SecurityTickerHistory.active_to.is_(None))
    ).scalar_one_or_none()
    if security_id is None:
        return 0
    bars = list(
        session.execute(
            select(models.PriceBar)
            .where(models.PriceBar.security_id == security_id)
            .where(models.PriceBar.event_time >= window.start)
            .where(models.PriceBar.event_time <= window.end)
            .order_by(models.PriceBar.event_time)
        ).scalars()
    )
    count = 0
    for previous, current in zip(bars, bars[1:], strict=False):
        return_bps = ((float(current.adjusted_close) / float(previous.adjusted_close)) - 1.0) * 10_000
        stmt = insert(models.FactorReturn).values(
            factor_name=factor_name,
            factor_family=factor_family,
            return_bps=return_bps,
            source=f"proxy_price:{ticker}",
            event_time=current.event_time,
            ingestion_time=current.ingestion_time,
            timestamp_available=current.timestamp_available,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_factor_return_source_time",
            set_={
                "return_bps": stmt.excluded.return_bps,
                "factor_family": stmt.excluded.factor_family,
                "ingestion_time": stmt.excluded.ingestion_time,
                "timestamp_available": stmt.excluded.timestamp_available,
            },
        )
        session.execute(stmt)
        count += 1
    return count


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()

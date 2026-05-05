from __future__ import annotations

import argparse
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from adapters.fmp.client import FmpHistoricalPriceBar, fetch_historical_prices
from adapters.source_policy import require_confirmed_production_source
from db import models
from db.session import session_scope


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest FMP historical daily prices")
    parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--from", dest="start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--company-name", help="Legal/company display name")
    parser.add_argument("--exchange", default="UNKNOWN")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    require_confirmed_production_source(
        source_name="FMP price data",
        env_var="FMP_PRODUCTION_LICENSE_CONFIRMED",
    )
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    ingestion_time = datetime.now(timezone.utc)
    bars = fetch_historical_prices(
        ticker=ticker,
        start=start,
        end=end,
        ingestion_time=ingestion_time,
    )

    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        security = ensure_security(
            ticker=ticker,
            company_name=args.company_name or ticker,
            exchange=args.exchange,
            first_seen=ingestion_time,
            session=session,
        )
        upsert_price_bars(session=session, security_id=security.security_id, bars=bars)

    print(f"ingested {len(bars)} FMP price bars for {ticker}")


def ensure_security(
    *,
    ticker: str,
    company_name: str,
    exchange: str,
    first_seen: datetime,
    session,
) -> models.Security:
    existing = session.execute(
        select(models.Security)
        .join(
            models.SecurityTickerHistory,
            models.Security.security_id == models.SecurityTickerHistory.security_id,
        )
        .where(models.SecurityTickerHistory.ticker == ticker)
        .where(models.SecurityTickerHistory.active_to.is_(None))
        .order_by(models.SecurityTickerHistory.active_from.desc())
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    company = models.Company(
        company_id=uuid.uuid4(),
        cik=None,
        legal_name=company_name,
        created_at=first_seen,
    )
    security = models.Security(
        security_id=uuid.uuid4(),
        company=company,
        figi=None,
        isin=None,
        cusip=None,
        exchange=exchange,
        share_class=None,
        active_from=first_seen,
        active_to=None,
    )
    session.add_all([company, security])
    session.flush()
    ticker_history = models.SecurityTickerHistory(
        ticker_history_id=uuid.uuid4(),
        security_id=security.security_id,
        ticker=ticker,
        active_from=first_seen,
        active_to=None,
    )
    session.add(ticker_history)
    session.flush()
    return security


def upsert_price_bars(
    *,
    session,
    security_id: uuid.UUID,
    bars: list[FmpHistoricalPriceBar],
) -> None:
    for bar in bars:
        stmt = insert(models.PriceBar).values(
            price_bar_id=uuid.uuid4(),
            security_id=security_id,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            adjusted_close=bar.adjusted_close,
            volume=bar.volume,
            currency=bar.currency,
            source=bar.source,
            event_time=bar.event_time,
            ingestion_time=bar.ingestion_time,
            timestamp_available=bar.timestamp_available,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_price_bar_source_time",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "adjusted_close": stmt.excluded.adjusted_close,
                "volume": stmt.excluded.volume,
                "currency": stmt.excluded.currency,
                "ingestion_time": stmt.excluded.ingestion_time,
                "timestamp_available": stmt.excluded.timestamp_available,
            },
        )
        session.execute(stmt)


if __name__ == "__main__":
    main()

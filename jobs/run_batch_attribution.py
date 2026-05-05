from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, time, timezone

from sqlalchemy import select

from db import models
from db.session import session_scope
from engine.contracts import TimeWindow
from jobs.run_attribution import find_security, run_attribution_for_ticker


def main() -> None:
    parser = argparse.ArgumentParser(description="Run attribution over trading-date windows")
    parser.add_argument("ticker")
    parser.add_argument("--from", dest="start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--cadence", choices=["daily", "weekly", "monthly"], default="daily")
    parser.add_argument("--use-french-factors", action="store_true")
    parser.add_argument("--use-expanded-mvp", action="store_true")
    parser.add_argument("--include-event-evidence", action="store_true")
    parser.add_argument("--lookback-days", type=int, default=60)
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    start = _date_to_utc_datetime(date.fromisoformat(args.start))
    end = _date_to_utc_datetime(date.fromisoformat(args.end))
    cutoff = datetime.now(timezone.utc)

    ran = 0
    skipped = 0
    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        security = find_security(session=session, ticker=ticker)
        trading_dates = load_trading_dates(
            session=session,
            security_id=security.security_id,
            start=start,
            end=end,
        )
        for window in build_windows(trading_dates=trading_dates, cadence=args.cadence):
            try:
                run_attribution_for_ticker(
                    session=session,
                    ticker=ticker,
                    window=window,
                    attribution_cutoff=cutoff,
                    use_french_factors=args.use_french_factors,
                    use_expanded_mvp=args.use_expanded_mvp,
                    include_event_evidence=args.include_event_evidence,
                    lookback_days=args.lookback_days,
                    cadence=args.cadence,
                )
                ran += 1
            except ValueError:
                skipped += 1

    print(f"ran {ran} {args.cadence} attribution window(s) for {ticker}; skipped {skipped}")


def load_trading_dates(
    *,
    session,
    security_id,
    start: datetime,
    end: datetime,
) -> list[datetime]:
    rows = session.execute(
        select(models.PriceBar.event_time)
        .distinct()
        .where(models.PriceBar.security_id == security_id)
        .where(models.PriceBar.event_time >= start)
        .where(models.PriceBar.event_time <= end)
        .order_by(models.PriceBar.event_time)
    )
    return [row[0] for row in rows]


def build_windows(*, trading_dates: list[datetime], cadence: str) -> list[TimeWindow]:
    trading_dates = sorted(set(trading_dates))
    if cadence == "daily":
        return [
            TimeWindow(start=previous, end=current)
            for previous, current in zip(trading_dates, trading_dates[1:], strict=False)
        ]

    grouped: dict[tuple[int, int] | tuple[int, int, int], list[datetime]] = defaultdict(list)
    for trading_date in trading_dates:
        if cadence == "weekly":
            iso = trading_date.isocalendar()
            key = (iso.year, iso.week)
        elif cadence == "monthly":
            key = (trading_date.year, trading_date.month, 1)
        else:
            raise ValueError(f"unknown cadence {cadence}")
        grouped[key].append(trading_date)

    windows = []
    for dates in grouped.values():
        if len(dates) >= 2:
            windows.append(TimeWindow(start=dates[0], end=dates[-1]))
    return windows


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()

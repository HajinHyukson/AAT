from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from adapters.french.client import FrenchFactorReturn, fetch_daily_5_factors
from db import models
from db.session import session_scope
from engine.contracts import TimeWindow


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Kenneth French daily five-factor returns")
    parser.add_argument("--from", dest="start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--cache-dir", default=".cache/french")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    window = TimeWindow(
        start=_date_to_utc_datetime(date.fromisoformat(args.start)),
        end=_date_to_utc_datetime(date.fromisoformat(args.end)),
    )
    records = fetch_daily_5_factors(
        window=window,
        ingestion_time=datetime.now(timezone.utc),
        cache_dir=Path(args.cache_dir),
    )

    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        upsert_factor_returns(session=session, records=records)

    print(f"ingested {len(records)} Kenneth French factor rows")


def upsert_factor_returns(*, session, records: list[FrenchFactorReturn]) -> None:
    for record in records:
        stmt = insert(models.FactorReturn).values(
            factor_name=record.factor_name,
            factor_family=record.factor_family,
            return_bps=record.return_bps,
            source=record.source,
            event_time=record.event_time,
            ingestion_time=record.ingestion_time,
            timestamp_available=record.timestamp_available,
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


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()

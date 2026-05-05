from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone

from sqlalchemy.dialects.postgresql import insert

from adapters.fred.client import FRED_SERIES, FredObservation, fetch_fred_csv_observations
from db import models
from db.session import session_scope


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest public FRED macro series")
    parser.add_argument("--from", dest="start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--series", nargs="*", default=list(FRED_SERIES), help="FRED series IDs")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    ingestion_time = datetime.now(timezone.utc)
    records: list[FredObservation] = []
    for series_name in args.series:
        records.extend(
            fetch_fred_csv_observations(
                series_name=series_name,
                start=start,
                end=end,
                ingestion_time=ingestion_time,
            )
        )

    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        upsert_macro_series(session=session, records=records)

    print(f"ingested {len(records)} FRED macro observations")


def upsert_macro_series(*, session, records: list[FredObservation]) -> None:
    for record in records:
        stmt = insert(models.MacroSeries).values(
            series_name=record.series_name,
            value=record.value,
            vintage=record.vintage,
            source=record.source,
            event_time=record.event_time,
            ingestion_time=record.ingestion_time,
            timestamp_available=record.timestamp_available,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_macro_series_vintage",
            set_={
                "value": stmt.excluded.value,
                "source": stmt.excluded.source,
                "ingestion_time": stmt.excluded.ingestion_time,
                "timestamp_available": stmt.excluded.timestamp_available,
            },
        )
        session.execute(stmt)


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()

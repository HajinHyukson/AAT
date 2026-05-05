from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timezone
from pathlib import Path

from db.session import session_scope
from engine.contracts import TimeWindow
from jobs.run_attribution import run_attribution_for_ticker


DEFAULT_CONFIG = Path("config/mvp_universe.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run expanded MVP daily attribution for the curated 50-name universe")
    parser.add_argument("--for-date", required=True, help="Attribution end date YYYY-MM-DD")
    parser.add_argument("--previous-date", required=True, help="Attribution start date YYYY-MM-DD")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--lookback-days", type=int, default=252)
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    window = TimeWindow(
        start=_date_to_utc_datetime(date.fromisoformat(args.previous_date)),
        end=_date_to_utc_datetime(date.fromisoformat(args.for_date)),
    )
    cutoff = datetime.now(timezone.utc)
    ran = 0
    skipped = 0
    failures: list[str] = []
    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        for item in payload["securities"]:
            ticker = item["ticker"]
            try:
                run_attribution_for_ticker(
                    session=session,
                    ticker=ticker,
                    window=window,
                    attribution_cutoff=cutoff,
                    use_expanded_mvp=True,
                    include_event_evidence=True,
                    lookback_days=args.lookback_days,
                )
                ran += 1
            except (RuntimeError, ValueError) as exc:
                skipped += 1
                failures.append(f"{ticker}: {exc}")

    print(f"mvp_daily_batch ran={ran} skipped={skipped} window={args.previous_date}->{args.for_date}")
    if failures:
        print("failures:")
        for failure in failures:
            print(f"  {failure}")


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()

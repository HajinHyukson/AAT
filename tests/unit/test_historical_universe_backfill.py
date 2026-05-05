from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from jobs.run_batch_attribution import build_windows
from jobs.run_historical_universe_backfill import (
    VALID_CADENCES,
    run_historical_universe_backfill,
    subtract_years,
)


def dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def test_historical_backfill_dry_run_records_expected_steps() -> None:
    seen: list[str] = []
    report = run_historical_universe_backfill(
        config_path=Path("config/mvp_universe.json"),
        end=date(2026, 5, 4),
        years=3,
        cadences=VALID_CADENCES,
        dry_run=True,
        step_runner=seen.append,
    )

    assert report.seeded_securities == 50
    assert report.analysis_start == date(2023, 5, 4)
    assert report.data_start < report.analysis_start
    assert seen == [
        "alembic_upgrade",
        "create_backfill_run",
        "seed_universe",
        "seed_mappings",
        "backfill_prices",
        "ingest_french",
        "ingest_fred",
        "build_proxy_returns",
        "ingest_edgar",
        "generate_event_features",
        "run_historical_attribution",
        "replay_audit",
        "complete_backfill_run",
    ]


def test_weekly_and_monthly_windows_are_distinct_from_daily_windows() -> None:
    trading_dates = [
        dt(2026, 1, 2),
        dt(2026, 1, 5),
        dt(2026, 1, 6),
        dt(2026, 2, 2),
        dt(2026, 2, 3),
    ]

    daily = build_windows(trading_dates=trading_dates, cadence="daily")
    weekly = build_windows(trading_dates=trading_dates, cadence="weekly")
    monthly = build_windows(trading_dates=trading_dates, cadence="monthly")

    assert len(daily) == 4
    assert [(window.start, window.end) for window in weekly] == [
        (dt(2026, 1, 5), dt(2026, 1, 6)),
        (dt(2026, 2, 2), dt(2026, 2, 3)),
    ]
    assert [(window.start, window.end) for window in monthly] == [
        (dt(2026, 1, 2), dt(2026, 1, 6)),
        (dt(2026, 2, 2), dt(2026, 2, 3)),
    ]


def test_subtract_years_handles_leap_day() -> None:
    assert subtract_years(end=date(2024, 2, 29), years=3) == date(2021, 2, 28)

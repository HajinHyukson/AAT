from __future__ import annotations

from datetime import datetime, timezone

from jobs.run_batch_attribution import build_windows


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_daily_windows_use_consecutive_trading_dates() -> None:
    windows = build_windows(trading_dates=[dt(2), dt(5), dt(5), dt(6)], cadence="daily")

    assert [(window.start.day, window.end.day) for window in windows] == [(2, 5), (5, 6)]


def test_weekly_windows_group_by_iso_week() -> None:
    windows = build_windows(trading_dates=[dt(5), dt(6), dt(12), dt(13)], cadence="weekly")

    assert [(window.start.day, window.end.day) for window in windows] == [(5, 6), (12, 13)]

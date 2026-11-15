from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from jobs.run_on_demand_attribution_worker import missing_windows_for_job


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_missing_windows_for_job_runs_newest_window_first() -> None:
    windows = missing_windows_for_job(
        session=ExistingWindowSession(existing=[]),
        security_id=uuid4(),
        methodology="residual_safety_v1",
        cadence="daily",
        trading_dates=[dt(day) for day in range(1, 6)],
        target_range_start=dt(2),
        target_range_end=dt(5),
    )

    assert [(window.start, window.end) for window in windows] == [
        (dt(4), dt(5)),
        (dt(1), dt(2)),
        (dt(2), dt(3)),
        (dt(3), dt(4)),
    ]


def test_missing_windows_for_job_skips_existing_selected_methodology_windows() -> None:
    windows = missing_windows_for_job(
        session=ExistingWindowSession(existing=[(dt(2), dt(3))]),
        security_id=uuid4(),
        methodology="residual_safety_v1",
        cadence="daily",
        trading_dates=[dt(day) for day in range(1, 5)],
        target_range_start=dt(2),
        target_range_end=dt(4),
    )

    assert [(window.start, window.end) for window in windows] == [
        (dt(3), dt(4)),
        (dt(1), dt(2)),
    ]


def test_missing_windows_for_job_supports_weekly_ranges() -> None:
    windows = missing_windows_for_job(
        session=ExistingWindowSession(existing=[(dt(5), dt(9))]),
        security_id=uuid4(),
        methodology="residual_safety_v1",
        cadence="weekly",
        trading_dates=[dt(day) for day in (5, 6, 7, 8, 9, 12, 13, 14, 15, 16)],
        target_range_start=dt(5),
        target_range_end=dt(16),
    )

    assert [(window.start, window.end) for window in windows] == [
        (dt(12), dt(16)),
    ]


def test_missing_windows_query_is_methodology_scoped() -> None:
    session = ExistingWindowSession(existing=[])

    missing_windows_for_job(
        session=session,
        security_id=uuid4(),
        methodology="residual_safety_v1",
        cadence="daily",
        trading_dates=[dt(day) for day in range(1, 4)],
        target_range_start=dt(2),
        target_range_end=dt(3),
    )

    assert "attribution_run.methodology" in str(session.statement)


class ExistingWindowSession:
    def __init__(self, existing):
        self.existing = existing
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return [
            SimpleNamespace(window_start=start, window_end=end)
            for start, end in self.existing
        ]

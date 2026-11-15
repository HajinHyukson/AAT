from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from db import models
from engine.contracts import TimeWindow
from jobs.run_batch_attribution import build_windows


def candidate_windows_for_range(
    *,
    trading_dates: Sequence[datetime],
    cadence: str,
    target_range_start: datetime,
    target_range_end: datetime,
) -> list[TimeWindow]:
    return [
        window
        for window in build_windows(trading_dates=list(trading_dates), cadence=cadence)
        if target_range_start <= window.end <= target_range_end
    ]


def missing_windows_for_range(
    *,
    session,
    security_id: uuid.UUID,
    methodology: str,
    cadence: str,
    trading_dates: Sequence[datetime],
    target_range_start: datetime,
    target_range_end: datetime,
    candidate_windows: Sequence[TimeWindow] | None = None,
) -> list[TimeWindow]:
    if candidate_windows is not None:
        windows = list(candidate_windows)
    else:
        windows = candidate_windows_for_range(
            trading_dates=trading_dates,
            cadence=cadence,
            target_range_start=target_range_start,
            target_range_end=target_range_end,
        )
    existing = {
        (row.window_start, row.window_end)
        for row in session.execute(
            select(models.AttributionRun.window_start, models.AttributionRun.window_end)
            .where(models.AttributionRun.security_id == security_id)
            .where(models.AttributionRun.methodology == methodology)
            .where(models.AttributionRun.cadence == cadence)
            .where(models.AttributionRun.window_end >= target_range_start)
            .where(models.AttributionRun.window_end <= target_range_end)
        )
    }
    missing = [window for window in windows if (window.start, window.end) not in existing]
    return newest_window_first(missing)


def newest_window_first(windows: Sequence[TimeWindow]) -> list[TimeWindow]:
    if not windows:
        return []
    latest = max(windows, key=lambda window: window.end)
    rest = sorted(
        [window for window in windows if window is not latest],
        key=lambda window: window.end,
    )
    return [latest, *rest]

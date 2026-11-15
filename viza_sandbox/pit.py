"""Point-in-time availability policy for the sandbox price panel.

A value observed on date ``D`` (an ``event_date``) is only visible to a
backtest or materialization run on date ``D`` or later once its
``available_at`` timestamp has passed. This module defines the single
availability policy the sandbox currently supports (end-of-day snapshot
availability) and the primitives used to enforce it: no caller may bypass
``visible_on`` to read a row before its ``available_at``.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

import polars as pl

EOD_POLICY_VERSION = "faustcalc_fmp_snapshot_eod_policy_v1"
EOD_AVAILABLE_HOUR_UTC = 21


def end_of_day_utc(d: date) -> datetime:
    """The last instant of UTC calendar day ``d``."""
    return datetime.combine(d, time(23, 59, 59, 999999), tzinfo=timezone.utc)


def eod_available_at(event_date: pl.Expr) -> pl.Expr:
    """Availability timestamp for a price row: ``event_date`` at 21:00 UTC."""
    return event_date.cast(pl.Datetime("us", "UTC")).dt.offset_by(
        f"{EOD_AVAILABLE_HOUR_UTC}h"
    )


def visible_on(frame: pl.DataFrame, on: date) -> pl.DataFrame:
    """Rows of ``frame`` visible as of the end of UTC day ``on``.

    Filters to rows whose ``available_at`` is at or before
    ``end_of_day_utc(on)``. This is the only sanctioned way to apply the
    point-in-time cutoff; there is no bypass.
    """
    cutoff = end_of_day_utc(on)
    return frame.filter(pl.col("available_at") <= cutoff)

"""Which dates of a wide price frame count as trading days.

The price source carries a few dates with bars for only a handful of securities: stray
weekend bars and holidays on which only some listings trade. Counting those as calendar days
would put a null in every other security's window. A date is a trading day when at least
``TRADING_DAY_MIN_COVERAGE`` of the usual number of securities have a bar on it.
"""

from __future__ import annotations

import pandas as pd

TRADING_DAY_MIN_COVERAGE = 0.5


def trading_day_mask(wide: pd.DataFrame) -> pd.Series:
    """True for index dates with at least half the median per-date count of non-null cells."""
    counts = wide.notna().sum(axis=1)
    if counts.empty:
        return counts.astype(bool)
    return counts >= TRADING_DAY_MIN_COVERAGE * counts.median()

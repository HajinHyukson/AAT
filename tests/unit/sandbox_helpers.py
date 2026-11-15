import json
from datetime import date, datetime, timezone
from pathlib import Path

import polars as pl


def make_panel(root: Path) -> Path:
    d = root / "panel"
    d.mkdir(parents=True)
    pl.DataFrame({
        "security_id": ["a", "a", "b"],
        "event_date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 2)],
        "available_at": [
            datetime(2024, 1, 2, 21, tzinfo=timezone.utc),
            datetime(2024, 1, 3, 21, tzinfo=timezone.utc),
            datetime(2024, 1, 2, 21, tzinfo=timezone.utc),
        ],
        "ingestion_time": [datetime(2024, 5, 1, tzinfo=timezone.utc)] * 3,
        "close": [10.0, 11.0, 5.0],
        "adjusted_close": [10.0, 11.0, 5.0],
        "volume": [1, 2, 3],
        "currency": ["USD"] * 3,
    }).write_parquet(d / "prices.parquet")
    pl.DataFrame({
        "event_date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 2)],
        "security_id": ["a", "a", "b"],
        "ticker": ["AAA", "AAA", "BBB"],
        "exchange": ["NYSE"] * 3,
        "currency": ["USD"] * 3,
        "sector": ["Tech", "Tech", None],
        "industry": [None] * 3,
        "classification_as_of": [None] * 3,
    }).write_parquet(d / "universe.parquet")
    (d / "manifest.json").write_text(json.dumps({
        "manifest_id": "m",
        "availability_policy_version": "faustcalc_fmp_snapshot_eod_policy_v1",
    }))
    return d


def synthetic_bars(start: date, end: date, security_ids=("a", "b", "c", "d"), scale=None):
    """Deterministic weekday bars. ``scale(security_id, event_date)`` may rescale a close."""
    import math
    from datetime import timedelta

    rows = []
    ingested = datetime(2024, 9, 1, tzinfo=timezone.utc)
    day, i = start, 0
    while day <= end:
        if day.weekday() < 5:
            for n, security_id in enumerate(security_ids):
                close = (20.0 + 10.0 * n) * (1.0 + 0.3 * math.sin(i * (0.11 + 0.03 * n)))
                if scale is not None:
                    close *= scale(security_id, day)
                rows.append((security_id, day, close, close, 1000 + 7 * i + n, "USD", ingested))
            i += 1
        day += timedelta(days=1)
    return pl.DataFrame(
        rows,
        schema={
            "security_id": pl.Utf8, "event_date": pl.Date, "close": pl.Float64,
            "adjusted_close": pl.Float64, "volume": pl.Int64, "currency": pl.Utf8,
            "ingestion_time": pl.Datetime("us", "UTC"),
        },
        orient="row",
    )


def synthetic_securities(security_ids=("a", "b", "c", "d"), sector="Tech"):
    n = len(security_ids)
    return pl.DataFrame(
        {
            "security_id": list(security_ids),
            "ticker": [s.upper() * 3 for s in security_ids],
            "exchange": ["NYSE"] * n,
            "currency": ["USD"] * n,
            "sector": [sector] * n,
            "industry": [None] * n,
            "classification_as_of": [None] * n,
        },
        schema_overrides={
            "industry": pl.Utf8, "classification_as_of": pl.Datetime("us", "UTC"),
        },
    )

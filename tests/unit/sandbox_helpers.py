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


def make_panel_with_attributes(root: Path, late_row: bool = False) -> Path:
    """``make_panel`` plus ``attributes.parquet`` and ``catalog.json`` for two keys.

    ``late_row`` adds a row for security ``b`` on 2024-01-03 whose ``available_at`` is a day
    after its own date; it must never be visible.
    """
    d = make_panel(root)
    eod = lambda day: datetime(2024, 1, day, 21, tzinfo=timezone.utc)  # noqa: E731
    rows = {
        "security_id": ["a", "a", "b"],
        "event_date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 2)],
        "available_at": [eod(2), eod(3), eod(2)],
        "ret_1d": [None, 0.1, None],
        "adv_21d": [10.0, 22.0, 15.0],
    }
    if late_row:
        rows["security_id"].append("b")
        rows["event_date"].append(date(2024, 1, 3))
        rows["available_at"].append(eod(4))
        rows["ret_1d"].append(9.9)
        rows["adv_21d"].append(99.0)
    pl.DataFrame(rows, schema_overrides={"ret_1d": pl.Float64}).write_parquet(
        d / "attributes.parquet"
    )
    entry = {
        "display_name": "n", "description": "d", "unit": "ratio",
        "classification_snapshot": False,
    }
    (d / "catalog.json").write_text(json.dumps({
        "catalog_version": "viza_sandbox_catalog_v1",
        "attributes": [{"key": "ret_1d", **entry}, {"key": "adv_21d", **entry}],
    }))
    return d

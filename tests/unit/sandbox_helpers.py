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

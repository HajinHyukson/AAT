from __future__ import annotations

from datetime import datetime, timezone

from adapters.french.client import parse_daily_5_factor_csv
from engine.contracts import TimeWindow


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_parse_daily_5_factor_csv_filters_window_and_converts_percent_to_bps() -> None:
    csv_text = """This file was created by CMPT_ME_BEME_RETS_DAILY using the 202601 CRSP database.
The Tbill return is the simple daily rate that, over the number of trading days
,Mkt-RF,SMB,HML,RMW,CMA,RF
20260102,1.23,-0.10,0.05,0.20,-0.30,0.01
20260104,0.50,0.10,-0.05,0.00,0.02,0.01

Copyright 2026 Kenneth R. French
"""

    records = parse_daily_5_factor_csv(
        csv_text,
        window=TimeWindow(start=dt(2), end=dt(3)),
        ingestion_time=dt(4),
    )

    assert len(records) == 6
    market = records[0]
    assert market.factor_name == "Mkt-RF"
    assert market.raw_percent_return == 1.23
    assert market.return_bps == 123.0
    assert market.timestamp_available == dt(4)

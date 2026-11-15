import polars as pl
from datetime import date, datetime, timezone
from viza_sandbox.pit import visible_on, end_of_day_utc, EOD_AVAILABLE_HOUR_UTC


def test_visible_on_excludes_rows_available_after_cutoff():
    frame = pl.DataFrame({"security_id": ["a", "a"], "event_date": [date(2024,1,2), date(2024,1,3)],
                          "available_at": [datetime(2024,1,2,21,tzinfo=timezone.utc), datetime(2024,1,3,21,tzinfo=timezone.utc)]})
    out = visible_on(frame, date(2024, 1, 2))
    assert out["event_date"].to_list() == [date(2024, 1, 2)]


def test_injected_future_row_is_refused():
    cutoff = date(2024, 1, 2)
    frame = pl.DataFrame({"security_id": ["leak"], "event_date": [cutoff], "available_at": [end_of_day_utc(cutoff) + __import__("datetime").timedelta(days=1)]})
    assert visible_on(frame, cutoff).height == 0


def test_eod_policy_hour_is_pinned():
    assert EOD_AVAILABLE_HOUR_UTC == 21

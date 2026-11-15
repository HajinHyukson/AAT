import polars as pl
from datetime import date, datetime, timezone
import pytest
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


# --- Production-path probes: materialized panel -> VizaData, and evaluate_scores ----------


def _materialized_panel(tmp_path):
    from viza_sandbox.canonical import InMemoryCanonicalSource
    from viza_sandbox.config import SandboxSettings
    from viza_sandbox.materialize import PanelSpec, materialize

    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    days = [date(2024, 1, d) for d in (2, 3, 4, 5, 8)]
    rows = [
        (sid, d, base + i, base + i, 1, "USD", t)
        for sid, base in (("a", 10.0), ("b", 20.0))
        for i, d in enumerate(days)
    ]
    prices = pl.DataFrame(
        rows,
        schema={
            "security_id": pl.Utf8,
            "event_date": pl.Date,
            "close": pl.Float64,
            "adjusted_close": pl.Float64,
            "volume": pl.Int64,
            "currency": pl.Utf8,
            "ingestion_time": pl.Datetime("us", "UTC"),
        },
        orient="row",
    )
    secs = pl.DataFrame(
        {
            "security_id": ["a", "b"],
            "ticker": ["AAA", "BBB"],
            "exchange": ["NYSE"] * 2,
            "currency": ["USD"] * 2,
            "sector": [None, None],
            "industry": [None, None],
            "classification_as_of": [None, None],
        }
    )
    settings = SandboxSettings(data_dir=tmp_path / "data")
    spec = PanelSpec(start=date(2024, 1, 1), end=date(2024, 1, 31))
    return materialize(InMemoryCanonicalSource(secs, prices), spec, settings).directory


def test_tampered_late_row_in_materialized_panel_is_hidden_everywhere(tmp_path):
    import pandas as pd

    from viza_sandbox.sdk import VizaData

    panel = _materialized_panel(tmp_path)
    leak_day = date(2024, 1, 4)
    path = panel / "prices.parquet"
    frame = pl.read_parquet(path)
    late = datetime(2024, 1, 5, 0, 0, 1, tzinfo=timezone.utc)  # after the end of its own day
    frame = frame.with_columns(
        pl.when((pl.col("security_id") == "a") & (pl.col("event_date") == leak_day))
        .then(pl.lit(late))
        .otherwise(pl.col("available_at"))
        .alias("available_at")
    )
    frame.write_parquet(path)

    data = VizaData(panel)
    leak = pd.Timestamp(leak_day)
    wide = data.prices("close")
    assert leak in wide.index and pd.isna(wide.loc[leak, "a"])
    assert wide.loc[leak, "b"] == 22.0
    long = data.prices_long(("close",))
    assert not ((long["security_id"] == "a") & (long["event_date"] == leak)).any()
    assert len(long) == 9
    for view_day in (date(2024, 1, 4), date(2024, 1, 5), date(2024, 1, 31)):
        view = data.as_of(view_day).prices_long(("close",))
        assert not ((view["security_id"] == "a") & (view["event_date"] == leak)).any()


def test_score_at_d_first_affects_d_plus_2_across_a_weight_change():
    import numpy as np
    import pandas as pd

    from viza_sandbox.evaluate import BacktestSettings, evaluate_scores

    dates = pd.bdate_range("2024-01-01", periods=8)
    # Distinct, known daily returns per security so each bucket's source is identifiable.
    ret_a = [np.nan, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07]
    ret_b = [np.nan, -0.01, -0.02, -0.03, -0.04, -0.05, -0.06, -0.07]

    def closes(rets):
        level, out = 100.0, []
        for r in rets:
            level = level if np.isnan(r) else level * (1 + r)
            out.append(level)
        return out

    close = pd.DataFrame({"a": closes(ret_a), "b": closes(ret_b)}, index=dates)
    scores = pd.DataFrame(np.nan, index=dates, columns=["a", "b"])
    d1, d2 = 1, 4
    scores.iloc[d1] = [1.0, 2.0]  # a -> q1, b -> q2
    scores.iloc[d2] = [2.0, 1.0]  # flipped: a -> q2, b -> q1
    ev = evaluate_scores(scores, close, BacktestSettings(quantiles=2, rebalance="daily"))
    q2 = ev.quantile_daily_returns["q2"]
    day = [d.strftime("%Y-%m-%d") for d in dates]

    for i in range(0, d1 + 2):  # nothing on or before D1 + 1
        assert q2.get(day[i]) is None
    for i in range(d1 + 2, d2 + 2):  # D1 weights through D2 + 1, including D2 itself
        assert q2[day[i]] == pytest.approx(ret_b[i])
    for i in range(d2 + 2, len(dates)):  # D2 weights only from D2 + 2
        assert q2[day[i]] == pytest.approx(ret_a[i])
    assert ev.rebalance_dates == [day[d1], day[d2]]


def test_sdk_visibility_boundary_is_pit_end_of_day(tmp_path):
    from datetime import timedelta

    from viza_sandbox.sdk import VizaData

    panel = _materialized_panel(tmp_path)
    path = panel / "prices.parquet"
    frame = pl.read_parquet(path)
    day = date(2024, 1, 3)
    edge = end_of_day_utc(day)
    for available, visible in ((edge, True), (edge + timedelta(microseconds=1), False)):
        frame.with_columns(
            pl.when(pl.col("event_date") == day)
            .then(pl.lit(available))
            .otherwise(pl.col("available_at"))
            .alias("available_at")
        ).write_parquet(path)
        rows = VizaData(panel).prices_long(("close",))
        assert (rows["event_date"].dt.date == day).any() == visible

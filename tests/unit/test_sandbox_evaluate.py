import numpy as np
import pandas as pd
import pytest

from viza_sandbox.evaluate import (
    EXECUTION_CONVENTION,
    BacktestSettings,
    EvaluationError,
    evaluate_scores,
    rebalance_dates,
)

DATES = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"])


def _close():
    return pd.DataFrame(
        {"a": [10, 11, 12, 13, 14], "b": [10, 10, 10, 10, 10], "c": [10, 9, 8, 7, 6]},
        index=DATES,
        dtype=float,
    )


def _scores_once():
    s = pd.DataFrame(np.nan, index=DATES, columns=["a", "b", "c"])
    s.loc[DATES[0]] = [3.0, 2.0, 1.0]   # a top, c bottom
    return s


def test_signal_at_d_applies_to_return_from_close_d1_to_close_d2():
    ev = evaluate_scores(
        _scores_once(), _close(), BacktestSettings(quantiles=3, rebalance="daily")
    )
    r_a_d2 = 12 / 11 - 1
    r_c_d2 = 8 / 9 - 1
    assert ev.quantile_daily_returns["q3"]["2024-01-04"] == pytest.approx(r_a_d2)
    assert ev.quantile_daily_returns["q1"]["2024-01-04"] == pytest.approx(r_c_d2)
    assert ev.quantile_daily_returns["q3"].get("2024-01-03") is None
    assert ev.long_short_daily["2024-01-04"] == pytest.approx(r_a_d2 - r_c_d2)
    assert ev.execution == EXECUTION_CONVENTION


def test_equity_curve_compounds_from_one():
    ev = evaluate_scores(
        _scores_once(), _close(), BacktestSettings(quantiles=3, rebalance="daily")
    )
    curve = ev.equity_curves["q3"]
    assert curve["2024-01-04"] == pytest.approx(12 / 11)
    assert curve["2024-01-05"] == pytest.approx(13 / 11)


def test_missing_close_is_excluded_not_zero():
    close = _close()
    close.loc[DATES[2], "a"] = np.nan   # a has no close on D2 (2024-01-04)
    ev = evaluate_scores(
        _scores_once(), close, BacktestSettings(quantiles=3, rebalance="daily")
    )
    # q3 = {a}; no contributor, not 0.0
    assert ev.quantile_daily_returns["q3"]["2024-01-04"] is None
    # r_a on D3 needs close on D2, also missing
    assert ev.quantile_daily_returns["q3"]["2024-01-05"] is None
    # curve unchanged, never multiplied by 0
    assert ev.equity_curves["q3"]["2024-01-05"] == pytest.approx(1.0)
    # b is flat: a real 0.0
    assert ev.quantile_daily_returns["q2"]["2024-01-04"] == pytest.approx(0.0)


def test_unknown_securities_are_dropped_with_warning():
    s = _scores_once()
    s["zzz"] = 5.0
    ev = evaluate_scores(s, _close(), BacktestSettings(quantiles=3, rebalance="daily"))
    assert ev.warnings == ["Dropped 1 scored securities not in the universe: zzz"]


def test_no_overlapping_dates_raises():
    s = pd.DataFrame({"a": [1.0]}, index=pd.to_datetime(["2019-01-02"]))
    with pytest.raises(EvaluationError, match="No scores fall inside the panel date range."):
        evaluate_scores(s, _close(), BacktestSettings(quantiles=2, rebalance="daily"))


def test_rebalance_dates_weekly_and_monthly():
    idx = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08", "2024-01-31", "2024-02-01"]
    )
    # 01-31 and 02-01 share ISO week 5
    assert list(rebalance_dates(idx, "weekly")) == list(
        pd.to_datetime(["2024-01-05", "2024-01-08", "2024-02-01"])
    )
    assert list(rebalance_dates(idx, "monthly")) == list(
        pd.to_datetime(["2024-01-31", "2024-02-01"])
    )


def test_rank_stability_and_top_bottom():
    s = pd.DataFrame({"a": [3.0, 3.0], "b": [2.0, 1.0], "c": [1.0, 2.0]}, index=DATES[:2])
    ev = evaluate_scores(s, _close(), BacktestSettings(quantiles=3, rebalance="daily", top_n=1))
    assert ev.rank_stability["2024-01-03"] == pytest.approx(0.5)
    assert ev.top_bottom["2024-01-02"] == {"top": ["a"], "bottom": ["c"]}


def test_settings_require_quantiles_and_rebalance():
    with pytest.raises(Exception):
        BacktestSettings()

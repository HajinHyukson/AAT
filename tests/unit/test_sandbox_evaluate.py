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


# --- Extreme one-day moves are disclosed, never removed --------------------------------------

from viza_sandbox.evaluate import EXTREME_MOVE_RATIO  # noqa: E402

LONG_DATES = pd.bdate_range("2024-01-02", periods=8)


def _constant_scores(columns):
    s = pd.DataFrame(np.nan, index=LONG_DATES, columns=columns)
    s.loc[LONG_DATES[0]] = [float(i + 1) for i in range(len(columns))]
    return s


def test_extreme_moves_are_counted_and_warned_not_removed():
    close = pd.DataFrame(
        {
            "w": [10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7],
            "x": [1.0, 1.0, 1.0, 1.0, 1000.0, 1.0, 1.0, 1.0],
            "y": [20.0] * 8,
            "z": [30.0, 30.3, 30.6, 30.9, 31.2, 31.5, 31.8, 32.1],
        },
        index=LONG_DATES,
    )
    out = evaluate_scores(
        _constant_scores(["w", "x", "y", "z"]),
        close,
        BacktestSettings(quantiles=2, rebalance="daily"),
    )
    assert EXTREME_MOVE_RATIO == 10.0
    assert out.extreme_moves == {"ratio": 10.0, "security_days": 2, "securities": 1}
    assert (
        "2 scored security-days across 1 securities had a one-day close move of 10x or more; "
        "quantile returns include them unclipped."
    ) in out.warnings
    spike_day = LONG_DATES[4].strftime("%Y-%m-%d")
    assert out.quantile_daily_returns["q1"][spike_day] == pytest.approx((0.1 / 10.3 + 999.0) / 2)


def test_extreme_move_outside_the_held_window_is_not_counted():
    close = pd.DataFrame(
        {"w": [10.0, 10.1, 10.2, 10.3], "x": [1.0, 1000.0, 1000.0, 1000.0], "y": [20.0] * 4},
        index=LONG_DATES[:4],
    )
    scores = pd.DataFrame(np.nan, index=LONG_DATES[:4], columns=["w", "x", "y"])
    scores.loc[LONG_DATES[0]] = [1.0, 2.0, 3.0]
    out = evaluate_scores(scores, close, BacktestSettings(quantiles=3, rebalance="daily"))
    assert out.extreme_moves == {"ratio": 10.0, "security_days": 0, "securities": 0}
    assert not any("one-day close move" in w for w in out.warnings)


def test_no_extreme_moves_no_warning():
    out = evaluate_scores(_scores_once(), _close(), BacktestSettings(quantiles=3, rebalance="daily"))
    assert out.extreme_moves == {"ratio": 10.0, "security_days": 0, "securities": 0}
    assert not any("one-day close move" in w for w in out.warnings)


# --- Scores for securities outside the universe are not ranked -------------------------------


def test_scores_outside_universe_are_dropped_and_counted():
    close = pd.DataFrame(
        {"a": [10, 11, 12, 13, 14], "b": [10.0] * 5, "c": [10, 9, 8, 7, 6], "junk": [1.0] * 5},
        index=DATES,
        dtype=float,
    )
    scores = pd.DataFrame(
        {"a": 3.0, "b": 2.0, "c": 1.0, "junk": 99.0}, index=DATES, columns=["a", "b", "c", "junk"]
    )
    universe = pd.DataFrame(
        [(d, s) for d in DATES for s in ("a", "b", "c")], columns=["event_date", "security_id"]
    )
    out = evaluate_scores(
        scores, close, BacktestSettings(quantiles=3, rebalance="daily"), universe=universe
    )
    assert out.scores_outside_universe == 5
    assert out.securities_scored == 3
    assert "5 scores were for securities outside the universe on their date and were not ranked." \
        in out.warnings
    assert all("junk" not in ids["top"] for ids in out.top_bottom.values())


def test_membership_is_checked_per_date():
    close = pd.DataFrame(
        {"a": [10, 11, 12, 13, 14], "b": [10.0] * 5, "c": [10, 9, 8, 7, 6]},
        index=DATES,
        dtype=float,
    )
    scores = pd.DataFrame({"a": 3.0, "b": 2.0, "c": 1.0}, index=DATES, columns=["a", "b", "c"])
    pairs = [(d, s) for d in DATES for s in ("a", "b", "c") if not (s == "a" and d == DATES[0])]
    universe = pd.DataFrame(pairs, columns=["event_date", "security_id"])
    out = evaluate_scores(
        scores, close, BacktestSettings(quantiles=2, rebalance="daily"), universe=universe
    )
    assert out.scores_outside_universe == 1
    first = out.top_bottom[DATES[0].strftime("%Y-%m-%d")]
    assert "a" not in first["top"] and "a" not in first["bottom"]
    assert out.top_bottom[DATES[1].strftime("%Y-%m-%d")]["top"][0] == "a"


def test_without_a_universe_nothing_is_dropped():
    out = evaluate_scores(_scores_once(), _close(), BacktestSettings(quantiles=3, rebalance="daily"))
    assert out.scores_outside_universe == 0


# --- Sparse dates are not trading days ---------------------------------------------------------


def test_return_across_a_sparse_date_is_kept():
    index = pd.to_datetime(
        ["2024-01-11", "2024-01-12", "2024-01-15", "2024-01-16", "2024-01-17"]
    )
    close = pd.DataFrame(
        {
            "a": [10.0, 11.0, np.nan, 12.1, 13.31],
            "b": [10.0, 10.0, np.nan, 10.0, 10.0],
            "c": [10.0, 9.0, np.nan, 8.1, 7.29],
            "odd": [5.0, 5.0, 5.0, 5.0, 5.0],
        },
        index=index,
    )
    scores = pd.DataFrame(np.nan, index=index, columns=["a", "b", "c"])
    scores.loc[index[0]] = [3.0, 2.0, 1.0]
    out = evaluate_scores(scores, close, BacktestSettings(quantiles=3, rebalance="daily"))
    assert out.non_trading_dates == ["2024-01-15"]
    assert "2024-01-15" not in out.quantile_daily_returns["q3"]
    # Scores on 01-11 earn from the close of 01-12; the holiday is not a row, so the
    # 01-12 -> 01-16 return is realized on 01-16 instead of being lost.
    assert out.quantile_daily_returns["q3"]["2024-01-16"] == pytest.approx(0.10)
    assert out.quantile_daily_returns["q1"]["2024-01-16"] == pytest.approx(-0.10)
    assert any("non-trading" in w for w in out.warnings)


def test_no_sparse_dates_no_warning():
    out = evaluate_scores(_scores_once(), _close(), BacktestSettings(quantiles=3, rebalance="daily"))
    assert out.non_trading_dates == []
    assert not any("non-trading" in w for w in out.warnings)

import numpy as np
import pandas as pd
import pytest
from pytest import approx

from viza_sandbox.attributes import compute_base, sector_zscore
from viza_sandbox.catalog import load_catalog


def wide(columns):
    length = len(next(iter(columns.values())))
    index = pd.bdate_range("2024-01-01", periods=length, name="event_date")
    return pd.DataFrame(columns, index=index, dtype="float64")


def base(close, volume=None):
    if volume is None:
        volume = pd.DataFrame(1.0, index=close.index, columns=close.columns)
    return compute_base(close, volume, load_catalog())


def test_returns_every_base_key_with_the_input_shape():
    close = wide({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    out = base(close)
    assert list(out) == [spec.key for spec in load_catalog().base()]
    for frame in out.values():
        assert frame.index.equals(close.index)
        assert list(frame.columns) == ["a", "b"]


def test_simple_return_and_gap_gives_null():
    close = wide({"a": [10, 11, None, 12.1, 13.31, 14.641]})
    out = base(close)["ret_1d"]["a"]
    assert out.iloc[1] == approx(0.10)
    assert pd.isna(out.iloc[2]) and pd.isna(out.iloc[3])
    assert out.iloc[4] == approx(0.10)


def test_longer_return_uses_the_calendar_offset():
    close = wide({"a": [float(v) for v in range(1, 8)]})
    out = base(close)["ret_5d"]["a"]
    assert out.iloc[:5].isna().all()
    assert out.iloc[5] == approx(6 / 1 - 1)
    assert out.iloc[6] == approx(7 / 2 - 1)


def test_rolling_windows_need_every_observation():
    values = [float(v) for v in range(1, 26)]
    gappy = list(values)
    gappy[9] = None
    close = wide({"a": values, "b": gappy})
    volume = pd.DataFrame(2.0, index=close.index, columns=close.columns)
    out = base(close, volume)
    assert pd.isna(out["ma_20d"]["a"].iloc[18])
    assert out["ma_20d"]["a"].iloc[19] == approx(10.5)
    assert out["ma_20d"]["b"].iloc[19:25].isna().all()
    assert pd.isna(out["adv_21d"]["a"].iloc[19])
    assert out["adv_21d"]["a"].iloc[20] == approx(sum(c * 2 for c in range(1, 22)) / 21)


def test_missing_volume_makes_dollar_volume_null():
    close = wide({"a": [10.0] * 22})
    volume = wide({"a": [5.0] * 22})
    volume.iloc[3, 0] = np.nan
    out = base(close, volume)["adv_21d"]["a"]
    assert pd.isna(out.iloc[20]) and pd.isna(out.iloc[21])


def test_volatility_is_sample_std_of_daily_returns():
    prices = [100.0]
    for i in range(22):
        prices.append(prices[-1] * (1.01 if i % 2 == 0 else 0.99))
    out = base(wide({"a": prices}))
    returns = pd.Series(prices).pct_change(fill_method=None).iloc[1:22]
    assert pd.isna(out["vol_21d"]["a"].iloc[20])
    assert out["vol_21d"]["a"].iloc[21] == approx(np.std(returns, ddof=1))


@pytest.mark.parametrize(
    "closes, expected",
    [
        ([float(v) for v in range(1, 16)], 100.0),
        ([7.0] * 15, 50.0),
        ([10.0 + (i % 2) for i in range(15)], 50.0),
        ([10.0] + [v for i in range(7) for v in (12.0 + i, 11.0 + i)], 66.6667),
    ],
)
def test_rsi_cutler_edges(closes, expected):
    out = base(wide({"a": closes}))["rsi_14d"]["a"]
    assert pd.isna(out.iloc[13])
    assert out.iloc[14] == approx(expected, abs=1e-4)


def test_bad_tick_passes_through_unclipped():
    out = base(wide({"a": [0.05, 5000.0, 0.05]}))["ret_1d"]["a"]
    assert out.iloc[1] == approx(99999.0)
    assert out.iloc[2] == approx(-0.99999)


def test_sector_zscore_nulls():
    values = wide(
        {"a": [1.0], "b": [2.0], "c": [3.0], "d": [5.0], "e": [5.0], "f": [5.0], "g": [9.0],
         "h": [1.0], "i": [2.0]}
    )
    sector = {"a": "T", "b": "T", "c": "T", "d": "U", "e": "U", "f": "U", "g": None,
              "h": "V", "i": "V"}
    z = sector_zscore(values, sector)
    assert z.index.equals(values.index) and list(z.columns) == list(values.columns)
    row = z.iloc[0]
    assert row[["a", "b", "c"]].tolist() == approx([-1.0, 0.0, 1.0])
    assert row[["d", "e", "f"]].isna().all()
    assert pd.isna(row["g"])
    assert row[["h", "i"]].isna().all()


def test_sector_zscore_ignores_members_without_a_value():
    values = wide({"a": [1.0], "b": [2.0], "c": [3.0], "d": [None]})
    z = sector_zscore(values, {"a": "T", "b": "T", "c": "T", "d": "T"}).iloc[0]
    assert z[["a", "b", "c"]].tolist() == approx([-1.0, 0.0, 1.0])
    assert pd.isna(z["d"])


# --- Final-review fixes ---------------------------------------------------------------------


def _path_with_tick(days=90, tick_at=5):
    closes = [100.0]
    for i in range(days - 1):
        closes.append(closes[-1] * (1.0005 if i % 2 == 0 else 0.9995))
    closes[tick_at] *= 100_000.0
    return closes


def test_volatility_is_exact_after_a_bad_tick_has_left_the_window():
    closes = _path_with_tick()
    out = base(wide({"a": closes}))["vol_21d"]["a"]
    returns = pd.Series(closes).pct_change(fill_method=None)
    expected = np.std(returns.iloc[-21:].to_numpy(), ddof=1)
    assert out.iloc[-1] == approx(expected, rel=1e-12)


def test_windowed_values_do_not_depend_on_where_history_starts():
    closes = _path_with_tick()
    full = base(wide({"a": closes}))
    late = base(wide({"a": closes[20:]}))
    for key in ("vol_21d", "ma_20d", "adv_21d", "rsi_14d"):
        assert full[key]["a"].iloc[-1] == late[key]["a"].iloc[-1], key


def test_sector_zscore_is_null_for_identical_values_that_are_not_exact_in_binary():
    values = wide({"a": [0.1], "b": [0.1], "c": [0.1], "d": [1.1], "e": [1.1], "f": [1.1],
                   "g": [1.1], "h": [1.1], "i": [1.1], "j": [1.1]})
    sector = {k: "T" for k in "abc"} | {k: "U" for k in "defghij"}
    assert sector_zscore(values, sector).iloc[0].isna().all()

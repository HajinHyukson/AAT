from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import polars as pl
import pytest
from sandbox_helpers import make_panel as _panel

from viza_sandbox.sdk import ReturnDeclarationError, VizaData, coerce_return, scores


def test_prices_wide_has_nan_for_missing_days(tmp_path):
    data = VizaData(_panel(tmp_path))
    wide = data.prices("close")
    assert list(wide.columns) == ["a", "b"] and wide.index.name == "event_date"
    assert wide.loc["2024-01-03", "a"] == 11.0 and np.isnan(wide.loc["2024-01-03", "b"])


def test_as_of_hides_rows_after_cutoff(tmp_path):
    data = VizaData(_panel(tmp_path)).as_of(date(2024, 1, 2))
    assert data.prices("close").index.max() == pd.Timestamp("2024-01-02")


def test_row_available_after_its_own_date_is_hidden(tmp_path):
    d = _panel(tmp_path)
    late = pl.lit(datetime(2024, 1, 5, 21, tzinfo=timezone.utc))
    frame = pl.read_parquet(d / "prices.parquet").with_columns(
        pl.when(pl.col("security_id") == "b")
        .then(late)
        .otherwise(pl.col("available_at"))
        .alias("available_at")
    )
    frame.write_parquet(d / "prices.parquet")
    assert "b" not in VizaData(d).prices("close").columns


def test_empty_range_returns_empty_frame_with_index_name(tmp_path):
    wide = VizaData(_panel(tmp_path)).prices("close", start=date(2020, 1, 1), end=date(2020, 1, 31))
    assert wide.empty and wide.index.name == "event_date"


def test_manifest_and_universe(tmp_path):
    data = VizaData(_panel(tmp_path))
    assert data.manifest["manifest_id"] == "m"
    assert set(data.universe()["ticker"]) == {"AAA", "BBB"}


def test_coerce_return_rules():
    idx = pd.to_datetime(["2024-01-02"])
    f = pd.DataFrame({"a": [1.0]}, index=idx)
    assert coerce_return(scores(f)).frame.equals(f)
    with pytest.raises(
        ReturnDeclarationError,
        match=r"declare it with viza\.scores\(df\) or viza\.weights\(df\)\.",
    ):
        coerce_return(f)
    with pytest.raises(ReturnDeclarationError, match="Boolean signals"):
        coerce_return(f > 0)
    with pytest.raises(ReturnDeclarationError, match="Report returns"):
        coerce_return({"x": 1})


def test_as_of_cannot_widen_an_existing_cutoff(tmp_path):
    data = VizaData(_panel(tmp_path)).as_of(date(2024, 1, 2)).as_of(date(2030, 1, 1))
    assert data.prices("close").index.max() == pd.Timestamp("2024-01-02")

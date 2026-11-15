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


# --- Catalog attributes ---------------------------------------------------------------------

import json  # noqa: E402

from sandbox_helpers import make_panel_with_attributes  # noqa: E402

from viza_sandbox.sdk import AttributeUnavailableError  # noqa: E402


def test_attribute_returns_a_wide_frame_like_prices(tmp_path):
    data = VizaData(make_panel_with_attributes(tmp_path))
    wide = data.attribute("adv_21d")
    prices = data.prices("close")
    assert wide.index.equals(prices.index) and wide.index.name == "event_date"
    assert list(wide.columns) == list(prices.columns) == ["a", "b"]
    assert wide.columns.name is None
    assert wide.loc["2024-01-02", "b"] == 15.0
    assert np.isnan(wide.loc["2024-01-03", "b"])
    returns = data.attribute("ret_1d")
    assert returns.loc["2024-01-03", "a"] == pytest.approx(0.1)
    assert np.isnan(returns.loc["2024-01-02", "a"])


def test_attribute_honours_start_and_end(tmp_path):
    data = VizaData(make_panel_with_attributes(tmp_path))
    wide = data.attribute("adv_21d", start=date(2024, 1, 3), end=date(2024, 1, 3))
    assert [d.date() for d in wide.index] == [date(2024, 1, 3)]


def test_unknown_key_lists_the_available_keys(tmp_path):
    data = VizaData(make_panel_with_attributes(tmp_path))
    with pytest.raises(AttributeUnavailableError) as raised:
        data.attribute("nope")
    assert str(raised.value) == "Unknown attribute 'nope'. Available: ret_1d, adv_21d"


def test_panel_without_attributes_raises_the_manifest_reason(tmp_path):
    panel = _panel(tmp_path)
    with pytest.raises(AttributeUnavailableError) as raised:
        VizaData(panel).attribute("ret_1d")
    assert str(raised.value) == "This panel has no catalog attributes."
    manifest = json.loads((panel / "manifest.json").read_text())
    manifest["attributes_unavailable_reason"] = "No store. Run build-attributes."
    (panel / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(AttributeUnavailableError) as raised:
        VizaData(panel).attribute("ret_1d")
    assert str(raised.value) == "No store. Run build-attributes."
    with pytest.raises(AttributeUnavailableError):
        VizaData(panel).catalog()


def test_catalog_lists_every_key(tmp_path):
    catalog = VizaData(make_panel_with_attributes(tmp_path)).catalog()
    assert list(catalog.columns) == [
        "key", "display_name", "description", "unit", "classification_snapshot",
    ]
    assert catalog["key"].tolist() == ["ret_1d", "adv_21d"]

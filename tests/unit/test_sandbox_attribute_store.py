from datetime import date

import polars as pl
from polars.testing import assert_frame_equal
from sandbox_helpers import synthetic_bars, synthetic_securities

from viza_sandbox import cli
from viza_sandbox.attribute_store import (
    LOOKBACK_CALENDAR_DAYS,
    attribute_store_id,
    build_attribute_store,
    find_attribute_store,
    read_attributes,
)
from viza_sandbox.attributes import compute_base, sector_zscore
from viza_sandbox.canonical import InMemoryCanonicalSource
from viza_sandbox.catalog import CATALOG_VERSION, load_catalog
from viza_sandbox.config import SandboxSettings

HISTORY_START = date(2023, 1, 2)
END = date(2024, 6, 28)


def _source():
    return InMemoryCanonicalSource(synthetic_securities(), synthetic_bars(HISTORY_START, END))


def _reference(bars: pl.DataFrame, start: date, end: date) -> pl.DataFrame:
    """Every attribute computed once over the whole history, in the store's long layout."""
    catalog = load_catalog()
    frame = bars.select(["security_id", "event_date", "close", "volume"]).to_pandas()
    close = frame.pivot(index="event_date", columns="security_id", values="close")
    volume = frame.pivot(index="event_date", columns="security_id", values="volume")
    values = compute_base(close, volume.astype("float64"), catalog)
    sector = {s: "Tech" for s in close.columns}
    for spec in catalog.sector_relative():
        values[spec.key] = sector_zscore(values[spec.inputs[0]], sector)
    long = None
    for key in catalog.keys():
        part = pl.from_pandas(
            values[key].reset_index().melt(id_vars="event_date", var_name="security_id",
                                           value_name=key)
        ).with_columns(pl.col("event_date").cast(pl.Date), pl.col(key).fill_nan(None))
        long = part if long is None else long.join(part, on=["event_date", "security_id"])
    keys = catalog.keys()
    return (
        long.filter((pl.col("event_date") >= start) & (pl.col("event_date") <= end))
        .filter(pl.any_horizontal(pl.col(keys).is_not_null()))
        .select(["security_id", "event_date", *keys])
        .sort(["event_date", "security_id"])
    )


def test_lookback_covers_the_longest_window():
    assert LOOKBACK_CALENDAR_DAYS == 400


def test_build_writes_one_file_per_year_and_a_manifest(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    source = _source()
    manifest = build_attribute_store(source, settings, start=HISTORY_START, end=END)
    assert manifest.store_id == attribute_store_id(
        CATALOG_VERSION, source.snapshot_id(), "faustcalc_fmp_snapshot", "unverified"
    )
    assert (manifest.start, manifest.end) == (HISTORY_START, END)
    assert manifest.keys == load_catalog().keys()
    assert manifest.catalog_version == CATALOG_VERSION
    directory = tmp_path / "attributes" / manifest.store_id
    assert sorted(p.name for p in directory.iterdir()) == [
        "2023.parquet", "2024.parquet", "store.json",
    ]
    assert set(manifest.row_counts) == {"2023", "2024"}
    assert manifest.row_counts["2024"] == pl.read_parquet(directory / "2024.parquet").height
    assert find_attribute_store(settings, manifest.store_id) == manifest


def test_chunked_build_equals_single_computation(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    source = _source()
    start = date(2023, 7, 3)
    manifest = build_attribute_store(source, settings, start=start, end=END)
    stored = read_attributes(settings, manifest.store_id, start, END)
    assert stored.columns == ["security_id", "event_date", *load_catalog().keys()]
    expected = _reference(source.price_bars(HISTORY_START, END), start, END)
    assert stored["ret_252d"].drop_nulls().len() > 0
    assert_frame_equal(
        stored.sort(["event_date", "security_id"]), expected, check_exact=False, abs_tol=1e-9
    )


def test_read_filters_to_the_requested_dates(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    manifest = build_attribute_store(_source(), settings, start=HISTORY_START, end=END)
    part = read_attributes(settings, manifest.store_id, date(2023, 12, 20), date(2024, 1, 10))
    assert part["event_date"].min() == date(2023, 12, 20)
    assert part["event_date"].max() == date(2024, 1, 10)


def test_first_days_are_null_not_guessed(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    manifest = build_attribute_store(_source(), settings, start=HISTORY_START, end=END)
    stored = read_attributes(settings, manifest.store_id, HISTORY_START, END)
    calendar = sorted(stored["event_date"].unique().to_list())
    early = stored.filter(pl.col("event_date") <= calendar[250])
    assert early["ret_252d"].null_count() == early.height
    assert stored.filter(pl.col("event_date") == HISTORY_START).height == 0


def test_rebuild_is_atomic_and_idempotent(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    source = _source()
    first = build_attribute_store(source, settings, start=HISTORY_START, end=END)
    second = build_attribute_store(source, settings, start=HISTORY_START, end=END)
    assert second == first
    assert [p.name for p in (tmp_path / "attributes").iterdir()] == [first.store_id]


def test_rebuild_with_a_different_range_replaces_the_store(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    source = _source()
    build_attribute_store(source, settings, start=HISTORY_START, end=END)
    narrow = build_attribute_store(source, settings, start=date(2024, 1, 1), end=END)
    assert narrow.start == date(2024, 1, 1)
    directory = tmp_path / "attributes" / narrow.store_id
    assert sorted(p.name for p in directory.iterdir()) == ["2024.parquet", "store.json"]


def test_find_returns_none_for_unknown_store(tmp_path):
    assert find_attribute_store(SandboxSettings(data_dir=tmp_path), "missing") is None


def test_cli_build_attributes_fails_closed_without_canonical_url(monkeypatch, capsys):
    monkeypatch.delenv("VIZA_SANDBOX_CANONICAL_DATABASE_URL", raising=False)
    code = cli.main(["build-attributes", "--from", "2024-01-01", "--to", "2024-01-31"])
    assert code != 0
    assert "VIZA_SANDBOX_CANONICAL_DATABASE_URL is required" in capsys.readouterr().err

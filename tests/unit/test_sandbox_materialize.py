import polars as pl
import pytest
from datetime import date, datetime, timedelta, timezone
from viza_sandbox.canonical import InMemoryCanonicalSource
from viza_sandbox.config import SandboxSettings
from viza_sandbox.materialize import PanelSpec, materialize, derive_membership, MaterializationError
from viza_sandbox.pit import EOD_POLICY_VERSION


def _source(prices):
    secs = pl.DataFrame({"security_id": ["a", "b"], "ticker": ["AAA", "BBB"], "exchange": ["NYSE"]*2, "currency": ["USD", "KRW"], "sector": ["Tech", None], "industry": ["Chips", None], "classification_as_of": [None, None]})
    return InMemoryCanonicalSource(secs, prices)


def _prices(rows):
    return pl.DataFrame(rows, schema={"security_id": pl.Utf8, "event_date": pl.Date, "close": pl.Float64, "adjusted_close": pl.Float64, "volume": pl.Int64, "currency": pl.Utf8, "ingestion_time": pl.Datetime("us", "UTC")}, orient="row")


def test_materialize_applies_eod_policy_and_writes_manifest(tmp_path):
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    src = _source(_prices([("a", date(2024,1,2), 10.0, 10.0, 1, "USD", t), ("b", date(2024,1,2), 5.0, 5.0, 1, "KRW", t)]))
    settings = SandboxSettings(data_dir=tmp_path)
    panel = materialize(src, PanelSpec(start=date(2024,1,1), end=date(2024,1,31)), settings)
    prices = pl.read_parquet(panel.directory / "prices.parquet")
    assert prices["available_at"].to_list()[0] == datetime(2024, 1, 2, 21, 0, tzinfo=timezone.utc)
    m = panel.manifest
    assert m.availability_policy_version == EOD_POLICY_VERSION
    assert m.cutoff_available_at == datetime(2024, 1, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
    assert sorted(m.currencies) == ["KRW", "USD"] and m.row_counts == {"prices": 2, "universe": 2}
    assert (panel.directory / "manifest.json").exists()


def test_materialize_is_cached_by_manifest_id(tmp_path):
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    src = _source(_prices([("a", date(2024,1,2), 10.0, 10.0, 1, "USD", t)]))
    settings = SandboxSettings(data_dir=tmp_path)
    spec = PanelSpec(start=date(2024,1,1), end=date(2024,1,31))
    first = materialize(src, spec, settings)
    src.price_bars = lambda *a, **k: (_ for _ in ()).throw(AssertionError("source must not be read on cache hit"))
    second = materialize(src, spec, settings)
    assert first.manifest.manifest_id == second.manifest.manifest_id


def test_duplicate_rows_raise(tmp_path):
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    src = _source(_prices([("a", date(2024,1,2), 10.0, 10.0, 1, "USD", t), ("a", date(2024,1,2), 10.5, 10.5, 1, "USD", t)]))
    with pytest.raises(MaterializationError, match="a.*2024-01-02"):
        materialize(src, PanelSpec(start=date(2024,1,1), end=date(2024,1,31)), SandboxSettings(data_dir=tmp_path))


def test_membership_uses_five_trading_day_lookback():
    days = [date(2024,1,d) for d in (2,3,4,5,8,9,10)]
    rows = [("a", d, 1.0, 1.0, 1, "USD", datetime(2024,5,1,tzinfo=timezone.utc)) for d in days]
    rows += [("b", days[0], 1.0, 1.0, 1, "USD", datetime(2024,5,1,tzinfo=timezone.utc))]
    members = derive_membership(_prices(rows), 5)
    b_days = members.filter(pl.col("security_id") == "b")["event_date"].to_list()
    assert b_days == days[:5]          # b priced only on day 1 stays a member through day 5, drops on day 6


def _universe_currency(panel):
    uni = pl.read_parquet(panel.directory / "universe.parquet")
    return sorted(zip(uni["security_id"].to_list(), uni["currency"].to_list()))


def test_universe_currency_comes_from_price_rows_not_securities(tmp_path):
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    # securities() says b is "KRW"/a is "USD"; price rows say the opposite.
    src = _source(_prices([("a", date(2024,1,2), 10.0, 10.0, 1, "KRW", t), ("b", date(2024,1,2), 5.0, 5.0, 1, "USD", t)]))
    panel = materialize(src, PanelSpec(start=date(2024,1,1), end=date(2024,1,31)), SandboxSettings(data_dir=tmp_path))
    assert _universe_currency(panel) == [("a", "KRW"), ("b", "USD")]
    assert panel.manifest.currencies == ["KRW", "USD"]


def test_universe_currency_is_earliest_event_date_regardless_of_row_order(tmp_path):
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    # Rows deliberately out of date order; earliest event_date currency is EUR.
    src = _source(_prices([("b", date(2024,1,3), 5.0, 5.0, 1, "USD", t), ("b", date(2024,1,2), 5.0, 5.0, 1, "EUR", t)]))
    panel = materialize(src, PanelSpec(start=date(2024,1,1), end=date(2024,1,31)), SandboxSettings(data_dir=tmp_path))
    assert set(_universe_currency(panel)) == {("b", "EUR")}


def _spec():
    return PanelSpec(start=date(2024, 1, 1), end=date(2024, 1, 31))


def _one_row_source():
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    return _source(_prices([("a", date(2024, 1, 2), 10.0, 10.0, 1, "USD", t)]))


def test_prices_parquet_carries_ingestion_time_after_available_at(tmp_path):
    t = datetime(2024, 5, 1, 3, tzinfo=timezone.utc)
    src = _source(_prices([("a", date(2024, 1, 2), 10.0, 10.0, 1, "USD", t)]))
    panel = materialize(src, _spec(), SandboxSettings(data_dir=tmp_path))
    prices = pl.read_parquet(panel.directory / "prices.parquet")
    assert prices.columns == [
        "security_id",
        "event_date",
        "available_at",
        "ingestion_time",
        "close",
        "adjusted_close",
        "volume",
        "currency",
    ]
    assert prices.schema["ingestion_time"] == pl.Datetime("us", "UTC")
    assert prices["ingestion_time"].to_list() == [t]


def test_duplicate_securities_rows_raise(tmp_path):
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    secs = pl.DataFrame(
        {
            "security_id": ["b", "b", "a", "a"],
            "ticker": ["BBB", "BBB2", "AAA", "AAA2"],
            "exchange": ["NYSE"] * 4,
            "currency": ["USD"] * 4,
            "sector": ["Tech", "Fin", None, None],
            "industry": [None] * 4,
            "classification_as_of": [None] * 4,
        }
    )
    src = InMemoryCanonicalSource(
        secs, _prices([("a", date(2024, 1, 2), 10.0, 10.0, 1, "USD", t)])
    )
    message = r"^Duplicate securities rows for security_id=a$"
    with pytest.raises(MaterializationError, match=message):
        materialize(src, _spec(), SandboxSettings(data_dir=tmp_path))


def test_panel_write_leaves_only_the_final_directory(tmp_path):
    panel = materialize(_one_row_source(), _spec(), SandboxSettings(data_dir=tmp_path))
    assert [p.name for p in (tmp_path / "panels").iterdir()] == [panel.manifest.manifest_id]
    assert sorted(p.name for p in panel.directory.iterdir()) == [
        "manifest.json",
        "prices.parquet",
        "universe.parquet",
    ]


def test_concurrent_winner_panel_is_returned_and_temp_discarded(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    src = _one_row_source()
    original = src.securities
    winner = {}

    def securities_with_race():
        if not winner:
            winner["panel"] = materialize(_one_row_source(), _spec(), settings)
        return original()

    src.securities = securities_with_race
    loser = materialize(src, _spec(), settings)
    assert loser.directory == winner["panel"].directory
    assert loser.manifest.created_at == winner["panel"].manifest.created_at
    assert [p.name for p in (tmp_path / "panels").iterdir()] == [loser.manifest.manifest_id]


def test_failed_panel_write_leaves_no_temp_dir(tmp_path, monkeypatch):
    def boom(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(pl.DataFrame, "write_parquet", boom)
    with pytest.raises(OSError, match="disk full"):
        materialize(_one_row_source(), _spec(), SandboxSettings(data_dir=tmp_path))
    assert list((tmp_path / "panels").iterdir()) == []


def _reference_membership(prices, lookback):
    calendar = sorted(set(prices["event_date"].to_list()))
    index_of = {d: i for i, d in enumerate(calendar)}
    priced = {}
    for sid, d in zip(prices["security_id"].to_list(), prices["event_date"].to_list()):
        priced.setdefault(sid, set()).add(index_of[d])
    return sorted(
        (calendar[i], sid)
        for sid, js in priced.items()
        for i in range(len(calendar))
        if any(i - lookback + 1 <= j <= i for j in js)
    )


def test_membership_matches_index_definition_on_random_panels():
    import random

    rng = random.Random(7)
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    days = [date(2024, 1, 1) + timedelta(days=k) for k in range(40)]
    for lookback in (1, 3, 5, 10):
        rows = [
            (sid, d, 1.0, 1.0, 1, "USD", t)
            for sid in ("a", "b", "c", "d")
            for d in days
            if rng.random() < 0.3
        ]
        prices = _prices(rows)
        got = derive_membership(prices, lookback)
        assert got.schema == {"event_date": pl.Date, "security_id": pl.Utf8}
        assert list(zip(got["event_date"].to_list(), got["security_id"].to_list())) == (
            _reference_membership(prices, lookback)
        )


# --- Catalog attributes sliced from the attribute store ------------------------------------

import json  # noqa: E402

from sandbox_helpers import synthetic_bars, synthetic_securities  # noqa: E402

from viza_sandbox.attribute_store import build_attribute_store  # noqa: E402
from viza_sandbox.catalog import CATALOG_VERSION, load_catalog  # noqa: E402

_NO_STORE = "No attribute store is built for this data snapshot. Run build-attributes."


def _attr_source(extra=None):
    bars = synthetic_bars(date(2023, 11, 1), date(2024, 2, 29))
    if extra is not None:
        bars = pl.concat([bars, extra])
    return InMemoryCanonicalSource(synthetic_securities(), bars)


def test_panel_includes_attributes_when_the_store_covers_the_range(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    source = _attr_source()
    store = build_attribute_store(source, settings, start=date(2024, 1, 1), end=date(2024, 2, 29))
    panel = materialize(source, PanelSpec(start=date(2024, 1, 8), end=date(2024, 1, 31)), settings)
    manifest = panel.manifest
    assert manifest.series == ["prices", "universe", "attributes"]
    assert manifest.panel_schema_version == 2
    assert manifest.catalog_version == CATALOG_VERSION
    assert manifest.attribute_store_id == store.store_id
    assert manifest.attributes_unavailable_reason is None
    attributes = pl.read_parquet(panel.directory / "attributes.parquet")
    assert attributes.columns == ["security_id", "event_date", "available_at", *load_catalog().keys()]
    assert manifest.row_counts["attributes"] == attributes.height > 0
    assert attributes["event_date"].min() == date(2024, 1, 8)
    assert attributes["event_date"].max() == date(2024, 1, 31)
    for row in attributes.select(["event_date", "available_at"]).unique().iter_rows():
        assert row[1] == datetime(row[0].year, row[0].month, row[0].day, 21, tzinfo=timezone.utc)
    catalog = json.loads((panel.directory / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["catalog_version"] == CATALOG_VERSION
    assert [a["key"] for a in catalog["attributes"]] == load_catalog().keys()


def test_panel_without_a_store_says_why(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    panel = materialize(
        _attr_source(), PanelSpec(start=date(2024, 1, 8), end=date(2024, 1, 31)), settings
    )
    assert not (panel.directory / "attributes.parquet").exists()
    assert not (panel.directory / "catalog.json").exists()
    assert panel.manifest.series == ["prices", "universe"]
    assert panel.manifest.attribute_store_id is None
    assert panel.manifest.catalog_version is None
    assert panel.manifest.attributes_unavailable_reason == _NO_STORE


def test_store_that_does_not_cover_the_range_is_refused(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    source = _attr_source()
    build_attribute_store(source, settings, start=date(2024, 1, 1), end=date(2024, 1, 31))
    panel = materialize(source, PanelSpec(start=date(2024, 1, 15), end=date(2024, 2, 15)), settings)
    assert not (panel.directory / "attributes.parquet").exists()
    assert panel.manifest.attribute_store_id is None
    assert panel.manifest.attributes_unavailable_reason == (
        "The attribute store covers 2024-01-01 to 2024-01-31, not the requested range."
    )


def test_store_from_an_older_snapshot_is_not_used(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    build_attribute_store(_attr_source(), settings, start=date(2024, 1, 1), end=date(2024, 2, 29))
    later = _prices(
        [("a", date(2024, 3, 1), 9.0, 9.0, 1, "USD", datetime(2024, 10, 1, tzinfo=timezone.utc))]
    )
    panel = materialize(
        _attr_source(later), PanelSpec(start=date(2024, 1, 8), end=date(2024, 1, 31)), settings
    )
    assert panel.manifest.attribute_store_id is None
    assert panel.manifest.attributes_unavailable_reason == _NO_STORE


def test_manifest_id_changes_when_a_store_appears(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    source = _attr_source()
    spec = PanelSpec(start=date(2024, 1, 8), end=date(2024, 1, 31))
    first = materialize(source, spec, settings)
    build_attribute_store(source, settings, start=date(2024, 1, 1), end=date(2024, 2, 29))
    second = materialize(source, spec, settings)
    assert second.manifest.manifest_id != first.manifest.manifest_id
    assert (second.directory / "attributes.parquet").exists()


# --- Liquidity floor on universe membership --------------------------------------------------

from viza_sandbox.materialize import (  # noqa: E402
    LIQUIDITY_LOOKBACK_CALENDAR_DAYS,
    LIQUIDITY_MIN_OBSERVATIONS,
    LIQUIDITY_WINDOW,
)

_FLOOR = 1_000_000.0


def _weekdays(start, count):
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def _liquidity_source(days, extra_rows=()):
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    rows = []
    for i, day in enumerate(days):
        rows.append(("liquid", day, 10.0, 10.0, 200_000, "USD", t))
        rows.append(("thin", day, 10.0, 10.0, 50_000, "USD", t))
        shell_close = 5000.0 if i % 7 == 3 else 0.05
        rows.append(("shell", day, shell_close, shell_close, 2_000_000, "USD", t))
    rows.extend(extra_rows)
    ids = sorted({row[0] for row in rows})
    secs = pl.DataFrame({
        "security_id": ids, "ticker": [s.upper() for s in ids], "exchange": ["NYSE"] * len(ids),
        "currency": ["USD"] * len(ids), "sector": [None] * len(ids),
        "industry": [None] * len(ids), "classification_as_of": [None] * len(ids),
    })
    return InMemoryCanonicalSource(secs, _prices(rows))


def _members(panel):
    return sorted(pl.read_parquet(panel.directory / "universe.parquet")["security_id"].unique())


def test_liquidity_constants():
    assert (LIQUIDITY_WINDOW, LIQUIDITY_MIN_OBSERVATIONS) == (21, 15)
    assert LIQUIDITY_LOOKBACK_CALENDAR_DAYS == 45


def test_membership_requires_median_dollar_volume(tmp_path):
    days = _weekdays(date(2024, 1, 1), 30)
    spec = PanelSpec(start=days[0], end=days[-1], min_median_dollar_volume=_FLOOR)
    panel = materialize(_liquidity_source(days), spec, SandboxSettings(data_dir=tmp_path))
    universe = pl.read_parquet(panel.directory / "universe.parquet")
    assert _members(panel) == ["liquid"]
    # 15 observations are needed, so membership starts on the 15th trading day.
    assert universe["event_date"].min() == days[14]
    assert universe["event_date"].max() == days[-1]
    prices = pl.read_parquet(panel.directory / "prices.parquet")
    assert sorted(prices["security_id"].unique()) == ["liquid", "shell", "thin"]
    assert panel.manifest.row_counts["universe"] == universe.height == 16


def test_floor_uses_prices_before_start(tmp_path):
    days = _weekdays(date(2024, 1, 1), 40)
    start = days[30]
    assert (start - days[0]).days <= LIQUIDITY_LOOKBACK_CALENDAR_DAYS
    spec = PanelSpec(start=start, end=days[-1], min_median_dollar_volume=_FLOOR)
    panel = materialize(_liquidity_source(days), spec, SandboxSettings(data_dir=tmp_path))
    universe = pl.read_parquet(panel.directory / "universe.parquet")
    assert _members(panel) == ["liquid"]
    assert universe["event_date"].min() == start
    prices = pl.read_parquet(panel.directory / "prices.parquet")
    assert prices["event_date"].min() == start


def test_fewer_than_15_observations_is_not_a_member(tmp_path):
    days = _weekdays(date(2024, 1, 1), 30)
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    newcomer = [("new", day, 10.0, 10.0, 900_000, "USD", t) for day in days[-14:]]
    spec = PanelSpec(start=days[0], end=days[-1], min_median_dollar_volume=_FLOOR)
    panel = materialize(
        _liquidity_source(days, newcomer), spec, SandboxSettings(data_dir=tmp_path)
    )
    assert _members(panel) == ["liquid"]


def test_zero_disables_the_floor(tmp_path):
    days = _weekdays(date(2024, 1, 1), 30)
    spec = PanelSpec(start=days[0], end=days[-1], min_median_dollar_volume=0)
    panel = materialize(_liquidity_source(days), spec, SandboxSettings(data_dir=tmp_path))
    assert _members(panel) == ["liquid", "shell", "thin"]
    universe = pl.read_parquet(panel.directory / "universe.parquet")
    assert universe["event_date"].min() == days[0]


def test_floor_is_part_of_the_manifest_id(tmp_path):
    days = _weekdays(date(2024, 1, 1), 30)
    settings = SandboxSettings(data_dir=tmp_path)
    source = _liquidity_source(days)
    ids = {
        materialize(
            source, PanelSpec(start=days[0], end=days[-1], min_median_dollar_volume=floor),
            settings,
        ).manifest.manifest_id
        for floor in (0, _FLOOR, 2 * _FLOOR)
    }
    assert len(ids) == 3


def test_reclassified_sector_makes_the_store_unavailable(tmp_path):
    settings = SandboxSettings(data_dir=tmp_path)
    bars = synthetic_bars(date(2023, 11, 1), date(2024, 2, 29))
    build_attribute_store(
        InMemoryCanonicalSource(synthetic_securities(), bars), settings,
        start=date(2024, 1, 1), end=date(2024, 2, 29),
    )
    moved = InMemoryCanonicalSource(synthetic_securities(sector="Energy"), bars)
    panel = materialize(moved, PanelSpec(start=date(2024, 1, 8), end=date(2024, 1, 31)), settings)
    assert panel.manifest.attribute_store_id is None
    assert panel.manifest.attributes_unavailable_reason == _NO_STORE


def test_floor_ignores_sparse_dates(tmp_path):
    days = _weekdays(date(2024, 1, 1), 30)
    t = datetime(2024, 5, 1, tzinfo=timezone.utc)
    stray = [("liquid", date(2024, 1, 21), 10.0, 10.0, 200_000, "USD", t)]  # a Sunday
    spec = PanelSpec(start=days[0], end=days[-1], min_median_dollar_volume=_FLOOR)
    panel = materialize(
        _liquidity_source(days, stray), spec, SandboxSettings(data_dir=tmp_path)
    )
    universe = pl.read_parquet(panel.directory / "universe.parquet")
    assert date(2024, 1, 21) not in universe["event_date"].to_list()
    assert universe["event_date"].min() == days[14]

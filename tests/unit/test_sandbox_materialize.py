import polars as pl, pytest
from datetime import date, datetime, timezone
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

# VIZA Quant Sandbox Phase 3a (Price-Based Attribute Catalog) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A quant calls `data.attribute("ret_21d")` inside a sandbox strategy and gets a VIZA-precomputed, point-in-time daily attribute for the whole universe.

**Architecture:** A catalog file names 24 price-based attributes. An operator command computes them from canonical prices into a Parquet attribute store keyed by data snapshot. Panel materialization slices the store into the panel directory, and `VizaData.attribute` reads it under the same visibility rule as prices. Nothing in the request path computes attributes.

**Tech Stack:** Python 3.14, polars (host), pandas and numpy (formulas, SDK), pydantic, pytest. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-15-viza-quant-sandbox-design.md` (sections 7.3, 7.4, 7.5, 7.8, 8 phase 3). This plan covers the price-based half of phase 3. Fundamentals, the FMP statements loader, market cap, the fundamental seed attributes and `data.series` are phase 3b, a separate plan.

## Global Constraints

- Do not edit frozen files: `alembic/versions/*`, `db/models.py`, `db/session.py`, `jobs/import_faustcalc_feature_store.py`, `jobs/import_faustcalc_sec_filings.py`, `jobs/build_faustcalc_universe.py`, `jobs/seed_faustcalc_auto_mappings.py`, `jobs/run_faustcalc_attribution_backfill.py`, `jobs/run_attribution.py`.
- `viza_sandbox` never imports the desktop `viza` package. Do not edit `config/viza_attribute_registry.json`: its loader (`viza/attribute_registry.py`) forbids extra fields and ships in the desktop package.
- Every sandbox setting has the prefix `VIZA_SANDBOX_` and a default.
- The canonical `attribution` database is read-only to the sandbox.
- Point-in-time: a value is visible on date D iff `available_at <= end_of_day_utc(D)`. There is no bypass. An attribute's `available_at` is `eod_available_at(event_date)` (21:00 UTC), the availability of its latest input.
- No interpretation by VIZA: attribute values are never clipped, winsorized or filled. A missing input gives a null, never zero and never a carried-forward value.
- Unit tests never need Postgres or Docker. Test output is pristine (no warnings).
- Line length 100; `ruff check --select E4,E7,E9,F` clean.
- One conventional commit per task, ending with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- `CHANGELOG.md` is append-only.

## Decisions that depart from the spec's letter (owner may override)

1. **Separate catalog file.** Spec 7.5 names `config/viza_attribute_registry.json` as the catalog. This plan uses `config/viza_sandbox_attribute_catalog.json`, for the reason in Global Constraints. Marking the synthetic desktop entries `synthetic_prototype` is a desktop-side change and is not in this plan; the sandbox cannot reach them.
2. **Parquet store, not database rows.** Spec 7.7 puts attribute series in the `viza_sandbox` database. 24 attributes over about 11.3 million security-days is about 270 million values; this plan stores them as yearly Parquet files under `VIZA_SANDBOX_DATA_DIR/attributes/`.
3. **RSI uses simple 14-day averages (Cutler), not Wilder smoothing.** Wilder's value depends on where the history starts, so the same date would get different values from different build windows.
4. **Sector z-scores use the snapshot sector.** They carry `classification_snapshot: true` in the catalog (spec 7.3.1).

## The catalog (exact keys)

Base attributes, all computed on `close` and `volume` over the **trading calendar** (the sorted distinct `event_date` values across all securities of the price source). A security with no bar on a calendar date has a null there; windows never skip over a gap.

| Key | Formula id | Params | Definition |
|---|---|---|---|
| `ret_1d`, `ret_5d`, `ret_21d`, `ret_63d`, `ret_252d` | `simple_return` | `window` | `close[t] / close[t-n] - 1`; null if either endpoint is null |
| `vol_21d`, `vol_63d` | `rolling_std` | `window` | sample std (ddof=1) of `ret_1d` over the last n calendar days; null unless all n are present |
| `ma_20d`, `ma_50d`, `ma_200d` | `rolling_mean` | `window` | mean of `close` over the last n calendar days; null unless all n are present |
| `rsi_14d` | `rsi_cutler` | `window=14` | `100 - 100 / (1 + G/L)`, G and L the mean gain and mean loss of `close` differences over the last 14 calendar days; null unless all 14 are present; `L == 0 and G > 0` gives 100; `G == 0 and L == 0` gives 50 |
| `adv_21d` | `rolling_mean_dollar_volume` | `window=21` | mean of `close * volume` over the last 21 calendar days; null unless all 21 are present |

Sector-relative attributes: one `<base>_sector_z` per base key (12 more, 24 total), formula id `sector_zscore`, input the base key. For each date and sector: `(x - mean) / std(ddof=1)` over securities with a non-null base value. Null when the sector is null, fewer than 3 securities have a value, or the std is 0.

Catalog version string: `viza_sandbox_catalog_v1`. Every entry has `source_type: "viza_computed"`, `rights_class: "viza_computed"`, `availability_rule: "eod_of_latest_input"`.

## Review Focus

1. **A security with a gap in its bars.** A reasonable user expects a null, not a return measured across the gap. Pinned in Task 2.
2. **A run whose date range is not fully covered by the built store.** The user expects attributes to be refused with a reason, not silently present for only part of the range. Pinned in Task 4.
3. **Canonical data refreshed after the store was built.** The user expects attributes to be unavailable until rebuilt, not served from the older snapshot. Pinned in Task 4.
4. **A sector with one member, or with identical values.** The user expects null, not `inf` or `NaN` noise presented as a z-score. Pinned in Task 2.
5. **Bad ticks (a close jumping 100,000x for a day).** The user expects the value to pass through untouched and the result to say that such moves were present. Pinned in Tasks 2 and 6.

---

### Task 1: Catalog file and loader

**Files:**
- Create: `config/viza_sandbox_attribute_catalog.json`, `viza_sandbox/catalog.py`
- Test: `tests/unit/test_sandbox_catalog.py`

**Interfaces:**
- Produces: `CATALOG_VERSION = "viza_sandbox_catalog_v1"`; `class AttributeSpec(BaseModel)` (`extra="forbid"`) with fields `key: str`, `display_name: str`, `description: str`, `unit: str`, `formula: Literal["simple_return", "rolling_std", "rolling_mean", "rsi_cutler", "rolling_mean_dollar_volume", "sector_zscore"]`, `params: dict[str, int]`, `inputs: list[str]`, `availability_rule: Literal["eod_of_latest_input"]`, `source_type: Literal["viza_computed"]`, `rights_class: Literal["viza_computed"]`, `classification_snapshot: bool = False`; `class Catalog(BaseModel)` with `catalog_version: str`, `attributes: list[AttributeSpec]`, method `keys() -> list[str]` (file order), `base() -> list[AttributeSpec]`, `sector_relative() -> list[AttributeSpec]`; `load_catalog(path: Path | None = None) -> Catalog` (default: the config file resolved from the repo root via `Path(__file__).resolve().parents[1] / "config" / ...`).

- [ ] **Step 1: Write the failing tests**

```python
def test_catalog_has_the_24_seed_keys():
    catalog = load_catalog()
    assert catalog.catalog_version == CATALOG_VERSION == "viza_sandbox_catalog_v1"
    base = ["ret_1d", "ret_5d", "ret_21d", "ret_63d", "ret_252d", "vol_21d", "vol_63d",
            "ma_20d", "ma_50d", "ma_200d", "rsi_14d", "adv_21d"]
    assert catalog.keys() == base + [f"{k}_sector_z" for k in base]
    assert [a.key for a in catalog.base()] == base

def test_sector_relative_entries_point_at_their_base_and_are_flagged():
    for spec in load_catalog().sector_relative():
        assert spec.formula == "sector_zscore"
        assert spec.inputs == [spec.key.removesuffix("_sector_z")]
        assert spec.classification_snapshot is True

def test_every_entry_is_viza_computed():
    for spec in load_catalog().attributes:
        assert (spec.source_type, spec.rights_class) == ("viza_computed", "viza_computed")
        assert spec.availability_rule == "eod_of_latest_input"

def test_loader_rejects_duplicate_keys_and_unknown_inputs(tmp_path):
    # write a catalog with ret_1d twice -> ValueError("duplicate attribute keys: ret_1d")
    # write a catalog whose sector_zscore input is "nope" -> ValueError("unknown input: nope")
```

- [ ] **Step 2: Run** `python -m pytest tests/unit/test_sandbox_catalog.py -q`. Expected: FAIL, `viza_sandbox.catalog` not found.
- [ ] **Step 3: Write the JSON file** with the 24 entries from "The catalog" section (windows in `params` as `{"window": n}`; `vol_*` inputs `["ret_1d"]`, others `["close"]`, `adv_21d` `["close", "volume"]`), then implement `viza_sandbox/catalog.py`. `inputs` may name `close`, `volume` or another catalog key.
- [ ] **Step 4: Run the test file.** Expected: 4 passed.
- [ ] **Step 5: Commit** `feat(sandbox): attribute catalog file and loader`.

### Task 2: Attribute formulas

**Files:**
- Create: `viza_sandbox/attributes.py`
- Test: `tests/unit/test_sandbox_attributes.py`

**Interfaces:**
- Consumes: `Catalog`, `AttributeSpec` (Task 1).
- Produces: `compute_base(close: pd.DataFrame, volume: pd.DataFrame, catalog: Catalog) -> dict[str, pd.DataFrame]` and `sector_zscore(values: pd.DataFrame, sector: Mapping[str, str | None]) -> pd.DataFrame`. `close` and `volume` are wide: index = the full trading calendar (ascending `DatetimeIndex`), columns = `security_id`, NaN where a security has no bar. Every returned frame has the same index and columns as `close`.

- [ ] **Step 1: Write the failing tests** (build `close`/`volume` with `pd.DataFrame`, use `pytest.approx`):

```python
def test_simple_return_and_gap_gives_null():
    close = wide({"a": [10, 11, None, 12.1, 13.31, 14.641]})  # 6 calendar days
    out = compute_base(close, wide({"a": [1] * 6}), load_catalog())["ret_1d"]["a"]
    assert out.iloc[1] == approx(0.10)
    assert pd.isna(out.iloc[2]) and pd.isna(out.iloc[3])   # no return across the gap
    assert out.iloc[4] == approx(0.10)

def test_rolling_windows_need_every_observation():
    # 25 days of close 1..25 for "a"; "b" identical but NaN on day 10
    assert pd.isna(out["ma_20d"]["a"].iloc[18]) and out["ma_20d"]["a"].iloc[19] == approx(10.5)
    assert out["ma_20d"]["b"].iloc[19:25].isna().all()     # window still contains the gap
    assert out["adv_21d"]["a"].iloc[20] == approx(sum(c * 2 for c in range(1, 22)) / 21)  # volume 2

def test_volatility_is_sample_std_of_daily_returns():
    # ret_1d alternates +1%, -1% for 21 days -> vol_21d == np.std(returns, ddof=1)

def test_rsi_cutler_edges():
    # 15 strictly rising closes -> rsi_14d.iloc[14] == 100
    # 15 equal closes -> 50
    # 7 gains of 1 and 7 losses of 1 -> 50; gains 2, losses 1 (7 each) -> approx(66.6667, abs=1e-4)

def test_bad_tick_passes_through_unclipped():
    close = wide({"a": [0.05, 5000.0, 0.05]})
    r = compute_base(close, wide({"a": [1, 1, 1]}), load_catalog())["ret_1d"]["a"]
    assert r.iloc[1] == approx(99999.0) and r.iloc[2] == approx(-0.99999)

def test_sector_zscore_nulls():
    values = wide({"a": [1.0], "b": [2.0], "c": [3.0], "d": [5.0], "e": [5.0], "f": [5.0], "g": [9.0]})
    sector = {"a": "T", "b": "T", "c": "T", "d": "U", "e": "U", "f": "U", "g": None}
    z = sector_zscore(values, sector).iloc[0]
    assert z[["a", "b", "c"]].tolist() == approx([-1.0, 0.0, 1.0])
    assert z[["d", "e", "f"]].isna().all()   # std 0
    assert pd.isna(z["g"])                    # no sector
    # a sector with 2 valued members -> all null
```

- [ ] **Step 2: Run the file.** Expected: FAIL on import.
- [ ] **Step 3: Implement both functions in `viza_sandbox/attributes.py`.** Use `shift(n)` and `rolling(n, min_periods=n)` on the wide frames; never `ffill`, `fillna` or `pct_change` (its default fill is the look-through this plan forbids). `compute_base` dispatches on `spec.formula` and raises `ValueError` for a formula it does not handle.
- [ ] **Step 4: Run the file.** Expected: all pass, no warnings (`-W error`).
- [ ] **Step 5: Commit** `feat(sandbox): price-based attribute formulas`.

### Task 3: Attribute store and the build command

**Files:**
- Create: `viza_sandbox/attribute_store.py`
- Modify: `viza_sandbox/cli.py` (new subcommand `build-attributes`)
- Test: `tests/unit/test_sandbox_attribute_store.py`, `tests/lookahead_audit/test_sandbox_pit.py` (append)

**Interfaces:**
- Consumes: `CanonicalSource.price_bars/securities/snapshot_id`, `SandboxSettings`, `load_catalog`, `compute_base`, `sector_zscore`.
- Produces:
  - `LOOKBACK_CALENDAR_DAYS = 400` (covers 252 trading days).
  - `attribute_store_id(catalog_version: str, canonical_snapshot_id: str, price_source: str, price_adjustment_status: str) -> str` (sha256 hex of the sorted-key JSON of those four).
  - `class AttributeStoreManifest(BaseModel)`: `store_id`, `catalog_version`, `canonical_snapshot_id`, `price_source`, `price_adjustment_status`, `start: date`, `end: date`, `keys: list[str]`, `row_counts: dict[str, int]` (per year), `built_at: datetime`.
  - `build_attribute_store(source: CanonicalSource, settings: SandboxSettings, *, start: date, end: date, price_source: str = "faustcalc_fmp_snapshot") -> AttributeStoreManifest`
  - `find_attribute_store(settings: SandboxSettings, store_id: str) -> AttributeStoreManifest | None`
  - `read_attributes(settings: SandboxSettings, store_id: str, start: date, end: date) -> pl.DataFrame` with columns `security_id` (Utf8), `event_date` (Date), then one Float64 column per catalog key, in catalog order.
- Layout: `settings.data_dir / "attributes" / store_id /` holding `store.json` and one `YYYY.parquet` per calendar year in `[start, end]`. A row is written only if at least one attribute is non-null.

- [ ] **Step 1: Write the failing tests** (use `InMemoryCanonicalSource`; generate about 300 business days of bars for 4 securities across two calendar years, with a deterministic price path):

```python
def test_build_writes_one_file_per_year_and_a_manifest(tmp_path): ...
    # manifest.start/end echo the request; keys == load_catalog().keys(); files 2023.parquet, 2024.parquet

def test_chunked_build_equals_single_computation(tmp_path):
    # read_attributes over the whole range == compute_base/sector_zscore run once over all bars,
    # compared with pl.testing.assert_frame_equal(check_exact=False). Proves the lookback
    # buffer at the year boundary loses nothing.

def test_first_days_are_null_not_guessed(tmp_path):
    # with history starting on `start`, ret_252d is null for every row in the first 252 days

def test_rebuild_is_atomic_and_idempotent(tmp_path):
    # building twice returns the same store_id and leaves no ".tmp-" sibling directory

def test_find_returns_none_for_unknown_store(tmp_path): ...

def test_cli_build_attributes_fails_closed_without_canonical_url(monkeypatch, capsys):
    # main(["build-attributes", "--from", "2024-01-01", "--to", "2024-01-31"]) returns nonzero and
    # prints "VIZA_SANDBOX_CANONICAL_DATABASE_URL is required"
```

Append to `tests/lookahead_audit/test_sandbox_pit.py`:

```python
def test_attribute_values_do_not_depend_on_later_prices(tmp_path):
    # build store A; multiply every close after date D by 7 and build store B (different
    # snapshot_id, so a different store). For every key, rows with event_date <= D are equal.
```

- [ ] **Step 2: Run both files with `-k attribute`.** Expected: FAIL on import.
- [ ] **Step 3: Implement.** For each calendar year in range: load bars from `max(year start, start) - LOOKBACK_CALENDAR_DAYS` to `min(year end, end)`, pivot to wide on the distinct `event_date` values of what was loaded, compute, keep only rows inside the year and the request, write long. Build in a temp sibling directory and `os.replace` it into place, as `materialize` does. If the store already exists with the same `start`/`end`, return its manifest without rebuilding; if it exists with a different range, rebuild and replace. The CLI subcommand takes `--from`, `--to`, optional `--source`, and prints `store_id=...` and one `YYYY rows=N` line per year.
- [ ] **Step 4: Run** `python -m pytest tests/unit/test_sandbox_attribute_store.py tests/lookahead_audit/test_sandbox_pit.py -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(sandbox): attribute store and build-attributes command`.

### Task 4: Slice the store into the panel

**Files:**
- Modify: `viza_sandbox/materialize.py`
- Test: `tests/unit/test_sandbox_materialize.py` (append)

**Interfaces:**
- Consumes: `attribute_store_id`, `find_attribute_store`, `read_attributes`, `CATALOG_VERSION`, `load_catalog`.
- Produces: `ATTRIBUTES_FILENAME = "attributes.parquet"`, `CATALOG_FILENAME = "catalog.json"`, `PANEL_SCHEMA_VERSION = 2`; new `DataManifest` fields `panel_schema_version: int = 1`, `catalog_version: str | None = None`, `attribute_store_id: str | None = None`, `attributes_unavailable_reason: str | None = None`. `attributes.parquet` columns: `security_id`, `event_date`, `available_at` (`eod_available_at(event_date)`), then the catalog keys. `catalog.json` is the catalog file's content, copied.

- [ ] **Step 1: Write the failing tests**

```python
def test_panel_includes_attributes_when_the_store_covers_the_range(tmp_path):
    # build store for the range, materialize -> attributes.parquet and catalog.json exist;
    # manifest.series == ["prices", "universe", "attributes"]; catalog_version and
    # attribute_store_id set; attributes_unavailable_reason is None;
    # available_at == event_date at 21:00 UTC for every row

def test_panel_without_a_store_says_why(tmp_path):
    # no store -> no attributes.parquet; manifest.attribute_store_id is None;
    # reason == "No attribute store is built for this data snapshot. Run build-attributes."

def test_store_that_does_not_cover_the_range_is_refused(tmp_path):
    # store built for 2024-01-01..2024-01-31, panel for 2024-01-15..2024-02-15 ->
    # no attributes.parquet; reason ==
    # "The attribute store covers 2024-01-01 to 2024-01-31, not the requested range."

def test_store_from_an_older_snapshot_is_not_used(tmp_path):
    # build store, then add a bar with a later ingestion_time (snapshot_id changes) ->
    # materialize gives the "No attribute store is built" reason

def test_manifest_id_changes_when_a_store_appears(tmp_path):
    # materialize (no store) -> id1; build store; materialize -> id2 != id1 and has attributes
```

- [ ] **Step 2: Run the file with `-k "attributes or store or manifest_id"`.** Expected: FAIL.
- [ ] **Step 3: Implement.** Add `panel_schema_version` (2), the catalog version and the resolved `attribute_store_id` (or `None`) to the `_manifest_id` payload, so panels cached before this change and panels cached before a store existed are not reused.
- [ ] **Step 4: Run** `python -m pytest tests/unit/test_sandbox_materialize.py -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(sandbox): include catalog attributes in materialized panels`.

### Task 5: `data.attribute` and `data.catalog` in the SDK

**Files:**
- Modify: `viza_sandbox/sdk.py`, `tests/unit/sandbox_helpers.py` (add `make_panel_with_attributes(root: Path) -> Path`)
- Test: `tests/unit/test_sandbox_sdk.py` (append), `tests/lookahead_audit/test_sandbox_pit.py` (append)

**Interfaces:**
- Consumes: the panel files of Task 4.
- Produces: `VizaData.attribute(key: str, start: date | None = None, end: date | None = None) -> pd.DataFrame` (wide: `event_date` index, `security_id` columns, like `prices`); `VizaData.catalog() -> pd.DataFrame` with columns `key`, `display_name`, `description`, `unit`, `classification_snapshot`; `class AttributeUnavailableError(LookupError)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_attribute_returns_a_wide_frame_like_prices(tmp_path): ...
    # same index name and column layout as data.prices("close") for the same panel

def test_unknown_key_lists_the_available_keys(tmp_path):
    # raises AttributeUnavailableError whose message starts "Unknown attribute 'nope'. Available: "

def test_panel_without_attributes_raises_the_manifest_reason(tmp_path):
    # make_panel (no attributes) with manifest attributes_unavailable_reason set ->
    # AttributeUnavailableError(str == that reason); with no reason in the manifest ->
    # "This panel has no catalog attributes."

def test_catalog_lists_every_key(tmp_path): ...
```

Append to the look-ahead audit:

```python
def test_attribute_respects_as_of_cutoff(tmp_path):
    # data.as_of(date(2024, 1, 2)).attribute("ret_1d") has no row after 2024-01-02

def test_attribute_row_with_late_available_at_is_hidden(tmp_path):
    # a row whose available_at is after end_of_day_utc(event_date) never appears
```

- [ ] **Step 2: Run both files with `-k "attribute or catalog"`.** Expected: FAIL.
- [ ] **Step 3: Implement**, reusing the visibility logic of `_visible_prices` (factor it into one private method taking the file name; do not duplicate the filter). Read only the needed column plus keys with `pd.read_parquet(columns=...)`.
- [ ] **Step 4: Run** `python -m pytest tests/unit/test_sandbox_sdk.py tests/lookahead_audit/test_sandbox_pit.py -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(sandbox): data.attribute and data.catalog`.

### Task 6: Disclose extreme price moves, document, verify end to end

**Files:**
- Modify: `viza_sandbox/evaluate.py`, `viza_sandbox/runs.py` (header keys), `docs/viza_end_product/VIZA_SANDBOX_OPERATIONS.md`, `PROJECT_STATUS.md`, `CHANGELOG.md`
- Test: `tests/unit/test_sandbox_evaluate.py` (append), `tests/unit/test_sandbox_api.py` (append)

**Interfaces:**
- Produces: `EXTREME_MOVE_RATIO = 10.0`; new `ScoresEvaluation` field `extreme_moves: dict` = `{"ratio": 10.0, "security_days": int, "securities": int}` counting scored security-days whose realized one-day close ratio is `>= 10` or `<= 0.1`; when `security_days > 0`, a `warnings` entry `"{n} scored security-days across {m} securities had a one-day close move of 10x or more; quantile returns include them unclipped."`. Result header gains `catalog_version` and `attribute_store_id`, read from the run's stored manifest.

- [ ] **Step 1: Write the failing tests**

```python
def test_extreme_moves_are_counted_and_warned_not_removed():
    # 4 securities, one with closes [1, 1, 1000, 1]; evaluate_scores(...) ->
    # extreme_moves == {"ratio": 10.0, "security_days": 2, "securities": 1}; the warning text
    # above is present; the affected quantile's daily return still contains the 999x move

def test_no_extreme_moves_no_warning(): ...

def test_api_run_can_call_data_attribute(tmp_path):
    # with the local runner and an in-memory source with a built store, a strategy returning
    # scores(data.attribute("ret_1d")) completes; header.catalog_version == "viza_sandbox_catalog_v1"
```

- [ ] **Step 2: Run both files.** Expected: the three new tests FAIL.
- [ ] **Step 3: Implement.** The count uses the same return matrix `evaluate_scores` already builds; it changes no return.
- [ ] **Step 4: Run the full sandbox suite** `python -m pytest tests/unit tests/lookahead_audit -q -k sandbox`. Expected: all pass, Docker test passing or skipped.
- [ ] **Step 5: Update the docs.** Operations guide: a "Build the attribute store" section (`python -m viza_sandbox.cli build-attributes --from ... --to ...`, rebuild after every canonical refresh, rebuild the runtime image since the SDK changed), the 24 keys with one-line definitions, the three "why attributes are unavailable" reasons, and the `extreme_moves` disclosure. `PROJECT_STATUS.md`: phase 3a done, 3b next. Append one line to `CHANGELOG.md`.
- [ ] **Step 6: Commit** `feat(sandbox): disclose extreme price moves; document the attribute catalog`.

## Operator verification after the last task (not automatable in unit tests)

1. `build-attributes` over the full price range against the canonical database; record wall time and peak memory in the operations guide.
2. Rebuild the runtime image, submit `scores(data.attribute("ret_21d").where(data.attribute("adv_21d") > 1e6))` for one month, and confirm the header shows `catalog_version` and the `extreme_moves` count.

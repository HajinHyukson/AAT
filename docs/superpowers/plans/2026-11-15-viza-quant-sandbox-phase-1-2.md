# VIZA Quant Sandbox, Phases 1 and 2: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A quant submits a Python `strategy(data)` over HTTP, it runs isolated against a point-in-time panel of FaustCalc-universe daily prices, and they get back a quantile backtest of the scores it returned.

**Architecture:** A new `viza_sandbox/` package, separate from the desktop engine in `viza/`. A data service reads the canonical `attribution` tables read-only, applies the EOD availability policy, and materializes Parquet panels keyed by a data manifest. A runner executes the user's code in a Docker container (or a local subprocess in tests) with the panel mounted read-only. An evaluator turns returned scores into a quantile backtest with a disclosed D+1 execution convention. Run records and user accounts live in the sandbox's own database.

**Tech Stack:** Python 3.12+ (repo runs 3.14), FastAPI, SQLAlchemy 2 Core and ORM, pydantic 2, pydantic-settings, polars for materialization, pandas and pyarrow inside the SDK, Docker CLI via subprocess, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-viza-quant-sandbox-design.md`. This plan implements spec phases 1 and 2 (section 8). Phases 3 to 6 are separate plans.

## Global Constraints

- Do not edit any file frozen by `docs/viza_research/aat_foundation/LIVE_BACKFILL_DEVELOPMENT_GUARDRAILS.md`: `alembic/versions/*`, `db/models.py`, `db/session.py`, `jobs/import_faustcalc_feature_store.py`, `jobs/import_faustcalc_sec_filings.py`, `jobs/build_faustcalc_universe.py`, `jobs/seed_faustcalc_auto_mappings.py`, `jobs/run_faustcalc_attribution_backfill.py`, `jobs/run_attribution.py`. Importing from them is fine.
- No new required environment variable for existing server jobs. Every sandbox setting has the prefix `VIZA_SANDBOX_` and a default.
- The canonical `attribution` database is read-only to the sandbox. Sandbox code opens canonical connections with `SET TRANSACTION READ ONLY` and never issues DDL or DML against them.
- Sandbox tables must run on SQLite in tests and Postgres in deployment: use `sqlalchemy.String(36)` for ids and `sqlalchemy.JSON`, never `postgresql.UUID` or `JSONB`.
- Point-in-time: a value is visible on date D iff `available_at <= end_of_day_utc(D)`. There is no bypass. Availability policy version string: `faustcalc_fmp_snapshot_eod_policy_v1`. EOD availability timestamp: `event_date` at `21:00:00 UTC`.
- Universe membership on date D: the security has a close on one of the last 5 trading days ending at D inclusive, where trading days are the distinct `event_date` values in the price panel.
- Execution convention printed in every result: `signal_lag_days = 1`, `transaction_cost = 0.0`, `benchmark = null`. Scores at date D apply to the return realized from the close of D+1 to the close of D+2.
- Resource limits defaults: `wall_clock_seconds = 600`, `memory_gb = 8`, `cpus = 2`. Container has `--network none`.
- Synthetic resolvers in `viza/attribute_resolvers.py` are never imported by `viza_sandbox`.
- Every return from user code must be declared. A bare float `DataFrame` fails with exactly: `Return value is a float DataFrame; declare it with viza.scores(df) or viza.weights(df).`
- Tests: `python -m pytest tests/unit/test_sandbox_*.py tests/lookahead_audit/test_sandbox_pit.py -q` must pass at the end of every task. Unit tests never need Postgres or Docker; the single Docker test skips when `docker` is unavailable.
- Commits: conventional prefix, one commit per task, on a branch `viza-quant-sandbox` created from the current HEAD.

## Review Focus

Inputs the spec implies but no obvious test exercises. Each line has a pinned test in the named task.

1. A security with missing days inside the range: missing closes must be `NaN` in the wide panel, excluded from that day's quantile, and never filled with zero. Task 6.
2. A requested date range entirely before available data: `VizaData.prices` returns an empty frame with the right shape and `evaluate_scores` raises `EvaluationError("No scores fall inside the panel date range.")` instead of crashing. Tasks 4 and 6.
3. A strategy that returns columns not in the universe: the evaluator drops them and lists them in `warnings`, it does not silently score them. Task 6.
4. Duplicate `(security_id, event_date)` rows from the canonical source: materialization raises `MaterializationError` naming the first duplicate. Task 3.
5. A user requesting another user's run: `GET /sandbox/runs/{id}` returns 404, not 403, so run ids leak nothing. Task 7.

---

## File Structure

```
viza_sandbox/
  __init__.py
  config.py            SandboxSettings (pydantic-settings, prefix VIZA_SANDBOX_)
  store.py             SQLAlchemy models SandboxUser, SandboxRun; SandboxStore CRUD; token hashing
  canonical.py         CanonicalSource protocol, PostgresCanonicalSource, InMemoryCanonicalSource, lightweight Core tables
  pit.py               end_of_day_utc, eod_available_at, visible_on, policy constants
  materialize.py       PanelSpec, DataManifest, materialize(), membership derivation, panel cache
  sdk.py               VizaData, Scores, scores(), coerce_return(), ReturnDeclarationError
  runner.py            RunLimits, RunOutcome, Runner protocol, LocalProcessRunner, DockerRunner
  runner_entry.py      container/subprocess entrypoint: load strategy.py, build VizaData, write out/
  evaluate.py          BacktestSettings, ScoresEvaluation, evaluate_scores(), EvaluationError
  runs.py              RunRequest, submit_run(), execute_run(): materialize -> run -> evaluate -> persist
  api.py               FastAPI app: POST /sandbox/runs, GET /sandbox/runs/{id}, GET /sandbox/runs/{id}/result
  cli.py               init-db, create-user, check-split-adjustment, serve
  runtime_image/
    Dockerfile         python:3.14-slim + pandas pyarrow numpy scipy statsmodels + viza_sandbox + viza alias
    viza/__init__.py   alias package: from viza_sandbox.sdk import *
tests/unit/test_sandbox_store.py
tests/unit/test_sandbox_canonical.py
tests/unit/test_sandbox_materialize.py
tests/unit/test_sandbox_sdk.py
tests/unit/test_sandbox_runner.py
tests/unit/test_sandbox_evaluate.py
tests/unit/test_sandbox_api.py
tests/unit/test_sandbox_cli.py
tests/lookahead_audit/test_sandbox_pit.py
docs/viza_end_product/VIZA_SANDBOX_OPERATIONS.md
pyproject.toml         add viza_sandbox* to packages, add pandas and pyarrow to dependencies
```

---

### Task 1: Package scaffold, settings, and the sandbox store

**Files:**
- Create: `viza_sandbox/__init__.py`, `viza_sandbox/config.py`, `viza_sandbox/store.py`
- Modify: `pyproject.toml` (packages include list; dependencies)
- Test: `tests/unit/test_sandbox_store.py`

**Interfaces:**
- Produces:
  - `SandboxSettings(BaseSettings)` with fields and defaults: `database_url: str = "sqlite:///./data/viza_sandbox/sandbox.db"`, `canonical_database_url: str | None = None`, `data_dir: Path = Path("data/viza_sandbox")`, `runs_dir: Path = Path("data/viza_sandbox/runs")`, `runner: Literal["docker", "local"] = "docker"`, `docker_image: str = "viza-sandbox-runtime:latest"`, `wall_clock_seconds: int = 600`, `memory_gb: int = 8`, `cpus: int = 2`, `price_adjustment_status: Literal["unverified", "adjusted", "unadjusted"] = "unverified"`, `source_rights_state: str = "development_proving"`. `model_config = SettingsConfigDict(env_prefix="VIZA_SANDBOX_")`.
  - `class SandboxUser(Base)`: `user_id: str(36) pk`, `name: str`, `token_hash: str(64) unique`, `created_at: datetime`, `is_owner: bool default False`.
  - `class SandboxRun(Base)`: `run_id: str(36) pk`, `user_id: str(36) fk`, `status: str` in `{"queued","running","completed","failed","timed_out"}`, `code_text: Text`, `code_hash: str(64)`, `request: JSON`, `data_manifest: JSON | None`, `limits: JSON`, `exit_code: int | None`, `stdout: Text`, `stderr: Text`, `result_kind: str | None`, `result_path: str | None`, `evaluation: JSON | None`, `error: Text | None`, `created_at`, `started_at | None`, `finished_at | None`.
  - `class SandboxStore`: `__init__(self, database_url: str)`; `create_schema() -> None`; `create_user(name: str, *, is_owner: bool = False) -> tuple[SandboxUser, str]` returning the plaintext token once; `user_for_token(token: str) -> SandboxUser | None`; `create_run(user_id: str, code_text: str, request: dict, limits: dict) -> SandboxRun`; `get_run(run_id: str) -> SandboxRun | None`; `update_run(run_id: str, **fields) -> SandboxRun`; `list_runs(user_id: str) -> list[SandboxRun]`.
  - `hash_token(token: str) -> str` = sha256 hex. Tokens are `secrets.token_urlsafe(32)`. `code_hash` = sha256 hex of the UTF-8 code bytes. Ids are `str(uuid4())`.

- [ ] **Step 1: Add the package and dependencies to `pyproject.toml`**

Add `"viza_sandbox*"` to `[tool.setuptools.packages.find].include`. Add `"pandas>=2.2"` and `"pyarrow>=15"` to `dependencies`.

- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/test_sandbox_store.py
from viza_sandbox.config import SandboxSettings
from viza_sandbox.store import SandboxStore, hash_token

def test_settings_defaults_and_prefix(monkeypatch, tmp_path):
    monkeypatch.setenv("VIZA_SANDBOX_WALL_CLOCK_SECONDS", "30")
    s = SandboxSettings()
    assert s.wall_clock_seconds == 30
    assert s.memory_gb == 8 and s.cpus == 2 and s.runner == "docker"
    assert s.price_adjustment_status == "unverified"

def test_create_user_returns_token_once_and_resolves(tmp_path):
    store = SandboxStore(f"sqlite:///{tmp_path/'s.db'}")
    store.create_schema()
    user, token = store.create_user("alice", is_owner=True)
    assert user.token_hash == hash_token(token)
    assert store.user_for_token(token).user_id == user.user_id
    assert store.user_for_token("wrong") is None

def test_run_lifecycle(tmp_path):
    store = SandboxStore(f"sqlite:///{tmp_path/'s.db'}")
    store.create_schema()
    user, _ = store.create_user("bob")
    run = store.create_run(user.user_id, "def strategy(data): ...", {"start": "2024-01-01"}, {"cpus": 2})
    assert run.status == "queued" and len(run.code_hash) == 64
    updated = store.update_run(run.run_id, status="completed", exit_code=0)
    assert updated.status == "completed"
    assert [r.run_id for r in store.list_runs(user.user_id)] == [run.run_id]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_sandbox_store.py -q`
Expected: FAIL with `ModuleNotFoundError: viza_sandbox`

- [ ] **Step 4: Implement `config.py` and `store.py`**

`store.py` declares its own `Base = declarative_base()`; it does not import `db.models`. `SandboxStore` uses `create_engine(database_url)` with `connect_args={"check_same_thread": False}` when the URL starts with `sqlite`. `update_run` raises `KeyError(run_id)` when missing.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_sandbox_store.py -q`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git switch viza-quant-sandbox 2>/dev/null || git switch -c viza-quant-sandbox
git add pyproject.toml viza_sandbox/__init__.py viza_sandbox/config.py viza_sandbox/store.py tests/unit/test_sandbox_store.py
git commit -m "feat(sandbox): scaffold viza_sandbox package with settings and run store"
```

---

### Task 2: Canonical read-only source

**Files:**
- Create: `viza_sandbox/canonical.py`
- Test: `tests/unit/test_sandbox_canonical.py`

**Interfaces:**
- Produces:
  - Frames are `polars.DataFrame`. Securities frame columns: `security_id: Utf8`, `ticker: Utf8`, `exchange: Utf8`, `currency: Utf8`, `sector: Utf8 (nullable)`, `industry: Utf8 (nullable)`, `classification_as_of: Datetime(UTC) (nullable)`. Price frame columns: `security_id: Utf8`, `event_date: Date`, `close: Float64`, `adjusted_close: Float64`, `volume: Int64 (nullable)`, `currency: Utf8`, `ingestion_time: Datetime(UTC)`.
  - `class CanonicalSource(Protocol)`: `securities(self) -> pl.DataFrame`; `price_bars(self, start: date, end: date, *, source: str = "faustcalc_fmp_snapshot") -> pl.DataFrame`; `snapshot_id(self, *, source: str = "faustcalc_fmp_snapshot") -> str` (ISO-8601 of `max(ingestion_time)` for that source, naive values treated as UTC, or `"empty"`).
  - `class InMemoryCanonicalSource`: `__init__(self, securities: pl.DataFrame, price_bars: pl.DataFrame)`; implements the protocol; `price_bars` filters by `event_date` range and `source` column if present.
  - `class PostgresCanonicalSource`: `__init__(self, database_url: str)`; implements the protocol with SQLAlchemy Core against lightweight `Table` objects `security_t`, `security_ticker_history_t`, `price_bar_t`, `faustcalc_company_t` declared in this module with generic types. Every query runs inside `with engine.connect() as conn: conn.execute(text("SET TRANSACTION READ ONLY"))` on Postgres dialects.
  - Ticker as-of: the `securities()` query joins the ticker row with `active_to IS NULL`; sector and industry come from `faustcalc_company` on `canonical_ticker = ticker`; `classification_as_of = faustcalc_company.source_last_updated`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_sandbox_canonical.py
import polars as pl
from datetime import date, datetime, timezone
from viza_sandbox.canonical import InMemoryCanonicalSource, PostgresCanonicalSource, price_bar_t, security_t, security_ticker_history_t, faustcalc_company_t

def _prices():
    return pl.DataFrame({
        "security_id": ["a", "a", "b"],
        "event_date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 2)],
        "close": [10.0, 11.0, 5.0], "adjusted_close": [10.0, 11.0, 5.0],
        "volume": [100, 110, 50], "currency": ["USD"] * 3,
        "ingestion_time": [datetime(2024, 5, 1, tzinfo=timezone.utc)] * 3,
    })

def test_in_memory_filters_range_and_reports_snapshot():
    src = InMemoryCanonicalSource(pl.DataFrame({"security_id": ["a", "b"], "ticker": ["AAA", "BBB"], "exchange": ["NYSE"]*2, "currency": ["USD"]*2, "sector": [None, "Tech"], "industry": [None, "Chips"], "classification_as_of": [None, None]}), _prices())
    out = src.price_bars(date(2024, 1, 3), date(2024, 1, 3))
    assert out["security_id"].to_list() == ["a"]
    assert src.snapshot_id() == "2024-05-01T00:00:00+00:00"

def test_lightweight_tables_match_canonical_column_names():
    from db import models
    for table, model in [(price_bar_t, models.PriceBar), (security_t, models.Security), (security_ticker_history_t, models.SecurityTickerHistory), (faustcalc_company_t, models.FaustcalcCompany)]:
        assert set(table.c.keys()) <= set(model.__table__.c.keys())

def test_postgres_source_reads_through_sqlite_schema(tmp_path):
    url = f"sqlite:///{tmp_path/'canon.db'}"
    src = PostgresCanonicalSource(url)
    src.create_tables_for_tests()
    src.insert_for_tests(security_t, [{"security_id": "a", "company_id": "c", "exchange": "NYSE", "active_from": datetime(2020,1,1,tzinfo=timezone.utc), "active_to": None}])
    src.insert_for_tests(security_ticker_history_t, [{"ticker_history_id": "t1", "security_id": "a", "ticker": "AAA", "active_from": datetime(2020,1,1,tzinfo=timezone.utc), "active_to": None}])
    src.insert_for_tests(faustcalc_company_t, [{"faustcalc_company_id": "f1", "source_ticker": "AAA", "canonical_ticker": "AAA", "sector": "Tech", "industry": "Chips", "source_last_updated": datetime(2024,5,1,tzinfo=timezone.utc)}])
    src.insert_for_tests(price_bar_t, [{"price_bar_id": "p1", "security_id": "a", "event_time": datetime(2024,1,2,tzinfo=timezone.utc), "ingestion_time": datetime(2024,5,1,tzinfo=timezone.utc), "timestamp_available": datetime(2024,5,1,tzinfo=timezone.utc), "close": 10.0, "adjusted_close": 10.0, "volume": 100, "currency": "USD", "source": "faustcalc_fmp_snapshot"}])
    secs = src.securities()
    assert secs.row(0, named=True)["ticker"] == "AAA" and secs.row(0, named=True)["sector"] == "Tech"
    bars = src.price_bars(date(2024, 1, 1), date(2024, 1, 31))
    assert bars["event_date"].to_list() == [date(2024, 1, 2)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_sandbox_canonical.py -q`
Expected: FAIL with `ImportError` on `viza_sandbox.canonical`

- [ ] **Step 3: Implement `canonical.py`**

Lightweight tables carry only the columns the sandbox reads plus primary keys and the NOT NULL columns needed for test inserts. `create_tables_for_tests()` and `insert_for_tests(table, rows)` are test helpers guarded to refuse when the dialect is `postgresql`. `price_bars` converts `event_time` to `event_date` via `.date()` in UTC. `SET TRANSACTION READ ONLY` is issued only when `engine.dialect.name == "postgresql"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_sandbox_canonical.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add viza_sandbox/canonical.py tests/unit/test_sandbox_canonical.py
git commit -m "feat(sandbox): read-only canonical source with in-memory and postgres implementations"
```

---

### Task 3: Availability policy and point-in-time panel materialization

**Files:**
- Create: `viza_sandbox/pit.py`, `viza_sandbox/materialize.py`
- Test: `tests/unit/test_sandbox_materialize.py`, `tests/lookahead_audit/test_sandbox_pit.py`

**Interfaces:**
- Consumes: `CanonicalSource` (Task 2), `SandboxSettings` (Task 1).
- Produces:
  - `pit.py`: `EOD_POLICY_VERSION = "faustcalc_fmp_snapshot_eod_policy_v1"`; `EOD_AVAILABLE_HOUR_UTC = 21`; `end_of_day_utc(d: date) -> datetime` (23:59:59.999999 UTC); `eod_available_at(event_date: pl.Expr) -> pl.Expr`; `visible_on(frame: pl.DataFrame, on: date) -> pl.DataFrame` filtering `available_at <= end_of_day_utc(on)`.
  - `materialize.py`:
    - `class PanelSpec(BaseModel)`: `start: date`, `end: date`, `price_source: str = "faustcalc_fmp_snapshot"`, `membership_lookback_trading_days: int = 5`.
    - `class DataManifest(BaseModel)`: `manifest_id: str`, `spec: PanelSpec`, `availability_policy_version: str`, `canonical_snapshot_id: str`, `price_adjustment_status: str`, `source_rights_state: str`, `cutoff_available_at: datetime` (= `end_of_day_utc(spec.end)`), `series: list[str]` (= `["prices", "universe"]`), `row_counts: dict[str, int]`, `currencies: list[str]`, `created_at: datetime`. `manifest_id` = sha256 hex of the JSON of `(spec, availability_policy_version, canonical_snapshot_id, price_adjustment_status)`.
    - `class MaterializedPanel(BaseModel)`: `directory: Path`, `manifest: DataManifest`.
    - `class MaterializationError(ValueError)`.
    - `materialize(source: CanonicalSource, spec: PanelSpec, settings: SandboxSettings) -> MaterializedPanel`. Writes `<settings.data_dir>/panels/<manifest_id>/prices.parquet`, `universe.parquet`, `manifest.json`. If the directory and `manifest.json` already exist, returns them without touching the source (the cache).
    - `derive_membership(prices: pl.DataFrame, lookback_trading_days: int) -> pl.DataFrame` with columns `event_date, security_id` for member pairs.
  - `prices.parquet` columns: `security_id, event_date, available_at (Datetime UTC), close, adjusted_close, volume, currency`. `universe.parquet` columns: `event_date, security_id, ticker, exchange, currency, sector, industry, classification_as_of`.

- [ ] **Step 1: Write the failing unit tests**

```python
# tests/unit/test_sandbox_materialize.py
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
```

- [ ] **Step 2: Write the failing look-ahead audit test**

```python
# tests/lookahead_audit/test_sandbox_pit.py
import polars as pl
from datetime import date, datetime, timezone
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_sandbox_materialize.py tests/lookahead_audit/test_sandbox_pit.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 4: Implement `pit.py` and `materialize.py`**

`materialize` steps: read `source.snapshot_id()`, build the manifest id, return cache hit if present; read `price_bars`, assert uniqueness on `(security_id, event_date)` raising `MaterializationError(f"Duplicate price rows for security_id={sid} event_date={d}")`; add `available_at = eod_available_at(event_date)`; derive membership; join securities onto membership pairs for `universe.parquet`; write files; write `manifest.json` last so a crashed write never looks like a cache hit.

`derive_membership`: trading calendar = sorted unique `event_date`; for each security, the set of calendar indices with a close; a security is a member at calendar index i if any priced index j satisfies `i - lookback + 1 <= j <= i`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_sandbox_materialize.py tests/lookahead_audit/test_sandbox_pit.py -q`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add viza_sandbox/pit.py viza_sandbox/materialize.py tests/unit/test_sandbox_materialize.py tests/lookahead_audit/test_sandbox_pit.py
git commit -m "feat(sandbox): EOD availability policy and point-in-time panel materialization"
```

---

### Task 4: The user-facing SDK

**Files:**
- Create: `viza_sandbox/sdk.py`, `tests/unit/sandbox_helpers.py`
- Test: `tests/unit/test_sandbox_sdk.py`

**Interfaces:**
- Consumes: panel directory layout and `manifest.json` (Task 3), `end_of_day_utc` (Task 3).
- Produces:
  - `class VizaData`: `__init__(self, panel_dir: Path, cutoff: datetime | None = None)`; `manifest: dict` property (parsed `manifest.json`); `prices(self, field: str = "close", start: date | None = None, end: date | None = None) -> pd.DataFrame` wide: `DatetimeIndex` named `event_date`, columns `security_id` strings, `NaN` where no row; `prices_long(self, fields: Sequence[str] = ("close", "volume"), start=None, end=None) -> pd.DataFrame` with columns `event_date, security_id, *fields`; `universe(self, start=None, end=None) -> pd.DataFrame` long with columns `event_date, security_id, ticker, exchange, currency, sector, industry, classification_as_of`; `as_of(self, on: date) -> VizaData` returning a new instance with `cutoff = end_of_day_utc(on)`.
  - Visibility rule inside every accessor: keep rows where `available_at <= end_of_day_utc(event_date)` and, when `cutoff` is set, `available_at <= cutoff`.
  - `class Scores`: `frame: pd.DataFrame` (wide: date index, security columns, float). `scores(frame: pd.DataFrame) -> Scores` validates dtype is numeric and index is datetime-like, else raises `ReturnDeclarationError`.
  - `class ReturnDeclarationError(ValueError)`.
  - `coerce_return(value: object) -> Scores`: `Scores` passes through; bare float `DataFrame` raises with the exact Global Constraints message; bool `DataFrame` raises `ReturnDeclarationError("Boolean signals are not supported in this version; return viza.scores(df).")`; `dict` raises `ReturnDeclarationError("Report returns are not supported in this version; return viza.scores(df).")`; anything else raises `ReturnDeclarationError(f"Unsupported return type {type(value).__name__}.")`.
  - `__all__ = ["VizaData", "Scores", "scores", "coerce_return", "ReturnDeclarationError"]`.
  - `tests/unit/sandbox_helpers.py`: `make_panel(root: Path) -> Path` writing a three-row test panel under `root / "panel"` (creating parents) and returning the panel directory. The `tests/` tree has no `__init__.py`, so later tests import it as `from sandbox_helpers import make_panel` (pytest prepends the test file's directory to `sys.path`).

- [ ] **Step 1: Write the helper and the failing tests**

```python
# tests/unit/sandbox_helpers.py
import json, polars as pl
from datetime import date, datetime, timezone
from pathlib import Path

def make_panel(root: Path) -> Path:
    d = root / "panel"; d.mkdir(parents=True)
    pl.DataFrame({"security_id": ["a","a","b"], "event_date": [date(2024,1,2), date(2024,1,3), date(2024,1,2)],
                  "available_at": [datetime(2024,1,2,21,tzinfo=timezone.utc), datetime(2024,1,3,21,tzinfo=timezone.utc), datetime(2024,1,2,21,tzinfo=timezone.utc)],
                  "close": [10.0, 11.0, 5.0], "adjusted_close": [10.0, 11.0, 5.0], "volume": [1,2,3], "currency": ["USD"]*3}).write_parquet(d/"prices.parquet")
    pl.DataFrame({"event_date": [date(2024,1,2), date(2024,1,3), date(2024,1,2)], "security_id": ["a","a","b"], "ticker": ["AAA","AAA","BBB"], "exchange": ["NYSE"]*3, "currency": ["USD"]*3, "sector": ["Tech","Tech",None], "industry": [None]*3, "classification_as_of": [None]*3}).write_parquet(d/"universe.parquet")
    (d/"manifest.json").write_text(json.dumps({"manifest_id": "m", "availability_policy_version": "faustcalc_fmp_snapshot_eod_policy_v1"}))
    return d
```

```python
# tests/unit/test_sandbox_sdk.py
import numpy as np, pandas as pd, polars as pl, pytest
from datetime import date, datetime, timezone
from sandbox_helpers import make_panel as _panel
from viza_sandbox.sdk import VizaData, scores, coerce_return, ReturnDeclarationError

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
    frame = pl.read_parquet(d/"prices.parquet").with_columns(pl.when(pl.col("security_id") == "b").then(pl.lit(datetime(2024,1,5,21,tzinfo=timezone.utc))).otherwise(pl.col("available_at")).alias("available_at"))
    frame.write_parquet(d/"prices.parquet")
    assert "b" not in VizaData(d).prices("close").columns

def test_empty_range_returns_empty_frame_with_index_name(tmp_path):
    wide = VizaData(_panel(tmp_path)).prices("close", start=date(2020,1,1), end=date(2020,1,31))
    assert wide.empty and wide.index.name == "event_date"

def test_manifest_and_universe(tmp_path):
    data = VizaData(_panel(tmp_path))
    assert data.manifest["manifest_id"] == "m"
    assert set(data.universe()["ticker"]) == {"AAA", "BBB"}

def test_coerce_return_rules():
    idx = pd.to_datetime(["2024-01-02"]); f = pd.DataFrame({"a": [1.0]}, index=idx)
    assert coerce_return(scores(f)).frame.equals(f)
    with pytest.raises(ReturnDeclarationError, match=r"declare it with viza\.scores\(df\) or viza\.weights\(df\)\."):
        coerce_return(f)
    with pytest.raises(ReturnDeclarationError, match="Boolean signals"):
        coerce_return(f > 0)
    with pytest.raises(ReturnDeclarationError, match="Report returns"):
        coerce_return({"x": 1})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_sandbox_sdk.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `sdk.py`**

Read parquet with `pandas.read_parquet(..., engine="pyarrow")`. Convert `event_date` to `pd.Timestamp` (naive dates) for the index; keep `available_at` tz-aware UTC for comparisons. Build the wide frame with `pivot(index="event_date", columns="security_id", values=field)` and `columns.name = None`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_sandbox_sdk.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add viza_sandbox/sdk.py tests/unit/sandbox_helpers.py tests/unit/test_sandbox_sdk.py
git commit -m "feat(sandbox): VizaData SDK with point-in-time accessors and declared score returns"
```

---

### Task 5: Isolated runner and entrypoint

**Files:**
- Create: `viza_sandbox/runner.py`, `viza_sandbox/runner_entry.py`, `viza_sandbox/runtime_image/Dockerfile`, `viza_sandbox/runtime_image/viza/__init__.py`
- Test: `tests/unit/test_sandbox_runner.py`

**Interfaces:**
- Consumes: `VizaData`, `coerce_return`, `ReturnDeclarationError` (Task 4).
- Produces:
  - Run directory layout (created by the caller): `<run_dir>/strategy.py`, `<run_dir>/data/` (a materialized panel directory or a copy of one), `<run_dir>/out/` (empty, writable).
  - `runner_entry.py`: `main(argv: list[str]) -> int` taking `[run_dir]`; imports `strategy.py` as module `user_strategy` via `importlib.util`; requires a callable `strategy`; calls `strategy(VizaData(run_dir/"data"))`; on success writes `out/result.parquet` (long: `event_date, security_id, score`) and `out/result.json` `{"kind": "scores", "rows": int, "securities": int, "dates": int}` and returns 0; on `ReturnDeclarationError` or any exception writes `out/error.json` `{"type": str, "message": str, "traceback": str}` and returns 1. Module executable as `python -m viza_sandbox.runner_entry <run_dir>`.
  - `runner.py`: `class RunLimits(BaseModel)`: `wall_clock_seconds: int = 600`, `memory_gb: int = 8`, `cpus: int = 2`. `class RunOutcome(BaseModel)`: `exit_code: int | None`, `timed_out: bool`, `stdout: str`, `stderr: str`, `duration_seconds: float`. `class Runner(Protocol)`: `run(self, run_dir: Path, limits: RunLimits) -> RunOutcome`. `class LocalProcessRunner`: subprocess `[sys.executable, "-m", "viza_sandbox.runner_entry", str(run_dir)]` with `timeout=limits.wall_clock_seconds`, `cwd=run_dir`, and `PYTHONPATH` set to the repo root (`Path(viza_sandbox.__file__).resolve().parents[1]`) so the entry imports `viza_sandbox` regardless of the caller's cwd; on `TimeoutExpired` kill and return `timed_out=True, exit_code=None`. `class DockerRunner`: `__init__(self, image: str)`; command `docker run --rm --name viza-run-<uuid> --network none --memory <gb>g --cpus <n> --read-only --tmpfs /tmp -v <run_dir>/strategy.py:/run/strategy.py:ro -v <run_dir>/data:/run/data:ro -v <run_dir>/out:/run/out:rw <image> python -m viza_sandbox.runner_entry /run`; on timeout `docker kill <name>`. `docker_available() -> bool` via `shutil.which("docker")` and `docker version` exit code 0. Both runners cap captured stdout and stderr at 65536 characters, keeping the tail.
  - `Dockerfile`: `FROM python:3.14-slim`; installs `pandas pyarrow numpy scipy statsmodels pydantic polars`; copies `viza_sandbox/` to `/app/viza_sandbox` and `viza_sandbox/runtime_image/viza` to `/app/viza`; `ENV PYTHONPATH=/app`; non-root user; no `CMD`. `viza/__init__.py` content is one line: `from viza_sandbox.sdk import *  # noqa: F401,F403`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_sandbox_runner.py
import json, shutil, pytest
from pathlib import Path
from viza_sandbox.runner import LocalProcessRunner, DockerRunner, RunLimits, docker_available
from sandbox_helpers import make_panel as _panel

def _run_dir(tmp_path, code):
    rd = tmp_path / "run"; (rd / "out").mkdir(parents=True)
    shutil.copytree(_panel(tmp_path / "src"), rd / "data")
    (rd / "strategy.py").write_text(code)
    return rd

MOMENTUM = """
from viza_sandbox.sdk import scores
def strategy(data):
    close = data.prices("close")
    return scores(close.pct_change())
"""

def test_local_runner_writes_scores(tmp_path):
    rd = _run_dir(tmp_path, MOMENTUM)
    out = LocalProcessRunner().run(rd, RunLimits(wall_clock_seconds=120))
    assert out.exit_code == 0 and not out.timed_out
    assert json.loads((rd/"out"/"result.json").read_text())["kind"] == "scores"
    assert (rd/"out"/"result.parquet").exists()

def test_local_runner_reports_declaration_error(tmp_path):
    rd = _run_dir(tmp_path, "def strategy(data):\n    return data.prices('close')\n")
    out = LocalProcessRunner().run(rd, RunLimits(wall_clock_seconds=120))
    assert out.exit_code == 1
    err = json.loads((rd/"out"/"error.json").read_text())
    assert err["type"] == "ReturnDeclarationError" and "viza.scores(df)" in err["message"]

def test_local_runner_times_out(tmp_path):
    rd = _run_dir(tmp_path, "import time\ndef strategy(data):\n    time.sleep(30)\n")
    out = LocalProcessRunner().run(rd, RunLimits(wall_clock_seconds=2))
    assert out.timed_out and out.exit_code is None

def test_local_runner_captures_stdout(tmp_path):
    rd = _run_dir(tmp_path, "from viza_sandbox.sdk import scores\ndef strategy(data):\n    print('hello from user')\n    return scores(data.prices('close'))\n")
    out = LocalProcessRunner().run(rd, RunLimits(wall_clock_seconds=120))
    assert "hello from user" in out.stdout

@pytest.mark.skipif(not docker_available(), reason="docker not available")
def test_docker_runner_blocks_network(tmp_path):
    rd = _run_dir(tmp_path, "import socket\nfrom viza_sandbox.sdk import scores\ndef strategy(data):\n    try:\n        socket.create_connection(('1.1.1.1', 53), timeout=3)\n        raise SystemExit(7)\n    except OSError:\n        return scores(data.prices('close'))\n")
    out = DockerRunner("viza-sandbox-runtime:latest").run(rd, RunLimits(wall_clock_seconds=120))
    assert out.exit_code == 0, out.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_sandbox_runner.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `runner_entry.py`, `runner.py`, the Dockerfile and the alias package**

The entry converts the wide `Scores.frame` to long with `frame.stack()` and column names `event_date, security_id, score`, dropping `NaN`. The Docker test requires the image to be built once: `docker build -t viza-sandbox-runtime:latest -f viza_sandbox/runtime_image/Dockerfile .`; if the image is missing the test will fail with a pull error, so build it before running the suite with Docker present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_sandbox_runner.py -q`
Expected: 4 passed, 1 skipped (or 5 passed with Docker and a built image)

- [ ] **Step 5: Commit**

```bash
git add viza_sandbox/runner.py viza_sandbox/runner_entry.py viza_sandbox/runtime_image tests/unit/test_sandbox_runner.py
git commit -m "feat(sandbox): isolated runner with local subprocess and docker backends"
```

---

### Task 6: Scores evaluator

**Files:**
- Create: `viza_sandbox/evaluate.py`
- Test: `tests/unit/test_sandbox_evaluate.py`

**Interfaces:**
- Consumes: wide close frame and wide scores frame as produced by Task 4 (`DatetimeIndex`, `security_id` columns).
- Produces:
  - `class BacktestSettings(BaseModel)`: `quantiles: int = Field(ge=2, le=20)`, `rebalance: Literal["daily", "weekly", "monthly"]`, `weighting: Literal["equal"] = "equal"`, `top_n: int = Field(default=20, ge=1)`. No defaults for `quantiles` and `rebalance`: the user must set them.
  - `EXECUTION_CONVENTION = {"signal_lag_days": 1, "transaction_cost": 0.0, "benchmark": None}`.
  - `class EvaluationError(ValueError)`.
  - `class ScoresEvaluation(BaseModel)`: `quantile_daily_returns: dict[str, dict[str, float | None]]` (`"q1".."qK"` -> `{iso_date: return}`), `equity_curves: dict[str, dict[str, float]]` (cumulative product, starting at 1.0), `long_short_daily: dict[str, float | None]` (`qK - q1`), `rank_stability: dict[str, float | None]` (Spearman correlation of score ranks between consecutive rebalance dates, keyed by the later date), `top_bottom: dict[str, dict[str, list[str]]]` (`{iso_date: {"top": [...], "bottom": [...]}}` for rebalance dates), `rebalance_dates: list[str]`, `execution: dict`, `settings: BacktestSettings`, `warnings: list[str]`, `securities_scored: int`, `dates_scored: int`.
  - `rebalance_dates(index: pd.DatetimeIndex, rebalance: str) -> pd.DatetimeIndex`: `daily` = every date; `weekly` = last trading date of each ISO week; `monthly` = last trading date of each month.
  - `evaluate_scores(scores: pd.DataFrame, close: pd.DataFrame, settings: BacktestSettings) -> ScoresEvaluation`.
  - Math, pinned: `r_t = close_t / close_{t-1} - 1` on the close frame's own index. On each rebalance date D, rank the non-`NaN` scores among securities that have a close on D with `rank(method="first")` (ties broken by column order), cut into `settings.quantiles` equal-count buckets (`pd.qcut` on rank, `q1` lowest score), equal weights within a bucket. A rebalance date with no non-`NaN` scores is skipped and the previous weights persist. Weights set at D are applied to `r_t` for every trading date `t` with `t >= D + 2 trading days` until the next effective rebalance date's weights take over at its own `D' + 2`. Bucket return on `t` = mean of `r_t` over bucket members with non-`NaN` `r_t`; a bucket with no contributing member on `t` has return `None` and its equity curve is unchanged on `t`. Securities in `scores` but not in `close` are dropped and reported as `warnings = [f"Dropped {n} scored securities not in the universe: {first five ids}"]`. Scores dates outside the close index are ignored; if none remain, raise `EvaluationError("No scores fall inside the panel date range.")`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_sandbox_evaluate.py
import numpy as np, pandas as pd, pytest
from viza_sandbox.evaluate import BacktestSettings, evaluate_scores, rebalance_dates, EvaluationError, EXECUTION_CONVENTION

DATES = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"])

def _close():
    return pd.DataFrame({"a": [10, 11, 12, 13, 14], "b": [10, 10, 10, 10, 10], "c": [10, 9, 8, 7, 6]}, index=DATES, dtype=float)

def _scores_once():
    s = pd.DataFrame(np.nan, index=DATES, columns=["a", "b", "c"])
    s.loc[DATES[0]] = [3.0, 2.0, 1.0]   # a top, c bottom
    return s

def test_signal_at_d_applies_to_return_from_close_d1_to_close_d2():
    ev = evaluate_scores(_scores_once(), _close(), BacktestSettings(quantiles=3, rebalance="daily"))
    r_a_d2 = 12 / 11 - 1
    r_c_d2 = 8 / 9 - 1
    assert ev.quantile_daily_returns["q3"]["2024-01-04"] == pytest.approx(r_a_d2)
    assert ev.quantile_daily_returns["q1"]["2024-01-04"] == pytest.approx(r_c_d2)
    assert ev.quantile_daily_returns["q3"].get("2024-01-03") is None
    assert ev.long_short_daily["2024-01-04"] == pytest.approx(r_a_d2 - r_c_d2)
    assert ev.execution == EXECUTION_CONVENTION

def test_equity_curve_compounds_from_one():
    ev = evaluate_scores(_scores_once(), _close(), BacktestSettings(quantiles=3, rebalance="daily"))
    curve = ev.equity_curves["q3"]
    assert curve["2024-01-04"] == pytest.approx(12 / 11)
    assert curve["2024-01-05"] == pytest.approx(13 / 11)

def test_missing_close_is_excluded_not_zero():
    close = _close(); close.loc[DATES[2], "a"] = np.nan   # a has no close on D2 (2024-01-04)
    ev = evaluate_scores(_scores_once(), close, BacktestSettings(quantiles=3, rebalance="daily"))
    assert ev.quantile_daily_returns["q3"]["2024-01-04"] is None          # q3 = {a}; no contributor, not 0.0
    assert ev.quantile_daily_returns["q3"]["2024-01-05"] is None          # r_a on D3 needs close on D2, also missing
    assert ev.equity_curves["q3"]["2024-01-05"] == pytest.approx(1.0)      # curve unchanged, never multiplied by 0
    assert ev.quantile_daily_returns["q2"]["2024-01-04"] == pytest.approx(0.0)   # b is flat: a real 0.0

def test_unknown_securities_are_dropped_with_warning():
    s = _scores_once(); s["zzz"] = 5.0
    ev = evaluate_scores(s, _close(), BacktestSettings(quantiles=3, rebalance="daily"))
    assert ev.warnings == ["Dropped 1 scored securities not in the universe: zzz"]

def test_no_overlapping_dates_raises():
    s = pd.DataFrame({"a": [1.0]}, index=pd.to_datetime(["2019-01-02"]))
    with pytest.raises(EvaluationError, match="No scores fall inside the panel date range."):
        evaluate_scores(s, _close(), BacktestSettings(quantiles=2, rebalance="daily"))

def test_rebalance_dates_weekly_and_monthly():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08", "2024-01-31", "2024-02-01"])
    assert list(rebalance_dates(idx, "weekly")) == list(pd.to_datetime(["2024-01-05", "2024-01-08", "2024-02-01"]))   # 01-31 and 02-01 share ISO week 5
    assert list(rebalance_dates(idx, "monthly")) == list(pd.to_datetime(["2024-01-31", "2024-02-01"]))

def test_rank_stability_and_top_bottom():
    s = pd.DataFrame({"a": [3.0, 3.0], "b": [2.0, 1.0], "c": [1.0, 2.0]}, index=DATES[:2])
    ev = evaluate_scores(s, _close(), BacktestSettings(quantiles=3, rebalance="daily", top_n=1))
    assert ev.rank_stability["2024-01-03"] == pytest.approx(0.5)
    assert ev.top_bottom["2024-01-02"] == {"top": ["a"], "bottom": ["c"]}

def test_settings_require_quantiles_and_rebalance():
    with pytest.raises(Exception):
        BacktestSettings()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_sandbox_evaluate.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `evaluate.py`**

Use `scipy.stats.spearmanr` for rank stability over the intersection of non-`NaN` securities on the two dates; `None` when fewer than 3 securities overlap. Serialize dates as `strftime("%Y-%m-%d")`. Returns that are `NaN` serialize as `None`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_sandbox_evaluate.py -q`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add viza_sandbox/evaluate.py tests/unit/test_sandbox_evaluate.py
git commit -m "feat(sandbox): quantile backtest evaluator with disclosed D+1 execution convention"
```

---

### Task 7: Run orchestration and HTTP API

**Files:**
- Create: `viza_sandbox/runs.py`, `viza_sandbox/api.py`
- Test: `tests/unit/test_sandbox_api.py`

**Interfaces:**
- Consumes: `SandboxStore`, `SandboxSettings` (Task 1); `CanonicalSource` (Task 2); `materialize`, `PanelSpec` (Task 3); `Runner`, `RunLimits`, `LocalProcessRunner`, `DockerRunner` (Task 5); `evaluate_scores`, `BacktestSettings`, `EvaluationError` (Task 6); `VizaData` (Task 4) for reading the close panel on the host side.
- Produces:
  - `runs.py`:
    - `class RunRequest(BaseModel)`: `code: str = Field(min_length=1)`, `start: date`, `end: date`, `backtest: BacktestSettings`. Validator: `end >= start`.
    - `class SandboxService`: `__init__(self, settings: SandboxSettings, store: SandboxStore, source: CanonicalSource, runner: Runner)`; `submit(self, user: SandboxUser, request: RunRequest) -> SandboxRun` (status `queued`, `limits` from settings); `execute(self, run_id: str) -> SandboxRun` performing: `running` + `started_at`; `materialize` with `PanelSpec(start, end)`; create `<runs_dir>/<run_id>/{strategy.py, out/}` and `data` as a directory junction/symlink to the panel directory, falling back to `shutil.copytree` when linking fails; run; on `timed_out` set status `timed_out`; on nonzero exit read `out/error.json` into `error` and set `failed`; on success load `out/result.parquet` to a wide scores frame, load close via `VizaData(panel.directory).prices("close")`, call `evaluate_scores`, persist `evaluation`, `result_kind="scores"`, `result_path`, `data_manifest = manifest.model_dump(mode="json")`, status `completed`; `EvaluationError` sets `failed` with its message. Always set `finished_at`, `stdout`, `stderr`, `exit_code`.
    - `result_header(run: SandboxRun) -> dict` with keys `run_id, code_hash, status, data_manifest, limits, execution, source_rights_state, price_adjustment_status, created_at, started_at, finished_at`.
  - `api.py`:
    - `create_app(service: SandboxService, store: SandboxStore) -> FastAPI`; module-level `app` built from settings via `build_default_app()` (chooses `DockerRunner` or `LocalProcessRunner` from `settings.runner`, `PostgresCanonicalSource(settings.canonical_database_url)`; raises `RuntimeError("VIZA_SANDBOX_CANONICAL_DATABASE_URL is required")` when missing).
    - Auth: `Authorization: Bearer <token>`; missing or unknown -> 401 `{"detail": "Invalid sandbox token."}`.
    - `POST /sandbox/runs` body `RunRequest` -> 202 `{"run_id": str, "status": "queued"}`; schedules `service.execute(run_id)` with `BackgroundTasks`.
    - `GET /sandbox/runs/{run_id}` -> `{"run": <all SandboxRun columns as JSON>, "header": result_header}`; 404 `{"detail": "Run not found."}` when missing or owned by another user. On a failed run, `run.error` is `f"{error_json['type']}: {error_json['message']}"`, or the `EvaluationError` message, or `"Timed out after {n} seconds."`.
    - `GET /sandbox/runs/{run_id}/result` -> `{"header": ..., "evaluation": ..., "warnings": [...]}`; 404 as above; 409 `{"detail": "Run is not completed."}` when status is not `completed`.
    - `GET /sandbox/health` -> `{"status": "ok", "service": "viza-sandbox"}` without auth.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_sandbox_api.py
import polars as pl, pytest
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient
from viza_sandbox.api import create_app
from viza_sandbox.canonical import InMemoryCanonicalSource
from viza_sandbox.config import SandboxSettings
from viza_sandbox.runner import LocalProcessRunner
from viza_sandbox.runs import SandboxService, RunRequest
from viza_sandbox.store import SandboxStore

MOMENTUM = "from viza_sandbox.sdk import scores\ndef strategy(data):\n    return scores(data.prices('close').pct_change(2))\n"

def _service(tmp_path):
    days = [date(2024,1,d) for d in (2,3,4,5,8,9,10,11)]
    t = datetime(2024,5,1,tzinfo=timezone.utc)
    rows = [(s, d, float(p), float(p), 1, "USD", t) for s, base in (("a", 10), ("b", 20), ("c", 30)) for d, p in zip(days, [base + i * (1 if s != "c" else -1) for i in range(len(days))])]
    prices = pl.DataFrame(rows, schema={"security_id": pl.Utf8, "event_date": pl.Date, "close": pl.Float64, "adjusted_close": pl.Float64, "volume": pl.Int64, "currency": pl.Utf8, "ingestion_time": pl.Datetime("us", "UTC")}, orient="row")
    secs = pl.DataFrame({"security_id": ["a","b","c"], "ticker": ["AAA","BBB","CCC"], "exchange": ["NYSE"]*3, "currency": ["USD"]*3, "sector": [None]*3, "industry": [None]*3, "classification_as_of": [None]*3})
    settings = SandboxSettings(database_url=f"sqlite:///{tmp_path/'s.db'}", data_dir=tmp_path/"data", runs_dir=tmp_path/"runs", runner="local", wall_clock_seconds=120)
    store = SandboxStore(settings.database_url); store.create_schema()
    service = SandboxService(settings, store, InMemoryCanonicalSource(secs, prices), LocalProcessRunner())
    return settings, store, service

def _client(tmp_path):
    settings, store, service = _service(tmp_path)
    client = TestClient(create_app(service, store))
    _, token = store.create_user("alice", is_owner=True)
    _, other = store.create_user("mallory")
    return client, {"Authorization": f"Bearer {token}"}, {"Authorization": f"Bearer {other}"}

def _request():
    return {"code": MOMENTUM, "start": "2024-01-01", "end": "2024-01-31", "backtest": {"quantiles": 3, "rebalance": "daily"}}

def test_end_to_end_momentum_run(tmp_path):
    client, auth, _ = _client(tmp_path)
    created = client.post("/sandbox/runs", json=_request(), headers=auth)
    assert created.status_code == 202
    run_id = created.json()["run_id"]
    result = client.get(f"/sandbox/runs/{run_id}/result", headers=auth)
    assert result.status_code == 200, client.get(f"/sandbox/runs/{run_id}", headers=auth).json()
    body = result.json()
    assert body["header"]["execution"] == {"signal_lag_days": 1, "transaction_cost": 0.0, "benchmark": None}
    assert body["header"]["data_manifest"]["availability_policy_version"] == "faustcalc_fmp_snapshot_eod_policy_v1"
    assert body["header"]["source_rights_state"] == "development_proving"
    assert set(body["evaluation"]["quantile_daily_returns"]) == {"q1", "q2", "q3"}

def test_unauthorized_and_cross_user_404(tmp_path):
    client, auth, other = _client(tmp_path)
    assert client.post("/sandbox/runs", json=_request()).status_code == 401
    run_id = client.post("/sandbox/runs", json=_request(), headers=auth).json()["run_id"]
    assert client.get(f"/sandbox/runs/{run_id}", headers=other).status_code == 404
    assert client.get(f"/sandbox/runs/{run_id}", headers=auth).status_code == 200

def test_failed_run_reports_error_and_result_409(tmp_path):
    client, auth, _ = _client(tmp_path)
    bad = dict(_request(), code="def strategy(data):\n    return data.prices('close')\n")
    run_id = client.post("/sandbox/runs", json=bad, headers=auth).json()["run_id"]
    run = client.get(f"/sandbox/runs/{run_id}", headers=auth).json()["run"]
    assert run["status"] == "failed" and "viza.scores(df)" in run["error"]
    assert client.get(f"/sandbox/runs/{run_id}/result", headers=auth).status_code == 409

def test_same_code_and_manifest_reproduce_identical_evaluation(tmp_path):
    settings, store, service = _service(tmp_path)
    user, _ = store.create_user("alice")
    req = RunRequest(code=MOMENTUM, start=date(2024,1,1), end=date(2024,1,31), backtest={"quantiles": 3, "rebalance": "daily"})
    first = service.execute(service.submit(user, req).run_id)
    second = service.execute(service.submit(user, req).run_id)
    assert first.data_manifest["manifest_id"] == second.data_manifest["manifest_id"]
    assert first.code_hash == second.code_hash and first.evaluation == second.evaluation
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_sandbox_api.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `runs.py` and `api.py`**

`TestClient` runs `BackgroundTasks` synchronously before returning the response, so the end-to-end test reads a completed run right after the POST. Scores long-to-wide on the host: `pivot(index="event_date", columns="security_id", values="score")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_sandbox_api.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add viza_sandbox/runs.py viza_sandbox/api.py tests/unit/test_sandbox_api.py
git commit -m "feat(sandbox): run orchestration and HTTP API with per-user tokens"
```

---

### Task 8: Operator CLI, split-adjustment check, and operations doc

**Files:**
- Create: `viza_sandbox/cli.py`, `docs/viza_end_product/VIZA_SANDBOX_OPERATIONS.md`
- Modify: `PROJECT_STATUS.md` (one bullet under the VIZA section), `CHANGELOG.md` (one entry), `docs/00_AGENT_START_HERE.md` (add the spec, plan and operations doc to Read First)
- Test: `tests/unit/test_sandbox_cli.py`

**Interfaces:**
- Consumes: `SandboxStore` (Task 1), `CanonicalSource` implementations (Task 2), `build_default_app` (Task 7).
- Produces: `python -m viza_sandbox.cli <command>` with subcommands:
  - `init-db`: `SandboxStore(settings.database_url).create_schema()`; prints `schema ready: <url with password redacted>`.
  - `create-user --name NAME [--owner]`: prints exactly `user_id=<id>\ntoken=<token>` once.
  - `check-split-adjustment --ticker T --from YYYY-MM-DD --to YYYY-MM-DD [--source S]`: `split_adjustment_verdict(bars: pl.DataFrame, threshold: float = 3.0) -> str` returning `"unadjusted"` when any consecutive close ratio is `>= threshold` or `<= 1/threshold`, else `"no_split_signature"`; prints each `event_date close adjusted_close` row and a final line `verdict=<verdict>`; exit code 0.
  - `serve [--host 127.0.0.1] [--port 8781]`: `uvicorn.run(build_default_app(), ...)`.
  - `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_sandbox_cli.py
import polars as pl
from datetime import date
from viza_sandbox.cli import main, split_adjustment_verdict

def test_create_user_prints_token_once(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VIZA_SANDBOX_DATABASE_URL", f"sqlite:///{tmp_path/'s.db'}")
    assert main(["init-db"]) == 0
    assert main(["create-user", "--name", "alice", "--owner"]) == 0
    out = capsys.readouterr().out
    assert "user_id=" in out and "token=" in out

def test_split_verdict_detects_ten_for_one():
    bars = pl.DataFrame({"event_date": [date(2024,6,7), date(2024,6,10)], "close": [1208.88, 121.79], "adjusted_close": [1208.88, 121.79]})
    assert split_adjustment_verdict(bars) == "unadjusted"
    flat = pl.DataFrame({"event_date": [date(2024,6,7), date(2024,6,10)], "close": [120.89, 121.79], "adjusted_close": [120.89, 121.79]})
    assert split_adjustment_verdict(flat) == "no_split_signature"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_sandbox_cli.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `cli.py`**

`check-split-adjustment` resolves `security_id` from `ticker` through `PostgresCanonicalSource.securities()` and reads `price_bars` for the window.

- [ ] **Step 4: Write `docs/viza_end_product/VIZA_SANDBOX_OPERATIONS.md`**

Sections, in order: purpose and link to spec and plan; server prerequisites (Docker, access to the AAT Postgres); SQL the operator runs once against the server, verbatim:

```sql
CREATE DATABASE viza_sandbox;
CREATE ROLE viza_sandbox_ro LOGIN PASSWORD '<choose>';
GRANT CONNECT ON DATABASE attribution TO viza_sandbox_ro;
\c attribution
GRANT USAGE ON SCHEMA public TO viza_sandbox_ro;
GRANT SELECT ON price_bar, security, security_ticker_history, faustcalc_company TO viza_sandbox_ro;
```

with the note that this creates no table and alters no canonical table, so it is compatible with the backfill guardrails, and that the operator confirms the backfill status first with the read-only `--status-only` command. Then: environment variables (`VIZA_SANDBOX_DATABASE_URL`, `VIZA_SANDBOX_CANONICAL_DATABASE_URL` using the read-only role, `VIZA_SANDBOX_DATA_DIR`, `VIZA_SANDBOX_RUNS_DIR`, `VIZA_SANDBOX_RUNNER`, `VIZA_SANDBOX_DOCKER_IMAGE`, `VIZA_SANDBOX_PRICE_ADJUSTMENT_STATUS`); build the image command; `init-db`, `create-user`, `serve`; the split-adjustment check for `NVDA --from 2024-06-05 --to 2024-06-12` and what verdict means for `VIZA_SANDBOX_PRICE_ADJUSTMENT_STATUS`; a `curl` example submitting the momentum strategy from the tests; the execution convention and PIT policy as the operator should explain them to a quant; what is not in this phase (fundamentals, catalog attributes, signals, weights, reports, rights filter, desktop surface, refresh job).

- [ ] **Step 5: Update `PROJECT_STATUS.md`, `CHANGELOG.md`, `docs/00_AGENT_START_HERE.md`**

One bullet each, factual, pointing at the spec, plan and operations doc. Append to `CHANGELOG.md`, do not rewrite.

- [ ] **Step 6: Run the full sandbox suite and the existing suites**

Run: `python -m pytest tests/unit/test_sandbox_*.py tests/lookahead_audit/test_sandbox_pit.py -q`
Expected: all passed (one skip without Docker)

Run: `python -m pytest tests/unit tests/lookahead_audit -q`
Expected: no new failures relative to `main`

- [ ] **Step 7: Commit**

```bash
git add viza_sandbox/cli.py tests/unit/test_sandbox_cli.py docs/viza_end_product/VIZA_SANDBOX_OPERATIONS.md PROJECT_STATUS.md CHANGELOG.md docs/00_AGENT_START_HERE.md
git commit -m "feat(sandbox): operator CLI, split-adjustment check, and operations doc"
```

---

## Out of scope for this plan (next plans)

- Plan 2, spec phase 3: precomputed attribute job and registry entries, FMP annual statements loader with `acceptedDate` availability, `fundamentals`, `attribute`, `series` on `VizaData`.
- Plan 3, spec phase 4: `signals`, `weights`, `report` return kinds and their evaluators; `rights_class` on series and the result-channel rights filter.
- Plan 4, spec phase 5: desktop feature for code submission and results, workflow diagram, data-quality panel.
- Plan 5, spec phase 6: daily FaustCalc pull, FMP incremental statements, attribute recompute under Task Scheduler.

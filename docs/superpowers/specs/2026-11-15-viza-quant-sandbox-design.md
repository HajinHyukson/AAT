# VIZA Quant Sandbox: Design

Date: 2026-11-15
Status: draft for approval
Supersedes in direction: the "methodology canvas as authoring surface" posture in `docs/viza_end_product/VIZA_PRODUCT_SPEC.md` v0.4. That spec stays in force for everything this document does not touch.

## 1. Intent

VIZA becomes a sandbox where a quantitative investor tests their own strategy, written as code, against live-updating market data under point-in-time discipline. Today VIZA screens with pre-defined, pre-calculated attributes applied to a stale data snapshot. The target state is: the user brings a model, VIZA supplies the data and the execution environment, and the user gets a backtest that faithfully reflects what they wrote.

The owner's success criterion, in translation: "In the end it is the backtest result. If the result clearly reflects the quant's strategy and the attributes they set, that is success."

The owner's view of VIZA's advantage, in translation: "VIZA precomputes attributes. The quant does not compute attributes themselves; they call them." The precomputed attribute catalog is therefore the product. Raw data access exists so that the catalog is never a ceiling, but the catalog is where VIZA's value and VIZA's intellectual property sit. Vendor licensing (section 7.11) points the same way: VIZA will likely not be allowed to redistribute raw vendor data, but attributes VIZA computes are VIZA's own.

### Why now

- The existing VIZA attribute values are largely synthetic. `viza/attribute_resolvers.py` hashes the ticker to produce stable pseudo-random numbers for fundamental, positioning and event attributes. Only macro exposures and a few universe fields are real. Nobody can test a real idea on that.
- The FaustCalc universe already exists in the AAT server database: about 24,500 securities and about 11.3 million daily close/volume rows, plus fundamentals, price features, theme scores, filing analysis and peer analysis in staging. That is enough real data to make the sandbox useful on day one.
- The last ten VIZA phases (26 to 37) went into compliance structure and an investment-command layer around one narrow template. Nothing in that work widened what a user can express.

## 2. Goals

1. A user submits Python code. VIZA runs it on the server against FaustCalc-universe daily data and returns the result.
2. The data the code sees is point-in-time correct by construction. At any evaluation date, only values that were knowable at that date are visible.
3. Frequently used attributes are precomputed by VIZA and exposed through the same data API the user code uses.
4. The user decides what the code returns. Scores, boolean signals, target weights, or user-computed metrics are all accepted and rendered.
5. Data updates at whatever cadence the market data API allows. Daily is the first cadence. Hourly is added if FMP's plan permits.
6. The same code and data run both as a historical backtest and as a current-date screen.

## 3. Non-goals

- Extending the methodology canvas node vocabulary. The canvas becomes a read-only workflow diagram derived from the user's code, in the spirit of gitdiagram. It is not an authoring surface going forward.
- Changing strategy profiles, decisions, investment commands, `.viza` packaging, redaction modes or the non-advice language gate. They stay as they are and are not wired into the sandbox in this phase.
- An LLM translation layer from natural-language ideas to code. Input is code.
- Intraday or tick data.
- Order routing or broker connectivity.
- Serving the sandbox to anonymous public users. First users are the owner and invited quants.
- Letting a quant connect their own real-time data feed. The owner names this as a likely later extension once vendor licensing settles. The data access object should not make it impossible, but nothing is built for it in v1.

## 4. Anti-goals

These would make the result a failure even if the system runs:

- **Silent look-ahead.** Any path where a value with `available_at > evaluation_date` reaches user code. This is the project's standing rule (CLAUDE.md) and the thing a quant will never forgive.
- **Silent gaps.** Missing data treated as zero, or a security silently dropped from the universe, without the result saying so.
- **Interpretation by VIZA.** VIZA re-weighting, clipping, re-ranking or otherwise "helping" with the user's output beyond rendering it. The user's code is the methodology.
- **Fake data presented as real.** The synthetic resolvers must not be reachable from the sandbox data API.

## 5. Constraints

- Project rules in CLAUDE.md apply: immutable `security_id`, never ticker as a key; every feature row carries `event_time`, `ingestion_time`, `timestamp_available`; fail closed when a licensed adapter is enabled without credentials.
- FaustCalc and FMP data are development/proving data until source rights are confirmed (`FMP_PRODUCTION_LICENSE_CONFIRMED`). The sandbox inherits this. Results must carry the source-rights state.
- The owner's compute budget is a single server. The AAT server Postgres already holds about 7.7 GB and is expected to grow to 60 to 80 GB after the attribution backfill. The sandbox must not compete with the live backfill for the same database without coordination.
- User code is untrusted. It runs isolated, with CPU, memory and wall-clock limits, and no outbound network.

## 6. Decisions made in the conversation

These are the owner's decisions. They are not open.

| Topic | Decision |
|---|---|
| Real-time granularity | Whatever the market data API allows. Daily first. |
| Degree of user freedom | Full. The user writes code. Parameter-only or formula-only is not enough. |
| Who the attribute API serves | User code, as its primitive layer. |
| Universe | FaustCalc universe. |
| Where computation runs | VIZA server. |
| Historical frequency | Daily. Hourly if FMP allows, later. |
| Historical replay | Yes. Same code and data for backtest and current screen. |
| Output shape | All of: scores, boolean signals, target weights, user-computed metrics. |
| Canvas role | Read-only strategy workflow diagram derived from code. Not core. |
| Success criterion | A backtest result that faithfully reflects the user's strategy and attributes. |
| Fundamentals history | Pull from FMP if the current plan allows it, accepting the heavier refresh. Otherwise current-screen only. The plan allows annual statements, so FMP history is in (section 7.10). |
| FaustCalc source | Still refreshing on the FaustCalc side. Daily pull from it continues. |
| FMP plan | Starter. |
| Backfill freeze | Wait for the attribution backfill to complete. Do not lift the freeze. |
| Vendor rights | The license will most likely forbid redistribution of raw vendor data. Design for that now. |
| Core advantage | Precomputed attributes that the quant calls instead of computing. |

## 7. Decisions made by the designer

These are my calls. The owner can override any of them.

### 7.1 Language and runtime

Python at the version the repo already runs (3.14 at the time of writing), with numpy, pandas, scipy and statsmodels available. No other third-party packages in v1. Python is the quant standard and the AAT codebase is Python.

### 7.2 The contract between user code and VIZA

The user writes a module that defines one function:

```python
def strategy(data: VizaData) -> Any:
    ...
```

`VizaData` is the data access object (section 7.3). The function may return any of:

- A `pandas.DataFrame` indexed by date with `security_id` columns, holding floats. Interpreted as scores.
- The same shape holding booleans. Interpreted as pass/fail signals.
- The same shape holding floats declared as target weights.
- A `dict[str, Any]` of named values, each a scalar, Series, DataFrame or figure-ready array. Rendered as-is.
- A tuple of the above.

Shape detection is explicit, not guessed: the user declares the return kind with a return wrapper such as `viza.scores(df)`, `viza.signals(df)`, `viza.weights(df)`, `viza.report({...})`. Bare returns are accepted only when the shape is unambiguous (a boolean frame is a signal; a dict is a report). A bare float frame fails the run with a message asking the user to declare scores or weights. This is how the anti-goal "interpretation by VIZA" is enforced.

The user does not write the date loop. VIZA runs the function once and expects a panel. Vectorized pandas over a point-in-time panel is what quants actually write; a per-date callback is slower and more awkward. Point-in-time is enforced inside `VizaData` (section 7.3), not by the loop structure.

### 7.3 The data access object

`VizaData` exposes:

- `data.universe(start, end)`: FaustCalc universe membership per date as a frame of `security_id`, ticker-as-of-date, sector, industry, exchange, currency, active flag. Membership is itself point-in-time (section 7.3.1).
- `data.prices(fields=["close", "volume"], start, end)`: daily bars with a `MultiIndex(date, security_id)` or wide form. Adjusted close is included where known.
- `data.fundamentals(fields, start, end)`: fundamental fields as of their `available_at`, forward-filled only when the user asks for it explicitly.
- `data.attribute(key, start, end)`: a VIZA-precomputed attribute (section 7.5).
- `data.series(source, key, start, end)`: escape hatch for any other registered daily series such as theme scores or price features.

Every value has an `available_at`. The view returned to the user is **as-known at each row's own date**: for row date D, the value shown is the latest value with `available_at <= D` and `event_time <= D`. This makes a vectorized backtest point-in-time correct without a loop. Fundamentals therefore appear on the day they were published, not the fiscal period they describe.

`data.as_of(T)` returns the same panels truncated to `available_at <= T`, for users who want to evaluate a single date explicitly.

There is no raw mode that bypasses `available_at`. This is the one place freedom is deliberately constrained.

#### 7.3.1 Universe membership without a membership history

The only existing FaustCalc universe (`faustcalc_active_us_equities_v0`) is a today-snapshot: it keeps only `is_active = true` assets and records no past membership. Serving it as-is would give every backtest survivorship bias, which violates the "faithfully reflects" criterion. My call for v1:

- The sandbox universe includes all FaustCalc assets, active and inactive (about 24,500), not only the 12,657 active ones.
- Membership on date D is derived from price coverage: a security is a member on D if it has a close within the previous 5 trading days. Delisted names therefore leave the universe when their prices stop.
- Owner decision, 2026-11-15, after the first real run showed OTC and shell tickers with bad price ticks dominating equal-weight results: the default universe also excludes illiquid names. A security is a member on D only if the median of `close * volume` over the trailing 21 trading days (at least 15 observations) is at least 1,000,000 USD. The floor is a deployment setting, is overridable per run (0 disables it), and is printed in the run header. Scores for non-members are not ranked and are counted in the result. `data.prices` is not filtered.
- Sector and industry are snapshot-only in FaustCalc. They are served with a `classification_as_of` column and flagged in the data-quality panel. Sector-relative attributes inherit this flag.
- A real membership-history source is a later improvement, not v1.

### 7.4 Point-in-time availability for backfilled history

The existing FaustCalc price promotion sets `timestamp_available` to the import time. Under strict PIT that would hide every price before the import date from a backtest. The sandbox needs a documented availability policy for historical rows:

- Daily prices: `available_at` = `price_date` end of day in the exchange's local time, converted to UTC. Vintage label `faustcalc_fmp_snapshot_eod_policy`.
- Fundamentals from FMP statements: `available_at` = FMP's `acceptedDate` (SEC acceptance timestamp) when present, else `fillingDate` end of day. These are true availability timestamps, not inferred. Fundamentals from the FaustCalc snapshot (a single current snapshot, about 17,000 rows for about 24,500 names): `available_at` = the snapshot `as_of_date`, flagged `availability_inferred=true`, and usable only from that date forward.
- Prices and splits: the FaustCalc promotion wrote `adjusted_close = close`, and whether the FaustCalc close is split-adjusted is unverified (a read-only check of NVDA around the 2024-06-10 10:1 split answers it; the designer's attempt to run it was blocked by permissions). Phase 1 runs that check. If closes are unadjusted, the sandbox pulls FMP `adjClose` for the universe (5 years on the Starter plan) and serves FaustCalc close only before the FMP window, flagged `adjustment=unverified`. Dividends are absent in both sources, so every return in v1 is a price return, stated in the run header.
- Derived FaustCalc features (price_feature, theme_score, filing_analysis, peer_analysis): `available_at` = the feature's own `as_of_date` end of day, flagged `availability_inferred=true` because FaustCalc computed them after the fact.

Inferred availability is shown in the result's data-quality panel. This policy must be reviewed by the `viza-pit-rights-auditor` agent before the first real run.

### 7.5 Precomputed attributes

VIZA maintains a daily job that computes a seed set of commonly used attributes over the whole universe and stores them as daily series with `available_at` equal to the latest `available_at` among their inputs. Seed set for v1: returns over 1, 5, 21, 63 and 252 days; rolling volatility 21 and 63; moving averages 20, 50 and 200; RSI 14; average dollar volume 21; market cap; book-to-market, earnings yield, ROE and leverage where the fundamental fields exist; sector-relative z-scores of each of the above.

The registry in `config/viza_attribute_registry.json` is the catalog. Each precomputed attribute is a registry entry with `source_type=viza_computed`, a formula reference, its input keys and its availability rule. The synthetic entries in `viza/attribute_expansion.py` are marked `deprecation_status=synthetic_prototype` and are not served by `VizaData`.

Publishing a user-computed attribute back into the catalog is out of scope for v1, but the registry shape must not prevent it.

### 7.6 Execution environment

- User code runs in a container per run. The base image holds Python and the allowed libraries. No network. Read-only filesystem except a scratch directory.
- Limits in v1: 10 minutes wall clock, 8 GB memory, 2 CPUs. Configurable per deployment.
- Data is delivered to the container as Parquet files materialized by the data service for the requested universe, fields and date range. User code never holds a database connection. This keeps the Postgres server, which also runs the attribution backfill, out of the untrusted path.
- A run record stores: code hash, data snapshot manifest (series, `available_at` cutoff, registry version), limits, exit status, stdout and stderr captures, and the result payload.
- Runs are reproducible from the run record: same code hash plus same data manifest gives the same result.

### 7.7 Deployment shape

The sandbox is a new service, `viza-sandbox`, with three parts: a data service that materializes point-in-time panels from the AAT Postgres, a run service that schedules containers, and an HTTP API that the desktop and a future web client call. It is a separate deployable from the desktop sidecar in `viza/service.py`. The desktop app gets a new feature surface that submits code and renders results; it does not run strategies locally.

Where the server lives (the existing AAT server at `10.0.0.60`, Railway, or elsewhere) is left to the builder with one constraint: low-latency access to the AAT Postgres.

Identity, my call: per-user accounts from the start, each with a token, and runs private to their owner. User code is the quant's intellectual property, so the current shared-key pattern used by the AAT dashboard is not acceptable here. Per-user quotas reuse the same account record. OAuth or SSO is not in v1.

Storage while the attribution backfill runs, my call following the owner's "wait" decision: the sandbox gets its own Postgres database, `viza_sandbox`, on the same server. It holds run records, user accounts, the precomputed attribute series, the FMP statements history and the availability-policy vintages. It reads the canonical `attribution` tables (`price_bar`, `security`, `security_ticker_history`, `faustcalc_*`) through a read-only role and never writes to them. The availability policy in section 7.4 is applied when panels are materialized, not by changing the price promotion job. No file frozen by `docs/LIVE_BACKFILL_DEVELOPMENT_GUARDRAILS.md` is touched: no edits to `db/models.py`, `alembic/versions/*`, `jobs/import_faustcalc_feature_store.py` or `jobs/build_faustcalc_universe.py`, and no new required environment variable for existing server jobs. The sandbox's own schema lives under `viza_sandbox/` with its own migrations. Work that genuinely needs the frozen files (for example writing corrected `timestamp_available` back into `price_bar`) is deferred until the backfill completes and the post-backfill backup exists.

### 7.8 Results view

The result screen shows, for any return kind:

- Run header: code hash, data manifest, universe size, date range, PIT policy version, source-rights state, limits used.
- Data-quality panel: securities with missing inputs, inferred-availability rows used, universe membership changes in range.
- For scores: top and bottom N by date, rank stability, and a quantile-portfolio backtest. Quantile count, rebalance frequency and weighting are user settings; VIZA does not pick them silently.
- Execution convention for every VIZA-rendered backtest, my call: a signal computed from the close of day D is traded at the close of day D+1 (one-day lag, since only closes exist in the data); zero transaction cost; no benchmark unless the user names one. All three are printed in the run header and are overridable in the run settings. Defaults that are disclosed and overridable do not count as silent interpretation.
- For signals: pass counts per date, current passing list, forward returns after a pass.
- For weights: equity curve, turnover, drawdown, exposure by sector.
- For reports: the user's named values rendered as tables and line charts.

The strategy workflow diagram (section 3) is rendered from a static read of the user's code: which `VizaData` methods were called with which fields, and what return kind was declared.

### 7.9 Data refresh

A daily job pulls the latest FaustCalc rows from the FaustCalc Railway Postgres into AAT staging through the existing `jobs/import_faustcalc_feature_store.py` path, promotes new price bars, then recomputes precomputed attributes for the new date. FMP fills what FaustCalc does not cover: annual statements and key metrics history, and adjusted closes if phase 1 finds FaustCalc closes unadjusted. All FMP calls go through the existing `FMP_*` configuration and rights flags. The scheduling pattern follows the existing KOSPI daily job (`scripts/run_pilot_kospi_daily.ps1` under Windows Task Scheduler) rather than introducing a new scheduler. While the backfill freeze holds, the sandbox refresh job is a new script that calls the existing import module without modifying it, and writes only to `viza_sandbox`.

### 7.10 What the FMP Starter plan allows

Verified on 2026-11-15 from FMP's pricing page. Starter: 300 API calls per minute, up to 5 years of historical data, US coverage, annual ratios and metrics, historical stock prices, and a trailing 30-day bandwidth cap of 20 GB. Quarterly statements and 30 years of history start at Premium (listed at 49 to 69 USD per month). Bulk and batch delivery starts at Ultimate.

Consequences for v1:

- Fundamentals history is annual, 5 years, US names only. For about 12,600 active names and three statements plus key metrics, the initial load is roughly 50,000 calls, under three hours at the rate limit, and small in bytes. Daily refresh is incremental by filing date.
- Adjusted prices from FMP, if needed, cover 5 years for about 24,500 names: roughly 24,500 calls and an estimated 4 to 5 GB, inside the bandwidth cap but to be spread over several days on first load.
- Quarterly fundamentals are a plan upgrade, not a design change. The statements loader must handle `period=quarter` so that upgrading is a configuration flip. Whether to upgrade is the owner's purchase decision and is not assumed here.

### 7.11 Vendor rights and the result channel

FMP's pricing page states that displaying or redistributing FMP-sourced data requires a separate Data Display and Licensing Agreement. The owner expects the eventual license to forbid redistribution. Design consequences:

- Every series in `VizaData` carries a `rights_class`: `vendor_raw` (FMP and FaustCalc-FMP prices, statements, snapshot fundamentals) or `viza_computed` (catalog attributes computed by VIZA).
- Within the sandbox container, user code sees everything. The constraint is on what leaves.
- Result rendering for a user who is not the owner blocks any returned frame or series that is a `vendor_raw` panel or a trivially reversible view of one (same index, values equal to a raw series or a constant multiple of it). The rendered result shows the block with the reason. Scores, signals, weights, portfolio curves and `viza_computed` attributes pass. This is a rights filter, not a methodology filter, so it does not conflict with the no-interpretation anti-goal; the filter is documented in the run header and is identical for every run.
- The owner's own runs are internal use and are not filtered.
- Until licensing is confirmed, every run header carries `source_rights_state=development_proving` and invited quants are told so in the results view.

The rights filter also encodes the business boundary: VIZA sells computed attributes and the sandbox around them, not raw data.

## 8. Phasing

1. **Data foundation.** `viza_sandbox` database and read-only role. Split-adjustment check on FaustCalc closes. Availability policy applied at materialization. Point-in-time panel materialization to Parquet for prices and universe membership (section 7.3.1). Auditor sign-off on leakage probes.
2. **Execution.** Container runner, `VizaData` with `prices` and `universe`, scores return kind, run record, per-user accounts. First end-to-end backtest of a simple momentum strategy.
3. **Catalog.** Precomputed attribute job and registry entries for the price-based seed set. FMP annual statements and key metrics loader with `acceptedDate` availability. Fundamental seed attributes. `fundamentals`, `attribute` and `series` on `VizaData`.
4. **Return kinds and rights.** Signals, weights and report return kinds. Rights filter on the result channel.
5. **Surface.** Desktop feature for code submission and results, workflow diagram, data-quality panel.
6. **Refresh.** Daily scheduled FaustCalc pull, FMP incremental statements, attribute recompute. Hourly data is not investigated in v1: the Starter plan has no intraday data.

Each phase ends with the look-ahead audit suite green. Nothing in phases 1 to 6 touches a file frozen by the backfill guardrails.

## 9. Left to the builder

- Exact Parquet layout and partitioning.
- Container technology. Docker is the obvious choice given the server already runs Docker Desktop under WSL2.
- Whether the data service caches materialized panels, and the eviction policy.
- How the desktop authenticates to the sandbox API. The existing local engine token pattern is a starting point, but the service is no longer local.
- The static-analysis approach for the workflow diagram.
- Which FaustCalc fundamental payload fields map to which catalog keys. The payload is raw JSONB and needs a one-time mapping pass.

## 10. Open questions for the owner

None. The builder check raised eight; four were settled by the designer (sections 7.3.1, 7.7 identity, 7.8 execution convention, 7.9 scheduling pattern) and four by the owner (section 6, last six rows). One factual check remains for phase 1: whether FaustCalc closes are split-adjusted (section 7.4).

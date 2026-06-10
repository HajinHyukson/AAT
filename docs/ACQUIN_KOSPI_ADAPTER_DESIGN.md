# Acquin KOSPI Adapter Design

Last updated: 2026-06-09
Status: Phase 1 implemented (staging models, migration `20260609_0012`, import,
promotion with continuity guard, flow evidence, and the KOSPI pilot runner).
Phase 2 enrichment not started.

## Purpose

Define how AAT ingests Korean (KOSPI) market data from the Acquin database and runs
attribution on a local KOSPI pilot track. The design follows the FaustCalc snapshot-import
pattern: stage source rows verbatim, then selectively promote into canonical AAT tables.

The design is explicitly two-phase:

- **Phase 1 (metadata-free):** ticker-only entities, price promotion, KOSPI market factor,
  investor-flow evidence. Fully runnable end-to-end attribution with market + residual.
- **Phase 2 (enrichment, optional):** names/ISINs, sector classifications, generated peer
  baskets, sector proxy factors. Added as new mapping rows with zero rework of Phase 1 data.

## Source: Acquin Railway Postgres

Acquin (`C:\Users\Hajin Son\Acquin`) is the KOSPI Investor Flow Intelligence Platform. Its
production Postgres on Railway is the import source. Connection is read-only via
`ACQUIN_DB_URL` in `.env` (public Railway proxy URL, read-only role recommended).

Profiled on 2026-06-09:

| Source Table | Rows | Contents |
|---|---:|---|
| `dim_stock` | 948 | KOSPI tickers (859 common, 89 preferred). No ISIN, names, sectors, listing dates, or delistings. |
| `fact_price_daily` | ~1.64M | Daily OHLCV + adjusted close + market cap + shares outstanding, 2019-01-02 to present, `source=pykrx`, `freshness_state=FINAL_EOD`. |
| `fact_investor_flow_daily` | ~4.86M | Buy/sell/net volume and amount per ticker/day for `retail`, `institution`, `foreign`. Full coverage. |
| `fact_foreign_holding_daily` | ~1.64M | Foreign held shares, ownership pct, limit shares, limit exhaustion pct. Full coverage. |
| `fact_index_daily` | 1,824 | KOSPI index (code `1001`) OHLC + `return_1d`, full date range. |
| `fact_features_daily` | ~1.64M | Acquin-derived flow/price features (not imported; AAT derives its own). |

Profiling scripts: `scripts/profile_acquin_db.py`, `scripts/profile_acquin_data.py`,
`scripts/profile_acquin_splits.py`.

### Profiling findings that drive the design

1. **Prices are split-adjusted as a frozen snapshot.** `adj_close = close` on every row;
   Kakao (035720) around its 2021-04-15 5:1 split shows adjusted continuity. The bulk
   backfill (created 2026-06-01/02) adjusted history as-of that date. The daily appender
   does **not** retro-adjust history when a new corporate action occurs, so continuity can
   silently break after a post-backfill split. Four rows with one-day drops <= -40% exist;
   two are recent (`204210` 2026-06-02, `140910` 2026-05-29) and unverified.
2. **Ingestion timestamps are honest only from 2026-06-05 onward.** All earlier rows carry
   bulk-backfill `created_at` values (2026-06-01/02). Daily rows since then are written at
   ~07:22 UTC (~16:22 KST), after KRX close.
3. **`dim_stock` metadata is empty** apart from `ticker`, `market`, `is_preferred`,
   `is_active`. Tickers are not all six-digit (`33637L` exists).
4. **Survivorship bias:** only currently-listed names; no delistings since 2019. Backtest
   interpretation must caveat this; per-ticker history depth ranges 65 to 1,824 rows.
5. **KRW magnitudes fit canonical columns.** `price_bar` `Numeric(18,6)` holds KRW prices;
   `volume` is `BigInteger`. Market cap and trading value (up to ~10^15) exceed canonical
   price precision and stay staging-only, like FaustCalc.

## Deployment Boundary

All KOSPI pilot work happens in a separate local database (`aat_pilot_kospi`), mirroring
the `aat_pilot_sp500` pattern. Nothing touches the server database while the FaustCalc
backfill run `a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c` is live, consistent with
`docs/LIVE_BACKFILL_DEVELOPMENT_GUARDRAILS.md`.

## Licensing

Acquin's price/flow data originates from pykrx (KRX public endpoints), prototype-grade per
Acquin's own data-source policy. AAT applies the standard fail-closed gate:

```python
require_confirmed_production_source(
    source_name="acquin_pykrx",
    env_var="ACQUIN_PYKRX_PRODUCTION_LICENSE_CONFIRMED",
)
```

Until a licensed KRX/Koscom/KIS feed replaces pykrx, KOSPI data is development/research
only and must not be served from a production deployment.

## Phase 1: Metadata-Free Pilot

### Staging tables (new Alembic migration)

Mirrors the `faustcalc_*` staging discipline: stage verbatim, validate, then promote.

| Table | Source | Notes |
|---|---|---|
| `acquin_import_run` | n/a | One row per import execution: scope, row counts, status. Mirrors `faustcalc_import_run`. |
| `acquin_validation_issue` | n/a | Quarantined rows + reason (continuity guard hits, bad values). Mirrors `faustcalc_validation_issue`. |
| `acquin_stock` | `dim_stock` | ticker, market, is_preferred, is_active, raw payload. |
| `acquin_price` | `fact_price_daily` | All columns verbatim incl. market_cap, trading_value, source `created_at`. |
| `acquin_investor_flow` | `fact_investor_flow_daily` | All columns verbatim. |
| `acquin_foreign_holding` | `fact_foreign_holding_daily` | All columns verbatim. |
| `acquin_index` | `fact_index_daily` | All columns verbatim. |

Staging columns use wide types (`Float`/`Numeric(30,6)`/`Text`) so no source row is ever
rejected at staging time — the FaustCalc precision lesson.

### Entity creation (placeholder identities)

For each `acquin_stock` row:

- `company.legal_name = "KOSPI <ticker> (placeholder)"`, no CIK.
- `security.exchange = "KRX"`, `share_class = "preferred"` when `is_preferred`, ISIN null.
- `security_ticker_history` row with the Acquin ticker, `active_from` = listing unknown ->
  pilot universe `active_from`.
- Tickers must be treated as opaque strings (`33637L` is valid), never parsed as 6 digits.
- Placeholder names carry a `(placeholder)` suffix so Phase 2 enrichment can target them
  without colliding with curated rows (FaustCalc generated-vs-curated convention).

`company_id`/`security_id` are immutable from this point; Phase 2 only updates metadata.

### Universe config

`config/pilot_kospi_universe.json`, mirroring `pilot_sp500_universe.json`:

```json
{
  "version": "kospi_static_2026_06_09_v0",
  "universe_name": "pilot_kospi_static",
  "source": "acquin_railway_dim_stock_snapshot",
  "retrieved_at": "<import time>",
  "notes": [
    "Static KOSPI pilot universe for local methodology research only.",
    "Survivorship-biased: active listings only, no delistings since 2019.",
    "No sector/industry metadata in Phase 1."
  ],
  "securities": [
    {"ticker": "005930", "market": "KOSPI", "is_preferred": false}
  ]
}
```

### Vintage policy (point-in-time correctness)

Every promoted row needs `event_time`, `ingestion_time`, `timestamp_available`:

| Rows | `event_time` | `ingestion_time` | `timestamp_available` |
|---|---|---|---|
| Backfilled (source `created_at` < 2026-06-03 00:00 UTC, or missing) | trade date 06:30 UTC (15:30 KST close) | source `created_at` | **trade date + 1 day 00:00 UTC** (conservative: true publication time unknowable) |
| Live (source `created_at` >= 2026-06-03 00:00 UTC) | trade date 06:30 UTC | source `created_at` | max(source `created_at`, event_time) (real post-close ingestion, ~07:22 UTC) |

The same policy applies to prices, flows, holdings, and index rows. This is deliberately
conservative for backfilled history: attribution never sees a bar before the day after its
trade date, so no backfilled row can leak same-day information.

### Price promotion with continuity guard

Promotion `acquin_price` -> `price_bar`:

- `currency = "KRW"`, `source = "acquin_pykrx"`, `close = adjusted_close = adj_close`.
- Reject (to `acquin_validation_issue`, not `price_bar`): non-positive close, null close.
- **Continuity guard:** any bar implying `abs(close-to-close return) > 0.40` against the
  prior promoted bar for that security is quarantined with reason
  `continuity_suspect`, along with all later bars for that security until manually
  reviewed. A genuine crash can be released from quarantine by marking the issue resolved;
  an unadjusted corporate action requires re-importing that ticker's full adjusted history.
- Market cap, trading value, shares outstanding stay staging-only.

The guard exists because the source's adjustment snapshot can silently break after a
post-backfill corporate action (finding 1). The two current suspects (`204210`, `140910`)
must be resolved before their securities' Phase 1 promotion.

### KOSPI market factor

From `acquin_index` (code `1001`):

- Compute daily close-to-close index returns; persist as `factor_return` rows with
  `factor_name = "kospi_market"`, `factor_family = "market_proxy"`,
  `source = "acquin_pykrx"`, same vintage policy as prices.
- Attribution uses the existing market-factor baseline path (rolling-window beta against
  `kospi_market`), exactly as the US side uses the French market factor or proxy ETFs.
- No risk-free leg in Phase 1: contributions are vs. raw index return, and that
  simplification is recorded in run metadata.

### Investor-flow evidence (evidence-only)

Stage flows/holdings and derive per-window evidence descriptors, e.g.:

- foreign net-buy streak length and 5d/20d net amounts,
- foreign ownership pct change over the window,
- foreign limit exhaustion level,
- institution/retail net-flow z-scores.

These attach to attribution results as evidence payload rows with `contribution_bps = 0`
(evidence-only), consistent with the project rule that uncalibrated inputs must not reduce
residual until a validated production factor return exists. They surface in the dashboard
evidence drawer like EDGAR event evidence does for US names.

### Phase 1 jobs

| Job | Purpose |
|---|---|
| `jobs/init_pilot_kospi_db.py` | Create/migrate the `aat_pilot_kospi` database (mirrors `init_pilot_sp500_db`). |
| `jobs/import_acquin_snapshot.py` | Read-only pull from `ACQUIN_DB_URL` into `acquin_*` staging; incremental by source `created_at`; records an `acquin_import_run`. |
| `jobs/promote_acquin_data.py` | Entities, universe membership, price promotion (continuity guard), index factor returns, vintage stamping. |
| `jobs/generate_acquin_flow_evidence.py` | Flow/holding evidence descriptors. |
| `jobs/run_pilot_kospi_attribution.py` | Windowed attribution runner (mirrors `run_pilot_sp500_attribution`; skips completed windows by default). |

### Phase 1 acceptance

- Import and promotion are idempotent (re-running creates no duplicates).
- Every promoted row passes the look-ahead audit suite (`tests/lookahead_audit`) patterns;
  new replay tests cover the backfilled-vs-live vintage split.
- A full pilot run produces daily/weekly/monthly attribution for the 948-name universe
  with `kospi_market` contributions, flow evidence payloads, and explicit
  `unexplained_residual` on every result.
- Residuals are expected to be larger than US names (market factor only); that is a
  correct degradation, not a failure.

## Phase 2: Metadata Enrichment (Optional, Later)

Unlocks, in dependency order:

1. **Names/ISINs:** static KRX listing file or pykrx from a Korean-IP host; replaces
   `(placeholder)` names, fills `security.isin`. No identity changes.
2. **Sector classification:** KRX industry classification into `sector_classification`
   rows with `source = "generated_acquin_krx"` — never overwriting curated rows.
3. **Generated peer baskets:** deterministic baskets from sector groups (FaustCalc
   pattern), enabling peer contribution rows.
4. **Sector proxy factors:** KODEX sector ETF prices (new ingestion) or sector-average
   return composites, enabling sector contribution rows via the existing proxy-factor path.
5. **Delistings/corporate actions:** licensed feed required; removes the survivorship
   caveat and the continuity-guard manual review burden.

Each step adds mapping/factor rows only; Phase 1 attribution runs remain valid and
reproducible.

## Open Questions

1. Resolve `204210` (2026-06-02, -66%) and `140910` (2026-05-29, -65%): real crash or
   unadjusted corporate action? Determines whether those tickers need re-import.
2. Daily sync cadence: pilot is manual re-import for now; a scheduled incremental import
   only matters if the KOSPI pilot becomes a standing track.
3. Risk-free rate for Korea (BOK base rate via FRED) — Phase 2 refinement of the market
   factor.
4. Whether Acquin's `fact_features_daily` should ever be imported, or AAT always derives
   its own descriptors from raw flows (current design: derive own).

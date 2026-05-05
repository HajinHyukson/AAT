# FaustCalc Data Implementation Report

Last updated: 2026-05-05

## Purpose

This report separates the FaustCalc data work from the general AAT project status. It documents what FaustCalc data is now inside AAT, how it is stored, what has been promoted into canonical AAT tables, and where the full-history attribution backfill currently stands.

The server database is now the operational source of truth for FaustCalc-expanded attribution work.

## Current Deployment State

The FaustCalc-augmented AAT database has been migrated from the original development machine to the server machine.

Current server setup:

- Server repo path: `~/work/AAT`
- Server Postgres container: `aat-postgres`
- Database: `attribution`
- Docker/WSL mode: Docker Desktop Linux containers through WSL2/Ubuntu
- Exposed Postgres port: `55432`
- Current server LAN IP used from the development machine: `10.0.0.60`

The development machine can read the server database with:

```powershell
$env:DATABASE_URL="postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution"
python -m jobs.run_faustcalc_attribution_backfill --status-only
```

For local server execution inside Ubuntu, continue using:

```bash
cd ~/work/AAT
source .venv/bin/activate
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --status-only
```

## FaustCalc Data Contents

Live counts from the server database on 2026-05-05:

| AAT Staging Table | Rows | Contents |
|---|---:|---|
| `faustcalc_asset` | 24,494 | FaustCalc asset/security universe snapshot with ticker, asset type, exchange, market, currency, and active flag. |
| `faustcalc_company` | 24,413 | FaustCalc company metadata including CIK, sector, industry, country, and raw source payload. |
| `faustcalc_price` | 11,267,847 | FaustCalc historical close/volume price rows staged at source granularity. |
| `faustcalc_fundamental` | 16,981 | Fundamental source rows staged for later feature expansion. |
| `faustcalc_price_feature` | 18,204 | FaustCalc price-derived feature rows staged for future model use. |
| `faustcalc_theme_score` | 56,830 | Theme score rows staged for future thematic attribution/research. |
| `faustcalc_filing_analysis` | 12,727 | FaustCalc filing-analysis source rows staged for future event/evidence expansion. |
| `faustcalc_peer_analysis` | 21,450 | FaustCalc peer-analysis source rows staged for future peer-model expansion. |
| `faustcalc_sec_filing` | 2,009 | Cleaned/deduped SEC filing catalog rows from FaustCalc normalized SEC files. |

Canonical rows currently promoted or linked from FaustCalc:

| Canonical Area | Rows | Notes |
|---|---:|---|
| `company` | 20,731 | Canonical company identities after FaustCalc promotion and existing AAT rows. |
| `security` | 24,495 | Canonical security identities. |
| `security_ticker_history` | 24,495 | Current ticker mappings, including FaustCalc-promoted identities. |
| `price_bar` from `faustcalc_fmp_snapshot` | 11,265,327 | Promoted FaustCalc historical prices. |
| `event` from `faustcalc_sec_edgar_snapshot` | 576 | Promoted SEC filing events. |
| `event_feature` for FaustCalc SEC events | 576 | Event features generated for promoted FaustCalc SEC events. |

Current server database size is about `7.7 GB` before the full FaustCalc attribution backfill completes. The expected final size after backfill is still roughly `60-80 GB`, with `100 GB` as a practical planning target and `150-200 GB+` free disk space preferred.

## Implementation Completed

### FaustCalc Staging And Import

Implemented in:

- `alembic/versions/20260504_0007_faustcalc_staging.py`
- `jobs/import_faustcalc_feature_store.py`
- `jobs/import_faustcalc_sec_filings.py`
- `jobs/faustcalc_common.py`

Implemented behavior:

- Added `faustcalc_` staging tables for source-preserved FaustCalc data.
- Added `faustcalc_import_run` and `faustcalc_validation_issue` audit tables.
- Added feature-store import CLI for FaustCalc DB tables.
- Added SEC filing import CLI for normalized FaustCalc SEC files.
- Added deterministic source-row IDs and idempotent upserts.
- Added ticker normalization including share-class aliases such as `BRK.B` / `BRK-B`.
- Preserved raw payloads in staging so future AAT features can be built without re-importing the source snapshot.

### Price Promotion

FaustCalc prices are promoted into canonical `price_bar` with:

- `source = faustcalc_fmp_snapshot`
- `event_time = price_date` at UTC midnight
- `close = FaustCalc close`
- `adjusted_close = FaustCalc close`
- `open`, `high`, and `low` left `NULL`
- `volume = FaustCalc volume`
- `currency` from FaustCalc asset metadata, defaulting to `USD`
- `timestamp_available` and `ingestion_time` set to the import time

Rows that fail canonical precision/range validation remain staged for audit instead of being forced into canonical data.

### SEC Filing Cleanup

Implemented behavior:

- Rebuilds the SEC filing catalog by scanning normalized SEC files instead of trusting only a manifest.
- Parses ticker and accession number from filename.
- Validates accession/doc metadata where available.
- Dedupes by accession number first, then content hash.
- Keeps source ticker aliases in staging metadata.
- Stores cleaned text files outside Postgres and stores only path/hash/metadata in the DB.
- Promotes clean filing metadata into canonical `event`.
- Generates event features for promoted SEC filing events.

### FaustCalc Universe

Implemented in:

- `alembic/versions/20260504_0011_faustcalc_universe_attribution.py`
- `jobs/build_faustcalc_universe.py`

Current universe:

| Field | Value |
|---|---|
| Universe name | `faustcalc_active_us_equities` |
| Universe version | `faustcalc_active_us_equities_v0` |
| Eligibility rule | active FaustCalc USD stock with canonical AAT security and FaustCalc price coverage |
| Eligible securities | 12,657 |
| Universe price bars | 7,581,216 |
| First universe price time | 2023-04-06 UTC |
| Last universe price time | 2026-04-02 UTC |

ETFs and inactive equities remain available in staging/canonical data but are excluded from this first expanded attribution universe.

### Generated Mapping Support

Implemented in:

- `jobs/seed_faustcalc_auto_mappings.py`

Generated mapping counts:

| Mapping Type | Rows |
|---|---:|
| Auto sector/industry classifications | 12,029 |
| Auto peer baskets | 12,029 |
| Auto peer basket members | 238,087 |
| Auto macro exposure gates | 32,656 |

Generated mappings use `faustcalc_auto_mapping_v0` and fill gaps without overwriting curated MVP mappings.

### Attribution Backfill Optimization

Implemented in:

- `jobs/run_faustcalc_attribution_backfill.py`
- `jobs/run_attribution.py`
- `db/session.py`
- `jobs/advisory_locks.py`

Implemented behavior:

- Added resumable backfill tasks in `attribution_backfill_task`.
- Added `--status-only` tracker output.
- Added `--window-commit-size`, defaulting to `25`, so long tasks checkpoint during execution.
- Added `--task-order expected-windows`, so shorter positive-window tasks complete first.
- Added preloaded price/factor/macro inputs per task.
- Added reusable peer context so peer price histories are loaded once per task instead of repeatedly per window.
- Fixed SQLAlchemy session pooling so repeated checkpoint sessions reuse a small shared engine/pool rather than exhausting Postgres clients.
- Added distributed task coordination with Postgres advisory locks so multiple updated CLI processes can join the same backfill without claiming the same task.
- Added opt-in `--workers`, defaulting to `1`, and `--worker-id` progress labels.
- Updated attribution persistence to use the attribution-run unique key through `ON CONFLICT DO UPDATE`, then replace contribution rows in the same transaction.

## Current Backfill State

Current FaustCalc backfill run:

```text
a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c
```

Live server snapshot from 2026-05-05:

| Status | Tasks | Expected Windows | Ran Windows | Skipped Windows |
|---|---:|---:|---:|---:|
| `completed` | 989 | 4,865 | 4,865 | 0 |
| `pending` | 36,828 | 7,151,605 | 0 | 0 |
| `running` | 1 | 8 | 0 | 0 |
| `skipped` | 153 | 0 | 0 | 0 |

Overall tracker:

| Metric | Value |
|---|---:|
| Total tasks | 37,971 |
| Finished tasks | 1,142 |
| Completed tasks | 989 |
| Skipped tasks | 153 |
| Failed tasks | 0 |
| Windows run | 4,865 |
| Total expected windows | 7,156,478 |

Last observed running task:

| Ticker | Cadence | Expected Windows | Ran Windows | Last Window End |
|---|---|---:|---:|---|
| `ZLS` | `monthly` | 8 | 0 | `NULL` |

Current attribution output tables:

| Table | Rows |
|---|---:|
| `attribution_run` | 6,929 |
| `attribution_contribution` | 86,244 |

The backfill is checkpointed and resumable. If interrupted, resume with:

```bash
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --backfill-run-id a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c --batch-size 200 --window-commit-size 25 --progress-every 10
```

Distributed workers can now join from multiple machines as long as every active worker is running the updated advisory-lock-aware code. Start conservatively with two total workers, then try three only if Postgres and disk pressure are stable.

Server-local worker:

```bash
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --backfill-run-id a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c --batch-size 200 --window-commit-size 25 --workers 1 --progress-every 10 --worker-id server-1
```

Development-machine remote worker:

```powershell
$env:DATABASE_URL="postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution"
python -m jobs.run_faustcalc_attribution_backfill --backfill-run-id a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c --batch-size 200 --window-commit-size 25 --workers 1 --progress-every 10 --worker-id dev-1
```

## Frontend And Summary State

Implemented:

- Added `security_attribution_summary`.
- Updated `/universe` API path to query universe membership and summaries with SQL pagination/filtering.
- Avoided loading all securities and deduping in Python for the expanded universe path.

Current summary table state:

| Run Status | Rows |
|---|---:|
| `available` | 50 |
| `missing` | 12,607 |

This is expected until the full FaustCalc backfill completes and summaries are refreshed.

After backfill completion, run:

```bash
python -m jobs.refresh_attribution_summaries --prefer-compose-port
```

Then verify the API:

```bash
curl "http://localhost:8000/universe?limit=50&prefer_compose_port=true"
```

## Operational Notes

- Treat the server DB as the source of truth after migration.
- Simultaneous backfill workers are now supported only when all workers are running the updated advisory-lock-aware code.
- The development machine can monitor or run remote jobs by setting `DATABASE_URL` to the server DB and omitting `--prefer-compose-port`.
- The server should keep Docker Desktop, WSL2, and Ubuntu running while backfill is active.
- FMP-derived FaustCalc price data remains development/proving data unless production licensing is confirmed.

## Remaining Work

1. Let the FaustCalc full-history attribution backfill complete.
2. Refresh `security_attribution_summary`.
3. Validate `/universe` response time and expanded coverage after summaries refresh.
4. Run spot checks for key tickers such as `AAPL`.
5. Create a post-backfill server DB dump.
6. Confirm production price-data licensing/source policy before any production use.

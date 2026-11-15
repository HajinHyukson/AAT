# VIZA Quant Sandbox: Operations

## Purpose

The sandbox lets a quant submit a Python strategy, run it in isolation against point-in-time
price panels built from the canonical `attribution` database, and read back a quantile backtest.
This document is for the operator who stands it up on the server.

- Design spec: `docs/superpowers/specs/2026-11-15-viza-quant-sandbox-design.md`
- Implementation plan: `docs/superpowers/plans/2026-11-15-viza-quant-sandbox-phase-1-2.md`

This delivers spec phases 1 (data foundation) and 2 (execution) only.

## Known gaps to close before trusting isolation

- The Docker image build and `DockerRunner` have not been executed in development, because no
  Docker daemon was available. On the server, build the image (below) and run
  `python -m pytest tests/unit/test_sandbox_runner.py -q`. The Docker test must pass, not skip.
  Until it does, treat container isolation as unverified.
- `VIZA_SANDBOX_RUNNER=local` runs user code as a plain subprocess with no network, memory or
  filesystem isolation, and with write access to the shared panel cache through the run
  directory's data link. It is for tests and development only. Never use it for code written by
  other people.

## Server prerequisites

- Docker, with a running daemon, for the default `docker` runner.
- Network access to the AAT Postgres server that holds the canonical `attribution` database.
- Python environment with this repo's dependencies installed.

## One-time SQL

First confirm the attribution backfill status with the read-only command
`python jobs/run_faustcalc_attribution_backfill.py --status-only`. Then run once as a Postgres
admin:

```sql
CREATE DATABASE viza_sandbox;
CREATE ROLE viza_sandbox_ro LOGIN PASSWORD '<choose>';
GRANT CONNECT ON DATABASE attribution TO viza_sandbox_ro;
\c attribution
GRANT USAGE ON SCHEMA public TO viza_sandbox_ro;
GRANT SELECT ON price_bar, security, security_ticker_history, faustcalc_company TO viza_sandbox_ro;
```

This creates no table and alters no canonical table, so it is compatible with the backfill
guardrails. The canonical database is read-only to the sandbox.

## Environment variables

All have the prefix `VIZA_SANDBOX_` and a default, except the canonical URL.

| Variable | Default | Meaning |
|---|---|---|
| `VIZA_SANDBOX_DATABASE_URL` | `sqlite:///./data/viza_sandbox/sandbox.db` | Sandbox store (users, runs). Point at the `viza_sandbox` database on the server. |
| `VIZA_SANDBOX_CANONICAL_DATABASE_URL` | none (required to serve) | Canonical `attribution` database, using the `viza_sandbox_ro` role. `serve` and `check-split-adjustment` fail closed without it. |
| `VIZA_SANDBOX_DATA_DIR` | `data/viza_sandbox` | Panel cache and sandbox data. |
| `VIZA_SANDBOX_RUNS_DIR` | `data/viza_sandbox/runs` | Per-run directories. |
| `VIZA_SANDBOX_RUNNER` | `docker` | `docker` or `local` (see known gaps). |
| `VIZA_SANDBOX_DOCKER_IMAGE` | `viza-sandbox-runtime:latest` | Image used by the docker runner. |
| `VIZA_SANDBOX_PRICE_ADJUSTMENT_STATUS` | `unverified` | `unverified`, `adjusted` or `unadjusted`. Disclosed in the run header. |

Limits (`VIZA_SANDBOX_WALL_CLOCK_SECONDS` 600, `VIZA_SANDBOX_MEMORY_GB` 8, `VIZA_SANDBOX_CPUS` 2)
and `VIZA_SANDBOX_SOURCE_RIGHTS_STATE` (`development_proving`) are also configurable.

## Build the image

From the repo root:

```bash
docker build -f viza_sandbox/runtime_image/Dockerfile -t viza-sandbox-runtime:latest .
```

## Initialize, create users, serve

```bash
python -m viza_sandbox.cli init-db
python -m viza_sandbox.cli create-user --name alice --owner
python -m viza_sandbox.cli serve --host 127.0.0.1 --port 8781
```

`init-db` prints the store URL with the password redacted. `create-user` prints
`user_id=...` and `token=...`. The token is shown once and only its hash is stored; give it to
the user over a private channel. `--owner` marks an owner account.

## Split-adjustment check

Whether FaustCalc closes are split-adjusted is unverified (spec section 7.4). The promotion
wrote `adjusted_close = close`. Check NVDA across the 2024-06-10 10-for-1 split:

```bash
python -m viza_sandbox.cli check-split-adjustment --ticker NVDA --from 2024-06-05 --to 2024-06-12
```

It prints each `event_date close adjusted_close` row and a final `verdict=...` line.
If fewer than two bars fall in the window (wrong `--source`, a window that misses the split,
or a data gap) the command exits nonzero with no verdict; that is not evidence of adjustment.

- `verdict=unadjusted`: a consecutive close ratio of 3x or more (or 1/3 or less) was found, so
  closes are not split-adjusted. Set `VIZA_SANDBOX_PRICE_ADJUSTMENT_STATUS=unadjusted`. Per the
  spec, the remedy is to source FMP `adjClose`; that is not built in this phase.
- `verdict=no_split_signature`: no jump was found in the window. This supports, but a single
  ticker does not prove, adjustment. Set `VIZA_SANDBOX_PRICE_ADJUSTMENT_STATUS=adjusted` only
  after you are satisfied, and leave `unverified` otherwise.

## Submitting a run

```bash
curl -X POST http://127.0.0.1:8781/sandbox/runs \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "code": "from viza_sandbox.sdk import scores\ndef strategy(data):\n    return scores(data.prices('"'"'close'"'"').pct_change(2))\n",
    "start": "2024-01-01",
    "end": "2024-01-31",
    "backtest": {"quantiles": 3, "rebalance": "daily"}
  }'
```

The response is `202` with a `run_id`. Poll `GET /sandbox/runs/{run_id}` for status and fetch
`GET /sandbox/runs/{run_id}/result` when it has finished. Runs are visible only to their owner.

## What to tell a quant

Execution convention (spec 7.8), printed in every result header:

- A signal computed from the close of day D is traded at the close of day D+1 (one-day lag).
- Zero transaction cost.
- No benchmark.

These defaults are disclosed in the header (`signal_lag_days`, `transaction_cost`, `benchmark`).
All returns are price returns; dividends are absent from the sources.

Point-in-time policy (spec 7.3, 7.4): a value is visible on date D if and only if its
`available_at` is at or before the end of D (UTC). Daily prices carry `available_at` of their
`event_date` at 21:00 UTC under the policy `faustcalc_fmp_snapshot_eod_policy_v1`, recorded in
the run's data manifest. There is no raw mode that bypasses `available_at`. Sector and industry
are snapshot-only and carry `classification_as_of`.

## Not in this phase

Fundamentals, catalog attributes (`data.attribute`, `data.series`), the `signals`, `weights` and
`report` return kinds, the vendor rights filter on the result channel, the desktop surface, and
the daily refresh job. See spec section 8, phases 3 to 6.

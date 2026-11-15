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

## Pre-flight before the first real run

- Build the image, run the Docker test above, and confirm it passes (not skips).
- On the first server build, pin the image's dependency versions in
  `viza_sandbox/runtime_image/Dockerfile` and record the built image digest
  (`docker image inspect --format '{{.Id}}' viza-sandbox-runtime:latest`) alongside the
  deployment, so a rebuild cannot silently change results for the same code and data manifest.
- Measure materialization time and memory for the intended date range before the first real
  run. Materialization runs in the API process, outside the container's limits.
- Run the split-adjustment check below and set `VIZA_SANDBOX_PRICE_ADJUSTMENT_STATUS`.

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

`VIZA_SANDBOX_DATABASE_URL` needs its own login role with rights to create and write tables in
the `viza_sandbox` database. Do not reuse `viza_sandbox_ro`: that role is for reading the
canonical database only.

## Environment variables

All have the prefix `VIZA_SANDBOX_` and a default, except the canonical URL.

| Variable | Default | Meaning |
|---|---|---|
| `VIZA_SANDBOX_DATABASE_URL` | `sqlite:///./data/viza_sandbox/sandbox.db` | Sandbox store (users, runs). Point at the `viza_sandbox` database on the server, with its own read-write role (not `viza_sandbox_ro`). For a SQLite file the parent directory is created. |
| `VIZA_SANDBOX_CANONICAL_DATABASE_URL` | none (required to serve) | Canonical `attribution` database, using the `viza_sandbox_ro` role. `serve` and `check-split-adjustment` fail closed without it. |
| `VIZA_SANDBOX_DATA_DIR` | `data/viza_sandbox` | Panel cache and sandbox data. |
| `VIZA_SANDBOX_RUNS_DIR` | `data/viza_sandbox/runs` | Per-run directories. |
| `VIZA_SANDBOX_RUNNER` | `docker` | `docker` or `local` (see known gaps). |
| `VIZA_SANDBOX_DOCKER_IMAGE` | `viza-sandbox-runtime:latest` | Image used by the docker runner. |
| `VIZA_SANDBOX_PRICE_ADJUSTMENT_STATUS` | `unverified` | `unverified`, `adjusted` or `unadjusted`. Disclosed in the run header. |
| `VIZA_SANDBOX_MAX_CONCURRENT_RUNS` | `2` | Runs executing at once in the service process. Further runs stay `queued` until a slot frees. |
| `VIZA_SANDBOX_MAX_RESULT_BYTES` | `268435456` | Largest `out/result.parquet` the host will read; a larger file fails the run. `out/error.json` has a fixed 1 MiB cap. |

Limits (`VIZA_SANDBOX_WALL_CLOCK_SECONDS` 600, `VIZA_SANDBOX_MEMORY_GB` 8, `VIZA_SANDBOX_CPUS` 2)
and `VIZA_SANDBOX_SOURCE_RIGHTS_STATE` (`development_proving`) are also configurable.

## Build the image

From the repo root:

```bash
docker build -f viza_sandbox/runtime_image/Dockerfile -t viza-sandbox-runtime:latest .
```

`viza_sandbox/runtime_image/Dockerfile.dockerignore` limits the build context to
`viza_sandbox/`, so panels and run directories under `data/` are not sent to the daemon. It
applies only to this Dockerfile and needs BuildKit (the default builder in current Docker).

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

The run's full stdout and stderr are written to `stdout.log` and `stderr.log` in its run
directory; the run record keeps the last 65536 characters of each. When the service starts, any
run a previous process left `queued` or `running` is marked `failed` with
`Interrupted by a service restart.`

## What to tell a quant

Execution convention (spec 7.8), printed in every result header:

- Scores dated D (computed from data visible by the close of D) apply to the return realized
  from the close of D+1 to the close of D+2 (one-day lag): the position is entered at the
  close of D+1.
- Zero transaction cost.
- No benchmark.
- Equal weight within each quantile, re-equalized every trading day at zero cost between
  rebalances (header key `weighting_basis`). Holdings are not left to drift between rebalance
  dates.
- Price return on close; dividends not included (header key `return_basis`). Dividends are
  absent from the sources.

These defaults are disclosed in the header (`execution` with `signal_lag_days`,
`transaction_cost`, `benchmark`; `weighting_basis`; `return_basis`).

Point-in-time policy (spec 7.3, 7.4): a value is visible on date D if and only if its
`available_at` is at or before the end of D (UTC). Daily prices carry `available_at` of their
`event_date` at 21:00 UTC under the policy `faustcalc_fmp_snapshot_eod_policy_v1`, recorded in
the run's data manifest. There is no raw mode that bypasses `available_at`. Sector and industry
are snapshot-only and carry `classification_as_of`.

## Not in this phase

Fundamentals, catalog attributes (`data.attribute`, `data.series`), the `signals`, `weights` and
`report` return kinds, the vendor rights filter on the result channel, the desktop surface, and
the daily refresh job. See spec section 8, phases 3 to 6.

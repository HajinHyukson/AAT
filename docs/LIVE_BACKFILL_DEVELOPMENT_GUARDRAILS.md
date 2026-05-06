# Live Backfill Development Guardrails

Last updated: 2026-05-06

## Warning

The FaustCalc attribution backfill is actively running on the server computer. During this period, AAT development may continue on this development machine, but pushed code must not disrupt the server database, the running backfill, or the data-loading sequence that the backfill depends on.

Treat the server database as a live production-like data job until the backfill is complete and a post-backfill backup has been created.

## Hard Rule

While the live FaustCalc backfill is running, do not make or deploy changes that require any of the following on the server:

- A database schema migration.
- A destructive database command.
- A reset, rebuild, or recreation of backfill tasks.
- A change to canonical table structure or constraints.
- A change to FaustCalc import, promotion, or loading order.
- A change that makes the current backfill runner incompatible with already-created tasks.
- A required new environment variable for existing server jobs.

In practical terms: frontend and read-only API work can continue, but schema/loading/backfill-contract changes are frozen.

## Frozen Areas

Avoid changing these areas in a way that would affect the server DB or active backfill:

- `alembic/versions/*`
- `db/models.py`
- `db/session.py`
- `jobs/import_faustcalc_feature_store.py`
- `jobs/import_faustcalc_sec_filings.py`
- `jobs/build_faustcalc_universe.py`
- `jobs/seed_faustcalc_auto_mappings.py`
- `jobs/run_faustcalc_attribution_backfill.py`
- `jobs/run_attribution.py`, if the change alters persisted attribution rows or backfill behavior
- Any script or command that runs Alembic, drops/recreates tables, or mutates canonical FaustCalc-imported data

Small bug fixes in these files should still be treated as high risk while backfill is live. If a fix is needed, document the reason, test it locally, stop workers, update every worker machine, and restart from the same backfill run only after confirming compatibility.

## Safe Work During Backfill

The following work is generally safe if it does not require a schema migration or data reload:

- Frontend-only changes in `dashboard/*`.
- Read-only API presentation changes.
- UI pagination, filtering, formatting, and display improvements.
- Documentation updates.
- Tests that do not mutate the server DB.
- Local-only experiments against a separate local/dev DB.
- New code paths hidden behind flags and not enabled on the server.

When connecting to the server DB for frontend or API checks, keep operations read-only unless the command is an approved backfill worker.

## Deployment Rules During Backfill

Before pushing or deploying code while the backfill is live:

1. Check the diff.

```powershell
git status --short
git diff --stat
```

2. Confirm the change does not add or require Alembic migrations.
3. Confirm the change does not alter active backfill task semantics.
4. Confirm the change does not require running:

```bash
alembic upgrade head
docker compose down
docker volume rm
DROP DATABASE
TRUNCATE
```

5. If deploying to the server, do not run DB migrations during the active backfill.
6. If pulling code onto the server only for frontend/API checks, ensure the running backfill worker is not using a half-updated codebase.

## If A Schema Or Loader Change Is Needed

Defer it until after backfill completion unless it is required to prevent data loss or unblock the running job.

If it cannot be deferred:

1. Stop all backfill workers with `Ctrl+C`.
2. Record current status with `--status-only`.
3. Create a server DB backup.
4. Implement and test the change locally.
5. Pull the same code version onto every worker machine.
6. Apply migrations only after confirming the backfill can resume safely.
7. Resume the same backfill run id.

Current backfill run id:

```text
a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c
```

## Current Approved Backfill Commands

Server-local worker:

```bash
python -m jobs.run_faustcalc_attribution_backfill --prefer-compose-port --backfill-run-id a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c --batch-size 200 --window-commit-size 25 --workers 1 --progress-every 10 --worker-id server-1
```

Development-machine remote worker:

```powershell
$env:DATABASE_URL="postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution"
python -m jobs.run_faustcalc_attribution_backfill --backfill-run-id a6b38bf6-ba13-4188-9dfe-b8e0e85dc47c --batch-size 200 --window-commit-size 25 --workers 1 --progress-every 10 --worker-id dev-1
```

Status check:

```powershell
$env:DATABASE_URL="postgresql+psycopg://attribution:attribution@10.0.0.60:55432/attribution"
python -m jobs.run_faustcalc_attribution_backfill --status-only
```

## Rule For Future Sessions

Before implementing any change while the FaustCalc backfill is still active, first classify the work:

- `safe`: frontend/read-only/docs/local-only, no schema or loader impact.
- `defer`: schema, migration, canonical DB, loader, or backfill-contract change.
- `emergency`: required to prevent loss/corruption or unblock the active backfill.

Only `safe` work should proceed during the live backfill without an explicit stop-backup-migrate-resume plan.

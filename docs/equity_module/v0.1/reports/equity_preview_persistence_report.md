# Equity Preview Persistence Report

## Summary

Added feature-flagged persistence and replayable audit history for `viza.finance.equity_investment v0.1` preview runs.

The implementation keeps the SEC-first `quality_value_long_only` preview as the only wired equity path. It does not add new profiles, trading, order routing, marketplace monetization, adviser functionality, or production-hardening claims.

## Storage Approach

Persistence uses the existing local VIZA project SQLite store resolved through `viza.project_store.project_store_path()`. No standalone equity database was created.

Added narrow equity preview audit tables in the same database:

- `equity_preview_runs`
- `equity_preview_evidence_bundles`
- `equity_preview_report_records`
- `equity_preview_run_observations`

The compact preview payload is also saved to existing `run_records`, and normalized SEC/FMP/FRED-derived observations are persisted through the existing observation store in `viza/observations.py`.

## Feature Flags

New persistence flags default off:

- `VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED=false`
- `VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED=false`

When persistence is disabled, preview behavior remains ephemeral. Run-history endpoints fail closed with `403`, and the desktop history surface is hidden. Replay with refresh is blocked unless the refresh flag is enabled.

## API

Modified:

- `POST /viza/equity/runtime-wedge/preview`
  - accepts `persist_run`
  - returns `run_id`, `persisted`, `persistence_status`, `history_url`, and `proof_checksum`

Added:

- `GET /viza/equity/runtime-wedge/runs`
- `GET /viza/equity/runtime-wedge/runs/{run_id}`
- `POST /viza/equity/runtime-wedge/runs/{run_id}/replay`

Replay from stored observations creates a linked child run and does not make live SEC/FMP/FRED calls. Replay with refresh is explicit, feature-flagged, and creates a new linked run without overwriting the original.

## Desktop UI

Extended the existing `EquityRuntimePreviewPanel` with:

- Save run toggle
- Recent preview runs table
- Run detail viewer
- Proof checksum display
- PIT, rights, validation, and package-redaction detail
- Replay from stored observations button
- Replay with refresh button disabled unless enabled by the sidecar status endpoint

The UI continues to call only the local sidecar bridge and renders the non-advice boundary.

## PIT Behavior

SEC observations persist with source lineage and PIT timestamps from filing/accepted/available/retrieved metadata. FRED observations remain latest-only / not true PIT-safe for backtests unless ALFRED-style vintage cutoff enforcement is implemented. Replay from stored observations uses persisted observations and does not refresh live data.

## Rights And Redaction

SEC-derived observations persist as `public_official` metadata/derived values. FMP observations remain `dev_only_unconfirmed`, `export_policy=blocked`, and `marketplace_policy=redacted` unless production rights are explicitly confirmed. Marketplace draft preview continues to redact restricted, unclear, user-private, or unconfirmed-license data.

## API Key Safety

The runtime reads FMP/FRED keys only through normal environment/config loading. Persistence stores connector modes, rights labels, and source references, not raw credentials. Tests set sentinel FMP/FRED key values and assert they do not appear in API responses or persisted records.

Actual `.env` secret scan result: 2 secret values checked across 164 generated/source/test files, 0 matches.

Proof checksum: `0FF48FEBB8F231F1E43C97D4E0493EE17C56F627419770AAE925773736759E9C`

## Verification

- `python -m pytest tests\unit\test_equity_runtime_wedge.py -q` -> `12 passed in 5.65s`
- `python -m pytest tests\unit\test_equity_module_loader.py tests\unit\test_equity_module_fixtures.py -q` -> `10 passed in 0.66s`
- `python -m pytest tests\unit\test_equity_runtime_wedge_api.py -q` -> `8 passed in 3.99s`
- `python -m pytest tests\unit\test_equity_preview_persistence.py -q` -> `8 passed in 8.42s`
- `python -m pytest tests\unit tests\lookahead_audit` -> `346 passed in 125.85s`
- `node --test tests\dashboard\attribution-period-bars.test.mjs` -> `2 passed`; Node emitted the existing module-type warning.
- `npm run typecheck` in `apps/viza-desktop` -> passed
- `npm run test:desktop` in `apps/viza-desktop` -> `23 passed`
- `npx tsc --noEmit --project tsconfig.json` in `dashboard` -> passed

## Limitations

- Not production-hardened.
- Mocked preview remains the default test path.
- Live SEC/FMP/FRED integration tests remain opt-in only.
- FMP production rights require legal/source-rights review.
- FRED true PIT backtesting requires ALFRED-style cutoff enforcement.
- Ticker alias resolution through a full security master remains future work unless already available.
- `quality_value_long_only` remains the only fully wired equity profile.
- No personalized investment advice, order routing, or monetized marketplace.

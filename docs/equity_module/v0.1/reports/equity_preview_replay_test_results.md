# Equity Preview Replay Test Results

Date: 2026-05-15

## Scope

Validated replayable audit history for the feature-flagged SEC-first equity preview path.

## Backend Replay Results

`tests/unit/test_equity_preview_persistence.py` covers:

- Persistence flag off returns a disabled persistence status and does not expose run history.
- Persistence flag on saves a run record with profile, target, status, warnings, hashes, and proof checksum.
- Saved SEC observations include `source_id`, `observed_at`, `available_at`, `retrieved_at`, PIT state, and rights policy.
- FMP observations persist as `dev_only_unconfirmed`, export blocked, and marketplace redacted unless production rights are confirmed.
- FRED observations persist as latest-only / not true PIT-safe unless vintage support exists.
- Validation report, source-rights report, and package-redaction preview are linked to the run.
- `GET /viza/equity/runtime-wedge/runs` returns compact history rows.
- `GET /viza/equity/runtime-wedge/runs/{run_id}` returns full detail.
- `replay_from_stored_observations` creates a linked child run without live connector calls.
- `replay_with_refresh` is blocked when disabled and creates a linked run only when the refresh flag is enabled.
- Original runs remain immutable across replay.
- Sentinel FMP/FRED key values do not appear in persisted records or API responses.

Command:

```powershell
python -m pytest tests\unit\test_equity_preview_persistence.py -q
```

Result:

```text
8 passed in 8.42s
```

## Desktop Replay Results

`apps/viza-desktop/test/equityPreviewPanel.test.mjs` statically verifies that the packaged desktop source includes:

- Save run persistence toggle
- Recent equity preview runs panel
- Run detail loading
- Replay from stored observations
- Replay with refresh gating
- Proof checksum display
- Local sidecar endpoint usage
- Conservative wording and non-advice boundary

Command:

```powershell
npm run test:desktop
```

Working directory:

```text
c:\Users\gkwls\AAT\apps\viza-desktop
```

Result:

```text
23 passed
```

## Package-Readiness Boundary

The prior packaged Windows preview milestone verified package build and package smoke. This persistence milestone did not rebuild the Windows installer. The new runtime, API, and desktop source paths are test-covered and ready for the next packaged rebuild/smoke cycle, but the module remains not production-hardened.

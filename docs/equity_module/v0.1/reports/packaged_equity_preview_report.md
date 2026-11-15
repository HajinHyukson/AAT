# Packaged Equity Preview Report

## Summary

The Windows packaged desktop prototype is applicable to the equity preview task. The integration now adds a default-off packaged preview path:

```text
Electron result sidebar
-> local FastAPI sidecar
-> feature-flagged equity runtime wedge
-> mocked SEC-first preview fixture by default
-> PIT, rights, validation, non-advice, and package-redaction preview
```

Conservative completion label:

```text
viza.finance.equity_investment v0.1
feature-flagged packaged Windows desktop preview for SEC-first runtime wedge
mock-contract-backed
sidecar endpoint reachable
PIT/rights/validation visible
package-redaction preview visible
not production-hardened
```

## Backend

Added:

- `GET /viza/equity/runtime-wedge/status`
- `POST /viza/equity/runtime-wedge/preview`
- `viza/equity/preview.py`

The endpoint uses `run_sec_quality_value_wedge()` from the existing runtime wedge. It does not duplicate the SEC/FMP/FRED logic. Mock transports are used unless `use_live_connectors=true`, and live mode is blocked unless `VIZA_EQUITY_LIVE_INTEGRATION_TESTS=true`.

Flags default off:

- `VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED=false`
- `VIZA_EQUITY_SEC_WEDGE_ENABLED=false`
- `VIZA_EQUITY_FMP_ENABLED=false`
- `VIZA_EQUITY_FRED_ENABLED=false`
- `VIZA_EQUITY_LIVE_INTEGRATION_TESTS=false`

## Desktop UI

Added `EquityRuntimePreviewPanel` to the existing result sidebar in `apps/viza-desktop/src/App.tsx`. The panel stays hidden unless the sidecar status endpoint reports the runtime and SEC wedge flags enabled.

The panel renders:

- target identity and alias-only ticker policy
- profile compatibility pass/warn/block
- SEC evidence refs and PIT timestamps
- SEC-derived fundamental attributes
- optional FMP rights status
- optional FRED PIT status
- equity radar preview cards
- validation report
- source-rights report
- package-redaction preview
- audit identifiers
- non-advice boundary

## Packaged Resources

Updated `apps/viza-desktop/electron-builder.yml` so rebuilt Windows packages include:

- `resources/engine/viza/equity/*`
- `resources/engine/docs/equity_module/v0.1/registries/**`
- `resources/engine/docs/equity_module/v0.1/schemas/**`
- `resources/engine/docs/equity_module/v0.1/fixtures/first_wedge_sec_quality_value/sec_fmp_fred_runtime_wedge_fixture.json`
- prior SEC/FMP/FRED wedge proof/report resources

`viza/equity/registry.py` now respects `VIZA_ENGINE_ROOT`, so packaged sidecars resolve equity resources under `resources/engine/docs/equity_module/v0.1`.

## Security

The endpoint, UI, proof, reports, and packaged smoke tests do not serialize raw `FMP_API_KEY` or `FRED_API_KEY` values. Sentinel tests and an actual `.env` value scan passed:

```text
secret_values_checked=2; scanned_files=200; secret_matches=0
```

## Verification

Proof checksum:

```text
2E50B1EC5574A24E3E0280838C08F6D4EC8A878157449F48EE4EDCFF9CD62B01
```

Primary commands:

- `python -m pytest tests\unit\test_equity_runtime_wedge_api.py -q` -> `8 passed in 3.79s`
- `python -m pytest tests\unit\test_equity_packaged_preview.py -q` -> `5 passed in 3.29s`
- `python -m pytest tests\unit tests\lookahead_audit` -> `338 passed in 126.13s`
- `npm run typecheck` in `apps/viza-desktop` -> passed
- `npm run test:desktop` in `apps/viza-desktop` -> `22 passed`
- `npm run package:win` in `apps/viza-desktop` -> passed after stopping a stale `release/win-unpacked` sidecar process that held the old `viza-engine.exe` open
- `npm run smoke:package` in `apps/viza-desktop` -> `VIZA Windows package contents smoke passed`

## Remaining Limits

- Not production-hardened.
- Mocked preview path remains the default.
- Live external API tests remain opt-in only.
- FMP production rights require legal/source-rights review.
- FRED true PIT backtesting requires ALFRED-style cutoff enforcement.
- Ticker alias resolution through a full security master remains future work.
- Valuation/margin-of-safety output remains warned or blocked when market price is unavailable.
- No personalized investment advice, order routing, or monetized marketplace behavior.

## Next Step

Persist packaged preview runs into the local project store / observation store and add replayable audit history.

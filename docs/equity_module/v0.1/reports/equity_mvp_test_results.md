# Equity MVP Test Results

Date: 2026-05-15

## Backend And Equity Tests

- Command: `python -m pytest tests\unit\test_equity_runtime_wedge.py -q`
  - Working directory: `c:\Users\gkwls\AAT`
  - Result: `12 passed in 5.78s`

- Command: `python -m pytest tests\unit\test_equity_module_loader.py tests\unit\test_equity_module_fixtures.py -q`
  - Working directory: `c:\Users\gkwls\AAT`
  - Result: `10 passed in 0.74s`

- Command: `python -m pytest tests\unit\test_equity_runtime_wedge_api.py -q`
  - Working directory: `c:\Users\gkwls\AAT`
  - Result: `8 passed in 4.13s`

- Command: `python -m pytest tests\unit\test_equity_preview_persistence.py -q`
  - Working directory: `c:\Users\gkwls\AAT`
  - Result: `8 passed in 9.56s`

- Command: `python -m pytest tests\unit\test_equity_mvp_package_export.py -q`
  - Working directory: `c:\Users\gkwls\AAT`
  - Result: `4 passed in 5.12s`

- Command: `python -m pytest tests\unit\test_equity_runtime_wedge_api.py tests\unit\test_equity_preview_persistence.py tests\unit\test_equity_mvp_package_export.py tests\unit\test_equity_packaged_preview.py -q`
  - Working directory: `c:\Users\gkwls\AAT`
  - Result: `25 passed in 19.44s`

## Full Regression

- Command: `python -m pytest tests\unit tests\lookahead_audit`
  - Working directory: `c:\Users\gkwls\AAT`
  - Result: `350 passed in 207.94s`

- Command: `node --test tests\dashboard\attribution-period-bars.test.mjs`
  - Working directory: `c:\Users\gkwls\AAT`
  - Result: `2 passed in 123.4459ms`
  - Warning: Node emitted the existing module-type warning for `dashboard/components/attribution-period-bars.ts`.

- Command: `npm run typecheck`
  - Working directory: `c:\Users\gkwls\AAT\apps\viza-desktop`
  - Result: passed

- Command: `npm run test:desktop`
  - Working directory: `c:\Users\gkwls\AAT\apps\viza-desktop`
  - Result: `23 passed in 210.9028ms`

- Command: `npx tsc --noEmit --project tsconfig.json`
  - Working directory: `c:\Users\gkwls\AAT\dashboard`
  - Result: passed

## Windows Package

- Command: `npm run package:win`
  - Working directory: `c:\Users\gkwls\AAT\apps\viza-desktop`
  - Result: passed in 98.6s
  - Warnings: unsigned Windows package without signing credentials, default Electron icon fallback, Vite chunk-size warning, Electron builder duplicate dependency references, and Node `DEP0190` warning from the build toolchain.

- Command: `npm run smoke:package`
  - Working directory: `c:\Users\gkwls\AAT\apps\viza-desktop`
  - Result: `VIZA Windows package contents smoke passed.`

## Secret Safety

Automated tests use fake sentinel FMP/FRED key values and assert those sentinels are absent from API responses and `.viza` package bytes. A final `.env` secret scan is recorded in the MVP proof.

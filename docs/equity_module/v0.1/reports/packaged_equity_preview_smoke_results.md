# Packaged Equity Preview Smoke Results

Date: 2026-05-14

## Windows Package Build

Command:

```powershell
cd apps\viza-desktop
npm run package:win
```

Result:

```text
passed
```

Notes:

- First attempt built the PyInstaller sidecar and Vite bundle, then failed because the old `release\win-unpacked\resources\engine\viza-engine.exe` was locked by a stale packaged sidecar process.
- Stopped only the stale `release\win-unpacked` sidecar process. The installed `C:\Program Files\VIZA\resources\engine\viza-engine.exe` process was left alone.
- Second attempt passed and rebuilt `release\win-unpacked` and `release\VIZA-0.1.0-win-x64.exe`.
- Warnings: unsigned local Windows package warning, missing custom icon fallback, existing Vite chunk-size warning, and existing Electron builder deprecation warning.

## Windows Package Smoke

Command:

```powershell
cd apps\viza-desktop
npm run smoke:package
```

Result:

```text
VIZA Windows package contents smoke passed.
```

Coverage:

- Packaged sidecar starts.
- `/health` passes.
- Existing packaged smoke endpoints pass.
- Existing packaged runtime job completes.
- Equity preview endpoint returns disabled/403 when flags are off.
- Equity preview endpoint is reachable when runtime/sec flags are on.
- Mocked SEC-first preview request returns target identity, evidence summary, PIT fields, rights fields, validation report, package-redaction preview, audit fields, and non-advice boundary.
- Sentinel FMP/FRED key values did not appear in preview payload or sidecar stderr.

## Secret Safety Scan

Command:

```powershell
# Reads .env values into memory and reports counts only.
```

Result:

```text
secret_values_checked=2; scanned_files=200; secret_matches=0
```

Scanned generated/source/package resource areas:

- `docs/equity_module/v0.1`
- `viza/equity`
- `viza/service.py`
- `apps/viza-desktop/src`
- `apps/viza-desktop/scripts`
- `apps/viza-desktop/electron-builder.yml`
- `apps/viza-desktop/release/win-unpacked/resources/engine/config`
- `apps/viza-desktop/release/win-unpacked/resources/engine/docs`
- `apps/viza-desktop/release/win-unpacked/resources/engine/viza/equity`

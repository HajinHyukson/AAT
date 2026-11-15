# VIZA Packaging Notes

Last updated: 2026-05-12

## Current Packaging Status

Phase 5 produces a Windows unpacked development build, and Phase 15 adds a macOS
external-distribution release path.

```text
apps/viza-desktop/release/win-unpacked/VIZA.exe
```

Build command:

```powershell
cd apps\viza-desktop
npm run package:win
```

The packaged app includes:

- the compiled React canvas,
- the Electron main/preload process,
- the VIZA Python package under `resources/engine/viza`,
- the starter attribute registry and local universe JSON files under `resources/engine/config`.

The macOS release build also includes a PyInstaller-built `viza-engine` sidecar
under `resources/engine/viza-engine`, so external Mac users do not need a source
checkout or system Python runtime.

## Runtime Model

The Phase 14 package model autostarts the local VIZA engine from the packaged `resources/engine` directory. It does not start or depend on the old AAT web dashboard.

Current development-build limitation:

- The package still uses a system Python executable, defaulting to `python`.
- Developers can override it with `VIZA_PYTHON`.
- Python must have the project runtime dependencies available, including FastAPI, Uvicorn, and Pydantic.
- The macOS external release command replaces this fallback with a bundled sidecar.

The local engine reports:

```text
GET /viza/runtime -> database_required: false
GET /viza/diagnostics -> engine/project/connector release-readiness diagnostics
```

Phase 14 does not require a remote database connection because the prototype uses local registry/universe files, deterministic prototype features, and a local SQLite project store.

## Diagnostics And Recovery

The desktop diagnostics panel surfaces:

- app version and packaged/dev mode,
- engine version and runtime mode,
- engine runtime path,
- project store path and health,
- engine log path,
- connector readiness summary,
- last persisted run status,
- backend diagnostics checks.

The Electron main process exposes a restart bridge that stops the local engine, starts a new session, refreshes the per-session token, and returns updated desktop status. Frontend engine requests clear their cached engine URL/token after restart before fetching fresh metadata.

The backend diagnostics endpoint is intentionally read-only for project-store inspection. Missing stores report `not_initialized`; corrupt or incomplete stores report `error` with a non-secret message instead of crashing the diagnostics response.

## Graph Save/Load Location

The desktop app creates and defaults graph saves to:

```text
%USERPROFILE%\Documents\VIZA Methodologies
~/Documents/VIZA Methodologies
```

Graph files remain plain `viza_graph_v0` JSON files.

## Windows Validation

Validated on Windows:

- `npm run package:win` creates `release/win-unpacked/VIZA.exe`.
- `npm run smoke:package` verifies the executable, Electron app archive, engine service, diagnostics module, registry, and local universe configs.
- The packaged executable starts the local engine on `127.0.0.1:8765`.
- The packaged engine returns `database_required=false`.
- The packaged engine should return `GET /viza/diagnostics` with app-readable engine and project-store health.
- The sample methodology returns completed radar output.
- The user-writable methodology directory is created under Documents.

## Blank Screen Check

Packaged Electron builds load `dist/index.html` through `file://`, so Vite assets must be emitted with relative paths. The desktop Vite config uses `base: "./"` for this reason.

If the unpacked `VIZA.exe` opens to a blank screen after a frontend build change, inspect `apps/viza-desktop/dist/index.html` and confirm its script and stylesheet paths start with `./assets/`, not `/assets/`.

## macOS Developer Build

macOS builds should be produced on macOS, not cross-built from Windows.

Developer build requirements:

- macOS with Apple Silicon or Intel support matching the target architecture.
- Node.js and npm.
- Python 3.12 or newer with the VIZA runtime dependencies.
- Xcode Command Line Tools.

Release distribution requirements:

- Apple Developer account.
- Developer ID Application certificate.
- Hardened runtime configuration.
- Notarization and stapling before external distribution.

Prototype macOS command once on a macOS machine:

```bash
cd apps/viza-desktop
npm install
npm run package:mac:dir
```

This developer package is for local validation and may still use the system-Python
fallback unless a sidecar is supplied.

## macOS External Release

The externally distributable macOS path is:

```bash
# From the repository root.
python3 -m pip install -e ".[release]"
cd apps/viza-desktop
npm install
npm run release:mac
```

`npm run release:mac` performs the release sequence end to end:

- refuses to run unless the host is macOS,
- requires Developer ID signing configuration,
- requires Apple notarization credentials,
- builds the React/Electron frontend,
- builds a bundled `viza-engine` sidecar with PyInstaller,
- packages DMG and ZIP artifacts for the current Mac architecture,
- verifies package contents, code signing, notarization stapling, and Gatekeeper assessment.

The default release architecture is the build host architecture. Override it with:

```bash
VIZA_MAC_ARCH=arm64 npm run release:mac
VIZA_MAC_ARCH=x64 npm run release:mac
```

Required signing configuration:

- A Developer ID Application certificate installed in Keychain, or `CSC_NAME` / `CSC_LINK`.
- App Store Connect API credentials through `APPLE_API_KEY`, `APPLE_API_KEY_ID`, and `APPLE_API_ISSUER`.

Electron Builder also supports Apple ID credentials (`APPLE_ID`,
`APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`) or a notarization keychain profile
(`APPLE_KEYCHAIN_PROFILE`), but the API key path is preferred for repeatable release
automation.

Expected outputs:

```text
apps/viza-desktop/release/VIZA-0.1.0-mac-arm64.dmg
apps/viza-desktop/release/VIZA-0.1.0-mac-arm64.zip
```

or the corresponding `x64` filenames when building on or targeting Intel.

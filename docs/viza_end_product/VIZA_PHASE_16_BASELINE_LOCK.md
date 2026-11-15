# VIZA Phase 16 Baseline Lock

Last updated: 2026-05-12
Branch: `viza-universal-file-and-modules`

## Purpose

Phase 16 freezes the Phase 0-15 behavior before the universal `.viza` container
and module migration begin. This document records the contracts that future
phases must preserve unless a migration is explicitly documented and tested.

## Verification Baseline

Baseline verification passed on 2026-05-12 after the Phase 16 compatibility
guardrails were added.

Required baseline command from the implementation plan:

```powershell
python -m pytest tests\unit tests\lookahead_audit
```

Focused Phase 16 verification:

```powershell
python -m pytest tests\unit\test_viza_compat.py tests\unit\test_viza_graph_schema.py tests\unit\test_viza_service.py
```

Additional verification:

```powershell
python -m pytest tests\unit\test_viza_project_store.py tests\unit\test_viza_runtime.py
cd apps\viza-desktop
npm run typecheck
npm run test:desktop
```

Result: passed with 182 Python unit/look-ahead tests, 5 Phase 16 compatibility
tests, TypeScript typecheck clean, and 14 desktop tests.

## Current Graph Contract

Current methodology graph schema:

```text
viza_graph_v0
```

Supported node types:

```text
universe
attribute
transform
filter
score
relationship
output_radar
```

Supported edge types:

```text
data_flow
relationship
evidence
```

## Current Attribute Registry

Current attribute registry schema:

```text
viza_attribute_registry_v1
```

Current registry version:

```text
1.1.0
```

## Current Project Store Tables

The local SQLite project store currently initializes these tables:

```text
projects
methodology_versions
run_records
saved_radar_outputs
connector_settings
user_settings
watchlists
alerts
```

Future migrations must be additive by default and must not rewrite existing
project store records in place.

## Current Package Behavior

Current package behavior to preserve:

- Windows packaging produces an unpacked development package.
- The packaged Windows development build may fall back to system Python unless a bundled engine sidecar is supplied.
- macOS external release automation exists, but signed and notarized artifacts must be produced on macOS with Apple credentials.
- The desktop app resolves a bundled engine sidecar first, then falls back to system Python for development builds.
- The existing canvas remains the first visible product surface.

## Phase 16 Lock

Phase 16 does not introduce visible product behavior changes. It only adds
compatibility policy, schema helpers, feature flags, and tests that future
container and module phases can depend on.

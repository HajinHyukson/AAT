# VIZA Compatibility Policy

Last updated: 2026-05-12

## Scope

This policy governs compatibility while VIZA moves from the current Phase 0-15
methodology graph prototype toward the universal `.viza` container and module
architecture.

## Required Compatibility Rules

- `viza_graph_v0` remains supported and loadable.
- Existing `.viza.json` methodology files remain importable.
- New `.viza` export becomes the default user-facing exchange format only after round-trip import/export tests pass.
- Existing project store records are not rewritten in place.
- Database migrations must be additive unless a breaking migration is explicitly documented, tested, and paired with a recovery path.
- Imported files must be inspected from internal metadata, not filename semantics.
- Future `.viza` containers must read `manifest.json` before loading optional sections.
- Unsupported schemas must fail closed or render as safe placeholders.
- New experimental graph schemas must remain behind feature flags until migration tests exist.

## Legacy Graph Policy

`viza_graph_v0` is both the current executable graph schema and the legacy graph
schema for the upcoming `.viza` container migration. It must continue to work
with:

- graph save/load,
- graph execution,
- project-store methodology versions,
- run manifests and reproducibility checks,
- batch/backtest flows,
- methodology export/debug JSON.

## Feature Flag Policy

Phase 16 introduces these baseline flags:

```text
VIZA_ENABLE_UNIVERSAL_CONTAINER=true
VIZA_ENABLE_MODULE_REGISTRY=true
VIZA_ENABLE_EXPERIMENTAL_GRAPH_V1=false
VIZA_ENABLE_NON_FINANCE_MODULES=false
```

The first two flags allow later phases to add infrastructure behind stable
entry points. Experimental graph migration and non-finance modules default off
until their own tests and UI safeguards exist.

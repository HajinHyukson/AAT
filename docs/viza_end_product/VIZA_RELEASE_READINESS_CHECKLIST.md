# VIZA Release Readiness Checklist

Last updated: 2026-05-12

Use this checklist before promoting a VIZA desktop build beyond a development prototype.

## Build Identity

- App version is visible in the desktop diagnostics panel.
- Engine version is visible through `GET /viza/diagnostics`.
- Diagnostics version is `viza_runtime_phase_14_release_readiness_v0` or newer.
- Attribute registry version and attribute count match the intended release catalog.
- Package smoke test confirms the Electron app, engine service, diagnostics module, registry, and universe files are present.

## Local Engine

- The desktop app starts the local engine on loopback only.
- Electron passes a per-session `VIZA_ENGINE_TOKEN` and frontend requests include it.
- The diagnostics panel does not display the token value.
- Engine log path is visible in the diagnostics panel.
- Restarting the local engine from the diagnostics panel returns the app to `online`.
- App startup still opens the window when the engine cannot start, with the launch error visible.

## Project Store

- Default project store path is visible in diagnostics.
- `project_store.status` is `ok` for a normal install.
- Missing stores report `not_initialized` rather than crashing diagnostics.
- Corrupt stores report `error` and include a non-secret error message.
- Last run status appears after executing a methodology with project persistence.
- Upgrade tests preserve existing projects, methodology versions, run records, radars, watchlists, and alerts.

## Connectors And Credentials

- Connector statuses are visible in diagnostics and the connector panel.
- Required credentials are reported as configured/not configured without exposing secrets.
- User-owned credential material is not written into exported methodologies, manifests, logs, or diagnostics.
- Connector failures produce warnings or unavailable statuses instead of crashing graph execution.
- Source license policy, cache policy, and export policy remain visible through connector metadata.

## Packaging

- Windows unpacked package smoke passes with `npm run smoke:package`.
- Windows installer build signs the app before beta distribution.
- macOS package is built on macOS with `npm run release:mac`, signed with Developer ID, notarized, stapled, and smoke-validated before distribution.
- Packaged runtime does not require a source repository checkout.
- macOS production release uses the bundled `viza-engine` sidecar rather than system Python.
- Uninstall leaves user methodology/project data in user-owned directories unless a separate data removal flow is explicitly selected.

## Smoke Scenario

- Launch VIZA from the packaged app.
- Confirm diagnostics show app version, engine version, runtime path, project path, log path, connector summary, and last run status.
- Run the sample methodology.
- Save a methodology version to the local project store.
- Save a `.viza.json` methodology file.
- Close and reopen the app, then load the saved methodology file.
- Restart the local engine from diagnostics and refresh metadata.
- Export CSV, JSON, manifest, and methodology payloads, confirming restricted fields are redacted.

## Decisions Output (Phases A–D, `docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md`)

- `DecisionFrame` schema is at `viza.decision.v1`; mode is `sandbox_replay` or `live` (no others accepted by the SQLite CHECK).
- `compile_decisions` is deterministic and PIT-filtered; `tests/lookahead_audit/test_decisions_pit.py` is green and the schema-invariant `replay_decisions_from_store` raises (rather than silently drops) on a corrupted `pit_state` row.
- Cooldown / dead-band enforced via `CooldownPolicy` on `DecisionRule`. Backtesting evaluator at `viza/decisions_backtesting.py` is sandbox-only by construction.
- Package-redaction supports `white_box` / `output_only` / `marketplace_draft` for decisions; `output_only` redacts `rule_text` + `trigger_observation_ids` while retaining `action_template` + `entity_id`; `marketplace_draft` strips per-decision content entirely; any decision with `source_rights_state.export_allowed=False` blocks the entire export in all three modes.
- Live mode is gated by `VIZA_LIVE_MODE_ENABLED=true` env flag PLUS per-profile `LiveModeOptIn` whose `accepted_disclosure_version` matches the engine's current `LIVE_MODE_DISCLOSURE_VERSION` PLUS per-rule `effective_from <= cutoff_timestamp`. Default-off. Distinct exception classes surface as HTTP 422 with structured `{code, message}` detail.
- Desktop UI: `DecisionsPanel` wired into `App.tsx`; sandbox/live mode selector; live-mode opt-in dialog renders disclosure version + text and records consent; engine-token-gated client surfaces `VizaLiveModeError` for deterministic routing.
- Validation ledger: every decision-bearing run emits a `VizaValidationRecord` with `result_checksum`, `evidence_checksum`, `PIT_summary`, and per-decision `outputs[]` references.
- Structural-point audit is documented at `docs/VIZA_DECISIONS_STRUCTURAL_AUDIT.md`. Run before every release.
- Legal-engagement brief: `docs/VIZA_DECISIONS_LEGAL_BRIEF.md`. Counsel memo (when received) is filed at `docs/VIZA_LEGAL_REVIEW_MEMO_2026.md`.

## Known Gaps

- Windows signing is still not automated in this repository.
- macOS release automation must be executed on macOS with Apple credentials; it cannot be completed from Windows.
- Marketing site / public help docs are not in this repo. When they land, run the same forbidden-language regex sweep enforced by the desktop tests (`/\bBuy\b/`, `/\bSell\b/`, `/\bAct\s+now\b/i`, `/\bTrade\w*\b/`, `/\bRecommend\w*\b/i`, `/\btoday\b/i`, `/\bcurrent\s+(price|reading|market)/i`) against the site source.
- The packaged Windows development build still falls back to system Python unless a bundled engine executable is provided.
- Secure OS credential storage is represented by metadata and environment-backed checks; native credential vault integration remains future work.

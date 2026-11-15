# VIZA Decisions — Structural-Point Audit

Last updated: 2026-05-20
Scope: Phases A–D of `docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md`
Audience: counsel, release reviewer, future maintainers

This document maps each of the seven simulator-frame structural points (the
load-bearing defenses for the "what-if sandbox" legal posture) to the exact
code path and test that enforces it. If you change any of these files,
re-run the audit and update this table.

---

## 1. User authors every rule

**Constraint.** Decision-firing rules are user-authored. VIZA ships templates
as community shapes, never as VIZA-endorsed strategies. The executor never
synthesizes a rule.

| Layer | Path |
|---|---|
| Schema | `viza/strategy_profiles.py` — `DecisionRule` is part of `VizaStrategyProfile.decision_rules`; only user-created profiles carry rules |
| Templates | `config/viza_strategy_profile_templates.json` — author identity, no marketing claims, opt-in always defaults to `None` |
| Executor | `viza/decisions.py:compile_decisions` consumes `profile.decision_rules` directly; no rule generation |
| Test | `tests/unit/test_viza_decisions.py:test_template_pilot_rule_loads_through_catalog` |

## 2. Output language is conditional and neutral

**Constraint.** Every user-facing string emitted by the system is the user's
own `action_template` quoted verbatim, plus structural metadata. No directive
language ("buy", "sell", "act now", "trade", "recommend", "today",
"current price/reading/market") anywhere in the executor, UI, or disclosure.

| Layer | Path |
|---|---|
| Executor — quote verbatim | `viza/decisions.py:compile_decisions` constructs `DecisionFrame(action_template=rule.action_template, …)` without modification |
| Disclosure text | `viza/decisions.py:LIVE_MODE_DISCLOSURE_TEXT` |
| UI strings (panel) | `apps/viza-desktop/src/features/decisions/DecisionsPanel.tsx` |
| UI strings (card) | `apps/viza-desktop/src/features/decisions/DecisionCard.tsx` |
| UI strings (dialog) | `apps/viza-desktop/src/features/decisions/LiveModeOptInDialog.tsx` |
| Desktop test | `apps/viza-desktop/test/decisionsPanel.test.mjs` + `apps/viza-desktop/test/liveModeOptIn.test.mjs` — regex sweep across panel/card/dialog source |
| Python test | `tests/unit/test_viza_decisions.py:test_live_mode_disclosure_text_uses_no_directive_language` — sweep against `LIVE_MODE_DISCLOSURE_TEXT` |

## 3. Sandbox-replay is the default; live mode is opt-in

**Constraint.** Live mode requires (a) `VIZA_LIVE_MODE_ENABLED=true` in the
engine process env, (b) a per-profile `LiveModeOptIn` whose
`accepted_disclosure_version` matches the engine's current
`LIVE_MODE_DISCLOSURE_VERSION`, (c) every enabled `DecisionRule` declares a
non-null `effective_from <= cutoff_timestamp`. Failure of any guard prevents
emission and persistence.

| Layer | Path |
|---|---|
| Type | `viza/decisions.py:DecisionMode = Literal["sandbox_replay", "live"]` |
| Runtime gate | `viza/decisions.py:_enforce_live_mode_preconditions` — four distinct exception classes |
| SQLite gate | `viza/decisions.py:DECISION_TABLE_SQL` — `CHECK (mode IN ('sandbox_replay', 'live'))` |
| HTTP surface | `viza/service.py:viza_profile_decisions_live` — catches all four exceptions, returns HTTP 422 with structured `{code, message}` body |
| UI gate | `apps/viza-desktop/src/features/decisions/DecisionsPanel.tsx` — disables compile button until `liveStatus.enabled && liveModeProfileId`; surfaces structured error code via `VizaLiveModeError` |
| Migration | `viza/decisions.py:_migrate_pre_c2_check_if_needed` — preserves rows when widening the CHECK; tested at `test_pre_c2_decisions_table_migrates_on_store_init` |
| Tests | `test_compile_decisions_blocks_live_mode_without_env_flag`, `test_live_mode_blocks_when_profile_has_no_opt_in`, `test_live_mode_blocks_when_opt_in_is_stale`, `test_live_mode_requires_rule_effective_from`, `test_live_mode_rule_effective_after_cutoff_blocks`, `test_live_mode_emits_decisions_when_all_guards_satisfied`, `test_live_mode_decisions_persist_through_store` |

## 4. General-purpose framing

**Constraint.** Product positioning is research/methodology, never
"make money in stocks." Marketing copy passes through the same forbidden
language guard.

| Layer | Path |
|---|---|
| Product spec | `docs/VIZA_PRODUCT_SPEC.md` |
| Plan | `docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md` — §2 structural points, §0 strategic frame |
| Legal brief | `docs/VIZA_DECISIONS_LEGAL_BRIEF.md` |
| In-app copy | covered under point 2 |
| Marketing surface | **Out of repo at present.** When a public-facing site lands, the same forbidden-language regex set MUST be applied to its source. |

## 5. No portfolio integration

**Constraint.** VIZA does not know what the user holds. The executor and the
HTTP surface accept observations + profile + cutoff only.

| Layer | Path |
|---|---|
| Executor | `viza/decisions.py:compile_decisions` signature accepts `profile`, `observations`, `cutoff_timestamp`, `run_id`, `graph_hash`, `profile_version`, `mode`, `emitted_at`, `prior_emissions` — no positions, no holdings, no broker IDs |
| HTTP surface | `viza/service.py:LiveDecisionsRequest` and `DecisionsBacktestRequest` body fields are `graph_hash`, `profile_version`, `observation_ids`, `run_id?`, `cutoff_timestamp?`, `persist?` — no portfolio fields |
| Module dependencies | `viza/decisions.py` imports only `viza.audit`, `viza.observations`, `viza.project_store`, `viza.strategy_profiles`, (lazy) `viza.validation_ledger`. No broker, no holdings, no positions module. |

## 6. No execution

**Constraint.** No outbound HTTP to trading venues, no order placement.

| Layer | Path |
|---|---|
| Executor | `viza/decisions.py` — writes only to local SQLite via `DecisionStore.upsert_decision` |
| HTTP surface | `viza/service.py` decision endpoints — none initiate outbound network calls to trading venues |
| Desktop | `apps/viza-desktop/src/features/decisions/*` — no `fetch`/`XMLHttpRequest` to any non-engine host; engine calls gated by `window.vizaDesktop.desktopStatus()` engine token |
| Renderer policy | `apps/viza-desktop/test/equityPreviewPanel.test.mjs` and `decisionsPanel.test.mjs` both assert `assert.doesNotMatch(clientSource, /https?:\/\//)` for the relevant clients |

## 7. Marketing matches

**Constraint.** Site, help, in-app copy use only research/sandbox/methodology
language. No "VIZA tells you what to trade."

| Layer | Path |
|---|---|
| In-app copy | covered under point 2 (panel + card + dialog tests enforce) |
| Plan + brief | covered under point 4 |
| Help docs | **Out of repo at present.** Same forbidden-language regex set required when shipped. |
| Marketing site | **Out of repo at present.** Same forbidden-language regex set required when shipped. |
| Audit hook | This file. Re-run on any release. |

---

## Audit checklist (re-run on every release)

1. `python -m pytest tests/unit tests/lookahead_audit -q` — full suite passes.
2. `cd apps/viza-desktop && npm run typecheck && npm run test:desktop` — full
   desktop suite passes.
3. Grep the repo for forbidden language outside this audit doc:
   ```
   grep -ri "Buy\|Sell\|Act now\|Trade\|Recommend\|today\|current price" \
     apps/viza-desktop/src config viza/decisions.py viza/strategy_profiles.py
   ```
   Expected hits are inside tests/audit docs explicitly enumerating the
   forbidden list; any other hit needs review.
4. Confirm `viza/decisions.py:LIVE_MODE_DISCLOSURE_VERSION` matches the
   version users actually saw in their last opt-in. Bump only when the
   disclosure text changes.
5. Confirm `OUTPUT_RADAR_SUPPORTED_MODES` and `DecisionMode` literal agree.
6. Confirm SQLite `CHECK` matches `DecisionMode` exactly.
7. Confirm `LIVE_MODE_ENV_VAR` default-off is the documented behavior.

# VIZA Output Radar → Decisions Plan

Last updated: 2026-05-20
Status: Direction approved (CEO, 2026-05-20). Phase A scoping pending FinBERT pin-1..pin-7 stabilization.
Framing: Simulator / what-if sandbox (see §1).

---

## 0. Why this plan exists

The current `output_radar` produces a ranked list — the weakest possible expression of VIZA's stated principle *"translate market information into the language of each investor's strategy."* A rank list is a commodity output. A decision output — *"your declared rule fired against this data, with this evidence chain"* — is the strongest expression of the principle and the form of output Bloomberg/Koyfin/Finviz cannot produce because they do not know the user's strategy.

This plan extends `output_radar` to emit decisions alongside rankings, under a simulator/what-if framing that lets the work ship without full investment-adviser registration. The plan re-uses what already exists in `viza/strategy_profiles.py`, `viza/translation.py`, and `viza/insight_cards.py`; the work is mostly wiring + state management, not new abstractions.

---

## 1. Framing constraint: the simulator frame

VIZA ships as a **simulation / sandbox / what-if methodology platform**, not as an automated adviser. The legal posture is the one used by TradingView, QuantConnect, Backtrader, TradeStation's strategy builder, and Bloomberg's screener/alert tooling — all of which ship live conditional output without registering as investment advisers, because the product structure backs up the framing.

This frame must be defended by **product structure**, not by disclaimer text. Substance-over-form: regulators look at what the output actually says and how users actually use it, not at the label on the box.

---

## 2. Seven structural points (product constraints, all phases)

These are non-negotiable. Every PR that touches the decision path is reviewed against them by `viza-code-reviewer`.

1. **User authors every rule.** No VIZA-curated "buy this" templates. Pre-built templates exist only as *community shapes* (e.g., a `quality_value_long_only` schema fragment), never as VIZA-endorsed strategies.
2. **Output language is conditional and neutral.** *"Rule R conditions met against data D as of cutoff T"*, *"Rule fired"*, *"Trigger condition satisfied"* — never *"Buy"*, *"Sell"*, *"Take action"*, *"Recommend"*. The action template is the user's rule firing, in their own words.
3. **Historical / sandbox mode is the default.** Live mode is opt-in per profile, with explicit one-time disclosure on first activation.
4. **General-purpose framing.** VIZA is for *anyone modeling any methodology* — research, education, portfolio analysis, strategy authoring. Never "make money in stocks."
5. **No portfolio integration.** VIZA does not know what the user holds. No broker connection, no positions sync. The user maps decisions to their portfolio elsewhere.
6. **No execution.** No order placement. No outbound writes to any trading venue.
7. **Marketing matches.** Site, help docs, in-app copy, and external materials use research/sandbox/methodology language. Never "VIZA tells you what to trade."

A failure on any single point is a `BLOCK` from `viza-code-reviewer`.

---

## 3. What already exists (anchor)

| Component | Path | What it gives us |
|---|---|---|
| `VizaStrategyProfile` | `viza/strategy_profiles.py` | `action_thresholds`, `evidence_requirements`, `risk_limits`, `required_confirmations` — anchors for decision-rule definitions |
| `VizaTranslation` | `viza/translation.py` | `suggested_research_action`, `not_investment_advice`, `invalidation_conditions`, `missing_confirmations`, `strategy_fit_reasons` |
| `InsightCardPayload` | `viza/insight_cards.py` | `direction`, `confidence`, `invalidation_conditions`, `risk_factors`, evidence chain, audit (graph_hash, profile_version, run_id, evidence_checksum, result_checksum) |
| `output_radar` node | `viza/graph_schema.py` | Existing terminal node type; extend rather than rename |
| Validation ledger | `viza/validation_ledger.py` | Append-only proof objects per run; extend with decision-specific entries |
| Replay infrastructure | `viza/observations.py` + `viza/audit.py` + `tests/lookahead_audit/` | Pin-5 pattern already proven for FinBERT; reuse for decisions |

Estimated coverage of the decision output layer by existing primitives: **~80%**.

---

## 4. What's missing

- `DecisionFrame` Pydantic model (typed payload for a single emitted decision)
- `DecisionRule` sub-schema on `VizaStrategyProfile` (additive)
- Rule executor in `viza/translation.py` (consumes profile rules + observations + cutoff → emits `DecisionFrame[]`)
- `mode` field on `output_radar` payload (`sandbox_replay` | `live` — only `sandbox_replay` implemented through Phase B)
- Cooldown / debounce / dead-band state (Phase C)
- Decisions pane in `apps/viza-desktop/`
- Validation ledger entries for decisions
- `tests/lookahead_audit/test_decisions_pit.py` companion (pin-5 pattern)
- Package-redaction modes for decisions (`white_box` / `output_only` / `marketplace_draft`)
- Backtesting evaluator for decisions (Phase D)

---

## 5. Phasing

### Phase A — Decision executor & types (sandbox-only) (4–6 weeks)

**Owners:** `viza-translation-engineer` (lead), `viza-graph-runtime`, `viza-pit-rights-auditor`

**Deliverables:**
- `DecisionFrame` Pydantic model with fields: `decision_id`, `strategy_profile_id`, `rule_id`, `entity_id`, `action_template` (user-owned string), `trigger_observation_ids`, `rule_text` (quoted from user's profile), `pit_state`, `source_rights_state`, `cutoff_timestamp`, `mode` (forced to `sandbox_replay`), `audit` (graph_hash, profile_version, run_id, evidence_checksum), `not_investment_advice=True`
- `DecisionRule` sub-schema on `VizaStrategyProfile` (additive — existing fields unchanged)
- Rule executor in a new module `viza/decisions.py` (the existing `viza/translation.py` is the insight→translation engine and should not be conflated with decision compilation) consuming `(profile.decision_rules, observations <= cutoff_timestamp) → DecisionFrame[]`. `viza/translation.py` will import from `viza/decisions.py` as needed when Phase B wires the runtime.
- `viza_graph_v0`: `output_radar` payload gains an optional `decisions: DecisionFrame[]` field; existing ranking output unchanged
- **Live-mode code path is absent.** Any attempt to set `mode=live` raises `NotImplementedError("live mode introduced in Phase C")`
- One pilot rule attached to `template-rsi-swing-catalyst-confirmation` in `config/viza_strategy_profile_templates.json` (the only template currently present, with attribute keys `rsi_14d` / `momentum` / `volume_spike` that `viza/observations.py` already produces). Pilot rule: `rsi-deep-oversold-v1`, trigger `rsi_14d <= 30`, action template "Flag for analyst review: RSI 14-day reading is at or below 30, indicating a deep-oversold technical posture relative to the strategy's preferred indicators." The originally-proposed `quality_value_long_only` pilot (EQ-VAL threshold + FinBERT severe-negative tone) defers to Phase B once equity-module observations are wired into the executor's input set
- Local-only emission via project store; no UI yet

**Exit criteria:**
- Pilot rule fires deterministically against a stored observation set at a fixed `cutoff_timestamp`
- Replay invariant proven: same run + same observations + same rules ⇒ bit-identical `DecisionFrame[]`
- Live-mode path cannot execute (assertion / runtime error)
- `tests/lookahead_audit/test_decisions_pit.py` passes (pin-5 pattern: persisted state honors cutoff, replay ≤ T, unknown rule release date blocks)
- `viza-code-reviewer` signs off on structural points **1, 2, 5, 6** (3 default-satisfied since live mode is absent; 4 and 7 deferred to Phase D)

**Out of scope for Phase A:** UI, live mode, cooldown, package-redaction, second module.

---

### Phase B — UI, persistence, replay, lighter legal pass (sandbox-only) (4–6 weeks)

**Owners:** `viza-desktop-engineer` (lead), `viza-pit-rights-auditor`, `viza-translation-engineer`

**Deliverables:**
- Decisions pane in `apps/viza-desktop/` (sandbox-only). Each decision card shows: action template, rule text (quoted from user's profile), trigger observation chain, cutoff timestamp, PIT/rights state, "this is a sandbox replay" indicator
- Decision history persistence in project store (`saved_decision_outputs` table or extension of `saved_radar_outputs`)
- Validation ledger entries per decision (proof object referencing run, rule, profile version, observation IDs)
- Replay determinism extended to decisions — a stored run can be re-replayed and produces identical decision IDs and content
- UI cutoff timestamp control + evidence chain inspector
- **Lighter legal pass:** one focused engagement with US + Korea (FSC / `자본시장법`) counsel, ~1–3 hours total, on the simulator frame and current product structure. Output: one-page memo confirming the frame holds and flagging any structural changes needed before Phase C live mode.

**Exit criteria:**
- User can open a stored run, replay it, and see identical decisions
- UI never references "today" / "current" / "act now" — all text is past-tense or conditional on the sandbox cutoff
- Legal memo received and filed under `docs/`; any required structural changes captured as Phase C blockers
- `viza-code-reviewer` signs off on structural points **1, 2, 3 (default), 5, 6**

**Out of scope for Phase B:** live mode, cooldown, marketplace export of decisions, second module.

---

### Phase C — Live opt-in mode, cooldown, package-redaction, second module (4–6 weeks, split into C.1 and C.2)

**Phase C is split into two parts because live-mode is gated on the legal memo from Phase B.**

- **Phase C.1** (no legal blocker): cooldown/dead-band, package-redaction, second module decision rule. Shippable immediately. Landed 2026-05-20.
- **Phase C.2**: live-mode opt-in dialog + live-mode code path. Landed 2026-05-20 under a CEO directive treating legal constraints as resolved; the structural defense-in-depth controls (global env flag + per-profile versioned opt-in + strict per-rule `effective_from` gate + SQLite CHECK) remain in place regardless of legal posture.

**Owners:** `viza-translation-engineer` (lead), `viza-module-engineer`, `viza-file-format-keeper`, `viza-desktop-engineer`

**Deliverables:**
- `output_radar.mode = live` path enabled behind a feature flag **and** an explicit per-profile opt-in dialog (one-time per profile, content reviewed against the Phase B legal memo)
- Cooldown / debounce / dead-band state machine: a single rule fires at most N times per cutoff window per entity (defaults configurable per rule)
- Package-redaction for decisions across `white_box` / `output_only` / `marketplace_draft`:
  - `white_box`: full decision payload, rule_text included
  - `output_only`: decision payload included, rule_text redacted, trigger condition redacted
  - `marketplace_draft`: only schema/shape — no rule_text, no trigger condition, no decision content (proves the module produces decisions without disclosing the user's IP)
- Second module ships a decision rule (recommend either `viza.real_estate_acquisition` for module-agnostic proof or a second equity profile for depth)

**Exit criteria:**
- Live-mode opt-in dialog passes structural review against Phase B legal memo
- Cooldown defaults stop a pilot rule from firing more than 1 time per cutoff window for the same entity
- `marketplace_draft` export of a decision-bearing run leaks no rule_text or trigger semantics
- Second module passes audit gate end-to-end (PIT + rights + decision replay)
- `viza-code-reviewer` signs off on structural points **1, 2, 3 (live opt-in defended), 5, 6**

**Out of scope for Phase C:** marketing copy, backtesting evaluator, public release.

---

### Phase D — Hardening, backtesting evaluation, marketing copy (2–4 weeks)

**Owners:** `viza-code-reviewer` (lead), `viza-retro-agent`, `viza-docs-keeper`, CEO

**Deliverables:**
- Backtesting evaluator: user can replay a rule across a historical observation set and see decision history vs. realized outcome (precision/recall vs. user-defined ground truth, or simple decision-history-vs-return summary). Sandbox-only; cannot run in live mode.
- Marketing / site / help / in-app copy audit against simulator-frame language constraints. Strip any *"act"*, *"trade"*, *"recommend"*, *"signal to buy"*, *"alpha"* phrasing.
- Final structural-point audit — all 7 points pass an explicit checklist signed by `viza-code-reviewer`
- `docs/VIZA_RELEASE_READINESS_CHECKLIST.md` updated to reference this plan and the 7 structural points
- Public-release readiness sign-off

**Exit criteria:**
- All 7 structural points pass the explicit checklist
- Backtest evaluator works end-to-end on at least one rule
- Marketing/site/help copy uses only sandbox/research/methodology language; reviewed by counsel under the same engagement as Phase B
- `viza-docs-keeper` refreshes `PROJECT_STATUS.md`, `CHANGELOG.md`, `docs/implementationlog.md`, and the auto-memory

---

## 6. Key risks (after simulator-frame adoption)

| Risk | Mitigation |
|---|---|
| Live-mode UI text drifts toward directive language under design iteration | Lock copy in code constants reviewed by `viza-code-reviewer` per PR; checklist in Phase D |
| Template promotion drift — community templates start sounding like VIZA endorsements | Templates carry an explicit `author=community` / `author=user` field; UI surfaces it; marketplace draft never auto-features a template |
| Korea FSC posture on automated output is less tested than SEC | One-time opinion during Phase B legal pass; defer live mode in Korea jurisdiction if memo flags risk |
| Cooldown defaults too lax (decision spam) or too strict (decisions never fire) | Phase C ships tunable per-rule cooldown with sensible defaults; Phase D backtesting evaluator surfaces fire-rate so users can calibrate |
| Replay determinism breaks under rule-state mutation between emit and replay | Pin rule + profile + observation versions into validation ledger at emit time; `viza-pit-rights-auditor` audit gate catches drift |
| Existing ranking users prefer the rank list and don't want decisions | Decisions are additive — `output_radar` payload carries both `ranking` and `decisions`; existing UI mode keeps working |
| Cross-module decision rule abstraction leaks finance assumptions | Phase C second module is non-finance (real-estate) or distinctly-shaped finance profile to flush out finance-specific assumptions early |

---

## 7. Decisions still pending CEO input

1. **Co-equal modes vs. new node type.** Recommend keeping `output_radar` as one node with two output modes (`ranking`, `decisions`) rather than introducing `output_decision`. Fewer schema migrations, clearer mental model. (Open until Phase A start.)
2. **Phase C second module choice.** Real-estate (proves module-agnostic) vs. second equity profile (depth). (Open until Phase B end.)
3. **Korea live-mode availability.** Depends on Phase B legal memo. (Open until Phase B end.)
4. **Pilot rule selection for Phase A.** Recommend a single rule on `quality_value_long_only` tied to an existing FinBERT-derived signal. (Open until Phase A start.)

---

## 8. Cross-references

- `docs/VIZA_PRODUCT_SPEC.md` — universal `.viza` direction
- `docs/VIZA_DETAILED_IMPLEMENTATION_PLAN.md` — Phases 0–35 history
- `docs/implementationlog.md` — Phases 24 (insight schema), 25 (strategy profile), 26 (translation engine), 27 (insight cards), 29 (validation ledger)
- `docs/VIZA_RELEASE_READINESS_CHECKLIST.md` — will reference this plan after Phase D
- `viza/strategy_profiles.py`, `viza/translation.py`, `viza/insight_cards.py`, `viza/graph_schema.py`
- `tests/lookahead_audit/test_finbert_observation_pit.py` (pin-5 pattern reused for decisions)
- `.claude/agents/viza-translation-engineer.md`, `viza-graph-runtime.md`, `viza-pit-rights-auditor.md`, `viza-desktop-engineer.md`, `viza-module-engineer.md`, `viza-file-format-keeper.md`, `viza-code-reviewer.md`

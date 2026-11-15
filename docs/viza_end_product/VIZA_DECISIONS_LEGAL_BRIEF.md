# VIZA Decisions Output — Legal Pass Engagement Brief

Last updated: 2026-05-20
Audience: outside counsel — US securities + Korea FSC (`자본시장법`) review
Purpose: focused review on the **simulator-frame** legal posture for VIZA's decisions output (1–3 hours of counsel time)
Reference: `docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md` (engineering plan; this brief is the legal-side companion)

---

## 1. What VIZA is, in one paragraph

VIZA is a local-first desktop research-methodology platform. A user designs a methodology as a node graph (universe → attribute → transform → filter → score → relationship → output_radar) and runs it against observational data they have already ingested into their local project store. Until now, the output was a ranked list of securities. We are adding a second output mode: **decisions**, defined as deterministic firings of *user-authored rules* against PIT-filtered observations. We do not connect to a brokerage, do not place orders, do not know what the user holds, and do not maintain a curated catalog of strategies that we market as recommendations.

## 2. The framing we want to defend

We are shipping decisions as a **simulator / what-if sandbox**, modeled on TradingView, QuantConnect, Backtrader, and Bloomberg's screener/alerts — none of which are registered as investment advisers. The user authors the rule, VIZA fires it, the output is research-process language. This is automation of the user's own declared logic, not generation of new investment advice.

## 3. The seven structural points (and where each is enforced in code)

| # | Constraint | Enforcement |
|---|---|---|
| 1 | User authors every rule. No VIZA-curated "buy this" templates. | `viza/strategy_profiles.py:DecisionRule` carries `rule_id`, `label`, `trigger`, `action_template`, `effective_from`. The sole shipped template (`config/viza_strategy_profile_templates.json::rsi-deep-oversold-v1`) is a community-shape example, not a VIZA-endorsed strategy. The pilot rule's `action_template` text was authored by the engineering team as an example and is replaceable by the end user. |
| 2 | Output language is conditional and neutral. | `viza/decisions.py:compile_decisions` quotes `rule.action_template` verbatim; no augmentation. The pilot rule reads: *"Flag for analyst review: RSI 14-day reading is at or below 30, indicating a deep-oversold technical posture relative to the strategy's preferred indicators."* UI source (`apps/viza-desktop/src/features/decisions/DecisionCard.tsx`) and the panel (`DecisionsPanel.tsx`) carry no directive language ("buy", "sell", "act", "trade", "recommend", "today", "current price/reading/market"). A desktop test (`apps/viza-desktop/test/decisionsPanel.test.mjs`) asserts the absence of those strings on every test run. |
| 3 | Historical / sandbox is the default. Live mode is opt-in. | `viza/decisions.py:DecisionMode = Literal["sandbox_replay"]`. `compile_decisions` raises `NotImplementedError` on `mode="live"`. `viza/graph_schema.py:output_radar_mode` raises `NotImplementedError` on the reserved `live` value. The SQLite `decisions` table carries `CHECK (mode = 'sandbox_replay')`. Three independent layers must be modified before live mode can execute. |
| 4 | General-purpose framing. Not "make money in stocks." | (Marketing copy is the binding surface — deferred to Phase D. The codebase positions the product as research/methodology throughout, including `docs/VIZA_PRODUCT_SPEC.md`.) |
| 5 | No portfolio integration. | `viza/decisions.py:compile_decisions` operates on observations + a profile; it has no knowledge of holdings. No imports of broker/portfolio modules. No portfolio-shaped data structures. |
| 6 | No execution. | `viza/decisions.py` emits frames and writes to a local SQLite. No outbound HTTP to any trading venue. No order placement. The desktop UI has no "place trade" affordance and no broker linkage. |
| 7 | Marketing matches. | Site, help, in-app copy under review in Phase D. The decision UI's own copy (the panel help text and card disclaimer) reads: *"Each decision below is a deterministic firing of a user-authored rule against observations available at the run's cutoff timestamp. This view replays a stored run from observations already persisted in the project store."* and *"Research-process flag from a user-authored rule. Not investment advice."* |

## 4. What we are explicitly NOT doing

- We do not maintain a curated catalog of strategies that VIZA promotes as profitable.
- We do not provide personalized output based on the user's holdings.
- We do not connect to brokerages.
- We do not place orders.
- We do not maintain a "decisions feed" or push-notification system for live signals.
- We do not provide LLM-generated recommendations. The decision executor is deterministic.
- We do not bypass the user's own rule authorship — every decision is the user's rule firing.

## 5. The exact user-visible strings in this release

### Pilot rule (`config/viza_strategy_profile_templates.json`, sole template)
- `rule_id`: `rsi-deep-oversold-v1`
- `label`: `Deep oversold reading (RSI 14d ≤ 30)`
- `action_template`: *"Flag for analyst review: RSI 14-day reading is at or below 30, indicating a deep-oversold technical posture relative to the strategy's preferred indicators."*

### Decision panel header copy
- Panel title: *"Decisions (sandbox replay)"*
- Badge: *"Sandbox replay only"*
- Help text: *"Each decision below is a deterministic firing of a user-authored rule against observations available at the run's cutoff timestamp. This view replays a stored run from observations already persisted in the project store."*
- Cutoff control: *"Replay cutoff (ISO timestamp)"*, *"Replay at cutoff"*, *"Reload full history"*

### Per-decision card copy
- Badge: *"Sandbox replay"*
- Disclaimer line: *"Research-process flag from a user-authored rule. Not investment advice."*
- Metadata: *"Entity"*, *"Cutoff (replay reference)"*, *"Latest triggering observation"*, *"Look-ahead risk"*, *"Source rights"*
- Evidence inspector: *"Show evidence chain"* / *"Hide evidence chain"*

## 6. Specific questions for counsel

### US (SEC / state)

1. **Classification.** Under the Investment Advisers Act of 1940 and SEC 2017 Robo-Adviser guidance, does our decisions output (as described in §1–5 above) constitute regulated investment advice? Where is the closest precedent (e.g., TradingView, QuantConnect, Backtrader)?
2. **Publisher's exemption.** Does the *Lowe v. SEC* impersonal-publishing exemption apply to a per-user-per-rule firing where the rules are authored by the user, not by VIZA? If yes, what structural features must we preserve to keep the exemption?
3. **Template risk.** Our pilot rule ships in a community-shape template authored by our engineering team as an example. Does that constitute VIZA "endorsing" a strategy and thereby losing the user-authorship defense? What structural mitigations preserve the defense (e.g., labeling, opt-in, removal of pre-fills)?
4. **Marketing constraint list.** What language must we avoid in marketing, help docs, and in-app copy to maintain the simulator/non-advice posture? Provide a do/don't list.
5. **State-level overlay.** Are there state-level adviser regulations (e.g., NY, CA) that differ materially from the federal framework and would catch this product despite federal exemption?

### Korea (FSC / `자본시장법`)

6. **Classification under `자본시장법`.** Is automated rule-firing on user-authored rules classified as 투자자문업 (investment advisory business) under Korean law? Where is the closest precedent?
7. **Live mode jurisdiction.** If Phase C live mode (Q3 2026 target) would require Korean adviser registration, can we geofence Korean users to sandbox-only and ship a sandbox-only product in Korea under a different classification?
8. **Marketing in Korean.** Are there Korean-language marketing constraints (e.g., 투자권유, 추천, 매수/매도) we must avoid?

### Both jurisdictions

9. **What structural changes would you require before launch?** Specifically, are any of the seven structural points (§3) inadequate as currently implemented? Where would you require additional defense-in-depth?
10. **Liability beyond regulation.** Civil-liability exposure from users acting on a decision and losing money — what disclaimer, ToS, and onboarding-flow language is needed to limit this?

## 7. Expected deliverable from counsel

A one-page memo confirming whether the simulator frame holds and listing any structural changes required before:
- Phase B GA (sandbox-only desktop, including this brief's UI surface)
- Phase C (Q3 2026 target: live-mode opt-in introduction)

The memo will be filed at `docs/VIZA_LEGAL_REVIEW_MEMO_2026.md` and any required structural changes become Phase C blockers (see `docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md` §5 Phase C exit criteria).

## 8. Repository entry points for counsel review

If counsel wants to inspect the code directly:

- `viza/decisions.py` — the executor and store
- `viza/strategy_profiles.py:DecisionRule` — the rule schema
- `apps/viza-desktop/src/features/decisions/` — the UI surface (4 files)
- `config/viza_strategy_profile_templates.json` — the sole shipped template
- `tests/lookahead_audit/test_decisions_pit.py` — the PIT correctness gate
- `docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md` — engineering plan
- `docs/VIZA_PRODUCT_SPEC.md` — product principle and positioning

## 9. Engagement logistics

- Estimated counsel time: **1–3 hours total** across US and Korea
- Format: counsel can deliver as a one-page memo + optional 30-minute Q&A
- Confidentiality: this brief and the code excerpts are confidential; counsel should treat the strategy IP, source-rights states, and product roadmap as such
- Turnaround target: **2 weeks calendar** from engagement (scheduling-bound, not coding-bound)

# VIZA Investment-Command Layer: Compliance-Aligned Implementation Plan

Last updated: 2026-05-21
Builds on: `docs/VIZA_PRODUCT_SPEC.md` v0.4, `docs/VIZA_KR_COMPLIANCE_REPORT.md`, and the user-authored investment-command proposal (this session).

## 0. What this document is

This plan does two things in one pass:

1. It **audits** the investment-command-decisions proposal against the eight knowledge-representation disciplines in `VIZA_KR_COMPLIANCE_REPORT.md` (ontology engineering, FIBO, PROV, DMN, Rete, CEP, bitemporal modeling, argumentation).
2. It then **interleaves** the proposed feature with the compliance restructure so neither blocks the other and neither bakes in tech debt the other will have to undo.

The proposal is correct in its core claim — VIZA's `output_radar` should become a selectable strategy-output surface rather than a Top-N table — and most of its scaffolding (DecisionFrame extension, RadarItem normalization, selection policies, package redaction extension) is in the right shape. The corrections this document recommends are narrow but load-bearing: they touch identity, lineage, taxonomy decomposition, and trigger expressivity. Each correction is cheap if made before the MVP, expensive if made after.

---

## 1. Audit of the proposal against the compliance report

### 1.1 What the proposal gets right (preserve as-is)

| Proposal element | Compliance principle it satisfies | Notes |
|---|---|---|
| Command registry as a JSON config | "Rules are data; engines are configuration" (§10.4) | Right shape. Just needs SKOS-style structure. |
| RadarItem as a normalized output of an adapter | DMN separation of `Decision` from `Output` | Keep. |
| `output_radar` consumes; does not execute | DMN engine/decision separation | Keep. |
| Selection policies (`top_n_by_score`, `quota_then_score`, `grouped_by_command_family`, …) | DMN hit policies | These ARE DMN hit policies. Make the equivalence explicit (§2.5 below). |
| Attribute pipeline preserved as the input substrate | "Rules are data; engines are configuration" | Keep. |
| PIT cutoff filter preserved (`available_at <= cutoff_timestamp`) | Bitemporal AS-OF semantics | Necessary but not sufficient — see D5. |
| Package redaction extended to commands | Existing rights/license discipline | Keep, with two adjustments in §2.4. |
| Strategy-command vs. broker-order boundary | "VIZA emits strategy commands; VIZA does not route" | Non-negotiable. Keep. |
| MVP scope of 8 commands, 3 radar modes | Avoiding over-design before evidence | Right call. |

### 1.2 Where the proposal diverges from compliance (correct before code)

These are the eight items that need to land in the schema *before* the first `compile_decisions` call emits a structured command.

#### D1. The command taxonomy is flat where it should be a multi-axis decomposition.

The proposal lists `BUY_TO_OPEN`, `ADD_LONG`, `HOLD`, `TRIM_LONG`, `SELL_TO_CLOSE`, `SET_TARGET_WEIGHT`, `WATCH_CLOSELY`, `AVOID`, `BLOCK_ACTION` as a flat enum. But the proposal also already groups them ("Position entry", "Position increase", "Hold / maintain", …) — that grouping is a SKOS hierarchy waiting to be made formal.

The flat enum hides three structural problems:

- It mixes orthogonal axes inside single labels. `BUY_TO_OPEN` encodes (direction=BUY) × (position_change=OPEN) × (side=LONG). `TRIM_LONG` encodes (direction=SELL) × (position_change=REDUCE) × (side=LONG). A consumer that asks "is this a SELL?" must parse the label.
- It treats `SET_TARGET_WEIGHT` as a peer of `BUY_TO_OPEN`. But target-weight is a *sizing method*, not a command. Every position-changing command has a sizing method; some compute it implicitly. Modeling it as a peer creates an impossible state space ("BUY_TO_OPEN with sizing_method=SET_TARGET_WEIGHT") that doesn't fit the enum.
- It conflates *position commands* with *attention commands* with *system vetoes*. `BUY_TO_OPEN`, `WATCH_CLOSELY`, and `BLOCK_ACTION` are three different *kinds* of decisions, not three values of one kind.

**Correction.** Decompose into three command kinds and four orthogonal axes — see §2.1.

#### D2. Command target is a bare string where it should be a FIBO IRI.

The proposal's command payload has:

```json
"target": {
  "entity_id": "eq_aapl",
  "security_id": "sec_aapl_common",
  "ticker_alias": "AAPL"
}
```

Per the compliance report §2, both `entity_id` and `security_id` should be FIBO-aligned IRIs. The proposal already separates the *issuer* (eq_aapl) from the *instrument* (sec_aapl_common), which is correct — but it conflates VIZA-local IDs with the external concept. A command that survives export to a `.viza` file needs a stable, externally-resolvable identifier; otherwise no other tool can replay it against a different security master.

**Correction.** §2.2 below: the target carries both a local `entity_id` (for the local store) and a canonical `fibo_iri` (for portability).

#### D3. DecisionFrame.audit lacks PROV vocabulary.

The proposed audit block has `cutoff_timestamp`, `graph_hash`, `profile_version`, `evidence_checksum`, `result_checksum`. The compliance report §3 names exactly these as fields that should be expressed in PROV vocabulary: each is either a `prov:Entity` (the graph, the result) or a property of the `prov:Activity` (the run). Without PROV, "where did this command come from?" remains a per-tool grep.

**Correction.** §2.3: every DecisionFrame is a `prov:Entity` with explicit `prov:wasGeneratedBy` (the run), `prov:used` (the observation IRIs), `prov:wasAttributedTo` (the profile creator / live-mode opt-in user).

#### D4. ObservationPredicate carries forward — no FEEL-S.

The proposal preserves `ObservationPredicate(attribute_key, operator, threshold)` as the trigger primitive. That works for the MVP examples ("RSI ≤ 30") but breaks the moment a real strategy needs:

- multi-attribute conjunction in one rule ("RSI < 30 AND volume_spike > 2 AND days_since(earnings) < 5"),
- arithmetic ("delta_weight = min(0.02, conviction_score / 50)"),
- temporal references ("event.observed_at within last 3 trading days").

Today VIZA would shard these across `transform` nodes in the methodology graph. That's expensive in cognitive load per rule and prevents the rule from being self-contained data.

**Correction.** §2.6: replace `ObservationPredicate` with a FEEL-S (DMN simplified-FEEL) string expression, evaluated against an observation context. Keep the structured form as a generated artifact for UI display.

#### D5. Sizing inputs need bitemporal discipline; the proposal only PIT-filters the trigger.

The proposal evaluates the trigger predicates against PIT-safe observations (correct). But sizing computation (conviction_score → target_weight, volatility → risk-adjusted size, liquidity → cap, portfolio_exposure → delta) is described as if it's a present-tense lookup. A backtest at cutoff D needs the sizing inputs *as the system believed them at D*, not as the store currently believes them. If the volatility series for AAPL was later corrected, replaying yesterday's command must use the original volatility.

This is exactly the gap §7 of the compliance report calls out: VIZA observes moments, not intervals; corrections overwrite (`viza/observations.py:147` `ON CONFLICT DO UPDATE`).

**Correction.** Two parts. §2.6 routes sizing through the same DMN/FEEL evaluator that drives the trigger, so sizing inputs are observations subject to the same `available_at` and (eventually) bitemporal filters. §3.3 (Phase 28) makes the observation store bitemporal so replay is correct.

#### D6. No argumentation over conflicting commands.

If rule A fires `BUY_TO_OPEN AAPL` and rule B fires `AVOID AAPL` against the same entity at the same cutoff, the proposal's `COLLECT` hit policy emits both. That is acceptable as raw output but unacceptable as a *radar* (the user needs one answer to "what does this strategy say to do with AAPL?"). The compliance report §8 addresses exactly this with a small ASPIC+ evaluator.

**Correction.** §2.7: command-conflict matrix with preference relations (`source_credibility × confidence × rule_priority`), grounded-extension computation, and per-target `argumentation_status: accepted | rejected | undecided`. Phase 31.

#### D7. `requires_portfolio_context: true` hand-waves portfolio state.

The proposed payload flags some commands as needing portfolio context. But portfolio state IS observable: `attribute_key="portfolio.position.weight"` keyed by `entity_id=<portfolio>:<security>`, with `valid_time` (the position interval) and `observed_at`. Modeling it as a *flag* on the command creates a parallel resolution path; modeling it as an observation lets the existing PIT + sizing pipeline handle it uniformly.

**Correction.** §2.6 makes portfolio state an observation source. The flag is dropped.

#### D8. `invalidation_conditions` is an unstructured string list.

The proposal carries `invalidation_conditions: list[str]` on the risk_controls block (matching the existing `viza/insights.py:78`). Per compliance §8.3 these should be structured defeaters with declared semantics (`evidence_absent`, `counter_event`, `time_decay`), windows, and required evidence keys. Without that, the runtime can't mechanically test "is this command defeated right now?"

**Correction.** §2.7 introduces structured `Defeater` records on both insights and commands.

#### D9. The proposal's `decision_filters.include_blocked` collapses two semantically different things.

A `BLOCK_ACTION` command is a *positive emission* — the rule fired, and the answer is "do not act." A package-redaction block (`export_allowed=False`) is *suppression of an emission* — the command exists but cannot leave the file. The proposal lets the user toggle `include_blocked` as if they're symmetric, but they are not: redactions are not negotiable by a UI toggle, they are governed by rights metadata.

**Correction.** §2.5 separates `include_veto_commands` (UI choice over BLOCK_ACTION emissions) from `respect_rights_policy` (non-negotiable, default true).

### 1.3 Summary of audit

The proposal's *architecture* is sound. Of the nine divergences:

- **D1, D2, D9** are taxonomy/identity fixes that must land *with* the MVP (Phase 27) — they're cheap and they prevent the schema from shipping wrong.
- **D3, D4, D6, D7, D8** are restructures that *should* land with the MVP but can be staged as fast-following phases (28–31) provided the MVP carries the right placeholder fields.
- **D5** straddles: the MVP must thread sizing through the existing PIT filter (Phase 27), and the full bitemporal correction follows (Phase 28).

This shapes the phasing in §3.

---

## 2. Compliance-corrected schemas

The schemas below replace the corresponding payloads in §5 of the user-authored proposal.

### 2.1 Command taxonomy — three kinds, four axes (D1)

Three top-level command kinds:

```
PositionCommand     direction × position_change × side × sizing_method
AttentionCommand    urgency
SystemCommand       veto_kind
```

For position commands, four orthogonal axes:

| Axis | Values |
|---|---|
| `direction` | `BUY`, `SELL`, `NONE` |
| `position_change` | `OPEN`, `INCREASE`, `MAINTAIN`, `REDUCE`, `CLOSE`, `REBALANCE` |
| `side` | `LONG`, `SHORT` |
| `sizing_method` | `TARGET_WEIGHT`, `DELTA_WEIGHT`, `TARGET_NOTIONAL`, `DELTA_NOTIONAL`, `SHARES`, `IMPLICIT` |

The user-facing names (`BUY_TO_OPEN`, `ADD_LONG`, `HOLD`, `TRIM_LONG`, `SELL_TO_CLOSE`) are kept as **SKOS `prefLabel`s** on concepts in `config/viza_command_taxonomy.json`:

```json
{
  "schema": "viza.command_taxonomy.v1",
  "concept_scheme": "http://viza.local/concepts/commands",
  "concepts": [
    {
      "iri": "viza:cmd/buy_to_open",
      "skos_pref_label": "BUY_TO_OPEN",
      "skos_alt_labels": ["BUY OPEN", "OPEN LONG"],
      "skos_broader": ["viza:cmd-family/position_entry"],
      "kind": "PositionCommand",
      "axes": {
        "direction": "BUY",
        "position_change": "OPEN",
        "side": "LONG",
        "sizing_method": "TARGET_WEIGHT"
      },
      "fibo_related_iri": null
    },
    {
      "iri": "viza:cmd/trim_long",
      "skos_pref_label": "TRIM_LONG",
      "skos_broader": ["viza:cmd-family/position_reduce"],
      "kind": "PositionCommand",
      "axes": {
        "direction": "SELL",
        "position_change": "REDUCE",
        "side": "LONG",
        "sizing_method": "DELTA_WEIGHT"
      }
    },
    {
      "iri": "viza:cmd/watch_closely",
      "skos_pref_label": "WATCH_CLOSELY",
      "skos_broader": ["viza:cmd-family/monitoring"],
      "kind": "AttentionCommand",
      "axes": {"urgency": "ELEVATED"}
    },
    {
      "iri": "viza:cmd/block_action",
      "skos_pref_label": "BLOCK_ACTION",
      "skos_broader": ["viza:cmd-family/system_veto"],
      "kind": "SystemCommand",
      "axes": {"veto_kind": "EMIT_BLOCKED"}
    }
  ]
}
```

The MVP ships 8 concepts (the user's MVP set) plus 2 system commands (`BLOCK_ACTION`, `BLOCK_EXPORT`). Adding a new command becomes a registry edit; no code change.

### 2.2 Command target — FIBO-aligned identity (D2)

```python
class CommandTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str                          # local VIZA legal-entity id
    instrument_id: str | None = None        # local VIZA instrument id
    ticker_alias: str | None = None         # display only
    fibo_legal_entity_iri: str | None = None    # e.g. fibo-be-le-fbo:FormalBusinessOrganization instance
    fibo_instrument_iri: str | None = None       # e.g. fibo-sec-eq-eq:CommonStock instance
    identifier_set: list[CanonicalIdentifier] = Field(default_factory=list)
```

`CanonicalIdentifier` is the same shape used by the future canonical asset master (Phase 30):

```python
class CanonicalIdentifier(BaseModel):
    scheme_iri: str    # e.g. fibo-fbc-fct-ra:SecCikIdentifier
    value: str         # e.g. "0000320193"
```

In the MVP, `fibo_*_iri` may be `None` because the canonical asset master is not yet seeded. The fields are present, so when Phase 30 ships, no command-payload migration is needed.

### 2.3 DecisionFrame.audit as PROV (D3)

```python
class DecisionProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_entity_iri: str               # prov:Entity for this decision
    was_generated_by_run_iri: str          # prov:Activity (the methodology run)
    was_attributed_to_agent_iri: str       # prov:Agent (profile creator / live opt-in user)
    used_observation_iris: list[str] = Field(default_factory=list)  # prov:used
    used_event_iris: list[str] = Field(default_factory=list)
    used_insight_iris: list[str] = Field(default_factory=list)
    was_derived_from_iris: list[str] = Field(default_factory=list)  # prov:wasDerivedFrom

    # Content addresses (still here, now interpreted as identifying prov:Entity instances)
    graph_hash: str
    profile_version: str
    evidence_checksum: str
    result_checksum: str
```

Replaces the existing `DecisionAudit` (`viza/decisions.py:119`). The four checksum fields remain; they are reinterpreted as IRIs of immutable `prov:Entity` instances forming a Merkle DAG. Phase 33 lifts this fully into a typed PROV edge table; the MVP only needs the field layout.

### 2.4 Package redaction with the kind/rights split (D9)

The current `decisions_redaction.py` operates on DecisionFrames. Extend it to operate on `RadarItem`s with two independent gates:

```python
class RadarRedactionPolicy(BaseModel):
    mode: Literal["white_box", "output_only", "marketplace_draft"]
    include_veto_commands: bool = True        # UI choice
    respect_rights_policy: bool = True        # NEVER False in any released code path
```

`respect_rights_policy=False` exists only as a test fixture. The runtime refuses to honor it from a `.viza` file or API call.

### 2.5 OutputRadarConfig with DMN hit policies (D9 + the proposal's selection policies)

```python
class OutputRadarConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["ranking_only", "decisions_only", "mixed"]
    max_items: int = Field(default=20, ge=1, le=200)
    sources: list[Literal["ranking_results", "decision_frames"]]
    hit_policy: Literal["UNIQUE", "COLLECT", "PRIORITY", "FIRST", "QUOTA_THEN_SCORE"]
    quotas: dict[str, int] = Field(default_factory=dict)
    sort_by: Literal["radar_score", "command_priority", "valid_time_start", "argumentation_status"]
    group_by: Literal["display_group", "command_family", "argumentation_status"] | None = None
    decision_filters: DecisionRadarFilters = Field(default_factory=DecisionRadarFilters)
```

Three of the proposal's policies map 1:1 to standard DMN hit policies:

| Proposal name | DMN equivalent |
|---|---|
| `top_n_by_score` | `COLLECT` + `sort_by=radar_score` + `max_items=N` |
| `decisions_by_priority` | `PRIORITY` + `sort_by=command_priority` |
| `blocked_first` | `PRIORITY` + custom comparator on system_command_first |
| `quota_then_score` | not standard DMN; keep VIZA-specific name `QUOTA_THEN_SCORE` |
| `grouped_by_command_family` | `COLLECT` + `group_by=command_family` |

This rename costs nothing and connects VIZA's vocabulary to a standard auditors recognize.

### 2.6 Trigger and sizing as FEEL-S expressions (D4, D5, D7)

Replace `DecisionTrigger.observation_predicates` with `feel_expression`:

```python
class DecisionTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feel_expression: str
    structured_predicates_view: list[ObservationPredicate] | None = None  # generated for UI
```

The expression evaluates against an *observation context*: a dict-like binding of attribute keys to their `available_at`-filtered latest values, plus a `portfolio` sub-binding when relevant.

Example expressions:

```text
technical.rsi_14 <= 30 and technical.volume_spike > 2
filing.tone_delta >= 0.20 and fundamental.cash_conversion >= 0.70
portfolio.position.weight[security] < 0.05 and conviction_score >= 0.65
```

`structured_predicates_view` is regenerated from the expression on save (round-trip) so existing UI that shows individual predicates keeps working.

The MVP implements **S-FEEL** (DMN conformance level 2): scalars, ranges, dates, durations, boolean operators, dotted attribute access, the existing comparison operators. No full FEEL function library yet.

Sizing uses the same evaluator over the same context:

```python
class SizingExpression(BaseModel):
    sizing_method: Literal[...]   # see §2.1 axes
    feel_expression: str          # e.g. "min(0.02, conviction_score / 50)"

class CommandMapping(BaseModel):
    command_iri: str              # references the SKOS concept
    sizing: SizingExpression | None = None
    when_no_emit_command: str | None = None    # alternative command if predicate doesn't trigger
```

Portfolio state (`portfolio.position.weight[security]`) is just another observation. D7's `requires_portfolio_context` flag is **dropped**; the FEEL evaluator either has the binding or doesn't, and if it doesn't, the rule does not fire (this becomes a `BLOCK_ACTION` if the strategy profile so requests).

### 2.7 Argumentation over conflicting commands (D6, D8)

Two pieces:

**Conflict graph.** A separate config `config/viza_command_conflicts.json`:

```json
{
  "schema": "viza.command_conflicts.v1",
  "conflicts": [
    {
      "left_command_iri": "viza:cmd/buy_to_open",
      "right_command_iri": "viza:cmd/avoid",
      "relation": "attacks",
      "scope": "same_target",
      "preference_basis": "command_confidence * source_credibility"
    },
    {
      "left_command_iri": "viza:cmd/system_veto/block_action",
      "right_command_iri": "*",
      "relation": "defeats_unconditionally",
      "scope": "same_target"
    }
  ]
}
```

**ASPIC+ evaluator.** Operates per-(entity, cutoff): builds the argument graph, applies preferences, computes the grounded extension, tags each command with `argumentation_status: accepted | rejected | undecided`. Rejected commands are still persisted (PROV integrity), but the radar default is to hide them unless the user toggles "show rejected arguments."

**Structured defeaters** on every command (replaces `invalidation_conditions: list[str]`):

```python
class Defeater(BaseModel):
    defeater_kind: Literal["evidence_absent", "counter_event", "time_decay", "rights_blocked"]
    window: str | None = None         # ISO-8601 duration
    required_evidence_keys: list[str] = Field(default_factory=list)
    countering_event_iris: list[str] = Field(default_factory=list)
```

A command with a triggered defeater becomes `argumentation_status="rejected"` automatically; no manual conflict edge needed.

---

## 3. Phased plan

Phases are numbered continuing from `VIZA_PRODUCT_SPEC.md` §24 (which ends at Phase 25). Each phase has explicit entry/exit criteria and approximate effort.

### Phase 26 — KR foundations (prerequisite for the command MVP)

**Goal.** Land the cheap, schema-only compliance moves that the command MVP depends on. No new product behavior; no UI changes.

**Tasks.**

- Add `config/viza_concepts.json` (or `.ttl` if you prefer RDF tooling) seeded with SKOS concept schemes for: command families, command axes, event families, insight families, relationship families.
- Migrate existing `family` string fields on `AttributeDefinition`, `EventTypeDefinition`, `InsightTypeDefinition`, `RelationshipEdge` to `family_concept_iri: str`, with a back-compat shim that resolves legacy strings to IRIs at load time.
- Add `prov:wasAttributedTo` and `prov:wasGeneratedBy` to the `.viza` manifest in `viza/file_format/`.
- Add the empty `config/viza_command_taxonomy.json` and `config/viza_command_conflicts.json` files with schema-only entries.
- Update `relationships.py:369` `_expand_family_aliases` to read from `viza_concepts.json` instead of the hardcoded dict.

**Exit criteria.**

- `relationship_family` and three `family` fields are IRIs at rest; legacy strings still load.
- A `.viza` file written by the current code is still readable, but new files carry PROV attribution.
- No regression in the existing test suite.

**Effort.** ~1 week.

### Phase 27 — Investment Commands MVP (the user's core proposal, compliance-aware)

**Goal.** Emit structured investment commands, render them in the radar, persist + replay + redact them — all with the compliance-corrected schemas from §2.

**Tasks.**

Schema (Pydantic + SQLite):

- `InvestmentCommandPayload` model (§2.1, §2.2).
- `DecisionProvenance` replaces `DecisionAudit` (§2.3).
- `DecisionFrame.command: InvestmentCommandPayload | None`.
- `RadarItem` and `RadarItemKind` models (§5.D of the user's proposal, target FIBO-aligned).
- `OutputRadarConfig` (§2.5).
- `Defeater` model (§2.7), wired into both `DecisionRule` and `InsightTypeDefinition`.
- Command registry seeded with 8 + 2 commands.

Execution:

- Extend `compile_decisions` (`viza/decisions.py:173`) to:
  - resolve `rule.command_mapping_iri` from the strategy profile,
  - evaluate sizing via the same context as the trigger (placeholder FEEL evaluator for MVP: supports the existing operators plus boolean `and`/`or`/`not` and `min`/`max`),
  - emit a `DecisionFrame` with both action_template (legacy) and `command` (new).
- Keep all existing live-mode preconditions, cooldown policy, dead-band suppression, and rights-state attachment.

Radar assembly:

- `decision_frame_to_radar_item` adapter.
- `ranking_result_to_radar_item` adapter (so today's Top-N rows fit the same shape).
- `assemble_output_radar(config, radar_items) -> OutputRadarView`.
- Implement the three MVP modes: `ranking_only`, `decisions_only`, `mixed`.
- Implement two hit policies: `COLLECT` (today's default) and `QUOTA_THEN_SCORE` (the user's flagship policy).

Argumentation (minimal):

- Detect `SystemCommand=BLOCK_ACTION` for a target and tag every other command on that target as `argumentation_status="rejected"` with reason `system_veto`.
- Detect attack edges from `viza_command_conflicts.json` (load-only; no preference resolution yet — both commands stay `undecided` and the radar shows both grouped).
- Full ASPIC+ resolution defers to Phase 31.

UI:

- New `DecisionCommandCard` renders the command kind, axes, sizing, mode badge (sandbox / live), PIT/rights/validation/audit chain, and the verbatim `action_template`.
- `BlockedCommandCard` for `SystemCommand`.
- `WatchCommandCard` for `AttentionCommand`.
- Radar mode selector in the radar UI.

Language gate:

- Update the desktop tests that currently assert no buy/sell language anywhere. The new rule (matching the user's §H): command words are allowed **only inside components whose React `displayName` is on a whitelist** (`DecisionCommandCard`, `BlockedCommandCard`, `WatchCommandCard`). The whitelist itself is config: `apps/viza-desktop/src/command_language_gate.json`.
- Add a Playwright/Vitest assertion: no text node *outside* a whitelisted component contains buy/sell/recommended/today phrasing.

Package + backtest + validation extensions:

- Extend `decisions_redaction.py` to operate on `RadarItem`s (§2.4).
- Extend `decisions_backtesting.py` reports to summarize commands by axis (direction, position_change, side, kind) in addition to by rule/entity/profile.
- Extend `validation_ledger.py` `outputs` summary to include command counts per axis.

**Exit criteria.**

- A strategy profile can declare a `DecisionRule` whose command is `BUY_TO_OPEN AAPL to 2.0% target weight`, and `compile_decisions` emits the structured payload.
- `output_radar` in `mixed` mode renders ranked tickers AND command cards in one view.
- A `.viza` exported in `white_box` mode round-trips commands losslessly; `output_only` redacts rule internals; `marketplace_draft` blocks export if `source_rights_state.export_allowed=False`.
- Sandbox replay reproduces commands deterministically.
- Live mode still requires env flag + per-profile opt-in + per-rule `effective_from`.
- Decision-backtest report summarizes command counts by axis.
- The buy/sell language gate passes: no command words appear outside whitelisted cards.

**Effort.** ~3 weeks.

### Phase 28 — Bitemporal observation + event store (closes D5)

**Goal.** Replay correctness for sizing. Today `compile_decisions` filters by `available_at <= cutoff`, but a corrected observation has overwritten the original. After this phase, replay returns the system's belief AS OF the cutoff transaction time, not its current belief.

**Tasks.**

- Add `valid_time_start`, `valid_time_end`, `transaction_time_start`, `transaction_time_end` columns to `observations`, `events`, `insights`. `available_at` is **retained** as the source-availability timestamp (it captures something neither valid time nor transaction time does — when the source first made the fact queryable to a consumer).
- Switch `viza/observations.py:147` from `ON CONFLICT(observation_id) DO UPDATE` to append-only writes: a correction closes the previous row's `transaction_time_end` and inserts a new row. `observation_id` becomes a logical key that can repeat.
- Add `ObservationStore.get_as_of_transaction_time(ttx)` and `get_as_of_valid_time(vt)` helpers.
- Add `compile_decisions(transaction_time_cutoff: datetime | None = None)` argument that, when set, filters to the system's belief at that transaction time. Default `None` = use current belief (back-compat with the current behavior).
- Update `replay_decisions_from_store` to use the transaction-time AS-OF query for full audit replay.
- Migration: existing observations get `valid_time_start = observed_at`, `transaction_time_start = retrieved_at`, both `_end` fields `NULL`.

**Exit criteria.**

- Correcting a historical observation produces TWO rows in the store, not one mutated row.
- `replay_decisions_from_store` at a past run_id returns identical commands to the original run, even if observations have been corrected since.
- `compile_decisions(transaction_time_cutoff=T)` returns what the system would have computed at transaction time T.

**Effort.** ~3 weeks. Schema migration is the risk; gate it on a `--migrate-bitemporal` CLI flag with a dry-run.

### Phase 29 — DMN FEEL-S trigger and sizing (closes D4)

**Goal.** Replace the placeholder FEEL evaluator from Phase 27 with a real S-FEEL implementation. Lift action thresholds to a true DMN decision table.

**Tasks.**

- Implement S-FEEL parser + evaluator (target ~600 lines of Python; the grammar is small).
- Migrate `DecisionTrigger.observation_predicates` to `feel_expression`. Generate `structured_predicates_view` on save for the existing UI.
- Lift `action_thresholds: dict[str, float]` (`viza/strategy_profiles.py:150`) to a `DecisionTable` model with declared `hit_policy: FIRST` ordered by descending threshold.
- Promote `technical_values_from_ohlcv` (`viza/observations.py:374`) to a named, versioned `BusinessKnowledgeModel` per indicator: `rsi_14`, `volume_spike`, `momentum_21`, `moving_average_trend`. Decision rules reference them via FEEL function calls.
- Export DMN XML from a strategy profile (Decision + InputData + BKM nodes).

**Exit criteria.**

- A rule can express "RSI < 30 AND volume_spike > 2 AND days(event.observed_at, cutoff) < 5" in one expression.
- A strategy profile's action thresholds are a real decision table with declared hit policy.
- A `.viza` strategy package can be exported as DMN XML and re-imported losslessly.

**Effort.** ~3 weeks.

### Phase 30 — FIBO identity (closes D2 properly)

**Goal.** Seed the canonical asset master against FIBO-SEC, so command targets carry real FIBO IRIs rather than placeholder `None`s.

**Tasks.**

- Seed `canonical_assets` from FIBO-SEC for the US equity universe.
- `Asset` model becomes a Pydantic projection of `fibo-sec-eq:CommonStock`.
- `identifiers.cik` etc. become typed `CanonicalIdentifier` instances with FIBO scheme IRIs.
- `CommandTarget.fibo_legal_entity_iri` and `fibo_instrument_iri` are populated by the asset resolver node from PROJECT_SPEC §15.3.
- Map `viza_event_registry.json` event types to FIBO-CAE where applicable (`confirmed_mna` → `fibo-cae-mer:MergerEvent`).

**Exit criteria.**

- Every command emitted by `compile_decisions` for a US equity carries non-null `fibo_legal_entity_iri` and `fibo_instrument_iri`.
- A `.viza` file's commands can be replayed against a different security master if both speak FIBO.

**Effort.** ~2–3 weeks.

### Phase 31 — Argumentation over commands (closes D6, D8)

**Goal.** Per-(entity, cutoff) conflict resolution that gives the user one defensible answer instead of contradictory raw firings.

**Tasks.**

- Implement the ASPIC+ extension evaluator described in §2.7.
- Wire `Defeater` evaluation into `compile_decisions` (mechanically test each defeater against current observations).
- Add `argumentation_status` to `DecisionFrame` and surface it in `RadarItem.argumentation_status`.
- Add a `radar_filter: include_rejected: bool = false` to `OutputRadarConfig`.
- UI: collapse rejected commands behind an expandable group per target.

**Exit criteria.**

- When two attacking commands fire on the same target, the grounded extension is computed and one wins (or both stay undecided with rationale).
- A `BLOCK_ACTION` defeats every position command on the same target.
- A command whose `evidence_absent` defeater is currently triggered is marked rejected without manual configuration.

**Effort.** ~2 weeks.

### Phase 32 — Pattern grammar for triggers (CEP-lite)

**Goal.** Multi-event sequence triggers ("acquisition_rumor followed-by unusual_volume within 3 trading days") expressed as data, not Python.

**Tasks.**

- Add an `EventPattern` field to `DecisionTrigger`. Grammar from compliance report §6, with operators `sequence`, `and`, `or`, `not`, `within`, plus Allen interval operators (`before`, `during`, `overlaps`).
- Implement a batch evaluator (no streaming engine).
- Lift the hardcoded `acquisition_rumor_with_technical_reversal_context` logic at `viza/insights.py:336` to a declared pattern in the insight registry.
- Use Allen operators on the relationship graph to scope `invalidates` / `confirms` edges by time.

**Exit criteria.**

- The insight registry can declare a multi-event composite insight as data.
- A `.viza` strategy package can express temporal patterns without imperative graph nodes.

**Effort.** ~2 weeks.

### Phase 33 — Full PROV graph + marketplace prep

**Goal.** Lineage becomes a queryable graph, not a per-output dict.

**Tasks.**

- Promote `MethodologyRunResult` to a first-class `prov:Activity` row with `startedAtTime`, `endedAtTime`, `wasAssociatedWith` (agent), and edges to every entity it `used`/`generated`.
- Replace `evidence_refs: list[str]` with a typed `ProvenanceEdge` table (subject_iri, predicate, object_iri, generated_at_time, rights_policy_ref).
- DecisionFrame becomes a `prov:Entity` with explicit `wasGeneratedBy` to the run and `used` to observations.
- Add a `/viza/provenance/query` endpoint that walks the PROV graph from any entity to its sources.
- Validation-replay becomes a graph isomorphism check, not a manifest dict comparison.

**Exit criteria.**

- For any command, a single API call returns its full PROV chain (Activity → Entities → Agents).
- Marketplace dispute resolution has the data needed: "show me the chain that produced this signal."

**Effort.** ~2 weeks.

### What stays deferred

Restated from the compliance report §9. These are **not** scheduled in this plan because their absence is not currently a bug:

- **Rete algorithm.** Until rule count or data volume forces it; until then, the existing `O(rules × entities)` loop plus the indexes added in Phase 28 is sufficient.
- **Full streaming CEP (Esper/Flink).** Until streaming becomes a real requirement; Phase 32's batch evaluator handles up to ~100k events comfortably.
- **AGM belief revision.** Phase 31's ASPIC+ is sufficient.
- **OWL reasoners as part of the runtime.** OWL stays an *export* format generated from the Pydantic models, not a runtime dependency.

---

## 4. Revised MVP checklist (replaces the proposal's §8)

This is the checklist for Phase 27, with the compliance corrections folded in.

### Taxonomy + identity
- [ ] `config/viza_command_taxonomy.json` seeded with 10 concepts (8 commands + BLOCK_ACTION + BLOCK_EXPORT), all carrying `skos_pref_label`, `skos_broader`, axes, and (where applicable) `fibo_related_iri`.
- [ ] `config/viza_command_conflicts.json` seeded with the obvious mutual-exclusion attack edges and the unconditional `BLOCK_ACTION` defeats-everything edge.
- [ ] `CanonicalIdentifier` + `CommandTarget` models present, with `fibo_*_iri` fields nullable until Phase 30.

### Schema + models
- [ ] `InvestmentCommandPayload` model (decomposed by kind + axes, NOT a flat enum).
- [ ] `DecisionProvenance` replaces `DecisionAudit`.
- [ ] `DecisionFrame.command: InvestmentCommandPayload | None`.
- [ ] `RadarItem`, `RadarItemKind`, `OutputRadarConfig` models.
- [ ] `Defeater` model wired into `DecisionRule` and `InsightTypeDefinition`.

### Strategy profile
- [ ] `DecisionRule.command_mapping_iri` references a command concept.
- [ ] `DecisionRule.sizing_expression` (FEEL-S string; placeholder evaluator in MVP).
- [ ] `VizaStrategyProfile.output_radar_config: OutputRadarConfig`.
- [ ] `DecisionRule.effective_from` preserved (live-mode gate).
- [ ] Cooldown / dead-band preserved.

### Decision execution
- [ ] `compile_decisions` emits structured commands.
- [ ] Sizing expression evaluated against the same PIT-filtered observation context as the trigger.
- [ ] Live-mode preconditions preserved.
- [ ] Validation-ledger emission preserved.
- [ ] Minimal argumentation: `BLOCK_ACTION` defeats all other commands on the same target.

### Radar assembly
- [ ] `decision_frame_to_radar_item` adapter.
- [ ] `ranking_result_to_radar_item` adapter (existing Top-N rows fit the new shape).
- [ ] `assemble_output_radar(config, items) -> OutputRadarView`.
- [ ] Modes: `ranking_only`, `decisions_only`, `mixed`.
- [ ] Hit policies: `COLLECT`, `QUOTA_THEN_SCORE`.

### UI
- [ ] Radar mode selector.
- [ ] `DecisionCommandCard`, `BlockedCommandCard`, `WatchCommandCard`.
- [ ] Card shows: command IRI prefLabel, axes, sizing, mode badge (sandbox / live), PIT / rights / validation / audit chain, verbatim `action_template`.
- [ ] Buy/sell language is allowed ONLY in components whose displayName is on `command_language_gate.json`.
- [ ] Test: no text node outside whitelisted components contains buy/sell/recommended/today phrasing.

### PROV at the manifest
- [ ] `.viza` manifest carries `prov:wasAttributedTo`, `prov:wasGeneratedBy`.
- [ ] DecisionProvenance fields populated on every emitted command.

### Package / export
- [ ] `decisions_redaction.py` extended to `RadarItem`s.
- [ ] `RadarRedactionPolicy` with `respect_rights_policy=True` enforced (no API path can set it False).
- [ ] `marketplace_draft` blocks export when any command's `source_rights_state.export_allowed=False`.

### Backtesting
- [ ] Backtest report counts commands by axis (direction × position_change × side × kind) in addition to by rule/entity/profile.
- [ ] Cooldown / dead-band preserved across cutoffs.
- [ ] PIT-blocked and rights-blocked counts surfaced.

### Tests
- [ ] DecisionRule can emit each of the 8 MVP commands.
- [ ] Attributes drive command predicates (no parallel pipeline).
- [ ] Missing PIT → `BLOCK_ACTION` emitted; not silent.
- [ ] Missing rights → `BLOCK_EXPORT` enforced at package time.
- [ ] Argumentation: `BLOCK_ACTION` causes co-firing position commands to be tagged `rejected`.
- [ ] Round-trip: command emitted, persisted, replayed, exported, re-imported → identical structured payload.
- [ ] Language gate: text-scan test passes on all three radar modes.

---

## 5. What stays intact from the user's proposal

To be explicit, none of the following change:

- The strategy-command-vs-broker-order boundary (§7 of the proposal). VIZA emits commands; it does not route orders.
- Live mode's preconditions (env flag + per-profile opt-in + per-rule `effective_from`).
- The package modes (`white_box`, `output_only`, `marketplace_draft`) and their existing semantics.
- The decision backtest pipeline.
- The MVP scope of 8 commands + 3 radar modes.
- The two pilot strategies (`template-rsi-swing-catalyst-confirmation`, `quality_value_long_only`).
- The end-to-end intended behavior described in §6 of the proposal.
- The architectural claim that `output_radar` consumes decisions rather than executing them.

The corrections in this document are **structural**, not behavioral: they reshape the schemas the command layer ships with, so the layer doesn't have to be re-shipped when Phases 28–33 land.

---

## 6. Effort summary

| Phase | Goal | Effort | Blocks |
|---|---|---|---|
| 26 | KR foundations | ~1 week | 27 |
| 27 | Investment commands MVP | ~3 weeks | — (delivers the user-visible feature) |
| 28 | Bitemporal store | ~3 weeks | — (replay correctness) |
| 29 | DMN FEEL-S | ~3 weeks | richer triggers / sizing |
| 30 | FIBO identity | ~2–3 weeks | marketplace portability |
| 31 | Argumentation | ~2 weeks | radar clarity on conflicts |
| 32 | Pattern grammar | ~2 weeks | composite insights as data |
| 33 | Full PROV graph | ~2 weeks | marketplace disputes |

Total ~18–19 weeks of focused work to get from the current Phase 15 prototype through the user-visible command feature AND the eight compliance disciplines. Phases 26 + 27 alone (~4 weeks) get the command feature shipped with the right *bones*, with the rest treated as a fast-following sequence.

---

## 7. Boundaries this plan does not cross

For the record:

- VIZA still does not route broker orders.
- Live mode still requires explicit opt-in per profile, per disclosure version.
- Strategy commands are never displayed without a clear simulation/live mode badge.
- Rights-policy redaction is never bypassable by a UI toggle.
- The methodology graph never executes arbitrary code; FEEL-S is side-effect-free by construction.
- Validation records never claim completed performance without observations (existing `validate_validation_proof` at `viza/validation_ledger.py:404` continues to apply).
- The "translation through the user's strategy lens" framing from `VIZA_PRODUCT_SPEC.md` §3 stays. Commands are the most concrete form of that translation; they do not replace insights, they consume them.

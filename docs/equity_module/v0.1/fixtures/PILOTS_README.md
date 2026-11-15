# v0.1 Pilot Fixtures — `viza.finance.equity_investment`

**Path:** `docs/equity_module/v0.1/fixtures/`
**Source:** CLAUDE log §41 Phase 3 (launch sequence).
**Baseline:** Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening.

These pilots verify the three v0.1 strategy profiles end-to-end without runtime engine code. Each pilot lives in its own directory with a self-contained verifier; `run_all_pilots.py` orchestrates them.

| Pilot | Directory | Strategy profile | Data sources | Licensed-data behaviour |
|---|---|---|---|---|
| 1 | [`first_wedge/`](first_wedge/) | `quality_value_long_only` | EDGAR + public derived calculations | None — public only |
| 2 | [`portfolio_risk_radar_pilot/`](portfolio_risk_radar_pilot/) | `portfolio_risk_radar` | Public market data + Kenneth French (latest_only) + synthetic user portfolio (private) | Barra / Axioma factor models listed as locked placeholders; S&P index membership locked; fallback to Kenneth French latest_only with PIT warning |
| 3 | [`earnings_revision_momentum_pilot/`](earnings_revision_momentum_pilot/) | `earnings_revision_momentum` | EDGAR 8-K Item 2.02 + management guidance press release (public Path B) | I/B/E/S consensus connector (Path A) fails closed → locked-preserve-config → Path B public fallback activates |

## Run all three

```bash
python docs/equity_module/v0.1/fixtures/run_all_pilots.py
```

Expected exit code 0. Final block:

```text
ALL PILOTS PASSED.
```

## Run individually

```bash
python docs/equity_module/v0.1/fixtures/first_wedge/verify_fixture.py
python docs/equity_module/v0.1/fixtures/portfolio_risk_radar_pilot/verify_fixture.py
python docs/equity_module/v0.1/fixtures/earnings_revision_momentum_pilot/verify_fixture.py
```

## Per-pilot deliverables

Each pilot directory contains at minimum:

```text
fixture.json                          <- full fixture inputs (entities, attributes, events, insights,
                                         decision, validation_record, rights_policy, graph, paths,
                                         expected warnings, package behaviour, test cases)
verify_fixture.py                     <- standalone verifier (10+ check groups, stable SHA-256 emission)
```

`first_wedge/` additionally ships:

```text
expected_validation_report.json
expected_source_rights_report.json
expected_memo_skeleton.md
expected_package_behavior.json
README.md
```

Pilots 2 and 3 inline these into `fixture.json` for compactness (`pit_report`, `source_rights_report`, `package_behavior`, `expected_warnings`, `test_cases` are top-level keys).

## Acceptance criteria (cross-pilot)

| Criterion | Where verified |
|---|---|
| All three profile graphs load | `run_all_pilots.py` invokes all three verifiers; each returns 0 |
| Section 19 validator runs on all graphs | Per-pilot `expected_validation_summary` (pass/warn/fail/not_applicable counts) + per-pilot validation rule list in `required_validation_rules` |
| Licensed-data profile fails closed or degrades to fallback | `earnings_revision_momentum_pilot/fixture.json` → `path_a_license_gated.fail_closed_behavior` + `path_b_public_fallback` active; portfolio_risk_radar → Barra/Axioma locked placeholders + Kenneth French latest_only fallback |
| No profile uses ticker as primary key | Each verifier asserts `immutable_keys == ['security_id']` and ticker stored only at `identifiers.ticker_display` |
| No profile emits personal advice | Action vocabularies use research-action language (buy_candidate, watch, monitor, alert_only, research_deeper, avoid, hedge_candidate). The portfolio_risk_radar pilot explicitly excludes buy_candidate/sell_candidate/short_candidate from its allowed_actions |
| All recommendation-like outputs contain non-advice boundary | Each fixture top-level `non_advice_boundary` field + every output view's required_sections includes `non_advice_boundary` |
| Existing tests remain green | Out of scope for the fixtures themselves. Verify in CI: `python -m pytest tests/unit tests/lookahead_audit` |

## Per-pilot constraint compliance

### Pilot 1 — `quality_value_long_only`

Constraint: **public EDGAR + public macro + public derived calculations only**.

- Data sources used: EDGAR 10-K filing, EDGAR XBRL facts (via evidence_bundle), public listing record. No macro inputs in this fixture; no licensed connectors invoked.
- 3 licensed connectors (estimates, borrow, options) listed in `source_rights_report` as locked placeholders with `license_status=missing` — never queried.

### Pilot 2 — `portfolio_risk_radar`

Constraint: **public data only unless user portfolio fixture is synthetic and marked private**.

- User portfolio: synthetic, 5 fictional positions, `license_policy=internal_research_only`, NAV $10M, `export_policy=blocked`, `marketplace_policy=blocked`, `redaction_required=true`.
- Market data: public delayed EOD via `licensed_market_data_connector` with `fall_back_to_delayed_eod_public_when_available` semantic.
- Factor data: Kenneth French current — explicitly `latest_only` per PROJECT_STATUS.md; PIT warning emitted: `pit_latest_only_not_backtest_safe_factor_data_public_kenneth_french`.
- Licensed alternatives (Barra, Axioma) listed as locked placeholders — never invoked.
- Output redaction in `marketplace_draft`: full user portfolio details (nav_usd, positions[*].market_value_usd, security_id_ref, weight) redacted to aggregates only.

### Pilot 3 — `earnings_revision_momentum`

Constraint: **license-gated if it requires estimates; provide fallback radar using EDGAR earnings surprise only**.

- Path A (license-gated): `licensed_estimates_connector` with `license_status=missing`. Behaviour:
  - `query_policy=blocked` (fail-closed)
  - 4 dependent nodes (`revisions_aggregator`, `earnings_surprise_calculator_consensus_variant`, `analyst_coverage_node`, `analyst_rating_change_intake`) marked `runtime_status=open_locked_preserve_config`
  - Profile `runtime_status=research_only`
  - Explicit user-facing warning; **no silent fallback to bad consensus data**
- Path B (public-data fallback) ACTIVE: computes `guidance_surprise_eps_pct = (0.98 − 0.92) / 0.92 = 6.52%` and `guidance_surprise_revenue_pct = (485 − 470) / 470 = 3.19%` using EDGAR 8-K Item 2.02 + prior-quarter management guidance press release.
- Path B emits warning `consensus_connector_unavailable_using_public_guidance_fallback` with explicit remediation (acquire I/B/E/S license).
- PIT chain: press_release (2025-07-25) → 8-K (2025-10-22) → decision (2025-11-15). All inputs precede decision; no lookahead.

## Stable hashes (recorded at first verifier run)

| Pilot | fixture sha256 (file bytes) | fixture sha256 (canonical JSON) |
|---|---|---|
| 1 quality_value_long_only | `c36f4b68377bc678b266331bbf49434aa6a74af93193124a41e58b8815a77c44` | `fbdd0fcdeec91971939928c226086365e298cc8ff52933846b8611398245c11d` |
| 2 portfolio_risk_radar | `a2ce33f6054a71c16e4a57b9cca99ebaf61f3bc848bd861f52144a0a513442e9` | `9fb9aac79c774b45105310a4f01c599b88d253440c7aa174614fc08e4d3fbfac` |
| 3 earnings_revision_momentum | `065f6094b9b892050286bb5da826a9f433a49130e0b27f139e5e6ffc522fff5e` | `ad970027b1579a53576a8c768fe2f14441cc919d49297bdec73451d21617cca0` |

Identical re-runs produce identical hashes; the `run_all_pilots.py` master runner emits a combined `combined_pilot_fixture_sha256` as the cross-pilot regression anchor.

## How these pilots wire into the runtime

When the loaders defined by [`IMPLEMENTATION_PLAN_LOADERS.md`](../IMPLEMENTATION_PLAN_LOADERS.md) are implemented:

1. Phase 5 of that plan adds `tests/unit/test_equity_first_wedge_fixture.py`, `tests/unit/test_equity_portfolio_risk_radar_pilot.py`, and `tests/unit/test_equity_earnings_revision_momentum_pilot.py`.
2. Each test imports `EquityModule` + the appropriate pilot's `fixture.json` and asserts:
   - The graph passes `viza.equity.cross_reference.CrossReferenceEngine.verify_all()`.
   - The validation engine emits the exact `expected_validation_summary` counts from the fixture.
   - The package builder produces the exact byte sequence for the `output_only` and `marketplace_draft` modes documented in the fixture.
3. Snapshot tests pin the canonical SHA-256 of each fixture's rendered outputs to detect any drift.

## Non-advice boundary

These fixtures are research / engineering scaffolding only. They do not constitute investment advice. ExampleCo Industrial, FictiTech Software, ExampleBio Pharma, SampleEnergy, ExampleFin Bank are all fictional placeholder identities. Past performance does not predict future results.

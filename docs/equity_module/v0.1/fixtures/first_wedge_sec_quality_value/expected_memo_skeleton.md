# Investment Memo — ExampleCo Industrial, Inc. (FICTIONAL FIXTURE)

**Strategy profile:** `quality_value_long_only`
**Decision ID:** `decision_exampleco_001`
**Run ID:** `run_2025_11_15_first_wedge_v01`
**Module version:** `viza.finance.equity_investment v0.1.0`
**Baseline:** Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening
**Analysis cutoff:** `2025-11-15T14:00:00Z`
**Confidence label:** `common_practice` (qualitative moat evidence + pending consensus license)
**PIT status:** `PIT_safe=true`, `lookahead_risk=low`
**Rights status:** `display_policy=allowed`, `export_policy=conditional`, `marketplace_policy=redacted`
**Status:** Research output, not investment advice.

> **Fixture disclosure:** ExampleCo Industrial, Inc. (ticker display `EXAMPLE.US`, placeholder CIK `0009999999`) is **fictional**. All financial values are illustrative and used solely to exercise the equity-module end-to-end flow.

---

## 1. Executive summary

- **Action:** `buy_candidate` (research action; not a personal recommendation).
- **Thesis (one-line):** Quality compounder available at a reasonable discount — ROIC ~18%, FCF conversion >90%, leverage 1.8x, P/E 14x vs peer median 18x, computed margin of safety ~25%.
- **Score:** quality_value_composite = 1.42 (decile 8).
- **Key signals:** valuation_discount, margin_of_safety_present, cash_conversion_strength, moat_widening (qualitative).
- **Key risks:** moat narrowing, cash-conversion break, leverage step-up, valuation premium versus peers, accounting-quality red flag.
- **Horizon:** 1y–5y.
- **Non-advice boundary:** see §13.

## 2. Company snapshot

| Field | Value |
|---|---|
| Company ID (immutable) | `co_exampleco_001` |
| Issuer ID (immutable) | `iss_exampleco_001` |
| Security ID (immutable) | `sec_exampleco_001` |
| Ticker (display only) | `EXAMPLE.US` |
| CIK (placeholder) | `0009999999` |
| LEI (placeholder) | `EXAMPLECO9999999999LEI` |
| Sector | Industrials |
| Industry | Capital Goods |
| Subindustry | Industrial Machinery |
| Country | US |
| Primary listing | NYSE / USD |
| Filing reference | 10-K FY2024, accession `0009999999-25-000001`, filed `2025-02-15T16:30:00Z` |

> **No ticker as primary key.** All cross-references use immutable IDs above.

## 3. Business model

ExampleCo manufactures industrial-machinery components for capital-goods customers. Revenue is largely repeat-customer driven; pricing power is sustained through engineering specifications. (Description abbreviated — fictional fixture.)

## 4. Industry context

Industrial machinery subindustry: mid-cycle exposure, GICS subindustry classification, peer set built per Bhojraj-Lee methodology with 7 peers across size / profitability / growth deciles.

## 5. Financial analysis

| Metric (TTM) | Value | Source |
|---|---|---|
| Revenue | $1,850 mm | `ev_filing_001_revenue` |
| Operating income | $333 mm | `ev_filing_001_op_inc` |
| Net income | $245 mm | `ev_filing_001_net_income` |
| Cash from operations | $280 mm | `ev_filing_001_cfo` |
| Free cash flow | $222 mm | `ev_filing_001_fcf` |
| Net debt | $720 mm | `ev_filing_001_net_debt` |
| Invested capital | $1,850 mm | `ev_filing_001_invested_capital` |

| Derived ratio (TTM) | Value | Computation |
|---|---|---|
| Revenue growth (Y/Y, q) | 8.2% | filing-derived |
| Gross margin | 38.5% | filing-derived |
| Operating margin | 18.0% | operating_income / revenue |
| FCF margin | 12.0% | fcf / revenue |
| ROIC | 18.0% | operating_income / invested_capital |
| Net debt / EBITDA | 1.80x | net_debt / EBITDA proxy |
| CFO / Net income | 1.143 | cfo / net_income |
| FCF / Net income | 0.906 | fcf / net_income |

## 6. Valuation support

### 6.1 DCF

- Method family: `dcf` (Gordon terminal)
- Horizon: 10 years
- Assumptions: perpetual growth 3.0% (band 2–4%); discount rate 8.0% (band 7–9%); terminal multiple 15x (band 13–17x). Every assumption carries a sensitivity band per CLAUDE §7.13.
- Output: intrinsic value per share $65 (range $55–$78).
- Sensitivity table: 2×3 grid over WACC × growth (see fixture.json `valuation_model_dcf.sensitivity_table`).
- Reverse-DCF cross-check: passed.

### 6.2 Relative valuation

- Peer methodology: Bhojraj-Lee (size + profitability + growth deciles within Industrials / Capital Goods / Industrial Machinery).
- Peer count: 7 (min 5 required per §8.5).
- Subject P/E TTM: 14.0x; peer median: 18.0x; subject z-score: -1.10.
- Subject EV/EBITDA TTM: 9.5x; peer median: 11.5x.
- Output: peer_underhang_flag = true; valuation_gap_pct = 28.6%.

### 6.3 Margin of safety

- Market price (decision timestamp): $48.75.
- Intrinsic value (base): $65.00.
- **Margin of safety:** ~25.0% (passes `quality_value_long_only.required_confirmations.margin_of_safety_present` gate; profile minimum 25%).

## 7. Thesis

- **Claim:** ExampleCo is a durable, quality-value industrial machinery business available at a reasonable discount to intrinsic value.
- **Strategy family:** quality_value + compounder.
- **Horizon:** 1y–5y.
- **Primary signals:** roic_ttm, fcf_yield_ttm, moat_score_qualitative, margin_of_safety_pct.
- **Confirmations observed:** cash_conversion_strength, moat_widening.
- **Confirmations pending:** governance_strong (placeholder until proxy_statement evidence is loaded).
- **Supporting evidence ids:** see fixture.json `thesis.supporting_evidence_ids` (7 entries from `fixture_filing_001`).
- **Contradictory evidence:** none observed in fixture data.

## 8. Catalysts

No company-specific catalyst currently. Profile is `quality_value_long_only`; catalysts are optional. Monitoring triggers per §7.6: next 10-Q, next 10-K, 8-K Item 4.02 restatement.

## 9. Risks

| Risk | Severity | Source |
|---|---|---|
| Moat erosion / industrial cyclicality | medium | qualitative |
| Cash-conversion break | low (currently 90%+) | `attr_fcf_to_ni_ttm` |
| Leverage step-up | low (1.8x today, 3x threshold) | `attr_net_debt_to_ebitda_ttm` |
| Peer multiple compression | medium | `valuation_model_relative` |
| Accounting-quality red flag | low (no flags observed) | `attr_cfo_to_ni_ttm` + `restatement_flag=false` |

## 10. Invalidation conditions

The thesis is **invalidated** if any of the following are observed:

1. `moat_narrowing_observed` — ROIC trends down two consecutive years AND qualitative moat downgraded.
2. `cash_conversion_breaks_below_70pct` — `fcf_to_ni_ttm < 0.70` for two consecutive quarters.
3. `leverage_above_3x_net_debt_ebitda` — sustained.
4. `valuation_premium_above_peer_median` — subject z-score crosses +1.0.
5. `accounting_quality_red_flag_severity_high` — restatement, going-concern, material weakness, or accounting_quality_score downgrade.

## 11. Liquidity / float review

Not material for this profile size; reviewed only at portfolio-context attach time. Quality-value long-only mandate horizon 1y–5y is forgiving of medium liquidity.

## 12. Management + governance

DEF 14A evidence not loaded in this fixture (fixture purposefully exercises 10-K-only path). `governance_strong` confirmation marked as placeholder pending proxy_statement load.

## 13. Recommendation logic + Non-advice boundary

- **Action class:** `buy_candidate` (research action under the `quality_value_long_only` profile).
- **Conviction label:** `common_practice`.
- **Confidence drivers:** valuation_discount, margin_of_safety_present, cash_conversion_strength, moat_widening.
- **Downgrade reasons:** qualitative moat evidence only; consensus estimate connector locked (no I/B/E/S license).
- **Target price methodology:** DCF base $65 (range $55–$78); reverse-DCF cross-check passed.

> **Non-advice boundary (REQUIRED):** This memo is research output produced by the `viza.finance.equity_investment` v0.1 module against fictional fixture data. It does NOT constitute investment advice, a recommendation, or a solicitation. ExampleCo Industrial, Inc. is fictional; no real issuer is represented. Past performance does not predict future results. Users must consult licensed advisors before acting on any analysis.

## 14. Portfolio context note

Not attached for this fixture (decision.portfolio_context = null). Size-adjustment and hedge actions are unavailable until a portfolio_context is bound (per profile validation rule `size_action_requires_portfolio_context`).

## 15. Evidence appendix

Evidence chain references — see fixture.json `entities.evidence_bundle.items`:
- `ev_filing_001_revenue` — Revenue (TTM) from `fixture_filing_001` income statement.
- `ev_filing_001_op_inc` — Operating income (TTM).
- `ev_filing_001_fcf` — Free cash flow (TTM).
- `ev_filing_001_net_debt` — Net debt at FY end.
- `ev_filing_001_invested_capital` — Invested capital at FY end.
- `ev_filing_001_cfo` — Cash from operations (TTM).
- `ev_filing_001_net_income` — Net income (TTM).

All evidence inherits `license_policy=public_official` and `available_at = filing_accepted_at = 2025-02-15T16:30:00Z`.

## 16. PIT summary

- `PIT_safe`: **true**.
- `lookahead_risk`: **low**.
- Earliest input `available_at`: `2025-02-15T16:30:00Z` (filing).
- Latest input `available_at`: `2025-11-15T13:55:00Z` (thesis creation, 5 minutes before `decision_timestamp`).
- Decision timestamp: `2025-11-15T14:00:00Z`.
- Vintage status: market price uses decision-timestamp snapshot; filing-derived attributes use filing-accepted-at vintage; no revised-data leakage.

## 17. Rights summary

- Public-official sources (EDGAR + listing record): 6 objects, displayable + exportable.
- Internal-research-only artifacts (thesis, valuation_models, decision, validation_record, rights_policy): 6 objects, **export blocked**, **marketplace_policy=blocked**, **redaction_required=true**.
- Licensed connectors used: 0. Locked placeholders (consensus, borrow, options): 3.

## 18. Validation summary

- Pass: 21 / Warn: 2 / Fail: 0 / Not-applicable: 22.
- Warnings: `pit_latest_only_not_backtest_safe_factor_attribution_unused_in_this_run` (info); `qualitative_moat_evidence_only` (warn).
- Status: **passed** at `confidence_label=high_confidence_core` for the validation record itself.

## 19. Open questions

- I/B/E/S consensus integration when license is confirmed → enables earnings_revision_momentum + post_earnings_drift_radar profiles for the same name.
- Quantitative moat-durability evidence (ROIC stability vs sector, intangible-asset durability) → can elevate moat insight from `common_practice` to `high_confidence_core`.
- Proxy_statement load → enables `governance_strong` confirmation and unlocks `activism_vulnerability_radar` overlay.

---

**End of memo skeleton.**

Generated by `viza.finance.equity_investment v0.1.0` against fixture `first_wedge_v0.1`. Run ID `run_2025_11_15_first_wedge_v01`. Proof checksum: `computed_at_load_time`. Audit record: `validation_record_first_wedge_001`. **Not investment advice.**

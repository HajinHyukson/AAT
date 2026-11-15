# First-Wedge Fixture — `viza.finance.equity_investment v0.1`

**Path:** `docs/equity_module/v0.1/fixtures/first_wedge/`
**Status:** registry-seedable fixture; promotes to implementation-ready when the verifier passes against a running loader.
**Baseline:** Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening.

This fixture exercises the canonical happy path of the equity module end-to-end:

```text
public SEC filing -> fundamental attributes -> valuation/thesis -> insight -> strategy profile -> output -> validation -> package rights report
```

## 1. Files

| File | Purpose |
|---|---|
| `fixture.json` | All fixture inputs: entities (company / issuer / equity_security / listing / filing / evidence_bundle / thesis / valuation_models / decision / validation_record / rights_policy), 15 attributes, 5 lifecycle events, 7 insights, 6 validation-rule outcomes, decision object with full audit metadata. |
| `expected_validation_report.json` | Canonical rendered `validation_report` view (21 PASS / 2 WARN / 0 FAIL / 22 N/A across 43 rules; PIT-safe; rights summary intact). |
| `expected_source_rights_report.json` | Canonical rendered `source_rights_report` view: 7 connector roles (4 used public-official, 3 listed as locked placeholders), per-object redaction requirements, package visibility matrix. |
| `expected_memo_skeleton.md` | Canonical rendered `investment_memo` skeleton — 19 sections, fully filled, with explicit non-advice boundary at §13. |
| `expected_package_behavior.json` | Per-package-mode behaviour: `white_box`, `gray_box`, `black_box`, `output_only`, `preview`, `marketplace_draft` (the 3 user-listed modes plus 3 additional Phase-30/35 modes). |
| `verify_fixture.py` | Acceptance verifier: runs 10 acceptance check groups, emits stable SHA-256 hashes per file + canonical JSON. Exit 0 = pass. |
| `README.md` | This file. |

## 2. Fixture identity

- **Company:** ExampleCo Industrial, Inc. — **fictional**, no real-issuer identity represented.
- **Placeholder identifiers:** `co_exampleco_001` / `iss_exampleco_001` / `sec_exampleco_001` / CIK `0009999999` / LEI `EXAMPLECO9999999999LEI` / ticker display `EXAMPLE.US`.
- **Profile:** `quality_value_long_only`.
- **Decision timestamp:** `2025-11-15T14:00:00Z` (9 months after filing acceptance).
- **Run ID:** `run_2025_11_15_first_wedge_v01` (deterministic).

## 3. How to run

```bash
python docs/equity_module/v0.1/fixtures/first_wedge/verify_fixture.py
```

Expected output (last line):

```text
=== ALL FIRST-WEDGE ACCEPTANCE CHECKS PASSED ===
```

The verifier emits SHA-256 hashes for every artifact file plus a combined hash. The fixture is fully deterministic: re-running on unchanged inputs produces identical hashes.

## 4. Coverage matrix

| Fixture component (user-listed) | Where |
|---|---|
| Entity: company | `fixture.json` → `entities.company` |
| Entity: issuer | `entities.issuer` |
| Entity: equity_security | `entities.equity_security` |
| Entity: listing | `entities.listing` |
| Entity: filing | `entities.filing` (10-K FY2024 + fiscal_period inline) |
| Entity: fiscal_period | `entities.filing.fiscal_period` (inline inside the filing per registry §20.3) |
| Entity: evidence_bundle | `entities.evidence_bundle` (7 items, all from EDGAR filing) |
| Entity: thesis | `entities.thesis` (5 invalidation conditions, 7 supporting evidence refs) |
| Entity: valuation_model | `entities.valuation_model_dcf` (DCF) + `entities.valuation_model_relative` (peer multiples) |
| Entity: decision | `entities.decision` (action=buy_candidate, run_id, audit fields) |
| Entity: validation_record | `entities.validation_record` (43 rule outcomes + 2 warnings + 0 failures) |
| Entity: rights_policy | `entities.rights_policy` (public-official + internal-research-only inventory) |
| Attribute: revenue growth | `attributes` → `attr_revenue_growth_yoy_q` = 8.2% |
| Attribute: gross margin | `attr_gross_margin_ttm` = 38.5% |
| Attribute: operating margin | `attr_operating_margin_ttm` = 18.0% |
| Attribute: FCF margin | `attr_fcf_margin_ttm` = 12.0% |
| Attribute: ROIC | `attr_roic_ttm` = 18.0% |
| Attribute: leverage | `attr_net_debt_to_ebitda_ttm` = 1.80x |
| Attribute: cash conversion | `attr_cfo_to_ni_ttm` = 1.143; `attr_fcf_to_ni_ttm` = 0.906 |
| Attribute: valuation multiple | `attr_pe_ttm` = 14.0x; `attr_fcf_yield_ttm` = 6.48% |
| Attribute: DCF assumption | encoded in `valuation_model_dcf.assumptions` (3 with sensitivity bands) |
| Attribute: margin_of_safety flag | `attr_margin_of_safety_pct` = 25%; `attr_valuation_gap_pct` = 33.33% |
| Attribute: PIT status | `attr_pit_status` (`PIT_safe_flag` = true) |
| Attribute: rights status | `attr_rights_status` (export_status = conditional) |
| Event: filing_received | `events` → `evt_filing_received_001` |
| Event: thesis_created | `evt_thesis_created_001` |
| Event: validation_completed | `evt_validation_completed_001` |
| Event: output_rendered | `evt_output_rendered_001` |
| Event: package_rights_reviewed | `evt_package_rights_reviewed_001` |
| Insight: quality_value_candidate | composite of `ins_cash_conversion_strength` + `ins_margin_of_safety_present` + `ins_valuation_discount` + `ins_moat_widening` |
| Insight: margin_of_safety_present | `ins_margin_of_safety_present` |
| Insight: cash_conversion_strength | `ins_cash_conversion_strength` |
| Insight: balance_sheet_fragility | `ins_balance_sheet_fragility_absent` (result=absent, gate passes) |
| Insight: rights_export_status | `ins_rights_export_status` |
| Insight: PIT_warning | `ins_pit_status` (no warning emitted; flag explicit) |
| Validation: no lookahead | `validation_checks_explicit.no_lookahead` + `validation_record.checks[pit_no_lookahead]` = pass |
| Validation: evidence present | `validation_checks_explicit.evidence_present` + `validation_record.checks[evidence_thesis_requires_evidence_horizon_invalidation]` |
| Validation: thesis has invalidation | thesis has 5 invalidation_conditions |
| Validation: valuation has assumptions | dcf has 3 assumptions + 6-row sensitivity table |
| Validation: non-advice boundary | memo §13 + validation_report + rights_report all carry boundary text |
| Validation: package redacts restricted | marketplace_draft redaction_targets list 15 fields |
| Output: fixture graph JSON | `fixture.json` |
| Output: expected validation report | `expected_validation_report.json` |
| Output: expected source rights report | `expected_source_rights_report.json` |
| Output: rendered memo skeleton | `expected_memo_skeleton.md` |
| Output: expected package behavior | `expected_package_behavior.json` (6 modes documented) |

## 5. Acceptance criteria → verifier checks

| Criterion (user-listed) | Verifier check group |
|---|---|
| Fixture runs without future data | `[1] Fixture runs without future data (no lookahead)` |
| Public data only or licensed marked locked | `[2] Public-only data or explicitly locked licensed connectors` |
| Validation report surfaces all warnings | `[3] Validation report surfaces warnings` |
| Marketplace draft redacts restricted/unclear | `[4] marketplace_draft redacts restricted / unclear data` |
| Output contains non-advice boundary | `[5] Output contains non-advice boundary` |
| Test can be run repeatedly with stable hashes | `[9] Stable artifact hashes (file bytes)` + `[10] Stable canonical-JSON hashes` |

Additional verifier groups (defensive depth beyond the stated criteria):

- `[6] No ticker as primary key` — CLAUDE.md project rule.
- `[7] Thesis has invalidation conditions` — Section 19 validation requirement.
- `[8] Valuation has assumptions + sensitivity` — Section 7 validation requirement.

## 6. Stability contract

The fixture is fully deterministic:

- Every timestamp is fixed (filing 2025-02-15, thesis 2025-11-15T13:55, decision 2025-11-15T14:00, validation 14:00:01, rendering 14:00:05, rights review 14:00:10).
- Every value is fixed (revenue, margins, ratios, multiples, peer count, sensitivity grid).
- Every ID is fixed (run_id, decision_id, validation_record_id, evidence_ids).
- Every JSON file is canonical (indented 2 spaces, sort_keys=False but field order stable).

Stable hashes (recorded at first emission for regression detection):

```text
fixture_canonical_json_sha256              # computed at first verifier run; regress only when fixture changes
validation_report_canonical_json_sha256
source_rights_report_canonical_json_sha256
package_behavior_canonical_json_sha256
combined_file_sha256
```

To regenerate hashes after intentional changes, run the verifier and capture the new values.

## 7. Compatibility with existing engine

This fixture **does not run code in the engine**. It is a static reference exercise. Wiring it into the loaders defined by [docs/equity_module/v0.1/IMPLEMENTATION_PLAN_LOADERS.md](../IMPLEMENTATION_PLAN_LOADERS.md) is Phase 5 work in that plan.

When integrated:

- The verifier becomes part of `tests/unit/test_equity_first_wedge_fixture.py`.
- Golden hashes assert that loader+validator output matches the canonical artifacts byte-for-byte (after JSON canonicalisation).
- Any drift triggers a CI failure with a diff against `expected_*.json` / `expected_memo_skeleton.md`.

## 8. Non-advice boundary (required disclosure)

This fixture is research / engineering scaffolding only. It does not constitute investment advice, a recommendation, or a solicitation. ExampleCo Industrial, Inc. is fictional and does not represent any real issuer. Financial values are illustrative.

## 9. Open questions

1. Should the fixture include a second-wedge variant that exercises a licensed connector via mock (locked) entitlement? Recommendation: yes, but as a separate fixture (`second_wedge_licensed_locked/`).
2. Should the fixture include a PIT-violation negative case (lookahead, 13F current positioning) to confirm fail-closed behaviour? Recommendation: yes, as `invalid_records/first_wedge_with_lookahead.json` per [IMPLEMENTATION_PLAN_LOADERS.md §5.2](../IMPLEMENTATION_PLAN_LOADERS.md).
3. Should the fixture include AAT integration when the submodule ships? Recommendation: yes, as `third_wedge_aat_factor_attribution/`, gated on AAT module installation.

---

**End of README.md.**

# Package + Redaction Test Matrix (`viza.finance.equity_investment` v0.1)

**Path:** `docs/equity_module/v0.1/fixtures/package_redaction_tests/`
**Baseline:** Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening
**Source:** CLAUDE log §22 (Packaging Layer) + §23 (.viza Container) + §29 (Source Rights Enforcement)

This matrix verifies the package builder's per-source-class behaviour across all six package modes. It is the canonical regression anchor for the v0.1 packaging + rights enforcement rules.

## Files

| File | Purpose |
|---|---|
| `package_redaction_test_matrix.json` | Full test data: 11 sample data objects, 66 per-cell test cases (11 data x 6 modes), 5 integration scenarios, per-mode required sections, coverage maps, non-advice boundary |
| `verify_package_redaction.py` | Standalone verifier (19 check groups, exits 0 on PASS, emits stable SHA-256 hashes) |
| `README.md` | This file |

## Run

```bash
python docs/equity_module/v0.1/fixtures/package_redaction_tests/verify_package_redaction.py
```

Expected exit code: `0`. Final block:

```text
=== PACKAGE + REDACTION TEST MATRIX PASSED ===
```

## Sample data objects (11)

Each sample covers a distinct `license_policy` class so that the 6-mode matrix exercises every behaviour branch in the packaging layer.

| Data ID | Display name | License policy | Connector role | PIT-safe |
|---|---|---|---|---|
| `d01_edgar_filing_metadata` | Public EDGAR filing metadata (10-K) | `public_official` | `sec_filings` | true |
| `d02_derived_ratios_from_edgar` | Derived ratios from public XBRL | `derived_only` | `derived_calculation_engine` | true |
| `d03_fred_macro_current` | FRED macro current (latest_only) | `public_official` | `fred_macro` | `latest_only_until_alfred_pipeline` |
| `d04_alfred_macro_vintaged` | ALFRED-style vintaged macro | `public_official` | `alfred_macro_vintage` | true |
| `d05_finra_short_interest` | FINRA bi-weekly short interest | `public_official` | `finra_short_interest` | true |
| `d06_licensed_market_data` | Licensed market data placeholder | `licensed_provider_required` | `licensed_market_data_connector` | true |
| `d07_licensed_analyst_estimates` | Licensed estimates placeholder (I/B/E/S) | `licensed_provider_required` | `licensed_estimates_connector` | true |
| `d08_licensed_transcript_news` | Licensed transcript/news placeholder | `licensed_provider_required` | `licensed_text_connector` | true |
| `d09_user_portfolio_holdings` | User-private synthetic portfolio | `internal_research_only` | `user_portfolio_connector` | true |
| `d10_user_document_memo` | User-authored memo (private) | `internal_research_only` | `user_document_connector` | true |
| `d11_raw_social_news_unclear_rights` | Raw social/news with platform TOS restrictions | `restricted_or_unclear` | `licensed_text_connector` | `latest_only` |

## Package modes (6)

`white_box` | `gray_box` | `black_box` | `output_only` | `preview` | `marketplace_draft`

Per-mode required sections (what must be included, redacted, locked, externally referenced, validated, or block-triggered) are listed under `per_mode_required_sections` in the matrix JSON.

## Per-cell expected behaviour (11 x 6 = 66 cells)

For each `(data_id, package_mode)` pair the matrix records `{included, redacted, blocked, entitlement_locked, reason}`. Verifier `[5]` re-derives these from each sample's `license_policy` and asserts the matrix matches:

- `restricted_or_unclear` -> `blocked=true` in every mode.
- `licensed_provider_required` -> `entitlement_locked=true` in every mode.
- `internal_research_only` -> `blocked=true` in `marketplace_draft`, `included=true` in `white_box` (creator-only).
- `public_official` and `derived_only` -> never blocked, never entitlement-locked.

## Integration scenarios (5)

| ID | Description | Worst-case behaviour |
|---|---|---|
| `is01_successful_public_only_package` | All 6 modes succeed on public-only bundle (d01 + d02 + d04 + d05). | 0 blocked, 0 redacted, 0 locked across every mode. |
| `is02_blocked_export_unclear_rights` | Bundle contains d11 (unclear rights). | Every mode emits `>=1` blocked export; `marketplace_draft` refuses entirely. |
| `is03_entitlement_locked_licensed_data` | Bundle contains d06+d07+d08 (license_status=missing). | Each mode entitlement-locks 3 licensed objects; gray/black/output/preview/marketplace_draft redact raw values; white_box surfaces locked shells. |
| `is04_user_private_blocked_in_marketplace` | Bundle contains d09 + d10. | `white_box` includes (creator-only); shared modes redact; `marketplace_draft` BLOCKS d09 + d10 entirely. |
| `is05_redacted_marketplace_draft_mixed` | All 11 data types into `marketplace_draft`. | Refuses entirely because d11 is present; remediation = remove d11 and rebuild. |

## Acceptance criteria coverage

| Criterion | Where verified |
|---|---|
| Tests cover each package mode | `per_cell_test_matrix` exercises every `(data_id, package_mode)` pair = 66 cells; integration scenarios additionally bundle modes |
| At least one blocked-export case | 8 per-cell blocked + `is02` + `is05` |
| At least one entitlement-locked case | 18 per-cell + `is03` |
| At least one redacted marketplace_draft case | `tc_d06_marketplace_draft`, `tc_d07_marketplace_draft`, `tc_d08_marketplace_draft`, `is03.marketplace_draft`, `is05` |
| One successful public-only package | `is01` (all 6 modes built with 0 blocked / 0 redacted / 0 locked) |

## Test requirements coverage

Cross-references between the user-stated test requirements and the cases that satisfy them are recorded under `test_requirements_coverage` in the matrix JSON. Verifier `[14]` asserts every requirement maps to >=1 covering test case.

## Stable hashes (recorded at first verifier run)

| Artifact | sha256 (file bytes) | sha256 (canonical JSON) |
|---|---|---|
| `package_redaction_test_matrix.json` | `945c2e0c8b637b37066770b173676551554872f6d4055069ad1e84ad0cda932a` | `c3791ea2e817c14f802401c2d59be370e572efdb4fa87d7d87fe92cbecb863cc` |

Identical re-runs of the verifier produce identical hashes.

## How this wires into the runtime

When the loaders defined in [`../../IMPLEMENTATION_PLAN_LOADERS.md`](../../IMPLEMENTATION_PLAN_LOADERS.md) are implemented, Phase 7 of that plan adds a test module `tests/unit/test_equity_package_redaction.py` that:

1. Imports the matrix JSON.
2. For each per-cell case, constructs a minimal graph containing the named sample data object and invokes the equity package builder for the named mode.
3. Asserts `package_builder.build(mode)` returns the same `(included, redacted, blocked, entitlement_locked)` quad as the matrix cell.
4. For each integration scenario, asserts the composite outcome (`blocked_exports`, `redacted_objects`, `entitlement_locked_objects`, `user_private_objects_blocked`) matches.
5. Snapshot-tests the canonical SHA-256 of the rendered package per cell to detect any byte-level drift.

## Non-advice boundary

This matrix renders sample data behaviour under the equity module v0.1. It does NOT constitute investment advice. All issuer / portfolio / user identities are fictional. Past performance does not predict future results.

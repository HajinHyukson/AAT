#!/usr/bin/env python3
"""Verifier for the package + redaction test matrix.

Walks every per-cell test case (data_id x package_mode), every integration
scenario, every per_mode_required_sections entry, and the test_requirements +
acceptance_criteria coverage maps. Emits stable SHA-256 hashes for regression
anchoring.

Usage:
    python docs/equity_module/v0.1/fixtures/package_redaction_tests/verify_package_redaction.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MATRIX = HERE / "package_redaction_test_matrix.json"

EXPECTED_MODES = ["white_box", "gray_box", "black_box", "output_only", "preview", "marketplace_draft"]
EXPECTED_DATA_IDS = [
    "d01_edgar_filing_metadata",
    "d02_derived_ratios_from_edgar",
    "d03_fred_macro_current",
    "d04_alfred_macro_vintaged",
    "d05_finra_short_interest",
    "d06_licensed_market_data",
    "d07_licensed_analyst_estimates",
    "d08_licensed_transcript_news",
    "d09_user_portfolio_holdings",
    "d10_user_document_memo",
    "d11_raw_social_news_unclear_rights",
]
EXPECTED_INTEGRATION_SCENARIO_IDS = [
    "is01_successful_public_only_package",
    "is02_blocked_export_unclear_rights",
    "is03_entitlement_locked_licensed_data",
    "is04_user_private_blocked_in_marketplace",
    "is05_redacted_marketplace_draft_mixed",
]
REQUIRED_MODE_SECTION_KEYS = {
    "included_sections",
    "redacted_sections",
    "entitlement_locked_sections",
    "external_references",
    "validation_proof_required",
    "source_rights_summary_required",
    "audit_hashes_required",
    "non_advice_boundary_required",
    "export_block_triggers",
}

ALLOWED_LICENSE_POLICIES = {
    "public_official",
    "public_professional",
    "academic_public",
    "licensed_provider_required",
    "user_entitled_provider",
    "restricted_or_unclear",
    "derived_only",
    "internal_research_only",
    "unknown",
}


def _sha256_bytes(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_canonical_json(obj) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{mark}] {label}{suffix}")
    if not condition:
        sys.exit(1)


def main() -> int:
    m = json.loads(MATRIX.read_text(encoding="utf-8"))

    print("=== package + redaction test matrix verification ===")
    print(f"test_matrix_id      : {m['test_matrix_id']}")
    print(f"module_id           : {m['module_id']}")
    print(f"module_version      : {m['module_version']}")
    print(f"baseline            : {m['baseline']}")
    print(f"test_decision_ts    : {m['test_decision_timestamp']}")
    print()

    print("[1] Matrix top-level structural keys present")
    required_keys = [
        "test_matrix_id",
        "module_id",
        "module_version",
        "baseline",
        "sample_data_objects",
        "package_modes",
        "per_cell_test_matrix",
        "integration_scenarios",
        "per_mode_required_sections",
        "test_requirements_coverage",
        "acceptance_criteria_coverage",
        "non_advice_boundary",
    ]
    for k in required_keys:
        _check(f"matrix has key '{k}'", k in m)

    print()
    print("[2] Sample data objects: 11 entries, all expected ids present")
    data = m["sample_data_objects"]
    _check("11 sample_data_objects", len(data) == 11, f"count={len(data)}")
    for did in EXPECTED_DATA_IDS:
        _check(f"sample_data_objects contains {did}", did in data)
    for did, rec in data.items():
        _check(
            f"{did} license_policy in allowed set",
            rec["license_policy"] in ALLOWED_LICENSE_POLICIES,
            f"actual={rec['license_policy']}",
        )
        _check(f"{did} has display_name", isinstance(rec.get("display_name"), str) and len(rec["display_name"]) > 0)
        _check(f"{did} has connector_role", isinstance(rec.get("connector_role"), str) and len(rec["connector_role"]) > 0)
        _check(f"{did} has pit_safe field", "pit_safe" in rec)
        _check(f"{did} has example_payload", isinstance(rec.get("example_payload"), dict))
        _check(
            f"{did} no ticker as primary key in payload",
            "ticker" not in rec["example_payload"] or "security_id" in rec["example_payload"],
            "payload exposes ticker without security_id key" if "ticker" in rec["example_payload"] else "",
        )

    print()
    print("[3] Package modes: exactly the canonical 6 modes")
    modes = m["package_modes"]
    _check("6 package_modes", len(modes) == 6, f"count={len(modes)}")
    for mode in EXPECTED_MODES:
        _check(f"package_modes contains '{mode}'", mode in modes)

    print()
    print("[4] Per-cell test matrix has 66 entries covering every (data_id, mode) pair")
    cells = m["per_cell_test_matrix"]
    _check("66 per_cell_test_matrix entries", len(cells) == 66, f"count={len(cells)}")
    seen_pairs = set()
    for c in cells:
        pair = (c["data_id"], c["package_mode"])
        _check(f"no duplicate cell for {pair}", pair not in seen_pairs)
        seen_pairs.add(pair)
        _check(f"{c['test_case_id']} data_id is registered", c["data_id"] in EXPECTED_DATA_IDS)
        _check(f"{c['test_case_id']} package_mode is canonical", c["package_mode"] in EXPECTED_MODES)
        exp = c["expected"]
        for fld in ("included", "redacted", "blocked", "entitlement_locked", "reason"):
            _check(f"{c['test_case_id']} expected.{fld} present", fld in exp)
        _check(
            f"{c['test_case_id']} not both included and blocked",
            not (exp["included"] is True and exp["blocked"] is True),
            f"included={exp['included']} blocked={exp['blocked']}",
        )
        _check(f"{c['test_case_id']} reason non-empty", isinstance(exp["reason"], str) and len(exp["reason"]) > 0)
    for did in EXPECTED_DATA_IDS:
        for mode in EXPECTED_MODES:
            _check(f"cell exists for ({did}, {mode})", (did, mode) in seen_pairs)

    print()
    print("[5] Per-cell semantic rules: license policy -> expected behaviour")
    for c in cells:
        d = data[c["data_id"]]
        lp = d["license_policy"]
        exp = c["expected"]
        mode = c["package_mode"]
        if lp == "restricted_or_unclear":
            _check(
                f"{c['test_case_id']} restricted_or_unclear -> blocked True in every mode",
                exp["blocked"] is True and exp["included"] is False,
                f"got included={exp['included']} blocked={exp['blocked']}",
            )
        elif lp == "licensed_provider_required":
            _check(
                f"{c['test_case_id']} licensed_provider_required -> entitlement_locked True",
                exp["entitlement_locked"] is True,
                f"got entitlement_locked={exp['entitlement_locked']}",
            )
        elif lp == "internal_research_only":
            if mode == "marketplace_draft":
                _check(
                    f"{c['test_case_id']} internal_research_only -> blocked True in marketplace_draft",
                    exp["blocked"] is True,
                    f"got blocked={exp['blocked']}",
                )
            if mode == "white_box":
                _check(
                    f"{c['test_case_id']} internal_research_only -> included True in white_box (creator-only)",
                    exp["included"] is True,
                    f"got included={exp['included']}",
                )
        elif lp in {"public_official", "derived_only"}:
            _check(
                f"{c['test_case_id']} {lp} -> not blocked and not entitlement_locked",
                exp["blocked"] is False and exp["entitlement_locked"] is False,
                f"got blocked={exp['blocked']} entitlement_locked={exp['entitlement_locked']}",
            )

    print()
    print("[6] Integration scenarios: 5 entries, all expected ids present")
    scenarios = m["integration_scenarios"]
    _check("5 integration_scenarios", len(scenarios) == 5, f"count={len(scenarios)}")
    seen_scen_ids = set()
    for s in scenarios:
        sid = s["scenario_id"]
        _check(f"scenario {sid} not duplicated", sid not in seen_scen_ids)
        seen_scen_ids.add(sid)
        _check(f"scenario {sid} has description", isinstance(s.get("description"), str) and len(s["description"]) > 0)
        _check(f"scenario {sid} has input_data_ids list", isinstance(s.get("input_data_ids"), list) and len(s["input_data_ids"]) >= 1)
        for did in s["input_data_ids"]:
            _check(f"scenario {sid} input_data_id {did} is registered", did in EXPECTED_DATA_IDS)
        _check(f"scenario {sid} has modes_to_build", isinstance(s.get("modes_to_build"), list) and len(s["modes_to_build"]) >= 1)
        for mode in s["modes_to_build"]:
            _check(f"scenario {sid} mode '{mode}' is canonical", mode in EXPECTED_MODES)
        _check(f"scenario {sid} has expected_outcomes", isinstance(s.get("expected_outcomes"), dict))
        for mode in s["modes_to_build"]:
            _check(f"scenario {sid} expected_outcomes['{mode}'] present", mode in s["expected_outcomes"])
            _check(
                f"scenario {sid} expected_outcomes['{mode}'].status present",
                "status" in s["expected_outcomes"][mode],
            )
    for sid in EXPECTED_INTEGRATION_SCENARIO_IDS:
        _check(f"integration scenario {sid} present", sid in seen_scen_ids)

    print()
    print("[7] is01 successful public-only package: all 6 modes built with 0 blocked / 0 redacted / 0 locked")
    is01 = next(s for s in scenarios if s["scenario_id"] == "is01_successful_public_only_package")
    for mode in EXPECTED_MODES:
        out = is01["expected_outcomes"][mode]
        _check(f"is01 {mode} status=built", out["status"] == "built")
        _check(f"is01 {mode} blocked_exports=0", out.get("blocked_exports", -1) == 0)
        _check(f"is01 {mode} redacted_objects=0", out.get("redacted_objects", -1) == 0)
        _check(f"is01 {mode} entitlement_locked_objects=0", out.get("entitlement_locked_objects", -1) == 0)
    _check("is01 non_advice_boundary_required true", is01.get("non_advice_boundary_required") is True)

    print()
    print("[8] is02 blocked-export unclear rights: every mode reports a blocked_export for d11")
    is02 = next(s for s in scenarios if s["scenario_id"] == "is02_blocked_export_unclear_rights")
    _check("is02 d11 present in input", "d11_raw_social_news_unclear_rights" in is02["input_data_ids"])
    for mode in EXPECTED_MODES:
        out = is02["expected_outcomes"][mode]
        _check(f"is02 {mode} has >=1 blocked_export", out.get("blocked_exports", 0) >= 1)
        _check(
            f"is02 {mode} blocked_ids contains d11",
            "d11_raw_social_news_unclear_rights" in out.get("blocked_ids", []),
        )
    _check(
        "is02 emits restricted_or_unclear warning code",
        "restricted_or_unclear_rights_blocks_export" in is02.get("expected_warning_codes", []),
    )

    print()
    print("[9] is03 entitlement-locked licensed data: marketplace_draft built with redacted licensed objects")
    is03 = next(s for s in scenarios if s["scenario_id"] == "is03_entitlement_locked_licensed_data")
    for did in ("d06_licensed_market_data", "d07_licensed_analyst_estimates", "d08_licensed_transcript_news"):
        _check(f"is03 input contains {did}", did in is03["input_data_ids"])
    md = is03["expected_outcomes"]["marketplace_draft"]
    _check("is03 marketplace_draft status=built", md["status"] == "built")
    _check("is03 marketplace_draft entitlement_locked_objects=3", md["entitlement_locked_objects"] == 3)
    _check("is03 marketplace_draft redacted_objects=3", md["redacted_objects"] == 3)
    _check("is03 marketplace_draft blocked_exports=0", md["blocked_exports"] == 0)
    _check(
        "is03 emits licensed_provider warning",
        "licensed_provider_required_redacted_in_marketplace" in is03.get("expected_warning_codes", []),
    )

    print()
    print("[10] is04 user-private blocked in marketplace_draft")
    is04 = next(s for s in scenarios if s["scenario_id"] == "is04_user_private_blocked_in_marketplace")
    for did in ("d09_user_portfolio_holdings", "d10_user_document_memo"):
        _check(f"is04 input contains {did}", did in is04["input_data_ids"])
    md = is04["expected_outcomes"]["marketplace_draft"]
    _check("is04 marketplace_draft user_private_objects_blocked=2", md["user_private_objects_blocked"] == 2)
    _check(
        "is04 marketplace_draft blocked ids = d09 + d10",
        set(md.get("user_private_blocked_ids", [])) == {"d09_user_portfolio_holdings", "d10_user_document_memo"},
    )
    wb = is04["expected_outcomes"]["white_box"]
    _check(
        "is04 white_box includes 2 user-private objects (creator-only)",
        wb.get("user_private_objects_included", 0) == 2,
    )
    for mode in ("gray_box", "black_box", "output_only", "preview"):
        out = is04["expected_outcomes"][mode]
        _check(
            f"is04 {mode} redacts 2 user-private objects",
            out.get("user_private_objects_redacted", 0) == 2,
        )

    print()
    print("[11] is05 redacted marketplace_draft mixed (worst case)")
    is05 = next(s for s in scenarios if s["scenario_id"] == "is05_redacted_marketplace_draft_mixed")
    _check("is05 input has all 11 data ids", set(is05["input_data_ids"]) == set(EXPECTED_DATA_IDS))
    _check("is05 modes_to_build = ['marketplace_draft']", is05["modes_to_build"] == ["marketplace_draft"])
    md = is05["expected_outcomes"]["marketplace_draft"]
    _check("is05 marketplace_draft status=blocked_entirely", md["status"].startswith("blocked_entirely"))
    _check("is05 marketplace_draft blocked_exports >= 1", md["blocked_exports"] >= 1)
    _check(
        "is05 marketplace_draft blocked_ids contains d11",
        "d11_raw_social_news_unclear_rights" in md["blocked_ids"],
    )
    _check("is05 user_private_objects_blocked >= 2", md["user_private_objects_blocked"] >= 2)
    _check("is05 licensed_objects_redacted_if_built == 3", md["licensed_objects_redacted_if_built"] == 3)
    _check("is05 public_objects_preserved_if_built >= 4", md["public_objects_preserved_if_built"] >= 4)
    _check("is05 remediation present", isinstance(md.get("remediation"), str) and len(md["remediation"]) > 0)
    for wcode in (
        "restricted_or_unclear_rights_blocks_export",
        "user_private_data_blocked_in_marketplace_draft",
        "licensed_provider_required_redacted_in_marketplace",
    ):
        _check(f"is05 emits warning '{wcode}'", wcode in is05["expected_warning_codes"])

    print()
    print("[12] per_mode_required_sections: every mode declares the required keys")
    sections = m["per_mode_required_sections"]
    for mode in EXPECTED_MODES:
        _check(f"per_mode_required_sections has '{mode}'", mode in sections)
        sec = sections[mode]
        for k in REQUIRED_MODE_SECTION_KEYS:
            _check(f"{mode}.{k} present", k in sec)
        _check(f"{mode}.included_sections non-empty", isinstance(sec["included_sections"], list) and len(sec["included_sections"]) >= 1)
        _check(f"{mode}.redacted_sections is list", isinstance(sec["redacted_sections"], list))
        _check(f"{mode}.entitlement_locked_sections is list", isinstance(sec["entitlement_locked_sections"], list))
        _check(f"{mode}.audit_hashes_required is list", isinstance(sec["audit_hashes_required"], list) and len(sec["audit_hashes_required"]) >= 1)
        _check(f"{mode}.non_advice_boundary_required is True", sec["non_advice_boundary_required"] is True)
        _check(
            f"{mode}.export_block_triggers includes restricted_or_unclear language",
            any("restricted_or_unclear" in t for t in sec["export_block_triggers"]),
        )

    print()
    print("[13] marketplace_draft mode enforces extra constraints (user-private block, ticker block, monetized-marketplace block)")
    md_sec = sections["marketplace_draft"]
    _check(
        "marketplace_draft export_block_triggers includes user-private",
        any("user-private" in t for t in md_sec["export_block_triggers"]),
    )
    _check(
        "marketplace_draft export_block_triggers includes ticker-as-primary-key",
        any("ticker" in t for t in md_sec["export_block_triggers"]),
    )
    _check(
        "marketplace_draft export_block_triggers includes monetized marketplace",
        any("monetized marketplace" in t for t in md_sec["export_block_triggers"]),
    )
    _check("marketplace_draft validation_proof_required True", md_sec["validation_proof_required"] is True)
    _check("marketplace_draft source_rights_summary_required True", md_sec["source_rights_summary_required"] is True)

    print()
    print("[14] test_requirements_coverage: every requirement maps to >=1 covering test")
    trc = m["test_requirements_coverage"]
    expected_reqs = [
        "unknown_rights_block_export",
        "restricted_raw_redacted_in_marketplace_draft",
        "user_private_no_export_unless_explicit",
        "licensed_provider_entitlement_locked",
        "derived_values_inherit_most_restrictive",
        "public_metadata_displayable_raw_text_limited",
        "package_proof_includes_rights_and_pit_summary",
    ]
    for req in expected_reqs:
        _check(f"test_requirements_coverage has '{req}'", req in trc)
        cov = trc[req].get("covered_by", [])
        _check(f"  '{req}' covered_by non-empty", isinstance(cov, list) and len(cov) >= 1)

    print()
    print("[15] acceptance_criteria_coverage: all 5 user-listed acceptance criteria satisfied")
    acc = m["acceptance_criteria_coverage"]
    expected_criteria = [
        "tests_cover_each_package_mode",
        "at_least_one_blocked_export_case",
        "at_least_one_entitlement_locked_case",
        "at_least_one_redacted_marketplace_draft_case",
        "one_successful_public_only_package",
    ]
    for crit in expected_criteria:
        _check(f"acceptance_criteria_coverage has '{crit}'", crit in acc)
        entry = acc[crit]
        _check(f"  '{crit}' has satisfied_by", "satisfied_by" in entry)
        sb = entry["satisfied_by"]
        _check(f"  '{crit}' satisfied_by non-empty", (isinstance(sb, str) and len(sb) > 0) or (isinstance(sb, list) and len(sb) >= 1))

    print()
    print("[16] Live re-derivation of acceptance criteria from per_cell_test_matrix + integration_scenarios")
    modes_covered_per_cell = {c["package_mode"] for c in cells}
    _check("modes covered by per_cell_test_matrix == 6", modes_covered_per_cell == set(EXPECTED_MODES), f"covered={sorted(modes_covered_per_cell)}")
    blocked_cells = [c for c in cells if c["expected"]["blocked"] is True]
    _check(f"at least one blocked-export cell (got {len(blocked_cells)})", len(blocked_cells) >= 1)
    entitlement_locked_cells = [c for c in cells if c["expected"]["entitlement_locked"] is True]
    _check(f"at least one entitlement-locked cell (got {len(entitlement_locked_cells)})", len(entitlement_locked_cells) >= 1)
    redacted_marketplace_cells = [
        c for c in cells
        if c["package_mode"] == "marketplace_draft" and c["expected"]["redacted"] is True
    ]
    _check(f"at least one redacted marketplace_draft cell (got {len(redacted_marketplace_cells)})", len(redacted_marketplace_cells) >= 1)
    is01_all_built = all(
        is01["expected_outcomes"][mode]["status"] == "built"
        for mode in EXPECTED_MODES
    )
    _check("is01 = one successful public-only package across all 6 modes", is01_all_built)

    print()
    print("[17] Non-advice boundary text present and references fictional identities")
    nab = m.get("non_advice_boundary", "")
    _check("non_advice_boundary present", isinstance(nab, str) and len(nab) > 0)
    _check("non_advice_boundary mentions 'investment advice'", "investment advice" in nab.lower())
    _check("non_advice_boundary mentions 'fictional'", "fictional" in nab.lower())

    print()
    print("[18] No ticker used as primary key anywhere in sample data payloads")
    for did, rec in data.items():
        payload = rec.get("example_payload", {})
        if "ticker" in payload and "security_id" not in payload:
            _check(f"{did} payload has security_id when ticker present", False, "ticker present without security_id")
    _check("no ticker-as-primary-key violation across 11 sample objects", True)

    print()
    print("[19] Stable hashes")
    file_h = _sha256_bytes(MATRIX)
    canon_h = _sha256_canonical_json(m)
    print(f"     matrix_file_sha256       : {file_h}")
    print(f"     matrix_canonical_sha256  : {canon_h}")

    print()
    print("=== ACCEPTANCE CRITERIA SUMMARY ===")
    print(f"  [1] Tests cover each package mode                    : PASS (6/6 modes, 66 per-cell tests)")
    print(f"  [2] At least one blocked-export case                  : PASS ({len(blocked_cells)} per-cell blocked + integration is02 + is05)")
    print(f"  [3] At least one entitlement-locked case              : PASS ({len(entitlement_locked_cells)} per-cell + integration is03)")
    print(f"  [4] At least one redacted marketplace_draft case      : PASS ({len(redacted_marketplace_cells)} per-cell + integration is03)")
    print(f"  [5] One successful public-only package                : PASS (integration is01, all 6 modes built)")
    print()
    print("=== PACKAGE + REDACTION TEST MATRIX PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

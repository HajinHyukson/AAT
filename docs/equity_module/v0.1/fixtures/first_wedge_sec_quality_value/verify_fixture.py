#!/usr/bin/env python3
"""
Verifier for the first-wedge fixture.

Runs the canonical acceptance assertions and emits stable SHA-256 hashes that
must remain identical on every re-run with the same fixture inputs.

Usage:
    python docs/equity_module/v0.1/fixtures/first_wedge/verify_fixture.py

Exit code 0 on success, 1 on failure.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

ARTIFACTS = {
    "fixture": HERE / "fixture.json",
    "validation_report": HERE / "expected_validation_report.json",
    "source_rights_report": HERE / "expected_source_rights_report.json",
    "memo_skeleton": HERE / "expected_memo_skeleton.md",
    "package_behavior": HERE / "expected_package_behavior.json",
}


def _sha256_bytes(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_canonical_json(obj: dict) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def _check(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{mark}] {label}{suffix}")
    if not condition:
        sys.exit(1)


def main() -> int:
    fixture = json.loads(ARTIFACTS["fixture"].read_text(encoding="utf-8"))
    validation_report = json.loads(ARTIFACTS["validation_report"].read_text(encoding="utf-8"))
    rights_report = json.loads(ARTIFACTS["source_rights_report"].read_text(encoding="utf-8"))
    package_behavior = json.loads(ARTIFACTS["package_behavior"].read_text(encoding="utf-8"))

    print("=== first-wedge fixture verification ===")
    print(f"fixture_id          : {fixture['fixture_id']}")
    print(f"module_id           : {fixture['fixture_module_id']}")
    print(f"module_version      : {fixture['fixture_module_version']}")
    print(f"run_id              : {fixture['fixture_run_id']}")
    print(f"decision_timestamp  : {fixture['fixture_decision_timestamp']}")
    print(f"strategy_profile_id : {fixture['fixture_strategy_profile_id']}")
    print()

    # ---- Acceptance criterion: fixture runs without future data (no lookahead) ----
    print("[1] Fixture runs without future data (no lookahead)")
    decision_ts = fixture["fixture_decision_timestamp"]
    filing_available_at = fixture["entities"]["filing"]["pit"]["available_at"]
    thesis_event_ts = fixture["events"][1]["available_at"]
    _check(
        "filing.available_at <= decision_timestamp",
        filing_available_at <= decision_ts,
        f"filing={filing_available_at} decision={decision_ts}",
    )
    _check(
        "thesis_created_event.available_at <= decision_timestamp",
        thesis_event_ts <= decision_ts,
        f"thesis={thesis_event_ts} decision={decision_ts}",
    )
    decision = fixture["entities"]["decision"]
    _check(
        "decision.pit_status.PIT_safe is true",
        decision["pit_status"]["PIT_safe"] is True,
    )
    _check(
        "decision.pit_status.lookahead_risk is 'low'",
        decision["pit_status"]["lookahead_risk"] == "low",
    )

    # ---- Acceptance criterion: public data only or licensed marked locked ----
    print("[2] Public-only data or explicitly locked licensed connectors")
    rights_in_use = set()
    def _walk(node):
        if isinstance(node, dict):
            if "rights" in node and isinstance(node["rights"], dict):
                lp = node["rights"].get("license_policy")
                if lp:
                    rights_in_use.add(lp)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)
    _walk(fixture)
    _check(
        "only public_official / internal_research_only licenses in fixture",
        rights_in_use.issubset({"public_official", "internal_research_only"}),
        f"actual={sorted(rights_in_use)}",
    )

    # ---- Acceptance criterion: validation report surfaces all warnings ----
    print("[3] Validation report surfaces warnings")
    warnings = validation_report["sections"]["warnings"]
    _check(
        "validation_report has 2 warnings",
        len(warnings) == 2,
        f"count={len(warnings)}",
    )
    warning_codes = {w["code"] for w in warnings}
    _check(
        "warnings include pit_latest_only and qualitative_moat",
        "pit_latest_only_not_backtest_safe_factor_attribution_unused_in_this_run" in warning_codes
        and "qualitative_moat_evidence_only" in warning_codes,
    )
    counts = validation_report["sections"]["validation_records"]["summary_counts"]
    _check(
        "summary_counts.fail == 0 AND summary_counts.block == 0",
        counts["fail"] == 0 and counts["block"] == 0,
    )
    _check(
        "summary_counts.pass == 21 (matches expected validation_rule applicability for quality_value_long_only)",
        counts["pass"] == 21,
    )

    # ---- Acceptance criterion: marketplace_draft redacts restricted/unclear data ----
    print("[4] marketplace_draft redacts restricted / unclear data")
    md = package_behavior["package_modes"]["marketplace_draft"]
    _check(
        "marketplace_draft redaction_required is true",
        md["redaction_required"] is True,
    )
    _check(
        "marketplace_draft.contains.non_advice_boundary == 'REQUIRED on every section'",
        md["contains"]["non_advice_boundary"] == "REQUIRED on every section",
    )
    redaction_targets = md["redaction_targets"]
    _check(
        "marketplace_draft redacts thesis claim",
        any("thesis_exampleco_qvalue_001.claim" == t for t in redaction_targets),
    )
    _check(
        "marketplace_draft redacts valuation intrinsic_value + sensitivity + margin_of_safety",
        all(
            t in redaction_targets
            for t in (
                "valuation_model_exampleco_dcf_001.outputs.intrinsic_value_per_share",
                "valuation_model_exampleco_dcf_001.sensitivity_table_values",
                "valuation_model_exampleco_dcf_001.margin_of_safety_pct",
            )
        ),
    )
    _check(
        "marketplace_draft redacts decision_rationale",
        "decision_exampleco_001.decision_rationale" in redaction_targets,
    )
    _check(
        "marketplace_endpoint_supported is false",
        md["marketplace_endpoint_supported"] is False,
    )

    # ---- Acceptance criterion: output contains non-advice boundary ----
    print("[5] Output contains non-advice boundary")
    _check(
        "validation_report.non_advice_boundary present",
        bool(validation_report.get("non_advice_boundary", "").strip()),
    )
    _check(
        "source_rights_report.non_advice_boundary present",
        bool(rights_report.get("non_advice_boundary", "").strip()),
    )
    memo = ARTIFACTS["memo_skeleton"].read_text(encoding="utf-8")
    _check(
        "memo §13 contains 'Non-advice boundary'",
        "Non-advice boundary" in memo,
    )
    _check(
        "memo contains 'NOT constitute investment advice'",
        "NOT constitute investment advice" in memo,
    )

    # ---- Acceptance criterion: no ticker as primary key ----
    print("[6] No ticker as primary key")
    sec = fixture["entities"]["equity_security"]
    _check(
        "equity_security.immutable_keys excludes 'ticker'",
        "ticker" not in sec["immutable_keys"],
    )
    _check(
        "company.immutable_keys == ['company_id']",
        fixture["entities"]["company"]["immutable_keys"] == ["company_id"],
    )
    _check(
        "equity_security.immutable_keys == ['security_id']",
        sec["immutable_keys"] == ["security_id"],
    )
    _check(
        "ticker is stored under identifiers.ticker_display only",
        "ticker_display" in sec["identifiers"] and "ticker" not in sec["identifiers"],
    )

    # ---- Acceptance criterion: thesis has invalidation ----
    print("[7] Thesis has invalidation conditions")
    thesis = fixture["entities"]["thesis"]
    _check(
        "thesis.invalidation_conditions has >= 1 entry",
        len(thesis["invalidation_conditions"]) >= 1,
        f"count={len(thesis['invalidation_conditions'])}",
    )

    # ---- Acceptance criterion: valuation has assumptions + sensitivity ----
    print("[8] Valuation has assumptions + sensitivity")
    dcf = fixture["entities"]["valuation_model_dcf"]
    _check(
        "dcf.assumptions has >= 3 entries",
        len(dcf["assumptions"]) >= 3,
    )
    _check(
        "dcf.sensitivity_table has >= 4 entries",
        len(dcf["sensitivity_table"]) >= 4,
    )
    relative = fixture["entities"]["valuation_model_relative"]
    _check(
        "relative_valuation.peer_set.peer_count >= 5",
        relative["peer_set"]["peer_count"] >= 5,
    )

    # ---- Acceptance criterion: test runs repeatedly with stable hashes ----
    print("[9] Stable artifact hashes (file bytes)")
    file_hashes = {label: _sha256_bytes(p) for label, p in ARTIFACTS.items()}
    for label, sha in file_hashes.items():
        print(f"     {label:24s}: {sha}")

    canonical_hashes = {
        "fixture_canonical_json_sha256": _sha256_canonical_json(fixture),
        "validation_report_canonical_json_sha256": _sha256_canonical_json(validation_report),
        "source_rights_report_canonical_json_sha256": _sha256_canonical_json(rights_report),
        "package_behavior_canonical_json_sha256": _sha256_canonical_json(package_behavior),
    }
    print("[10] Stable canonical-JSON hashes")
    for label, sha in canonical_hashes.items():
        print(f"     {label}: {sha}")

    combined = hashlib.sha256()
    for label in sorted(file_hashes):
        combined.update(file_hashes[label].encode("utf-8"))
    print(f"     combined_file_sha256: {combined.hexdigest()}")

    print()
    print("=== ALL FIRST-WEDGE ACCEPTANCE CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

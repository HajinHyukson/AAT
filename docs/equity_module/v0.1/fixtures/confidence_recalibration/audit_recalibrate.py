#!/usr/bin/env python3
"""Confidence recalibration + downgrade audit for v0.1 artifacts.

Walks every record in every registry, answers the 10 audit questions,
applies the downgrade rules, and emits:
  - equity_rejection_and_downgrade_log.csv
  - per-record findings (cached as JSON for the report writer)

Run:
    python docs/equity_module/v0.1/fixtures/confidence_recalibration/audit_recalibrate.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "registries"
OUT = Path(__file__).resolve().parent

JSON_REGISTRIES = [
    "equity_entity_types",
    "equity_node_types",
    "equity_edge_types",
    "equity_event_registry_seed",
    "equity_insight_registry_seed",
    "equity_strategy_profiles",
    "equity_output_views",
    "equity_validation_rules",
    "equity_connector_requirements",
]

CONFIDENCE_LADDER = [
    "high_confidence_core",
    "common_practice",
    "research_supported_experimental",
    "practitioner_observed",
    "speculative_or_low_confidence",
    "rejected_or_deferred",
]


def load_items(name: str):
    d = json.loads((REG / f"{name}.json").read_text(encoding="utf-8"))
    items_key = None
    for k, v in d.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            items_key = k
            break
    return d, items_key, d.get(items_key, [])


def _has_pit(it: dict) -> bool:
    pit = it.get("pit")
    if not isinstance(pit, dict):
        return False
    return bool(pit.get("available_at_policy") or pit.get("observed_at_policy"))


def _has_rights(it: dict) -> tuple[bool, str]:
    rights = it.get("rights")
    if not isinstance(rights, dict):
        return False, "rights_block_missing"
    lp = rights.get("license_policy")
    if not lp:
        return False, "license_policy_missing"
    if lp == "unknown":
        return False, "license_policy_unknown"
    return True, lp


def _has_failure_modes(it: dict) -> bool:
    fm = it.get("failure_modes") or []
    return isinstance(fm, list) and len(fm) >= 1


def _has_validation(it: dict) -> bool:
    vr = it.get("validation_rules") or []
    return isinstance(vr, list) and len(vr) >= 1


def _has_source(it: dict) -> bool:
    return bool(it.get("source_ids")) and bool(it.get("source_sections"))


def _has_compatible_profile(it: dict) -> bool:
    cp = it.get("compatible_strategy_profiles") or []
    return isinstance(cp, list) and len(cp) >= 1


def _has_fallback_metadata(it: dict) -> bool:
    fam = it.get("family_specific") or {}
    if fam.get("public_fallback") or fam.get("fallback_active") or fam.get("fallback") or fam.get("path_b_public_fallback"):
        return True
    pit = it.get("pit") or {}
    if pit.get("fallback"):
        return True
    return False


def _is_statistical(it: dict) -> bool:
    desc = (it.get("description") or "").lower()
    name = (it.get("display_name") or "").lower()
    sig = " ".join([desc, name])
    keys = ["factor", "regression", "beta", "z-score", "z_score", "rolling window", "rolling-window", "decile", "quintile", "rank-based", "percentile rank", "covariance", "correlation", "statistical"]
    return any(k in sig for k in keys)


def _is_sentiment_or_rumor(it: dict) -> bool:
    desc = (it.get("description") or "").lower()
    name = (it.get("display_name") or "").lower()
    sig = " ".join([desc, name])
    keys = ["rumor", "sentiment", "social media", "social-media", "tweet", "x_twitter", "stocktwits", "reddit", "8chan", "novelty", "credibility"]
    return any(k in sig for k in keys)


def _has_oos_guard(it: dict) -> bool:
    fam = it.get("family_specific") or {}
    for k, v in fam.items():
        kk = str(k).lower()
        if any(t in kk for t in ["out_of_sample", "oos", "multiple_testing", "cost_adjusted", "liquidity_adjusted", "deflated_sharpe", "white_reality_check"]):
            return True
    return False


def _has_source_credibility_guard(it: dict) -> bool:
    fam = it.get("family_specific") or {}
    for k, v in fam.items():
        kk = str(k).lower()
        if any(t in kk for t in ["credibility", "manipulation", "source_quality", "verification", "corroboration", "human_review"]):
            return True
    if it.get("human_review_required"):
        return True
    return False


def downgrade(current: str, issues: list[str]) -> tuple[str, str]:
    """Pick a new label from the ladder given the current label + issues."""
    if not issues:
        return current, ""
    # severity buckets:
    # - blocking: missing fundamentals (PIT, rights, source) -> drop two levels
    # - heavy: validation / statistical / sentiment gaps -> drop two levels
    # - moderate: licensed dependency / failure_modes / compatibility -> drop one level
    blocking = {"rights_policy_missing", "rights_policy_unknown", "license_policy_missing", "pit_policy_missing", "source_lineage_missing"}
    heavy = {"validation_rules_missing", "statistical_no_oos_review", "sentiment_no_credibility_guard"}
    moderate = {"failure_modes_missing", "no_compatible_profile", "licensed_no_fallback", "practitioner_only_but_hcc"}
    has_blocking = any(i in blocking for i in issues)
    has_heavy = any(i in heavy for i in issues)
    has_moderate = any(i in moderate for i in issues)

    if current == "high_confidence_core":
        if has_blocking or has_heavy:
            return "research_supported_experimental", ";".join(issues)
        elif has_moderate:
            return "common_practice", ";".join(issues)
    elif current == "common_practice":
        if has_blocking:
            return "research_supported_experimental", ";".join(issues)
        elif has_heavy:
            return "research_supported_experimental", ";".join(issues)
        elif has_moderate:
            return "common_practice", ""  # already at common_practice; do not double-downgrade for moderate alone
    elif current == "research_supported_experimental":
        if "rights_policy_missing" in issues or "license_policy_missing" in issues:
            return "practitioner_observed", ";".join(issues)
    return current, ""


def audit_record(it: dict, registry: str) -> dict:
    issues: list[str] = []

    if not _has_source(it):
        issues.append("source_lineage_missing")
    if not _has_pit(it):
        issues.append("pit_policy_missing")
    rights_ok, rights_detail = _has_rights(it)
    if not rights_ok:
        issues.append(rights_detail if rights_detail != "rights_block_missing" else "rights_policy_missing")
    # validation_rules check: exempt the validation-rules registry itself (rules don't refer to other rules)
    if registry != "equity_validation_rules" and not _has_validation(it):
        issues.append("validation_rules_missing")
    if not _has_failure_modes(it):
        issues.append("failure_modes_missing")

    if registry not in ("equity_strategy_profiles", "equity_output_views", "equity_validation_rules", "equity_connector_requirements", "equity_entity_types", "equity_edge_types"):
        if not _has_compatible_profile(it):
            issues.append("no_compatible_profile")

    rights = it.get("rights") or {}
    lp = rights.get("license_policy", "")
    if lp == "licensed_provider_required" and registry in ("equity_node_types", "equity_event_registry_seed", "equity_insight_registry_seed", "equity_strategy_profiles"):
        if not _has_fallback_metadata(it):
            issues.append("licensed_no_fallback")

    # statistical check: only flag for compute-class core primitives
    cp = (it.get("core_primitive") or "").lower()
    compute_primitives = {"attribute_computation", "derived_signal", "model_compute", "factor_decomposition", "regression", "computation", "scoring", "ranker", "classifier"}
    if registry in ("equity_insight_registry_seed", "equity_node_types") and _is_statistical(it) and (cp in compute_primitives or not cp):
        if not _has_oos_guard(it):
            issues.append("statistical_no_oos_review")

    if registry in ("equity_insight_registry_seed", "equity_event_registry_seed", "equity_node_types") and _is_sentiment_or_rumor(it):
        if not _has_source_credibility_guard(it):
            issues.append("sentiment_no_credibility_guard")

    current = it.get("confidence_label") or "unknown"
    sqm = it.get("source_quality_minimum")
    if current == "high_confidence_core" and (sqm is not None and sqm < 4):
        issues.append("practitioner_only_but_hcc")

    suggested, reason = downgrade(current, issues)

    return {
        "object_id": it.get("id"),
        "registry": registry,
        "display_name": it.get("display_name"),
        "current_label": current,
        "issues": ";".join(issues),
        "suggested_label": suggested,
        "downgrade_reason": reason,
        "changed": suggested != current,
        "rejected": suggested == "rejected_or_deferred",
        "source_quality_minimum": sqm,
        "compatible_strategy_profiles": it.get("compatible_strategy_profiles") or [],
        "license_policy": lp,
    }


def audit_attribute_csv() -> list[dict]:
    rows = list(csv.DictReader((REG / "equity_attribute_registry_seed.csv").open(encoding="utf-8")))
    findings = []
    for r in rows:
        issues = []
        if not (r.get("source_ids") and r.get("source_sections")):
            issues.append("source_lineage_missing")
        if not (r.get("observed_at_policy") and r.get("available_at_policy")):
            issues.append("pit_policy_missing")
        if not (r.get("entitlement_policy") and r.get("export_policy") and r.get("redistribution_policy")):
            issues.append("rights_policy_missing")
        if not r.get("validation_requirements"):
            issues.append("validation_rules_missing")
        if not r.get("failure_modes"):
            issues.append("failure_modes_missing")
        if not r.get("compatible_strategy_profiles"):
            issues.append("no_compatible_profile")

        ep = r.get("entitlement_policy", "")
        if ep == "licensed_provider_required":
            if "fallback" not in (r.get("limitations") or "").lower() and "fallback" not in (r.get("description") or "").lower():
                issues.append("licensed_no_fallback")

        desc = (r.get("description") or "").lower() + " " + (r.get("display_name") or "").lower()
        if any(k in desc for k in ["factor", "regression", "beta", "z-score", "z_score", "rolling", "decile", "quintile", "correlation"]):
            if not any(t in (r.get("validation_requirements") or "").lower() for t in ["oos", "out_of_sample", "multiple_testing", "deflated_sharpe", "cost_adjusted", "liquidity_adjusted"]):
                issues.append("statistical_no_oos_review")
        if any(k in desc for k in ["sentiment", "rumor", "social"]):
            if "credibility" not in (r.get("validation_requirements") or "").lower() and "manipulation" not in (r.get("validation_requirements") or "").lower():
                issues.append("sentiment_no_credibility_guard")

        current = r.get("confidence_label", "unknown")
        suggested, reason = downgrade(current, issues)
        findings.append({
            "object_id": r.get("key"),
            "registry": "equity_attribute_registry_seed",
            "display_name": r.get("display_name"),
            "current_label": current,
            "issues": ";".join(issues),
            "suggested_label": suggested,
            "downgrade_reason": reason,
            "changed": suggested != current,
            "rejected": suggested == "rejected_or_deferred",
            "source_quality_minimum": None,
            "compatible_strategy_profiles": (r.get("compatible_strategy_profiles") or "").split("|"),
            "license_policy": ep,
        })
    return findings


def main() -> int:
    findings: list[dict] = []
    counts_by_registry = {}

    for fname in JSON_REGISTRIES:
        _, _, items = load_items(fname)
        per_registry_changed = 0
        for it in items:
            f = audit_record(it, fname)
            findings.append(f)
            if f["changed"]:
                per_registry_changed += 1
        counts_by_registry[fname] = {"total": len(items), "changed": per_registry_changed}

    attr_findings = audit_attribute_csv()
    findings.extend(attr_findings)
    counts_by_registry["equity_attribute_registry_seed"] = {
        "total": len(attr_findings),
        "changed": sum(1 for f in attr_findings if f["changed"]),
    }

    # Write CSV log
    csv_path = OUT / "equity_rejection_and_downgrade_log.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "object_id", "registry", "display_name", "current_label", "issues",
            "suggested_label", "downgrade_reason", "changed", "rejected",
            "source_quality_minimum", "license_policy",
        ])
        w.writeheader()
        for f in findings:
            row = {k: ("|".join(v) if isinstance(v, list) else v) for k, v in f.items() if k != "compatible_strategy_profiles"}
            w.writerow(row)

    # Cache findings JSON for the report writer
    cache_path = OUT / "_findings_cache.json"
    cache_path.write_text(
        json.dumps({
            "findings": [{k: v for k, v in f.items()} for f in findings],
            "counts_by_registry": counts_by_registry,
        }, indent=2, default=str),
        encoding="utf-8",
    )

    total = len(findings)
    changed = sum(1 for f in findings if f["changed"])
    print(f"audit complete: {total} records audited, {changed} downgrades suggested")
    print(f"log: {csv_path}")
    print(f"cache: {cache_path}")
    print()
    print("per-registry totals:")
    for name, stats in counts_by_registry.items():
        print(f"  {name:50s} total={stats['total']:>4d}  changed={stats['changed']:>4d}")

    label_distribution = Counter(f["suggested_label"] for f in findings)
    print()
    print("suggested-label distribution after audit:")
    for label in CONFIDENCE_LADDER:
        if label in label_distribution:
            print(f"  {label:45s} {label_distribution[label]:>4d}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

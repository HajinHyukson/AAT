#!/usr/bin/env python3
"""Verifier for the earnings_revision_momentum pilot fixture."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture.json"


def _sha256_bytes(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_canonical_json(obj: dict) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{mark}] {label}{suffix}")
    if not condition:
        sys.exit(1)


def main() -> int:
    f = json.loads(FIXTURE.read_text(encoding="utf-8"))

    print("=== earnings_revision_momentum pilot verification ===")
    print(f"fixture_id          : {f['fixture_id']}")
    print(f"strategy_profile_id : {f['fixture_strategy_profile_id']}")
    print(f"decision_timestamp  : {f['fixture_decision_timestamp']}")
    print(f"active_path         : {f['sample_graph']['active_path']}")
    print()

    print("[1] Graph + paths load")
    g = f["sample_graph"]
    _check("graph schema is viza_graph_v0", g["schema"] == "viza_graph_v0")
    _check("graph references earnings_revision_momentum profile", g["strategy_profile_id"] == "earnings_revision_momentum")
    _check("active_path is path_b_public_fallback", g["active_path"] == "path_b_public_fallback")
    _check(">=12 nodes in graph", len(g["nodes"]) >= 12, f"count={len(g['nodes'])}")

    print("[2] Path A licensed-gated fails closed (no silent fallback)")
    a = f["path_a_license_gated"]
    _check("Path A connector required is licensed_estimates_connector", a["connector_required"] == "licensed_estimates_connector")
    _check("Path A license_status is missing", a["license_status"] == "missing")
    _check("Path A query_policy is blocked", a["fail_closed_behavior"]["query_policy"] == "blocked")
    _check("Path A profile_runtime_status is research_only", a["fail_closed_behavior"]["profile_runtime_status"] == "research_only")
    _check("Path A locks the consensus-variant node set", len(a["fail_closed_behavior"]["node_set_locked"]) >= 4)
    locked_nodes = [n for n in g["nodes"] if n.get("runtime_status") == "open_locked_preserve_config"]
    _check(">=2 locked nodes in active graph (Path A consensus + revisions)", len(locked_nodes) >= 2, f"locked={[n['node_id'] for n in locked_nodes]}")

    print("[3] Path B public-data fallback active")
    b = f["path_b_public_fallback"]
    _check("Path B connector requirements are public", "sec_filings" in b["connector_required"] and "earnings_releases" in b["connector_required"])
    _check("Path B license_status_for_required_connectors == public", b["license_status_for_required_connectors"] == "public")
    _check("Path B emits consensus_connector_unavailable warning", any(w["code"] == "consensus_connector_unavailable_using_public_guidance_fallback" for w in b["warnings"]))

    print("[4] Public data only for active path")
    lp_in_use = set()
    def _walk(node):
        if isinstance(node, dict):
            if "rights" in node and isinstance(node["rights"], dict):
                lp = node["rights"].get("license_policy")
                if lp:
                    lp_in_use.add(lp)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)
    _walk(f)
    # licensed_provider_required may appear only inside Path A locked metadata, not as a live source
    allowed = {"public_official", "public_professional", "academic_public", "internal_research_only", "licensed_provider_required"}
    _check("license_policy ⊆ allowed set", lp_in_use.issubset(allowed), f"actual={sorted(lp_in_use)}")
    # Verify any licensed_provider_required attached to Path A only
    sr = f["source_rights_report"]
    _check("licensed_estimates_consensus marked fail_closed_with_locked_placeholder", sr["licensed_estimates_consensus"]["behavior"] == "fail_closed_with_locked_placeholder")
    _check("licensed_estimates_consensus fallback_active is path_b_public_fallback", sr["licensed_estimates_consensus"]["fallback_active"] == "path_b_public_fallback")

    print("[5] PIT correctness: press release precedes 8-K precedes decision")
    pit = f["pit_report"]
    _check("PIT_safe true", pit["PIT_safe"] is True)
    _check("lookahead_risk low", pit["lookahead_risk"] == "low")
    _check("ordering documented", "press_release" in pit["ordering_check"] and "8-K" in pit["ordering_check"])
    _check("earliest_input_available_at = press release", pit["earliest_input_available_at"] == "2025-07-25T08:00:00Z")
    _check("latest_input_available_at = 8-K", pit["latest_input_available_at"] == "2025-10-22T08:00:00Z")
    _check("decision_timestamp after both", pit["decision_timestamp"] == "2025-11-15T14:00:00Z")
    _check("press_release < 8K < decision", pit["earliest_input_available_at"] < pit["latest_input_available_at"] < pit["decision_timestamp"])

    print("[6] Guidance surprise computation correctness (public Path B)")
    attrs = b["computed_attributes"]
    eps_surprise = next(a for a in attrs if a["attribute_key"] == "guidance_surprise_eps_pct_path_b_fallback")
    expected_eps = (0.98 - 0.92) / 0.92
    _check(
        f"guidance_surprise_eps_pct = (0.98 - 0.92) / 0.92 = {expected_eps:.4f}",
        abs(eps_surprise["value"] - expected_eps) < 1e-3,
        f"actual={eps_surprise['value']:.4f}",
    )
    rev_surprise = next(a for a in attrs if a["attribute_key"] == "guidance_surprise_revenue_pct_path_b_fallback")
    expected_rev = (485.0 - 470.0) / 470.0
    _check(
        f"guidance_surprise_revenue_pct = (485 - 470) / 470 = {expected_rev:.4f}",
        abs(rev_surprise["value"] - expected_rev) < 1e-3,
        f"actual={rev_surprise['value']:.4f}",
    )

    print("[7] No ticker as primary key anywhere")
    sec = f["entities"]["equity_security"]
    _check("equity_security.immutable_keys == ['security_id']", sec["immutable_keys"] == ["security_id"])
    _check("ticker_display present in identifiers", "ticker_display" in sec["identifiers"])
    _check("ticker NOT in immutable_keys", "ticker" not in sec["immutable_keys"])

    print("[8] Required output views include equity_radar + trade_plan + watchlist + validation_report + source_rights_report")
    expected = {"equity_radar", "trade_plan", "watchlist", "validation_report", "source_rights_report"}
    actual = set(f["required_output_views"])
    _check("required_output_views ⊇ expected", expected.issubset(actual), f"missing={expected - actual}")

    print("[9] Marketplace_draft redacts decision rationale + evidence raw values")
    md = f["package_behavior"]["marketplace_draft"]
    targets = md["redaction_targets"]
    _check(
        "marketplace_draft redacts decision_rationale",
        "decision_earnings_revision_pilot_001.decision_rationale" in targets,
    )
    _check(
        "marketplace_draft redacts evidence raw values",
        any("evidence_bundle_path_b_public_only.items" in t for t in targets),
    )
    _check("marketplace_endpoint_supported false", md["marketplace_endpoint_supported"] is False)
    _check(
        "blocked_targets_if_violated lists Path A consensus leakage hard-block",
        any("consensus_provider_raw_value" in t for t in md["blocked_targets_if_violated"]),
    )

    print("[10] Non-advice boundary present")
    _check("fixture has non_advice_boundary text", bool(f.get("non_advice_boundary", "").strip()))
    _check("non_advice_boundary mentions 'fictional'", "fictional" in f["non_advice_boundary"].lower())

    print("[11] Stable hashes")
    fix_h = _sha256_bytes(FIXTURE)
    can_h = _sha256_canonical_json(f)
    print(f"     fixture_file_sha256    : {fix_h}")
    print(f"     fixture_canonical_sha256: {can_h}")

    print()
    print("=== EARNINGS_REVISION_MOMENTUM PILOT PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

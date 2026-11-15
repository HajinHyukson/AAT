#!/usr/bin/env python3
"""Verifier for the portfolio_risk_radar pilot fixture."""

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

    print("=== portfolio_risk_radar pilot verification ===")
    print(f"fixture_id          : {f['fixture_id']}")
    print(f"module_id           : {f['fixture_module_id']}")
    print(f"module_version      : {f['fixture_module_version']}")
    print(f"run_id              : {f['fixture_run_id']}")
    print(f"strategy_profile_id : {f['fixture_strategy_profile_id']}")
    print(f"decision_timestamp  : {f['fixture_decision_timestamp']}")
    print()

    print("[1] Graph + portfolio context load")
    g = f["sample_graph"]
    _check("graph schema is viza_graph_v0", g["schema"] == "viza_graph_v0")
    _check("graph references portfolio_risk_radar profile", g["strategy_profile_id"] == "portfolio_risk_radar")
    _check(">=10 nodes in graph", len(g["nodes"]) >= 10, f"count={len(g['nodes'])}")
    _check(">=10 edges in graph", len(g["edges"]) >= 10, f"count={len(g['edges'])}")
    portfolio = f["portfolio"]
    _check("portfolio mandate.directionality is market_neutral", portfolio["mandate"]["directionality"] == "market_neutral")
    _check("portfolio NAV is synthetic ($10M)", portfolio["nav_usd"] == 10000000.0)
    _check("portfolio license_policy = internal_research_only", portfolio["rights"]["license_policy"] == "internal_research_only")
    _check("user-private portfolio: export_policy = blocked", portfolio["rights"]["export_policy"] == "blocked")
    _check("user-private portfolio: marketplace_policy = blocked", portfolio["rights"]["marketplace_policy"] == "blocked")

    print("[2] Public data only (user portfolio synthetic + private)")
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
    allowed = {"internal_research_only", "public_official", "public_professional", "academic_public"}
    _check("license_policy ⊆ allowed set (user-private + public-only)", lp_in_use.issubset(allowed), f"actual={sorted(lp_in_use)}")

    print("[3] Licensed factor models listed as locked")
    sr = f["source_rights_report"]
    _check("Barra/Axioma factor models: locked_placeholder", sr["factor_data_licensed_barra_axioma"]["behavior"] == "locked_placeholder")
    _check("S&P index membership: locked_placeholder", sr["benchmark_index_sp500_industrials"]["behavior"] == "locked_placeholder")

    print("[4] Position caps + sector caps + liquidity gates")
    positions = f["positions"]
    _check("position count == 5", len(positions) == 5)
    max_pos = max(p["weight"] for p in positions)
    _check("max position weight <= 0.25", max_pos <= 0.25 + 1e-9, f"max={max_pos}")
    by_sector = {}
    for p in positions:
        by_sector[p["sector"]] = by_sector.get(p["sector"], 0) + p["weight"]
    max_sector = max(by_sector.values())
    _check("max sector weight <= 0.30", max_sector <= 0.30 + 1e-9, f"by_sector={by_sector}")
    max_unwind = max(p["days_to_unwind_at_20pct_adv"] for p in positions)
    _check("max days_to_unwind <= 5", max_unwind <= 5.0, f"max={max_unwind}")

    print("[5] Factor exposure aggregation")
    sum_weighted = sum(p["weight"] * p["beta_mkt"] for p in positions)
    _check(
        "Portfolio market beta is in plausible range (1.0-1.3)",
        1.0 <= sum_weighted <= 1.3,
        f"portfolio_beta_mkt~{sum_weighted:.3f}",
    )

    print("[6] PIT warning for Kenneth French (latest_only)")
    pit = f["pit_report"]
    _check("PIT_safe true for live monitoring mandate", pit["PIT_safe"] is True)
    _check("lookahead_risk low", pit["lookahead_risk"] == "low")
    warning_codes = {w["code"] for w in pit["vintage_warnings"]}
    _check(
        "pit_latest_only_not_backtest_safe_factor_data_public_kenneth_french warning emitted",
        "pit_latest_only_not_backtest_safe_factor_data_public_kenneth_french" in warning_codes,
    )

    print("[7] No ticker as primary key in any reference")
    for p in positions:
        _check(
            f"position {p['id']} references security_id_ref (not ticker)",
            p["security_id_ref"].startswith("sec_") and "ticker" not in p["security_id_ref"].lower(),
        )

    print("[8] Required output views include risk_dashboard + portfolio_impact_report + validation_report + source_rights_report")
    expected_views = {"risk_dashboard", "portfolio_impact_report", "validation_report", "source_rights_report"}
    actual_views = set(f["required_output_views"])
    _check(
        "required_output_views ⊇ expected_views",
        expected_views.issubset(actual_views),
        f"missing={expected_views - actual_views}",
    )

    print("[9] Marketplace_draft FULLY redacts user portfolio data")
    md = f["package_behavior"]["marketplace_draft"]
    _check("marketplace_draft.contains.user_portfolio_data starts with FULLY REDACTED", md["contains"]["user_portfolio_data"].startswith("FULLY REDACTED"))
    _check("marketplace_endpoint_supported false", md["marketplace_endpoint_supported"] is False)

    print("[10] Non-advice boundary + no personal advice")
    _check("fixture has non_advice_boundary text", bool(f.get("non_advice_boundary", "").strip()))
    actions = portfolio["mandate"]["allowed_actions"]
    forbidden = {"buy_candidate", "sell_candidate", "short_candidate"}
    overlap = forbidden & set(actions)
    _check(
        "risk-only mandate does NOT include buy/sell/short actions",
        not overlap,
        f"overlap={overlap}",
    )

    print("[11] Stable hashes")
    fix_h = _sha256_bytes(FIXTURE)
    can_h = _sha256_canonical_json(f)
    print(f"     fixture_file_sha256    : {fix_h}")
    print(f"     fixture_canonical_sha256: {can_h}")

    print()
    print("=== PORTFOLIO_RISK_RADAR PILOT PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

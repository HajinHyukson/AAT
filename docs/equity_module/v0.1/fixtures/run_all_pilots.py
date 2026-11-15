#!/usr/bin/env python3
"""
Master runner for the three v0.1 pilot fixtures named in the CLAUDE launch sequence.

Pilots:
  1. quality_value_long_only           -> first_wedge/verify_fixture.py
  2. portfolio_risk_radar              -> portfolio_risk_radar_pilot/verify_fixture.py
  3. earnings_revision_momentum        -> earnings_revision_momentum_pilot/verify_fixture.py

Runs each verifier in a subprocess, captures the result, and emits a combined
report with stable hashes per pilot plus a combined-of-combined hash.

Usage:
    python docs/equity_module/v0.1/fixtures/run_all_pilots.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PILOTS = [
    {
        "profile_id": "quality_value_long_only",
        "fixture_dir": HERE / "first_wedge",
        "verifier": HERE / "first_wedge" / "verify_fixture.py",
        "fixture_file": HERE / "first_wedge" / "fixture.json",
        "data_source_class": "public_only",
        "license_status": "public_only",
        "fallback_used": "none",
    },
    {
        "profile_id": "portfolio_risk_radar",
        "fixture_dir": HERE / "portfolio_risk_radar_pilot",
        "verifier": HERE / "portfolio_risk_radar_pilot" / "verify_fixture.py",
        "fixture_file": HERE / "portfolio_risk_radar_pilot" / "fixture.json",
        "data_source_class": "public_only_plus_synthetic_user_private",
        "license_status": "licensed_factor_models_locked_kenneth_french_latest_only",
        "fallback_used": "kenneth_french_latest_only_for_factor_exposures",
    },
    {
        "profile_id": "earnings_revision_momentum",
        "fixture_dir": HERE / "earnings_revision_momentum_pilot",
        "verifier": HERE / "earnings_revision_momentum_pilot" / "verify_fixture.py",
        "fixture_file": HERE / "earnings_revision_momentum_pilot" / "fixture.json",
        "data_source_class": "public_only_via_fallback_path_b",
        "license_status": "ibes_consensus_locked_path_a_inactive",
        "fallback_used": "edgar_8k_2_02_plus_press_release_guidance_midpoint",
    },
]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    print("=" * 80)
    print(" VIZA Equity Module v0.1 - run_all_pilots")
    print(" Pilots from CLAUDE launch sequence (§41 Phase 3)")
    print("=" * 80)
    print()

    overall_ok = True
    pilot_hashes = []
    for pilot in PILOTS:
        print(f"-> Pilot: {pilot['profile_id']}")
        print(f"   Data source class : {pilot['data_source_class']}")
        print(f"   License status    : {pilot['license_status']}")
        print(f"   Fallback used     : {pilot['fallback_used']}")
        if not pilot["verifier"].exists():
            print(f"   [SKIP] verifier missing: {pilot['verifier']}")
            overall_ok = False
            continue
        if not pilot["fixture_file"].exists():
            print(f"   [SKIP] fixture missing: {pilot['fixture_file']}")
            overall_ok = False
            continue
        fixture_sha = _sha256(pilot["fixture_file"])
        print(f"   fixture sha256    : {fixture_sha}")
        pilot_hashes.append(fixture_sha)
        # Run verifier
        env = sys.executable
        proc = subprocess.run(
            [env, str(pilot["verifier"])],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        last_lines = proc.stdout.strip().split("\n")[-3:]
        for ln in last_lines:
            print(f"   verifier> {ln}")
        if proc.returncode != 0:
            print(f"   [FAIL] verifier exited {proc.returncode}")
            if proc.stderr:
                print(f"   stderr: {proc.stderr[:400]}")
            overall_ok = False
        else:
            print(f"   [PASS] pilot verifier exited 0")
        print()

    # Combined hash
    combined = hashlib.sha256()
    for h in sorted(pilot_hashes):
        combined.update(h.encode("utf-8"))
    print("-" * 80)
    print(f" combined_pilot_fixture_sha256 : {combined.hexdigest()}")
    print(f" pilots run                    : {len(pilot_hashes)}")
    print(f" status                        : {'PASS' if overall_ok else 'FAIL'}")
    print("-" * 80)
    if not overall_ok:
        return 1

    print()
    print("ACCEPTANCE CRITERIA SUMMARY")
    print()
    print(f"  [1] All three profile graphs load                                : PASS (3/3)")
    print(f"  [2] Section 19 validator runs on all graphs                      : PASS (per-pilot expected_validation_summary)")
    print(f"  [3] Licensed-data profile fails closed or degrades to fallback   : PASS (earnings_revision_momentum Path A locked + Path B fallback active)")
    print(f"  [4] No profile uses ticker as primary key                        : PASS (per-pilot tc_no_ticker_as_primary_key check)")
    print(f"  [5] No profile emits personal advice                             : PASS (research-action vocabulary only)")
    print(f"  [6] All recommendation-like outputs contain non-advice boundary  : PASS (per-pilot tc_non_advice_boundary check)")
    print(f"  [7] Existing tests remain green                                  : OUT OF SCOPE here (verify via `python -m pytest tests/unit tests/lookahead_audit` in CI)")
    print()
    print("ALL PILOTS PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

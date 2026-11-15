#!/usr/bin/env python3
"""Apply confidence-label downgrades suggested by audit_recalibrate.py.

Modifies the registry JSON / CSV files in place. Preserves the original
confidence label in a sibling `confidence_label_pre_recalibration` field
(JSON registries) or column (CSV).

Run after audit_recalibrate.py.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

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


def main() -> int:
    cache = json.loads((OUT / "_findings_cache.json").read_text(encoding="utf-8"))
    findings = cache["findings"]
    by_id: dict[tuple[str, str], dict] = {}
    for f in findings:
        if f["changed"]:
            by_id[(f["registry"], f["object_id"])] = f

    total_patched = 0

    # JSON registries
    for fname in JSON_REGISTRIES:
        path = REG / f"{fname}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        items_key = None
        for k, v in doc.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                items_key = k
                break
        if not items_key:
            continue
        patched = 0
        for it in doc[items_key]:
            key = (fname, it.get("id"))
            f = by_id.get(key)
            if not f:
                continue
            it["confidence_label_pre_recalibration"] = it.get("confidence_label")
            it["confidence_label"] = f["suggested_label"]
            it.setdefault("recalibration_notes", {})
            it["recalibration_notes"] = {
                "downgrade_reason": f["downgrade_reason"],
                "issues": f["issues"].split(";"),
                "recalibrated_at": "2026-05-14T00:00:00Z",
                "recalibration_id": "v0.1.0_confidence_recalibration_2026_05_14",
            }
            patched += 1
        if patched:
            path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  patched {fname}.json: {patched} records")
            total_patched += patched
        else:
            print(f"  patched {fname}.json: 0 records (no change)")

    # CSV attribute registry
    csv_path = REG / "equity_attribute_registry_seed.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    cols = list(rows[0].keys())
    # Add a column for pre-recal label if not present
    new_cols = list(cols)
    if "confidence_label_pre_recalibration" not in new_cols:
        new_cols.append("confidence_label_pre_recalibration")
    if "recalibration_downgrade_reason" not in new_cols:
        new_cols.append("recalibration_downgrade_reason")

    patched = 0
    for r in rows:
        key = ("equity_attribute_registry_seed", r.get("key"))
        f = by_id.get(key)
        # Ensure every row carries the new columns (empty for unchanged)
        if "confidence_label_pre_recalibration" not in r:
            r["confidence_label_pre_recalibration"] = ""
        if "recalibration_downgrade_reason" not in r:
            r["recalibration_downgrade_reason"] = ""
        if f:
            r["confidence_label_pre_recalibration"] = r.get("confidence_label", "")
            r["confidence_label"] = f["suggested_label"]
            r["recalibration_downgrade_reason"] = f["downgrade_reason"]
            patched += 1
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=new_cols)
        w.writeheader()
        for r in rows:
            row = {k: r.get(k, "") for k in new_cols}
            w.writerow(row)
    print(f"  patched equity_attribute_registry_seed.csv: {patched} records")
    total_patched += patched

    print()
    print(f"total patched: {total_patched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

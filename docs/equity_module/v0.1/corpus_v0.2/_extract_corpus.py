#!/usr/bin/env python3
"""Extract source corpus rows from CLAUDE_EQUITY_MODULE.md.

Walks every '### N.N Source corpus' subsection, parses the markdown table,
and emits a master CSV with the union of every cited source.

Output:
    docs/equity_module/v0.1/corpus_v0.2/_extracted_corpus_raw.csv
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path("C:/Users/gkwls/AAT")
LOG = ROOT / "docs" / "CLAUDE_EQUITY_MODULE.md"
OUT = ROOT / "docs" / "equity_module" / "v0.1" / "corpus_v0.2" / "_extracted_corpus_raw.csv"

# Section -> prefix map (from log appendix)
SECTION_PREFIX = {
    1: "B", 2: "P", 3: "G", 4: "T", 5: "ANL", 6: "F",
    7: "V", 8: "I", 9: "GOV", 10: "FA", 11: "PC", 12: "TE",
    13: "EV", 14: "OW", 15: "BE", 16: "MA", 17: "SH", 18: "DA",
}

SECTION_NAMES = {
    1: "Baseline", 2: "Protocol", 3: "Grammar", 4: "Taxonomy",
    5: "Analyst", 6: "Fundamentals", 7: "Valuation", 8: "Industry",
    9: "Governance", 10: "Factors", 11: "Portfolio", 12: "Technical",
    13: "Events", 14: "Ownership", 15: "Behavioral", 16: "Macro",
    17: "Short", 18: "Data Architecture",
}


def parse() -> list[dict]:
    text = LOG.read_text(encoding="utf-8")
    lines = text.split("\n")
    rows = []
    current_section = None
    in_corpus_table = False
    table_header = None

    src_id_re = re.compile(r"^`([A-Z]+-[0-9]{3,4})`$")

    for i, line in enumerate(lines):
        # Detect section header like "## Section N — ..."
        m = re.match(r"^## Section (\d+)", line)
        if m:
            try:
                current_section = int(m.group(1))
            except ValueError:
                current_section = None
            in_corpus_table = False
            table_header = None
            continue

        # Detect "### N.2 Source corpus" subsection headers
        if re.match(r"^###\s+\d+\.\d+\s+Source corpus", line):
            in_corpus_table = True
            table_header = None
            continue
        if line.startswith("### ") and in_corpus_table:
            in_corpus_table = False
            table_header = None
            continue

        if not in_corpus_table:
            continue

        # Parse markdown table inside corpus
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if table_header is None:
                if cells and cells[0].lower().startswith("source_id"):
                    table_header = [c.lower() for c in cells]
                continue
            if not cells or not cells[0]:
                continue
            if cells[0].startswith("---") or cells[0].startswith(":---") or cells[0].startswith("-"):
                continue

            mid = src_id_re.match(cells[0])
            if not mid:
                continue
            sid = mid.group(1)
            row = {h: cells[idx] if idx < len(cells) else "" for idx, h in enumerate(table_header)}
            row["source_id"] = sid
            row["section_number"] = current_section
            row["section_name"] = SECTION_NAMES.get(current_section, "Unknown") if current_section else ""
            row["section_prefix"] = SECTION_PREFIX.get(current_section, "") if current_section else ""
            rows.append(row)
        # Don't drop corpus mode on non-table text; rely on the next ### heading.
    return rows


def main() -> int:
    rows = parse()
    print(f"extracted {len(rows)} source rows from {LOG.name}")

    # Dedup by source_id (some appear in multiple sections; keep first)
    seen = {}
    for r in rows:
        if r["source_id"] not in seen:
            seen[r["source_id"]] = r
    print(f"unique source_ids: {len(seen)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["source_id", "section_number", "section_name", "section_prefix", "title", "type", "quality", "use", "path"]
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for sid in sorted(seen.keys(), key=lambda s: (s.split("-")[0], int(s.split("-")[1]))):
            row = seen[sid]
            w.writerow({k: row.get(k, "") for k in cols})
    print(f"wrote {OUT}")

    # Show summary
    from collections import Counter
    by_prefix = Counter(r["section_prefix"] for r in seen.values())
    print()
    print("by prefix:")
    for p, c in sorted(by_prefix.items()):
        print(f"  {p:4s} {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

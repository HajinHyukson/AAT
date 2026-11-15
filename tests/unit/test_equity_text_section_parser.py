"""Tests for the SEC iXBRL section parser (pin 3) and the available_at
precision policy (pin 4).
"""

from __future__ import annotations

from datetime import datetime, timezone

from viza.equity.text.section_parser import (
    PARSER_VERSION,
    parse_8k_items,
    parse_filing_acceptance,
    parse_ixbrl_filing,
)


RETRIEVED_AT = datetime(2026, 5, 14, 14, 0, tzinfo=timezone.utc)


IXBRL_DOC = """
<html><body>
  <ix:nonNumeric name="us-gaap:RiskFactorsTextBlock">
    Our business faces material risks from competition.
    There is no going concern language here.
  </ix:nonNumeric>
  <p>Boilerplate forward-looking disclaimer.</p>
  <ix:nonNumeric name="us-gaap:ManagementDiscussionAndAnalysisOfFinancialConditionAndResultsOfOperationsTextBlock">
    Revenue grew 8% year over year driven by services.
    Operating expenses were broadly flat.
  </ix:nonNumeric>
</body></html>
"""


def test_parse_ixbrl_filing_extracts_two_known_sections() -> None:
    sections = parse_ixbrl_filing(
        document_text=IXBRL_DOC,
        requested_sections=["risk_factors", "mdna"],
        filing_accession="0000320193-23-000106",
        cik="0000320193",
        form_type="10-K",
        acceptance_datetime="2023-11-02T18:08:27.000-05:00",
        filing_date="2023-11-03",
        retrieved_at=RETRIEVED_AT,
    )
    by_id = {s.section_id: s for s in sections}
    assert "risk_factors" in by_id
    assert "mdna" in by_id
    assert "competition" in by_id["risk_factors"].section_text
    assert "Revenue grew" in by_id["mdna"].section_text
    assert by_id["risk_factors"].parser_version == PARSER_VERSION


def test_parse_ixbrl_filing_emits_unparseable_for_missing_section() -> None:
    sections = parse_ixbrl_filing(
        document_text=IXBRL_DOC,
        requested_sections=["market_risk"],
        filing_accession="0000320193-23-000106",
        cik="0000320193",
        form_type="10-K",
        acceptance_datetime="2023-11-02T18:08:27.000-05:00",
        filing_date="2023-11-03",
        retrieved_at=RETRIEVED_AT,
    )
    assert len(sections) == 1
    assert sections[0].section_id == "section_unparseable"
    assert any("no_xbrl_section_tags" in w or "not present" in w for w in sections[0].warnings) or sections[0].pit_policy.get("reason") == "no_xbrl_section_tags"


def test_parse_filing_acceptance_minute_precision() -> None:
    available_at, risk = parse_filing_acceptance(
        acceptance_datetime="2023-11-02T18:08:27.000-05:00",
        filing_date="2023-11-03",
    )
    assert available_at is not None
    assert available_at.tzinfo is timezone.utc
    assert risk == "low"


def test_parse_filing_acceptance_day_precision_falls_back_to_21_et() -> None:
    available_at, risk = parse_filing_acceptance(
        acceptance_datetime=None,
        filing_date="2001-06-30",
    )
    assert available_at is not None
    # Converted from 21:00 ET; this is 01:00 UTC the next day (EDT is UTC-4
    # in June, so 21:00 ET = 01:00 UTC).
    assert risk == "warning"
    # Conservative wall-clock: the next-trading-day signal cannot be earlier.
    assert available_at.hour in (1, 2)


def test_parse_filing_acceptance_missing_inputs_blocks_backtest() -> None:
    available_at, risk = parse_filing_acceptance(
        acceptance_datetime=None,
        filing_date=None,
    )
    assert available_at is None
    assert risk == "not_backtest_safe"


def test_parse_8k_items_uses_header_item_list() -> None:
    sections = parse_8k_items(
        items=["2.02", "7.01", "9.99"],
        item_bodies={
            "2.02": "Earnings of $1.00 per share announced today.",
            "7.01": "Reg FD disclosure attached.",
            "9.99": "Unknown item code body.",
        },
        filing_accession="9999-25-000001",
        cik="0000320193",
        acceptance_datetime="2025-01-15T08:00:00.000-05:00",
        filing_date="2025-01-15",
        retrieved_at=RETRIEVED_AT,
    )
    by_id = {s.section_id: s for s in sections}
    assert "8k_2_02" in by_id
    assert "8k_7_01" in by_id
    # 9.99 is not in the supported item map.
    assert all(s.section_id != "8k_9_99" for s in sections)

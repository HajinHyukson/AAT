"""Pin-3 SEC iXBRL section parser.

Scope for v0.1:
  * 10-K / 10-Q with inline XBRL section tags: extract Risk Factors,
    MD&A, and Market Risk via XBRL TextBlock elements.
  * 8-K: section identity comes from the EDGAR submission header's items
    list, NOT from heuristic body parsing.
  * Otherwise: emit a single ParsedSection with section_id="section_unparseable"
    and stop.

Pin-4 available_at policy:
  * minute-precise acceptedDateTime  -> use directly, lookahead_risk="low"
  * day-precise acceptedDate         -> YYYY-MM-DDT21:00:00 ET, lookahead_risk="warning"
  * missing                          -> available_at=None, lookahead_risk="not_backtest_safe"

This module deliberately does NOT depend on any HTML parsing library at v0.1.
A small set of XBRL element names is extracted via regex against the well-
structured iXBRL contract; everything else is rejected.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from viza.equity.text.hashing import hash_section_text
from viza.equity.text.types import FormType, ParsedSection, SectionId


PARSER_VERSION = "ixbrl_section_parser_v1"
EDGAR_DAY_PRECISION_FALLBACK_HOUR_ET = 21


# Mapping from iXBRL element local-name (case-sensitive in spec, but issuers
# vary; we lowercase-match) to canonical section_id.
IXBRL_SECTION_ELEMENT_MAP: dict[str, SectionId] = {
    "riskfactorstextblock": "risk_factors",
    "managementdiscussionandanalysisoffinancialconditionandresultsofoperationstextblock": "mdna",
    "quantitativeandqualitativedisclosuresaboutmarketrisktextblock": "market_risk",
}


SECTION_LABEL_MAP: dict[SectionId, str] = {
    "risk_factors": "Risk Factors",
    "mdna": "Management Discussion and Analysis",
    "market_risk": "Quantitative and Qualitative Disclosures About Market Risk",
    "8k_2_02": "Results of Operations and Financial Condition",
    "8k_7_01": "Regulation FD Disclosure",
    "8k_8_01": "Other Events",
    "section_unparseable": "Section Unparseable",
}


_IXBRL_TAG_REGEX = re.compile(
    r"<(?:ix:nonNumeric|nonNumeric)\b[^>]*?\bname\s*=\s*\"(?P<name>[^\"]+)\"[^>]*?>"
    r"(?P<body>.*?)</(?:ix:nonNumeric|nonNumeric)>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_STRIP_REGEX = re.compile(r"<[^>]+>")
_WS_COLLAPSE = re.compile(r"\s+")


SEC_PUBLIC_TEXT_RIGHTS_POLICY: dict[str, Any] = {
    "license_policy": "public_official",
    "display_policy": "allowed_with_reference",
    "export_policy": "derived_summary_and_refs_by_default",
    "marketplace_policy": "derived_summary_refs_hashes_redact_bulk_raw_text",
    "redistribution_policy": "no_bulk_raw_filing_republication",
    "attribution_required": True,
}


_EASTERN = ZoneInfo("America/New_York")


def parse_filing_acceptance(
    *,
    acceptance_datetime: str | None,
    filing_date: str | None,
) -> tuple[datetime | None, str]:
    """Return (available_at, lookahead_risk) per pin 4.

    ``acceptance_datetime`` is the EDGAR ``acceptanceDateTime`` field
    (minute-precise when modern, ISO-8601 with timezone). ``filing_date`` is
    the day-precision fallback (``filingDate``).
    """
    if acceptance_datetime:
        try:
            parsed = datetime.fromisoformat(acceptance_datetime.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc), "low"

    if filing_date:
        try:
            year, month, day = (int(x) for x in filing_date.split("-"))
        except (ValueError, AttributeError):
            return None, "not_backtest_safe"
        fallback = datetime(
            year,
            month,
            day,
            EDGAR_DAY_PRECISION_FALLBACK_HOUR_ET,
            0,
            0,
            tzinfo=_EASTERN,
        ).astimezone(timezone.utc)
        return fallback, "warning"

    return None, "not_backtest_safe"


def _strip_html(body: str) -> str:
    body = _TAG_STRIP_REGEX.sub(" ", body)
    return _WS_COLLAPSE.sub(" ", body).strip()


def _local_name(qualified_name: str) -> str:
    if ":" in qualified_name:
        qualified_name = qualified_name.split(":", 1)[1]
    return qualified_name.lower()


def _extract_ixbrl_sections(
    document_text: str,
    *,
    requested_sections: Iterable[SectionId],
) -> dict[SectionId, str]:
    """Return {section_id: section_text} for any requested section present.

    Returns an empty dict if no recognized iXBRL section elements are found.
    """
    requested = set(requested_sections)
    found: dict[SectionId, str] = {}
    for match in _IXBRL_TAG_REGEX.finditer(document_text):
        local = _local_name(match.group("name"))
        section_id = IXBRL_SECTION_ELEMENT_MAP.get(local)
        if section_id is None or section_id not in requested:
            continue
        if section_id in found:
            # First occurrence wins; subsequent occurrences (rare) are skipped
            # to preserve determinism.
            continue
        found[section_id] = _strip_html(match.group("body"))
    return found


def parse_ixbrl_filing(
    *,
    document_text: str,
    requested_sections: Iterable[SectionId],
    filing_accession: str,
    cik: str,
    form_type: FormType,
    acceptance_datetime: str | None,
    filing_date: str | None,
    retrieved_at: datetime,
    document_url: str | None = None,
    entity_id: str | None = None,
) -> list[ParsedSection]:
    """Parse a 10-K/10-Q iXBRL document, returning ParsedSection records.

    For each requested section that is not found in the iXBRL body, a
    ``section_unparseable`` ParsedSection is returned with a warning. The
    caller can decide whether to proceed with the parsed sections or to fail
    the whole resolver run.
    """
    if form_type == "8-K":
        raise ValueError(
            "parse_ixbrl_filing is for 10-K/10-Q; use parse_8k_items for 8-K"
        )

    available_at, lookahead_risk = parse_filing_acceptance(
        acceptance_datetime=acceptance_datetime,
        filing_date=filing_date,
    )
    filing_accepted_at = available_at if lookahead_risk == "low" else None

    extracted = _extract_ixbrl_sections(
        document_text,
        requested_sections=requested_sections,
    )

    results: list[ParsedSection] = []
    for section_id in requested_sections:
        section_text = extracted.get(section_id)
        if section_text is None:
            results.append(
                ParsedSection(
                    filing_accession=filing_accession,
                    cik=cik,
                    company_id=entity_id,
                    form_type=form_type,
                    section_id="section_unparseable",
                    section_label=SECTION_LABEL_MAP["section_unparseable"],
                    section_text="",
                    section_text_hash=hash_section_text(""),
                    parser_version=PARSER_VERSION,
                    filing_accepted_at=filing_accepted_at,
                    available_at=available_at,
                    retrieved_at=retrieved_at,
                    document_url=document_url,
                    lookahead_risk=lookahead_risk,
                    rights_policy=dict(SEC_PUBLIC_TEXT_RIGHTS_POLICY),
                    pit_policy={
                        "requested_section_id": section_id,
                        "reason": "no_xbrl_section_tags",
                    },
                    warnings=[
                        f"section_id={section_id} not present as iXBRL TextBlock"
                    ],
                )
            )
            continue
        results.append(
            ParsedSection(
                filing_accession=filing_accession,
                cik=cik,
                company_id=entity_id,
                form_type=form_type,
                section_id=section_id,
                section_label=SECTION_LABEL_MAP[section_id],
                section_text=section_text,
                section_text_hash=hash_section_text(section_text),
                parser_version=PARSER_VERSION,
                filing_accepted_at=filing_accepted_at,
                available_at=available_at,
                retrieved_at=retrieved_at,
                document_url=document_url,
                lookahead_risk=lookahead_risk,
                rights_policy=dict(SEC_PUBLIC_TEXT_RIGHTS_POLICY),
                pit_policy={
                    "observed_at_basis": "filing_acceptance_or_day_precision_fallback",
                },
                warnings=[],
            )
        )
    return results


# 8-K item codes per pin 3: identity comes from the EDGAR header items list,
# not heuristic body parsing.
_EIGHT_K_ITEM_TO_SECTION_ID: dict[str, SectionId] = {
    "2.02": "8k_2_02",
    "7.01": "8k_7_01",
    "8.01": "8k_8_01",
}


def parse_8k_items(
    *,
    items: Iterable[str],
    item_bodies: dict[str, str],
    filing_accession: str,
    cik: str,
    acceptance_datetime: str | None,
    filing_date: str | None,
    retrieved_at: datetime,
    document_url: str | None = None,
    entity_id: str | None = None,
) -> list[ParsedSection]:
    """Parse an 8-K filing using the items list as the source of truth.

    ``item_bodies`` is a {item_code: text_block} map provided by the EDGAR
    adapter (the iXBRL element for an 8-K item is well-defined). Items not
    in ``_EIGHT_K_ITEM_TO_SECTION_ID`` are ignored at v0.1.
    """
    available_at, lookahead_risk = parse_filing_acceptance(
        acceptance_datetime=acceptance_datetime,
        filing_date=filing_date,
    )
    filing_accepted_at = available_at if lookahead_risk == "low" else None

    results: list[ParsedSection] = []
    for item_code in items:
        section_id = _EIGHT_K_ITEM_TO_SECTION_ID.get(item_code)
        if section_id is None:
            continue
        body = item_bodies.get(item_code, "")
        normalized = _WS_COLLAPSE.sub(" ", body).strip()
        results.append(
            ParsedSection(
                filing_accession=filing_accession,
                cik=cik,
                company_id=entity_id,
                form_type="8-K",
                section_id=section_id,
                section_label=SECTION_LABEL_MAP[section_id],
                section_text=normalized,
                section_text_hash=hash_section_text(normalized),
                parser_version=PARSER_VERSION,
                filing_accepted_at=filing_accepted_at,
                available_at=available_at,
                retrieved_at=retrieved_at,
                document_url=document_url,
                lookahead_risk=lookahead_risk,
                rights_policy=dict(SEC_PUBLIC_TEXT_RIGHTS_POLICY),
                pit_policy={
                    "observed_at_basis": "8k_item_header_list",
                    "item_code": item_code,
                },
                warnings=[] if normalized else [f"8-K item {item_code} body empty"],
            )
        )
    return results

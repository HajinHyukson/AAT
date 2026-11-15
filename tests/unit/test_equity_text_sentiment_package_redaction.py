"""Stage C tests for the package-redaction module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.hashing import hash_section_text
from viza.equity.text.package_redaction import (
    PackageRedactionBlocked,
    redact_for_package,
)
from viza.equity.text.resolver import resolve_finance_text_sentiment
from viza.equity.text.section_parser import (
    PARSER_VERSION,
    SEC_PUBLIC_TEXT_RIGHTS_POLICY,
)
from viza.equity.text.types import (
    ParsedSection,
    ResolverFilingSelector,
    ResolverRequest,
    ResolverResponse,
    ResolverTarget,
)


ACCEPTED_AT = datetime(2024, 11, 2, 23, 8, 27, tzinfo=timezone.utc)
RETRIEVED_AT = datetime(2026, 5, 14, 14, 0, tzinfo=timezone.utc)


def _enabled() -> EquityTextConfig:
    return EquityTextConfig(
        sec_text_analysis_enabled=True,
        text_sentiment_resolver_enabled=True,
        finbert_enabled=True,
    )


def _section(text: str) -> ParsedSection:
    return ParsedSection(
        filing_accession="acc-redact-1",
        cik="0000320193",
        form_type="10-K",
        section_id="risk_factors",
        section_label="Risk Factors",
        section_text=text,
        section_text_hash=hash_section_text(text),
        parser_version=PARSER_VERSION,
        filing_accepted_at=ACCEPTED_AT,
        available_at=ACCEPTED_AT,
        retrieved_at=RETRIEVED_AT,
        lookahead_risk="low",
        rights_policy=dict(SEC_PUBLIC_TEXT_RIGHTS_POLICY),
        pit_policy={"observed_at_basis": "filing_acceptance"},
        warnings=[],
    )


def _resolve(tmp_path: Path) -> ResolverResponse:
    return resolve_finance_text_sentiment(
        ResolverRequest(
            target=ResolverTarget(cik="0000320193"),
            filing=ResolverFilingSelector(accession="acc-redact-1"),
            sections=["risk_factors"],
            mock_parsed_sections=[_section("Competition is intense. Margins may compress.")],
        ),
        config=_enabled(),
        store_path=tmp_path / "store.sqlite",
    )


def test_white_box_includes_chunk_observations_but_no_raw_text(tmp_path: Path) -> None:
    response = _resolve(tmp_path)
    redacted = redact_for_package(response, mode="white_box")
    assert redacted["package_mode"] == "white_box"
    assert redacted["chunk_observations"]
    assert any(
        r["field"] == "chunk_text" and "bulk_raw_text_redacted" in r["reason"]
        for r in redacted["redactions"]
    )
    # No bare 'text' key in chunk payloads (SentimentObservation doesn't carry
    # raw text but we also strip excerpt/text defensively).
    for chunk in redacted["chunk_observations"]:
        assert "text" not in chunk
        assert "excerpt" not in chunk


def test_output_only_emits_filing_reading_card_no_chunks(tmp_path: Path) -> None:
    response = _resolve(tmp_path)
    redacted = redact_for_package(response, mode="output_only")
    assert redacted["package_mode"] == "output_only"
    assert "filing_reading_card" in redacted
    assert "chunk_observations" not in redacted
    assert any(
        r["field"] == "per_chunk_observations" for r in redacted["redactions"]
    )
    # Filing reading card has section-level aggregates.
    cards = redacted["filing_reading_card"]["filings"]
    assert len(cards) == 1
    assert cards[0]["filing_accession"] == "acc-redact-1"


def test_marketplace_draft_includes_summaries_only(tmp_path: Path) -> None:
    response = _resolve(tmp_path)
    redacted = redact_for_package(response, mode="marketplace_draft")
    assert redacted["package_mode"] == "marketplace_draft"
    assert "chunk_summaries" in redacted
    # Chunk summaries strip probabilities, keeping only label + confidence_label.
    for summary in redacted["chunk_summaries"]:
        assert "positive_prob" not in summary
        assert "negative_prob" not in summary
        assert "label" in summary
    # Section aggregates keep numbers but omit chunk_ids.
    for agg in redacted["section_aggregates"]:
        assert "chunk_observation_ids" not in agg
    # Non-advice boundary is always present.
    assert "FinBERT" in redacted["non_advice_boundary"] or "advice" in redacted["non_advice_boundary"]


def test_marketplace_draft_blocks_partial_runs() -> None:
    response = ResolverResponse(
        resolver_id="viza.finance.text.sentiment",
        status="partial",
        source="queued",
    )
    with pytest.raises(PackageRedactionBlocked) as excinfo:
        redact_for_package(response, mode="marketplace_draft")
    assert excinfo.value.reason == "partial_run_not_marketplace_ready"


def test_marketplace_redactions_list_includes_chunk_excerpt_field(
    tmp_path: Path,
) -> None:
    """Pin: marketplace_draft v0.1 includes no excerpts; the redaction
    manifest must explicitly call out the absence (not just silently drop)."""
    response = _resolve(tmp_path)
    redacted = redact_for_package(response, mode="marketplace_draft")
    redacted_fields = {r["field"] for r in redacted["redactions"]}
    assert "chunk_text" in redacted_fields
    assert "chunk_excerpt" in redacted_fields
    assert "per_chunk_probabilities" in redacted_fields

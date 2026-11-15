"""End-to-end tests for resolve_finance_text_sentiment with the mock model."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.hashing import hash_section_text
from viza.equity.text.resolver import RESOLVER_ID, resolve_finance_text_sentiment
from viza.equity.text.section_parser import (
    PARSER_VERSION,
    SEC_PUBLIC_TEXT_RIGHTS_POLICY,
)
from viza.equity.text.types import (
    ParsedSection,
    ResolverFilingSelector,
    ResolverRequest,
    ResolverTarget,
)


RETRIEVED_AT = datetime(2026, 5, 14, 14, 0, tzinfo=timezone.utc)
ACCEPTED_AT = datetime(2023, 11, 2, 23, 8, 27, tzinfo=timezone.utc)


def _enabled_config() -> EquityTextConfig:
    return EquityTextConfig(
        sec_text_analysis_enabled=True,
        text_sentiment_resolver_enabled=True,
        finbert_enabled=True,
    )


def _section(
    *,
    section_id: str,
    text: str,
    filing_accession: str = "0000320193-23-000106",
) -> ParsedSection:
    return ParsedSection(
        filing_accession=filing_accession,
        cik="0000320193",
        company_id="sec:cik:0000320193",
        form_type="10-K",
        section_id=section_id,  # type: ignore[arg-type]
        section_label=section_id.replace("_", " ").title(),
        section_text=text,
        section_text_hash=hash_section_text(text),
        parser_version=PARSER_VERSION,
        filing_accepted_at=ACCEPTED_AT,
        available_at=ACCEPTED_AT,
        retrieved_at=RETRIEVED_AT,
        document_url=None,
        lookahead_risk="low",
        rights_policy=dict(SEC_PUBLIC_TEXT_RIGHTS_POLICY),
        pit_policy={"observed_at_basis": "filing_acceptance"},
        warnings=[],
    )


def _request(
    sections: list[ParsedSection],
    *,
    cache_policy: str = "serve_or_compute",
    analysis_mode: str = "live_current",
) -> ResolverRequest:
    return ResolverRequest(
        target=ResolverTarget(cik="0000320193", ticker_alias="AAPL"),
        filing=ResolverFilingSelector(accession=sections[0].filing_accession),
        sections=[s.section_id for s in sections],  # type: ignore[misc]
        cache_policy=cache_policy,  # type: ignore[arg-type]
        analysis_mode=analysis_mode,  # type: ignore[arg-type]
        mock_parsed_sections=sections,
    )


def test_happy_path_returns_pass_status_and_observations(tmp_path: Path) -> None:
    sections = [
        _section(
            section_id="risk_factors",
            text=(
                "Competition in our industry is intense. "
                "Margins could compress under pricing pressure. "
                "Currency volatility affects international revenue."
            ),
        ),
        _section(
            section_id="mdna",
            text=(
                "Revenue grew 8% year over year driven by services. "
                "Operating expenses were broadly flat. "
                "Free cash flow remained strong throughout the period."
            ),
        ),
    ]
    response = resolve_finance_text_sentiment(
        _request(sections),
        config=_enabled_config(),
        store_path=tmp_path / "store.sqlite",
    )
    assert response.resolver_id == RESOLVER_ID
    assert response.status in ("pass", "warn")
    assert len(response.observations) > 0
    # Every observation must carry the model + cache identity.
    for obs in response.observations:
        assert obs.cache_key
        assert obs.model_id == "viza.mock/finbert"
        assert obs.parser_version == PARSER_VERSION
        assert obs.available_at == ACCEPTED_AT


def test_section_unparseable_is_warned_not_blocked(tmp_path: Path) -> None:
    unparseable = ParsedSection(
        filing_accession="acc-2",
        cik="0000320193",
        form_type="10-K",
        section_id="section_unparseable",
        section_label="Section Unparseable",
        section_text="",
        section_text_hash=hash_section_text(""),
        parser_version=PARSER_VERSION,
        filing_accepted_at=ACCEPTED_AT,
        available_at=ACCEPTED_AT,
        retrieved_at=RETRIEVED_AT,
        lookahead_risk="low",
        rights_policy=dict(SEC_PUBLIC_TEXT_RIGHTS_POLICY),
        pit_policy={"reason": "no_xbrl_section_tags"},
        warnings=["section_id=risk_factors not present"],
    )
    response = resolve_finance_text_sentiment(
        _request([unparseable]),
        config=_enabled_config(),
        store_path=tmp_path / "store.sqlite",
    )
    assert response.status == "warn"
    assert any("section_unparseable" in w for w in response.warnings)


def test_human_review_term_propagates_to_observation(tmp_path: Path) -> None:
    flagged = _section(
        section_id="risk_factors",
        text=(
            "There is substantial doubt about our ability to continue as a going concern. "
            "Operating results have deteriorated. "
            "We are pursuing financing alternatives."
        ),
    )
    response = resolve_finance_text_sentiment(
        _request([flagged]),
        config=_enabled_config(),
        store_path=tmp_path / "store.sqlite",
    )
    flagged_obs = [o for o in response.observations if o.requires_human_review]
    assert flagged_obs, "expected at least one chunk to be flagged for human review"
    assert response.status == "warn"
    assert any(
        "going concern" in o.matched_human_review_terms
        or "substantial doubt" in o.matched_human_review_terms
        for o in flagged_obs
    )


def test_retrospective_research_is_labeled_not_live_historical_pit(tmp_path: Path) -> None:
    sections = [
        _section(
            section_id="mdna",
            text="Revenue grew. Operating expenses were broadly flat.",
        )
    ]
    response = resolve_finance_text_sentiment(
        _request(sections, analysis_mode="retrospective_research"),
        config=_enabled_config(),
        store_path=tmp_path / "store.sqlite",
    )
    assert "retrospective_research:not_live_historical_PIT" in response.warnings


def test_missing_mock_sections_blocks_in_stage_a(tmp_path: Path) -> None:
    request = ResolverRequest(
        target=ResolverTarget(cik="0000320193"),
        filing=ResolverFilingSelector(latest=True),
        sections=["risk_factors"],
        mock_parsed_sections=None,
    )
    response = resolve_finance_text_sentiment(
        request,
        config=_enabled_config(),
        store_path=tmp_path / "store.sqlite",
    )
    assert response.status == "block"
    assert response.blocks
    assert response.blocks[0]["code"] == "stage_a_requires_mock_parsed_sections"

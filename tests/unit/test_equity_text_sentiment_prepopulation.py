"""Stage D active-scope prepopulation tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.hashing import hash_section_text
from viza.equity.text.prepopulation import (
    ALLOWED_SCOPE_TYPES,
    FORBIDDEN_SCOPE_IDS,
    PrepopulationScope,
    PrepopulationScopeRefused,
    get_job,
    prepopulate,
    validate_scope,
)
from viza.equity.text.section_parser import (
    PARSER_VERSION,
    SEC_PUBLIC_TEXT_RIGHTS_POLICY,
)
from viza.equity.text.types import ParsedSection


ACCEPTED_AT = datetime(2024, 11, 2, 23, 8, 27, tzinfo=timezone.utc)
RETRIEVED_AT = datetime(2026, 5, 14, 14, 0, tzinfo=timezone.utc)


def _section(accession: str, text: str) -> ParsedSection:
    return ParsedSection(
        filing_accession=accession,
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


def _enabled() -> EquityTextConfig:
    return EquityTextConfig(
        sec_text_analysis_enabled=True,
        text_sentiment_resolver_enabled=True,
        finbert_enabled=True,
        text_prepopulation_enabled=True,
    )


def test_validate_scope_accepts_allowed_scope_types() -> None:
    for scope_type in ALLOWED_SCOPE_TYPES:
        validate_scope(scope_type, "my-named-scope")


def test_validate_scope_rejects_unknown_scope_type() -> None:
    with pytest.raises(PrepopulationScopeRefused) as excinfo:
        validate_scope("market_wide", "any")
    assert excinfo.value.code == "scope_type_not_allowed"


def test_validate_scope_blocks_full_market_aliases() -> None:
    for alias in FORBIDDEN_SCOPE_IDS:
        with pytest.raises(PrepopulationScopeRefused) as excinfo:
            validate_scope("named_universe", alias)
        assert excinfo.value.code == "full_market_scope_blocked"


def test_validate_scope_rejects_empty_scope_id() -> None:
    with pytest.raises(PrepopulationScopeRefused) as excinfo:
        validate_scope("watchlist", "   ")
    assert excinfo.value.code == "empty_scope_id"


def test_prepopulate_requires_feature_flag(tmp_path: Path) -> None:
    scope = PrepopulationScope(
        scope_type="watchlist",
        scope_id="my-watchlist",
        parsed_sections=[_section("acc-1", "Competition is intense.")],
    )
    disabled = EquityTextConfig(
        sec_text_analysis_enabled=True,
        text_sentiment_resolver_enabled=True,
        finbert_enabled=True,
        text_prepopulation_enabled=False,
    )
    with pytest.raises(PermissionError):
        prepopulate(
            scope,
            config=disabled,
            store_path=tmp_path / "store.sqlite",
        )


def test_prepopulate_warms_cache_and_subsequent_call_is_cache_hit(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "store.sqlite"
    scope = PrepopulationScope(
        scope_type="watchlist",
        scope_id="my-watchlist",
        parsed_sections=[
            _section("acc-1", "Competition is intense. Margins may compress."),
            _section("acc-2", "Revenue grew driven by services."),
        ],
    )
    first = prepopulate(scope, config=_enabled(), store_path=store_path)
    assert first.status == "completed"
    assert first.filings_total == 2
    assert first.filings_completed == 2
    assert first.filings_skipped_cached == 0

    # Second pass over the same scope must serve from cache (no fresh compute).
    second = prepopulate(scope, config=_enabled(), store_path=store_path)
    assert second.filings_skipped_cached == 2
    assert second.filings_completed == 0


def test_get_job_returns_persisted_record(tmp_path: Path) -> None:
    store_path = tmp_path / "store.sqlite"
    scope = PrepopulationScope(
        scope_type="saved_thesis",
        scope_id="my-thesis",
        parsed_sections=[_section("acc-1", "Risk language about competition.")],
    )
    job = prepopulate(scope, config=_enabled(), store_path=store_path)
    fetched = get_job(job.job_id, store_path=store_path)
    assert fetched is not None
    assert fetched.scope_type == "saved_thesis"
    assert fetched.scope_id == "my-thesis"
    assert fetched.status == "completed"


def test_prepopulate_refuses_full_market_default(tmp_path: Path) -> None:
    scope = PrepopulationScope(
        scope_type="named_universe",
        scope_id="full_market",
        parsed_sections=[_section("acc-1", "Anything.")],
    )
    with pytest.raises(PrepopulationScopeRefused) as excinfo:
        prepopulate(
            scope,
            config=_enabled(),
            store_path=tmp_path / "store.sqlite",
        )
    assert excinfo.value.code == "full_market_scope_blocked"

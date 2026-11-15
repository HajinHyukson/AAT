"""Pin-5 look-ahead audit gate for the finance text sentiment resolver.

THREE REQUIRED ASSERTIONS (any failure must fail CI):

  A. Persistence integrity:
       For every persisted sentiment observation,
         observation.available_at == filing.accepted_datetime
       never retrieved_at or inference_at.

  B. Replay PIT correctness:
       For replay_from_stored_observations(run_id, cutoff_timestamp=T):
       every returned observation satisfies observation.available_at <= T.

  C. Historical-PIT model availability:
       analysis_mode="live_historical_PIT" with a (model_id, model_version) not
       in MODEL_RELEASE_DATES blocks with status="block",
       reason="model_release_date_unknown". And a cutoff before a known
       model's release date blocks with reason="model_not_available_at_cutoff".

This file lives in tests/lookahead_audit/ (NOT tests/unit/) because it gates
CI separately as a look-ahead safety check.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.hashing import hash_section_text
from viza.equity.text.models import get_model
from viza.equity.text.release_dates import MODEL_RELEASE_DATES
from viza.equity.text.resolver import resolve_finance_text_sentiment
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
        filing_accession="acc-pit-1",
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


def _request(section: ParsedSection, **kw) -> ResolverRequest:
    return ResolverRequest(
        target=ResolverTarget(cik="0000320193"),
        filing=ResolverFilingSelector(accession=section.filing_accession),
        sections=["risk_factors"],
        mock_parsed_sections=[section],
        **kw,
    )


# ---- Assertion A: persistence integrity ------------------------------------


def test_persisted_observation_available_at_equals_filing_accepted_at(
    tmp_path: Path,
) -> None:
    response = resolve_finance_text_sentiment(
        _request(_section("Risk language about competition.")),
        config=_enabled(),
        store_path=tmp_path / "pit.sqlite",
    )
    assert response.observations
    for obs in response.observations:
        assert obs.available_at == ACCEPTED_AT, (
            "available_at must equal the filing's accepted timestamp; "
            f"got {obs.available_at} vs ACCEPTED_AT={ACCEPTED_AT}"
        )
        # available_at MUST NOT equal retrieved_at or inference_at (they are
        # later by design — confirming the resolver did not silently use
        # 'now' as availability).
        assert obs.available_at != obs.retrieved_at
        assert obs.available_at != obs.inference_at


# ---- Assertion B: replay PIT correctness -----------------------------------


def test_replay_never_returns_future_available_observations(tmp_path: Path) -> None:
    store_path = tmp_path / "pit.sqlite"
    fresh = resolve_finance_text_sentiment(
        _request(_section("Risk language about supply chain.")),
        config=_enabled(),
        store_path=store_path,
    )
    run_id = fresh.audit["run_id"]

    cutoff = ACCEPTED_AT - timedelta(seconds=1)
    replay = resolve_finance_text_sentiment(
        ResolverRequest(
            target=ResolverTarget(entity_id=run_id),
            filing=ResolverFilingSelector(),
            sections=[],
            analysis_mode="replay_from_stored_observations",
            cutoff_timestamp=cutoff,
        ),
        config=_enabled(),
        store_path=store_path,
    )
    for obs in replay.observations:
        assert obs.available_at <= cutoff, (
            "replay returned an observation with available_at > cutoff"
        )
    # Specifically: any observation at ACCEPTED_AT must NOT appear.
    assert all(obs.available_at != ACCEPTED_AT for obs in replay.observations)


# ---- Assertion C: historical-PIT model availability gate -------------------


def test_live_historical_pit_blocks_unknown_model(tmp_path: Path) -> None:
    """A model_version not in MODEL_RELEASE_DATES must block, never silently
    treat as released."""
    impl = get_model("local_finbert_mock")
    # MockFinBert reports model_id="viza.mock/finbert" + model_version="mock_v1".
    # That key is intentionally absent from MODEL_RELEASE_DATES.
    assert (impl.metadata().model_id, impl.metadata().model_version) not in MODEL_RELEASE_DATES

    response = resolve_finance_text_sentiment(
        _request(
            _section("Risk language."),
            analysis_mode="live_historical_PIT",
            model_policy="pinned",
            cutoff_timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc),
        ),
        config=_enabled(),
        store_path=tmp_path / "pit.sqlite",
    )
    assert response.status == "block"
    assert any(b["code"] == "model_release_date_unknown" for b in response.blocks)


def test_live_historical_pit_blocks_cutoff_before_release(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Cutoff strictly before the model's release date must block with
    reason=model_not_available_at_cutoff (NOT pass, NOT warn)."""
    impl = get_model("local_finbert_mock")
    key = (impl.metadata().model_id, impl.metadata().model_version)

    # Inject a release date for the duration of the test. This guarantees the
    # release-date table is the only source of truth and there's no silent
    # fallback.
    monkeypatch.setitem(MODEL_RELEASE_DATES, key, datetime(2023, 1, 1).date())
    try:
        response = resolve_finance_text_sentiment(
            _request(
                _section("Risk language."),
                analysis_mode="live_historical_PIT",
                model_policy="pinned",
                cutoff_timestamp=datetime(2019, 1, 1, tzinfo=timezone.utc),
            ),
            config=_enabled(),
            store_path=tmp_path / "pit.sqlite",
        )
        assert response.status == "block"
        assert any(
            b["code"] == "model_not_available_at_cutoff" for b in response.blocks
        )
    finally:
        # monkeypatch.setitem auto-restores on teardown; explicit safety net.
        MODEL_RELEASE_DATES.pop(key, None)


def test_retrospective_research_does_not_silently_fall_back_to_pit(
    tmp_path: Path,
) -> None:
    """retrospective_research with old data is allowed, but the run is labeled
    not_live_historical_PIT so consumers can see the distinction."""
    response = resolve_finance_text_sentiment(
        _request(
            _section("Risk language about competition."),
            analysis_mode="retrospective_research",
            cutoff_timestamp=datetime(2010, 1, 1, tzinfo=timezone.utc),
        ),
        config=_enabled(),
        store_path=tmp_path / "pit.sqlite",
    )
    assert "retrospective_research:not_live_historical_PIT" in response.warnings
    # And it must NOT be silently labeled as a passing PIT run.
    assert response.status != "block"

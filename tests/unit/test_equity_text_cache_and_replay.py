"""Pin-6 cache vs replay tests.

  * cache hit returns observations whose cache_key matches the request
  * model_version change misses cache AND does not overwrite old observations
  * replay_from_stored_observations returns observations recorded under a
    run_id and never performs live computation
  * replay PIT cutoff filtering: observations with available_at > cutoff are
    never returned
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.hashing import hash_section_text
from viza.equity.text.models import get_model
from viza.equity.text.persistence import get_sentiment_observation_store
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


ACCEPTED_AT = datetime(2023, 11, 2, 23, 8, 27, tzinfo=timezone.utc)
RETRIEVED_AT = datetime(2026, 5, 14, 14, 0, tzinfo=timezone.utc)


def _enabled() -> EquityTextConfig:
    return EquityTextConfig(
        sec_text_analysis_enabled=True,
        text_sentiment_resolver_enabled=True,
        finbert_enabled=True,
    )


def _section(text: str, *, accession: str = "acc-1") -> ParsedSection:
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


def _request(
    section: ParsedSection,
    *,
    cache_policy: str = "serve_or_compute",
    analysis_mode: str = "live_current",
) -> ResolverRequest:
    return ResolverRequest(
        target=ResolverTarget(cik="0000320193"),
        filing=ResolverFilingSelector(accession=section.filing_accession),
        sections=["risk_factors"],
        cache_policy=cache_policy,  # type: ignore[arg-type]
        analysis_mode=analysis_mode,  # type: ignore[arg-type]
        mock_parsed_sections=[section],
    )


def test_cache_hit_returns_same_observations(tmp_path: Path) -> None:
    section = _section("Competition is intense. Margins may compress.")
    store_path = tmp_path / "store.sqlite"
    first = resolve_finance_text_sentiment(
        _request(section),
        config=_enabled(),
        store_path=store_path,
    )
    assert first.source == "fresh_compute"
    second = resolve_finance_text_sentiment(
        _request(section),
        config=_enabled(),
        store_path=store_path,
    )
    assert second.source == "cache"
    # The chunk identities and cache_keys must be the same.
    assert {o.cache_key for o in first.observations} == {
        o.cache_key for o in second.observations
    }
    assert {o.chunk_id for o in first.observations} == {
        o.chunk_id for o in second.observations
    }


def test_serve_only_with_no_cache_hit_returns_no_observations(tmp_path: Path) -> None:
    section = _section("Some risk language about competition and margins.")
    response = resolve_finance_text_sentiment(
        _request(section, cache_policy="serve_only"),
        config=_enabled(),
        store_path=tmp_path / "store.sqlite",
    )
    assert response.observations == []
    assert any("serve_only:cache_miss" in w for w in response.warnings)


def test_queue_if_missing_returns_queue_ticket(tmp_path: Path) -> None:
    section = _section("Risk language about regulatory exposure.")
    response = resolve_finance_text_sentiment(
        _request(section, cache_policy="queue_if_missing"),
        config=_enabled(),
        store_path=tmp_path / "store.sqlite",
    )
    assert response.status == "queued"
    assert response.source == "queued"
    assert len(response.queue_tickets) == 1
    assert response.queue_tickets[0].filing_accession == "acc-1"


def test_model_version_change_misses_cache_and_preserves_old(tmp_path: Path) -> None:
    """Critical PIN guarantee: silent model upgrade must NOT overwrite history.

    We simulate a model_version bump by overriding the metadata of the mock
    implementation in a copy and verifying the cache_key changes. The original
    observation row must remain untouched in the store.
    """
    section = _section("Risk language about competition and operations.")
    store_path = tmp_path / "store.sqlite"
    first = resolve_finance_text_sentiment(
        _request(section),
        config=_enabled(),
        store_path=store_path,
    )
    assert first.observations
    original_cache_key = first.observations[0].cache_key

    # Mutate the registered mock model to bump its model_version. We restore
    # afterwards to keep test isolation.
    impl = get_model("local_finbert_mock")
    original_hash = impl._model_hash  # type: ignore[attr-defined]
    impl._model_hash = "deadbeef" * 8  # type: ignore[attr-defined]
    try:
        second = resolve_finance_text_sentiment(
            _request(section),
            config=_enabled(),
            store_path=store_path,
        )
        # Different model identity must produce a different cache_key.
        assert second.observations
        assert second.observations[0].cache_key != original_cache_key
        # And the original observations must still be retrievable by their
        # original cache_key.
        store = get_sentiment_observation_store(store_path)
        original_rows = store.lookup_by_cache_key(original_cache_key)
        assert original_rows, "original observations were overwritten"
    finally:
        impl._model_hash = original_hash  # type: ignore[attr-defined]


def test_replay_returns_recorded_observations_no_live_calls(tmp_path: Path) -> None:
    section = _section("Risk language about supply chain.")
    store_path = tmp_path / "store.sqlite"
    fresh = resolve_finance_text_sentiment(
        _request(section),
        config=_enabled(),
        store_path=store_path,
    )
    run_id = fresh.audit["run_id"]

    replay_request = ResolverRequest(
        target=ResolverTarget(entity_id=run_id),
        filing=ResolverFilingSelector(),
        sections=[],
        analysis_mode="replay_from_stored_observations",
        mock_parsed_sections=None,
    )
    response = resolve_finance_text_sentiment(
        replay_request,
        config=_enabled(),
        store_path=store_path,
    )
    assert response.source == "stored_replay"
    assert response.status == "pass"
    assert len(response.observations) == len(fresh.observations)


def test_replay_pit_cutoff_filters_future_observations(tmp_path: Path) -> None:
    section = _section("Risk language about supply chain.")
    store_path = tmp_path / "store.sqlite"
    fresh = resolve_finance_text_sentiment(
        _request(section),
        config=_enabled(),
        store_path=store_path,
    )
    run_id = fresh.audit["run_id"]

    # Cutoff strictly before any observation's available_at.
    cutoff = ACCEPTED_AT - timedelta(days=1)
    replay_request = ResolverRequest(
        target=ResolverTarget(entity_id=run_id),
        filing=ResolverFilingSelector(),
        sections=[],
        analysis_mode="replay_from_stored_observations",
        cutoff_timestamp=cutoff,
        mock_parsed_sections=None,
    )
    response = resolve_finance_text_sentiment(
        replay_request,
        config=_enabled(),
        store_path=store_path,
    )
    assert response.observations == []

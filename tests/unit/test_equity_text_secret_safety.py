"""Stage B secret-safety sentinel sweep.

Per brief §18: no API keys may appear in observations, runs, reports,
proofs, fixtures, logs, API responses, package previews, or UI payloads.

This test sets sentinel placeholder values in the FMP, FRED, and HF env
vars, runs the resolver end-to-end (mock model, mocked filing), then asserts
no sentinel substring appears in:
  * the ResolverResponse JSON,
  * the persisted RunSnapshot JSON,
  * any persisted SentimentObservation JSON,
  * the EquityTextConfig.masked_summary() output,
  * the resolver's audit dict.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.hashing import hash_section_text
from viza.equity.text.persistence import get_sentiment_observation_store
from viza.equity.text.resolver import resolve_finance_text_sentiment
from viza.equity.text.secrets import (
    DEFAULT_SECRET_SENTINELS,
    SecretLeakError,
    scan_for_secrets,
)
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


@pytest.fixture
def planted_sentinels(monkeypatch):
    """Populate env vars with sentinel values for the duration of the test."""
    monkeypatch.setenv("FMP_API_KEY", "TEST_FMP_SECRET_SHOULD_NOT_APPEAR")
    monkeypatch.setenv("FRED_API_KEY", "TEST_FRED_SECRET_SHOULD_NOT_APPEAR")
    monkeypatch.setenv("HF_TOKEN", "TEST_HF_SECRET_SHOULD_NOT_APPEAR")
    yield


def _section(text: str) -> ParsedSection:
    return ParsedSection(
        filing_accession="acc-secrets-1",
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


def test_scan_for_secrets_finds_a_planted_value() -> None:
    payload = {"safe": "ok", "danger": "value contains TEST_FMP_SECRET_SHOULD_NOT_APPEAR here"}
    with pytest.raises(SecretLeakError) as excinfo:
        scan_for_secrets(payload)
    assert excinfo.value.sentinel == "TEST_FMP_SECRET_SHOULD_NOT_APPEAR"
    assert ".danger" in excinfo.value.location


def test_scan_for_secrets_handles_nested_structures() -> None:
    payload = {
        "level1": [
            {"level2": {"a": "TEST_HF_SECRET_SHOULD_NOT_APPEAR"}},
        ]
    }
    with pytest.raises(SecretLeakError):
        scan_for_secrets(payload)


def test_resolver_response_contains_no_sentinels(
    planted_sentinels, tmp_path: Path
) -> None:
    config = EquityTextConfig(
        sec_text_analysis_enabled=True,
        text_sentiment_resolver_enabled=True,
        finbert_enabled=True,
    )
    request = ResolverRequest(
        target=ResolverTarget(cik="0000320193", ticker_alias="AAPL"),
        filing=ResolverFilingSelector(accession="acc-secrets-1"),
        sections=["risk_factors"],
        mock_parsed_sections=[_section("Risk language about competition.")],
    )
    response = resolve_finance_text_sentiment(
        request,
        config=config,
        store_path=tmp_path / "store.sqlite",
    )
    # Serialize the entire response (Pydantic dump) and scan.
    scan_for_secrets(response.model_dump(mode="json"))


def test_persisted_observations_contain_no_sentinels(
    planted_sentinels, tmp_path: Path
) -> None:
    config = EquityTextConfig(
        sec_text_analysis_enabled=True,
        text_sentiment_resolver_enabled=True,
        finbert_enabled=True,
    )
    request = ResolverRequest(
        target=ResolverTarget(cik="0000320193"),
        filing=ResolverFilingSelector(accession="acc-secrets-1"),
        sections=["risk_factors"],
        mock_parsed_sections=[_section("Risk language about supply chain.")],
    )
    store_path = tmp_path / "store.sqlite"
    response = resolve_finance_text_sentiment(
        request,
        config=config,
        store_path=store_path,
    )
    run_id = response.audit["run_id"]
    store = get_sentiment_observation_store(store_path)
    snapshot = store.get_run(run_id)
    observations = store.list_observations_for_run(run_id)
    aggregates = store.list_section_aggregates_for_run(run_id)

    scan_for_secrets(snapshot.model_dump(mode="json"))
    for obs in observations:
        scan_for_secrets(obs.model_dump(mode="json"))
    for aggregate in aggregates:
        scan_for_secrets(aggregate.model_dump(mode="json"))


def test_masked_summary_redacts_secret_paths(planted_sentinels) -> None:
    config = EquityTextConfig.from_env(load_local_dotenv=False)
    summary = config.masked_summary()
    scan_for_secrets(summary)


def test_default_sentinel_set_matches_brief() -> None:
    assert set(DEFAULT_SECRET_SENTINELS) == {
        "TEST_FMP_SECRET_SHOULD_NOT_APPEAR",
        "TEST_FRED_SECRET_SHOULD_NOT_APPEAR",
        "TEST_HF_SECRET_SHOULD_NOT_APPEAR",
    }

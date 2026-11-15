"""Tests for the section aggregator and the delta-vs-prior-filing record."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from viza.equity.text.aggregation import (
    aggregate_section,
    build_delta,
    confidence_label_for,
)
from viza.equity.text.human_review import HUMAN_REVIEW_TERM_SET_VERSION
from viza.equity.text.types import SentimentObservation


NOW = datetime(2026, 5, 14, 14, 0, tzinfo=timezone.utc)
PRIOR = datetime(2024, 11, 2, 23, 8, 27, tzinfo=timezone.utc)
CURRENT = datetime(2025, 11, 2, 23, 8, 27, tzinfo=timezone.utc)


def _obs(
    *,
    positive: float,
    neutral: float,
    negative: float,
    label: str,
    confidence: float,
    requires_human_review: bool = False,
    matched: list[str] | None = None,
    filing_accession: str = "acc-current",
    available_at: datetime = CURRENT,
    cache_key: str = "x" * 64,
    model_version: str = "v1.0",
    chunking_policy_hash: str = "p" * 64,
    parser_version: str = "ixbrl_section_parser_v1",
) -> SentimentObservation:
    return SentimentObservation(
        observation_id=str(uuid4()),
        run_id="run-1",
        cache_key=cache_key,
        entity_id="sec:cik:0000320193",
        cik="0000320193",
        filing_accession=filing_accession,
        section_id="risk_factors",
        chunk_id=str(uuid4()),
        input_text_hash="a" * 64,
        section_text_hash="b" * 64,
        parser_version=parser_version,
        chunking_policy_hash=chunking_policy_hash,
        model_id="viza.mock/finbert",
        model_version=model_version,
        model_hash="c" * 64,
        tokenizer_hash="d" * 64,
        inference_config_hash="e" * 64,
        positive_prob=positive,
        neutral_prob=neutral,
        negative_prob=negative,
        label=label,  # type: ignore[arg-type]
        confidence=confidence,
        confidence_label=confidence_label_for(
            confidence=confidence,
            requires_human_review=requires_human_review,
        ),
        requires_human_review=requires_human_review,
        matched_human_review_terms=matched or [],
        human_review_term_set_version=HUMAN_REVIEW_TERM_SET_VERSION,
        observed_at=available_at,
        available_at=available_at,
        retrieved_at=NOW,
        inference_at=NOW,
        source_ref="sec:accession:acc-current/section:risk_factors/chunk:0",
    )


def test_confidence_label_thresholds() -> None:
    assert confidence_label_for(confidence=0.95, requires_human_review=False) == "model_supported_high"
    assert confidence_label_for(confidence=0.7, requires_human_review=False) == "model_supported_medium"
    assert confidence_label_for(confidence=0.3, requires_human_review=False) == "model_supported_low"
    # Human-review dominates regardless of confidence.
    assert confidence_label_for(confidence=0.99, requires_human_review=True) == "requires_human_review"


def test_aggregate_section_computes_dispersion_and_negative_ratio() -> None:
    obs = [
        _obs(positive=0.7, neutral=0.2, negative=0.1, label="positive", confidence=0.7),
        _obs(positive=0.2, neutral=0.2, negative=0.6, label="negative", confidence=0.6),
        _obs(positive=0.1, neutral=0.1, negative=0.8, label="negative", confidence=0.9),
    ]
    aggregate = aggregate_section(
        run_id="run-1",
        entity_id="sec:cik:0000320193",
        cik="0000320193",
        filing_accession="acc-current",
        section_id="risk_factors",
        chunk_observations=obs,
        available_at=CURRENT,
    )
    assert aggregate.chunks_count == 3
    assert 0.0 < aggregate.negative_chunk_ratio <= 1.0
    assert aggregate.high_confidence_negative_count == 1  # only the 0.9 confidence one
    assert aggregate.sentiment_dispersion > 0.0


def test_aggregate_section_propagates_human_review_flag() -> None:
    obs = [
        _obs(positive=0.4, neutral=0.4, negative=0.2, label="positive", confidence=0.5),
        _obs(
            positive=0.1,
            neutral=0.2,
            negative=0.7,
            label="negative",
            confidence=0.8,
            requires_human_review=True,
            matched=["going concern"],
        ),
    ]
    aggregate = aggregate_section(
        run_id="run-1",
        entity_id="sec:cik:0000320193",
        cik="0000320193",
        filing_accession="acc-current",
        section_id="risk_factors",
        chunk_observations=obs,
        available_at=CURRENT,
    )
    assert aggregate.requires_human_review is True
    assert "going concern" in aggregate.matched_human_review_terms
    assert aggregate.validation_status == "warn"


def test_build_delta_matches_metadata_and_reports_clean() -> None:
    current = [
        _obs(positive=0.3, neutral=0.3, negative=0.4, label="negative", confidence=0.6),
    ]
    prior = [
        _obs(
            positive=0.6,
            neutral=0.3,
            negative=0.1,
            label="positive",
            confidence=0.7,
            filing_accession="acc-prior",
            available_at=PRIOR,
        ),
    ]
    delta = build_delta(
        entity_id="sec:cik:0000320193",
        cik="0000320193",
        section_id="risk_factors",
        current_observations=current,
        prior_observations=prior,
        current_available_at=CURRENT,
        prior_available_at=PRIOR,
    )
    assert delta is not None
    assert delta.model_metadata_match is True
    # Negative tone delta should be positive (got more negative).
    assert delta.negative_tone_delta > 0
    # Net sentiment delta should be negative.
    assert delta.net_sentiment_delta < 0
    assert "model_metadata_mismatch" not in delta.warnings


def test_build_delta_warns_on_metadata_mismatch() -> None:
    current = [
        _obs(positive=0.3, neutral=0.3, negative=0.4, label="negative", confidence=0.6),
    ]
    prior = [
        _obs(
            positive=0.6,
            neutral=0.3,
            negative=0.1,
            label="positive",
            confidence=0.7,
            filing_accession="acc-prior",
            available_at=PRIOR,
            model_version="v0.9",  # MISMATCH
        ),
    ]
    delta = build_delta(
        entity_id="sec:cik:0000320193",
        cik="0000320193",
        section_id="risk_factors",
        current_observations=current,
        prior_observations=prior,
        current_available_at=CURRENT,
        prior_available_at=PRIOR,
    )
    assert delta is not None
    assert delta.model_metadata_match is False
    assert "model_metadata_mismatch" in delta.warnings
    assert delta.confidence_label == "comparison_unreliable"

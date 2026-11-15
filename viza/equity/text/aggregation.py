"""Section aggregation and delta-vs-prior-filing.

Per pin 8 (bonus pins from the design pass):
  * sentiment_dispersion = population stdev of net_sentiment across chunks.
  * confidence_label per chunk follows the threshold ladder; the human-review
    gate dominates (highest priority).
  * delta.model_metadata_match is the 5-field AND; mismatch -> warning +
    confidence_label="comparison_unreliable".

Aggregates and deltas are pure functions on top of the per-chunk observations
that the resolver produced; no DB access is required to compute them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import pstdev
from typing import Iterable
from uuid import uuid4

from viza.equity.text.types import (
    ConfidenceLabel,
    DeltaRecord,
    SectionAggregate,
    SentimentObservation,
)


HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.60


def confidence_label_for(
    *,
    confidence: float,
    requires_human_review: bool,
) -> ConfidenceLabel:
    """Per-chunk confidence label per the bonus-pin threshold ladder."""
    if requires_human_review:
        return "requires_human_review"
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return "model_supported_high"
    if confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "model_supported_medium"
    return "model_supported_low"


def aggregate_section(
    *,
    run_id: str,
    entity_id: str,
    cik: str,
    filing_accession: str,
    section_id: str,
    chunk_observations: list[SentimentObservation],
    available_at: datetime,
    pit_policy: dict | None = None,
    rights_policy: dict | None = None,
) -> SectionAggregate:
    """Aggregate per-chunk observations into one section-level record.

    All inputs are assumed to share the same filing_accession/section_id;
    this is the resolver's responsibility to enforce.
    """
    if not chunk_observations:
        raise ValueError(
            f"cannot aggregate empty chunk set for section {section_id}"
        )

    n = len(chunk_observations)
    pos_avg = sum(o.positive_prob for o in chunk_observations) / n
    neu_avg = sum(o.neutral_prob for o in chunk_observations) / n
    neg_avg = sum(o.negative_prob for o in chunk_observations) / n
    net = pos_avg - neg_avg

    nets = [o.positive_prob - o.negative_prob for o in chunk_observations]
    dispersion = pstdev(nets) if n >= 2 else 0.0

    high_conf_neg_count = sum(
        1
        for o in chunk_observations
        if o.label == "negative" and o.confidence >= HIGH_CONFIDENCE_THRESHOLD
    )
    negative_chunk_ratio = sum(1 for o in chunk_observations if o.label == "negative") / n

    any_human_review = any(o.requires_human_review for o in chunk_observations)
    matched_terms_union: list[str] = sorted(
        {t for o in chunk_observations for t in o.matched_human_review_terms}
    )

    return SectionAggregate(
        section_sentiment_id=str(uuid4()),
        run_id=run_id,
        entity_id=entity_id,
        cik=cik,
        filing_accession=filing_accession,
        section_id=section_id,  # type: ignore[arg-type]
        chunk_observation_ids=[o.observation_id for o in chunk_observations],
        chunks_count=n,
        positive_prob_avg=pos_avg,
        neutral_prob_avg=neu_avg,
        negative_prob_avg=neg_avg,
        net_sentiment=net,
        negative_chunk_ratio=negative_chunk_ratio,
        high_confidence_negative_count=high_conf_neg_count,
        sentiment_dispersion=dispersion,
        requires_human_review=any_human_review,
        matched_human_review_terms=matched_terms_union,
        available_at=available_at,
        pit_policy=pit_policy or {},
        rights_policy=rights_policy or {},
        validation_status="warn" if any_human_review else "pass",
    )


def _section_summary(observations: Iterable[SentimentObservation]) -> dict:
    """Reduce a section's chunks to a small comparable summary."""
    obs = list(observations)
    if not obs:
        return {
            "model_id": None,
            "model_version": None,
            "tokenizer_hash": None,
            "chunking_policy_hash": None,
            "parser_version": None,
            "negative_tone": 0.0,
            "net_sentiment": 0.0,
            "chunks": 0,
        }
    pos = sum(o.positive_prob for o in obs) / len(obs)
    neg = sum(o.negative_prob for o in obs) / len(obs)
    # All observations from a single filing+section share their model metadata;
    # we sample the first observation. Mismatch within a section is impossible
    # by construction in Stage A (one resolver call per filing+section).
    head = obs[0]
    return {
        "model_id": head.model_id,
        "model_version": head.model_version,
        "tokenizer_hash": head.tokenizer_hash,
        "chunking_policy_hash": head.chunking_policy_hash,
        "parser_version": head.parser_version,
        "negative_tone": neg,
        "net_sentiment": pos - neg,
        "chunks": len(obs),
    }


def build_delta(
    *,
    entity_id: str,
    cik: str,
    section_id: str,
    current_observations: list[SentimentObservation],
    prior_observations: list[SentimentObservation],
    current_available_at: datetime,
    prior_available_at: datetime,
    delta_method: str = "same_section_prior_filing",
) -> DeltaRecord | None:
    """Return a DeltaRecord, or None if no prior is available."""
    if not current_observations or not prior_observations:
        return None

    current_summary = _section_summary(current_observations)
    prior_summary = _section_summary(prior_observations)

    metadata_match = (
        current_summary["model_id"] == prior_summary["model_id"]
        and current_summary["model_version"] == prior_summary["model_version"]
        and current_summary["tokenizer_hash"] == prior_summary["tokenizer_hash"]
        and current_summary["chunking_policy_hash"] == prior_summary["chunking_policy_hash"]
        and current_summary["parser_version"] == prior_summary["parser_version"]
    )

    warnings: list[str] = []
    if not metadata_match:
        warnings.append("model_metadata_mismatch")

    current_filing_accession = current_observations[0].filing_accession
    prior_filing_accession = prior_observations[0].filing_accession

    # Crude novel-language signal: chunks in current whose text_hash is not in prior.
    prior_hashes = {o.input_text_hash for o in prior_observations}
    novel_sentence_count = sum(
        1 for o in current_observations if o.input_text_hash not in prior_hashes
    )

    new_negative_flag = (
        current_summary["negative_tone"] > prior_summary["negative_tone"] + 0.10
    )
    removed_positive_flag = (
        current_summary["net_sentiment"] < prior_summary["net_sentiment"] - 0.10
    )

    return DeltaRecord(
        delta_id=str(uuid4()),
        entity_id=entity_id,
        cik=cik,
        current_filing_accession=current_filing_accession,
        prior_filing_accession=prior_filing_accession,
        section_id=section_id,  # type: ignore[arg-type]
        delta_method=delta_method,  # type: ignore[arg-type]
        negative_tone_delta=current_summary["negative_tone"] - prior_summary["negative_tone"],
        net_sentiment_delta=current_summary["net_sentiment"] - prior_summary["net_sentiment"],
        new_negative_language_flag=new_negative_flag,
        removed_positive_language_flag=removed_positive_flag,
        novel_sentence_count=novel_sentence_count,
        prior_available_at=prior_available_at,
        current_available_at=current_available_at,
        model_metadata_match=metadata_match,
        warnings=warnings,
        confidence_label="comparison_unreliable" if not metadata_match else "research_supported_experimental",
    )

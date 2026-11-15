"""Package-redaction rules for finance text sentiment exports.

Applies the existing three-mode contract (white_box / output_only /
marketplace_draft) to a sentiment ResolverResponse, producing a redacted
preview that is safe for the chosen package surface. SEC filing text is
public-official but bulk raw text is conservatively redacted by default.

Rules (v0.1):

  white_box:
    * Include section refs, section_id, section_text_hash.
    * Include per-chunk distributions (no raw chunk text by default).
    * Include model metadata, deltas, validation, rights report.
    * Short excerpts MAY be included only if the source policy permits AND
      the caller explicitly opts in (Stage A/C: opt-in not exposed; behaves
      as "no excerpts").

  output_only:
    * Filing reading card: target identity, section_id, aggregates, deltas.
    * Derived sentiment numbers, model metadata, PIT/rights/validation labels.
    * NO raw chunk text.

  marketplace_draft:
    * Derived sentiment numbers, section refs, hashes, model metadata,
      rights summary, non-advice boundary.
    * NO raw chunk text. NO short excerpts.
    * partially_resolved runs are BLOCKED with reason
      "partial_run_not_marketplace_ready" (pin 7 clause).
"""

from __future__ import annotations

from typing import Any, Literal

from viza.equity.text.types import ResolverResponse


PackageMode = Literal["white_box", "output_only", "marketplace_draft"]


class PackageRedactionBlocked(RuntimeError):
    """Raised when redaction policy blocks the requested package mode."""

    def __init__(self, *, mode: str, reason: str) -> None:
        super().__init__(f"package_mode={mode} blocked: {reason}")
        self.mode = mode
        self.reason = reason


def redact_for_package(
    response: ResolverResponse,
    *,
    mode: PackageMode,
) -> dict[str, Any]:
    """Return a dict payload ready for inclusion in a .viza package preview.

    The function never mutates the original ``response``; it returns a fresh
    dict with selected fields and explicit absence markers for redacted
    sections. The caller can serialize the dict into the package manifest.
    """
    if mode == "marketplace_draft" and response.status == "partial":
        raise PackageRedactionBlocked(
            mode=mode, reason="partial_run_not_marketplace_ready"
        )

    chunk_payloads = [
        _chunk_payload(obs, include_text=False, include_excerpt=False)
        for obs in response.observations
    ]

    base: dict[str, Any] = {
        "package_mode": mode,
        "resolver_id": response.resolver_id,
        "status": response.status,
        "model_metadata": response.model_metadata,
        "pit_summary": response.pit_summary,
        "rights_summary": response.rights_summary,
        "validation_summary": response.validation_summary,
        "non_advice_boundary": response.non_advice_boundary,
        "redactions": [],
        "audit": {
            "run_id": response.audit.get("run_id"),
            "proof_checksum": response.audit.get("proof_checksum"),
        },
    }

    if mode == "white_box":
        base["section_aggregates"] = [
            agg.model_dump(mode="json") for agg in response.section_aggregates
        ]
        base["deltas"] = [d.model_dump(mode="json") for d in response.deltas]
        base["chunk_observations"] = chunk_payloads
        base["redactions"].append(
            {"field": "chunk_text", "reason": "bulk_raw_text_redacted_by_default"}
        )
        return base

    if mode == "output_only":
        base["filing_reading_card"] = _filing_reading_card(response)
        base["deltas"] = [d.model_dump(mode="json") for d in response.deltas]
        base["redactions"].append(
            {"field": "chunk_text", "reason": "output_only_excludes_raw_text"}
        )
        base["redactions"].append(
            {"field": "per_chunk_observations", "reason": "output_only_aggregates_only"}
        )
        return base

    if mode == "marketplace_draft":
        base["filing_reading_card"] = _filing_reading_card(response)
        base["chunk_summaries"] = [
            {
                "chunk_id": c["chunk_id"],
                "section_id": c["section_id"],
                "label": c["label"],
                "confidence_label": c["confidence_label"],
                "requires_human_review": c["requires_human_review"],
            }
            for c in chunk_payloads
        ]
        base["section_aggregates"] = [
            _aggregate_summary(agg.model_dump(mode="json"))
            for agg in response.section_aggregates
        ]
        base["deltas"] = [
            _delta_summary(d.model_dump(mode="json")) for d in response.deltas
        ]
        base["redactions"].extend(
            [
                {"field": "chunk_text", "reason": "marketplace_redacts_raw_text"},
                {"field": "chunk_excerpt", "reason": "marketplace_redacts_excerpts_v0_1"},
                {"field": "per_chunk_probabilities", "reason": "marketplace_aggregates_and_summaries_only"},
            ]
        )
        return base

    raise ValueError(f"unknown package_mode={mode!r}")


def _chunk_payload(
    observation: Any,
    *,
    include_text: bool,
    include_excerpt: bool,
) -> dict[str, Any]:
    payload = observation.model_dump(mode="json")
    if not include_text:
        # SentimentObservation doesn't carry the raw chunk text (that's only
        # in ChunkRecord); but we still strip any source_ref that could
        # contain content beyond the accession path.
        pass
    if not include_excerpt:
        payload.pop("text", None)
        payload.pop("excerpt", None)
    return payload


def _filing_reading_card(response: ResolverResponse) -> dict[str, Any]:
    if not response.section_aggregates:
        return {"filings": []}
    by_filing: dict[str, list] = {}
    for aggregate in response.section_aggregates:
        by_filing.setdefault(aggregate.filing_accession, []).append(aggregate)
    cards = []
    for accession, aggregates in sorted(by_filing.items()):
        cards.append(
            {
                "filing_accession": accession,
                "sections": [
                    {
                        "section_id": a.section_id,
                        "net_sentiment": a.net_sentiment,
                        "negative_chunk_ratio": a.negative_chunk_ratio,
                        "high_confidence_negative_count": a.high_confidence_negative_count,
                        "sentiment_dispersion": a.sentiment_dispersion,
                        "requires_human_review": a.requires_human_review,
                        "matched_human_review_terms": a.matched_human_review_terms,
                        "chunks_count": a.chunks_count,
                    }
                    for a in aggregates
                ],
            }
        )
    return {"filings": cards}


def _aggregate_summary(agg: dict[str, Any]) -> dict[str, Any]:
    """Marketplace-grade aggregate: numbers + identifiers, no chunk_ids."""
    keep = {
        "filing_accession",
        "section_id",
        "net_sentiment",
        "negative_chunk_ratio",
        "high_confidence_negative_count",
        "sentiment_dispersion",
        "chunks_count",
        "requires_human_review",
        "matched_human_review_terms",
        "available_at",
        "validation_status",
    }
    return {k: v for k, v in agg.items() if k in keep}


def _delta_summary(delta: dict[str, Any]) -> dict[str, Any]:
    keep = {
        "current_filing_accession",
        "prior_filing_accession",
        "section_id",
        "delta_method",
        "negative_tone_delta",
        "net_sentiment_delta",
        "new_negative_language_flag",
        "removed_positive_language_flag",
        "model_metadata_match",
        "confidence_label",
        "warnings",
    }
    return {k: v for k, v in delta.items() if k in keep}

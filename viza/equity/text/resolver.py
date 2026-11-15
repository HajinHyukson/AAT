"""The single public entry point: ``resolve_finance_text_sentiment``.

This is the resolver-as-syscall. Methodology graphs call it; the runtime
decides whether to serve from cache, compute fresh, queue, or replay. The
graph node sees the same response shape regardless of the underlying path.

The resolver is model-agnostic: it dispatches to a ``ModelImplementation``
chosen by ``implementation_id``. Stage A uses ``local_finbert_mock``; Stage B
adds the real local FinBERT implementations under the same protocol.

PIN COMPLIANCE
  pin 1 — hashes/cache_key per viza.equity.text.hashing
  pin 2 — human-review pre-filter runs upstream of inference
  pin 3 — only iXBRL section extraction (caller provides ParsedSections in
          Stage A; live SEC client wires in Stage C)
  pin 4 — available_at precision recorded on every observation
  pin 5 — live_historical_PIT blocks if model release date is unknown or after cutoff
  pin 6 — cache_key vs run_id are distinct lookup paths
  pin 7 — queue_if_missing returns queued status synchronously with a ticket
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from viza.equity.text.aggregation import (
    aggregate_section,
    build_delta,
    confidence_label_for,
)
from viza.equity.text.chunker import (
    DEFAULT_CHUNKING_POLICY,
    chunk_section_text,
)
from viza.equity.text.config import EquityTextConfig
from viza.equity.text.hashing import (
    canonical_json,
    compute_cache_key,
    hash_chunking_policy,
    sha256_hex,
)
from viza.equity.text.human_review import HUMAN_REVIEW_TERM_SET_VERSION, evaluate
from viza.equity.text.models import get_model
from viza.equity.text.persistence import (
    SentimentObservationStore,
    get_sentiment_observation_store,
)
from viza.equity.text.release_dates import (
    ModelReleaseDateUnknown,
    model_released_by,
)
from viza.equity.text.types import (
    AnalysisMode,
    DeltaRecord,
    ParsedSection,
    QueueTicket,
    ResolverRequest,
    ResolverResponse,
    RunSnapshot,
    SectionAggregate,
    SentimentObservation,
)


RESOLVER_ID = "viza.finance.text.sentiment"
RESOLVER_NAMESPACE = "viza.finance.text"
RESOLVER_VERSION = "v0.1.0_stage_a"

DEFAULT_IMPLEMENTATION_ID = "local_finbert_mock"


def resolve_finance_text_sentiment(
    request: ResolverRequest,
    *,
    config: EquityTextConfig | None = None,
    store: SentimentObservationStore | None = None,
    store_path: str | Path | None = None,
    implementation_id: str = DEFAULT_IMPLEMENTATION_ID,
    now: datetime | None = None,
) -> ResolverResponse:
    """Resolve sentiment for the requested filing+sections.

    Returns a ``ResolverResponse`` whose ``status`` field tells the caller
    what happened: ``pass`` / ``warn`` / ``block`` / ``queued`` / ``disabled`` /
    ``missing_model`` / ``partial``. The methodology graph reads observations
    and aggregates from the response; it never reaches into the store.
    """
    active_config = config or EquityTextConfig.from_env()
    current_time = now or datetime.now(timezone.utc)

    # ---- Feature flag gates ------------------------------------------------

    if active_config.feature_off():
        return _disabled_response(reason="text_sentiment_resolver_disabled")

    if request.analysis_mode in ("live_current", "live_historical_PIT", "retrospective_research"):
        if active_config.model_inference_off():
            return _disabled_response(
                reason="finbert_disabled",
                status="missing_model",
            )

    # ---- Pin 5: historical PIT model-availability gate --------------------

    impl = get_model(implementation_id)
    metadata = impl.metadata()
    blocks: list[dict] = []
    warnings: list[str] = []

    if (
        request.analysis_mode == "live_historical_PIT"
        and request.cutoff_timestamp is not None
        and request.model_policy in ("pinned", "replay_exact")
    ):
        try:
            released = model_released_by(
                model_id=metadata.model_id,
                model_version=metadata.model_version,
                cutoff=request.cutoff_timestamp.date(),
            )
        except ModelReleaseDateUnknown:
            blocks.append(
                {
                    "code": "model_release_date_unknown",
                    "model_id": metadata.model_id,
                    "model_version": metadata.model_version,
                }
            )
            return _blocked_response(blocks=blocks, model_metadata=metadata.model_dump(mode="json"))
        if not released:
            blocks.append(
                {
                    "code": "model_not_available_at_cutoff",
                    "model_id": metadata.model_id,
                    "model_version": metadata.model_version,
                    "cutoff": request.cutoff_timestamp.isoformat(),
                }
            )
            return _blocked_response(blocks=blocks, model_metadata=metadata.model_dump(mode="json"))

    if request.analysis_mode == "retrospective_research":
        # Retrospective use is allowed, but the run is labeled not_live_historical_PIT
        # so downstream consumers can see the distinction.
        warnings.append("retrospective_research:not_live_historical_PIT")

    # ---- Replay path ------------------------------------------------------

    active_store = store or get_sentiment_observation_store(store_path)

    if request.analysis_mode == "replay_from_stored_observations":
        # Replay requires an explicit run_id in the audit dict; for Stage A
        # the caller supplies one through the persisted run record. Without a
        # run_id, replay cannot proceed.
        run_id = (request.target.entity_id or "").strip()
        if not run_id:
            return _blocked_response(
                blocks=[{"code": "replay_requires_run_id_in_target_entity_id"}],
                model_metadata=metadata.model_dump(mode="json"),
            )
        replayed = active_store.list_observations_for_run(
            run_id,
            cutoff=request.cutoff_timestamp,
        )
        aggregates = active_store.list_section_aggregates_for_run(run_id)
        deltas = active_store.list_deltas_for_run(run_id)
        return ResolverResponse(
            resolver_id=RESOLVER_ID,
            status="pass" if replayed else "warn",
            source="stored_replay",
            observations=replayed,
            section_aggregates=aggregates,
            deltas=deltas,
            warnings=[] if replayed else ["replay_returned_no_observations"],
            model_metadata=metadata.model_dump(mode="json"),
            pit_summary=_pit_summary(replayed),
            rights_summary=_rights_summary(replayed),
            validation_summary=_validation_summary(replayed),
            audit={
                "run_id": run_id,
                "source_path": "replay_from_stored_observations",
            },
        )

    # ---- Section extraction (Stage A: mocked, supplied by caller) ---------

    if active_config.section_extraction_off():
        return _disabled_response(reason="sec_text_analysis_disabled")

    parsed_sections = request.mock_parsed_sections or []
    if not parsed_sections:
        # Stage A returns block; Stage C wires the live SEC client.
        return _blocked_response(
            blocks=[{"code": "stage_a_requires_mock_parsed_sections"}],
            model_metadata=metadata.model_dump(mode="json"),
        )

    # ---- Compute / cache for each parsed section --------------------------

    run_id = str(uuid4())
    all_observations: list[SentimentObservation] = []
    all_aggregates: list[SectionAggregate] = []
    all_deltas: list[DeltaRecord] = []
    queue_tickets: list[QueueTicket] = []
    sources_used: set[str] = set()

    chunking_policy = DEFAULT_CHUNKING_POLICY
    chunking_policy_hash = hash_chunking_policy(chunking_policy)

    for section in parsed_sections:
        if section.section_id == "section_unparseable":
            warnings.append(
                f"section_unparseable filing={section.filing_accession}"
            )
            continue

        # PIT availability check: a filing without available_at cannot be
        # used in live_historical_PIT mode (pin 4).
        if section.available_at is None and request.analysis_mode == "live_historical_PIT":
            blocks.append(
                {
                    "code": "filing_availability_unknown",
                    "filing_accession": section.filing_accession,
                    "section_id": section.section_id,
                }
            )
            continue

        cache_key = compute_cache_key(
            filing_accession=section.filing_accession,
            section_id=section.section_id,
            section_text_hash=section.section_text_hash,
            parser_version=section.parser_version,
            chunking_policy_hash=chunking_policy_hash,
            model_id=metadata.model_id,
            model_version=metadata.model_version,
            model_hash=metadata.model_hash,
            tokenizer_hash=metadata.tokenizer_hash,
            inference_config_hash=metadata.inference_config_hash,
        )

        # ---- Cache hit path ----
        cached = active_store.lookup_by_cache_key(cache_key)
        if cached and request.cache_policy in ("serve_or_compute", "serve_only"):
            # Re-key the cached observations under THIS run, but preserve
            # their identity and provenance. The cached observations are
            # already PIT-correct by construction (their available_at is the
            # filing's accepted timestamp).
            all_observations.extend(cached)
            sources_used.add("cache")
            section_available_at = cached[0].available_at
            aggregate = aggregate_section(
                run_id=run_id,
                entity_id=cached[0].entity_id,
                cik=cached[0].cik,
                filing_accession=section.filing_accession,
                section_id=section.section_id,
                chunk_observations=cached,
                available_at=section_available_at,
                pit_policy=section.pit_policy,
                rights_policy=section.rights_policy,
            )
            all_aggregates.append(aggregate)
            continue

        # ---- Compute-only / cache miss with serve_only ----
        if not cached and request.cache_policy == "serve_only":
            warnings.append(
                f"serve_only:cache_miss filing={section.filing_accession} "
                f"section={section.section_id}"
            )
            continue

        # ---- Queue path (pin 7) ----
        if not cached and request.cache_policy == "queue_if_missing":
            ticket = QueueTicket(
                queue_ticket_id=str(uuid4()),
                job_id=None,
                filing_accession=section.filing_accession,
                section_id=section.section_id,
                requested_at=current_time,
                resolver_request_hash=cache_key,
            )
            queue_tickets.append(ticket)
            sources_used.add("queued")
            continue

        # ---- Fresh compute path ----
        chunks = chunk_section_text(
            section_text=section.section_text,
            section_id=section.section_id,
            filing_accession=section.filing_accession,
            parser_version=section.parser_version,
            section_text_hash=section.section_text_hash,
            chunking_policy=chunking_policy,
            created_at=current_time,
        )
        if not chunks:
            warnings.append(
                f"empty_chunks filing={section.filing_accession} "
                f"section={section.section_id}"
            )
            continue

        # Run inference (mocked in Stage A; real in Stage B).
        inference_results = impl.classify(chunks)

        entity_id = (
            request.target.entity_id or f"sec:cik:{section.cik}"
        )
        section_observations: list[SentimentObservation] = []
        for chunk, result in zip(chunks, inference_results, strict=True):
            verdict = evaluate(chunk.text)
            confidence_label = confidence_label_for(
                confidence=result["confidence"],
                requires_human_review=verdict.requires_human_review,
            )
            observation = SentimentObservation(
                observation_id=str(uuid4()),
                run_id=run_id,
                cache_key=cache_key,
                entity_id=entity_id,
                cik=section.cik,
                ticker_alias=request.target.ticker_alias,
                filing_accession=section.filing_accession,
                section_id=section.section_id,
                chunk_id=chunk.chunk_id,
                input_text_hash=chunk.text_hash,
                section_text_hash=section.section_text_hash,
                parser_version=section.parser_version,
                chunking_policy_hash=chunking_policy_hash,
                model_id=metadata.model_id,
                model_version=metadata.model_version,
                model_hash=metadata.model_hash,
                tokenizer_hash=metadata.tokenizer_hash,
                inference_config_hash=metadata.inference_config_hash,
                positive_prob=result["positive_prob"],
                neutral_prob=result["neutral_prob"],
                negative_prob=result["negative_prob"],
                label=result["label"],  # type: ignore[arg-type]
                confidence=result["confidence"],
                confidence_label=confidence_label,
                requires_human_review=verdict.requires_human_review,
                matched_human_review_terms=list(verdict.matched_terms),
                human_review_term_set_version=HUMAN_REVIEW_TERM_SET_VERSION,
                # Pin 4: available_at is the filing's accepted timestamp, not now.
                observed_at=section.filing_accepted_at or section.available_at or current_time,
                available_at=section.available_at or current_time,
                retrieved_at=section.retrieved_at,
                inference_at=current_time,
                source_id="SEC_EDGAR",
                source_ref=f"sec:accession:{section.filing_accession}/section:{section.section_id}/chunk:{chunk.chunk_index}",
                lookahead_risk=section.lookahead_risk,
                rights_policy=section.rights_policy,
            )
            section_observations.append(observation)

        all_observations.extend(section_observations)
        sources_used.add("fresh_compute")

        aggregate = aggregate_section(
            run_id=run_id,
            entity_id=entity_id,
            cik=section.cik,
            filing_accession=section.filing_accession,
            section_id=section.section_id,
            chunk_observations=section_observations,
            available_at=section.available_at or current_time,
            pit_policy=section.pit_policy,
            rights_policy=section.rights_policy,
        )
        all_aggregates.append(aggregate)

        # ---- Delta vs prior filing (best-effort) ----
        prior = active_store.latest_prior_observations_for_section(
            entity_id=entity_id,
            section_id=section.section_id,
            current_filing_accession=section.filing_accession,
            current_available_at=section.available_at or current_time,
        )
        if prior:
            delta = build_delta(
                entity_id=entity_id,
                cik=section.cik,
                section_id=section.section_id,
                current_observations=section_observations,
                prior_observations=prior,
                current_available_at=section.available_at or current_time,
                prior_available_at=prior[0].available_at,
            )
            if delta is not None:
                all_deltas.append(delta)

    # ---- Persist if requested ---------------------------------------------

    snapshot = RunSnapshot(
        run_id=run_id,
        resolver_id=RESOLVER_ID,
        resolver_version=RESOLVER_VERSION,
        analysis_mode=request.analysis_mode,
        model_policy=request.model_policy,
        cache_policy=request.cache_policy,
        parser_version=parsed_sections[0].parser_version if parsed_sections else "n/a",
        chunking_policy=dict(chunking_policy),
        chunking_policy_hash=chunking_policy_hash,
        model_metadata=metadata.model_dump(mode="json"),
        inference_config_hash=metadata.inference_config_hash,
        cutoff_timestamp=request.cutoff_timestamp,
        created_at=current_time,
        status=_overall_status(blocks, warnings, all_observations, queue_tickets),
        partial_resolution_reasons=[t.model_dump(mode="json") for t in queue_tickets],
        proof_checksum=_compute_proof_checksum(
            observations=all_observations,
            aggregates=all_aggregates,
            deltas=all_deltas,
        ),
    )

    if request.persist_run:
        active_store.upsert_run(snapshot)
        for observation in all_observations:
            # Compute-only callers may have a cache hit row already; in that
            # case ON CONFLICT DO NOTHING preserves the original.
            active_store.upsert_observation(observation)
        for aggregate in all_aggregates:
            active_store.upsert_section_aggregate(aggregate)
        for delta in all_deltas:
            active_store.upsert_delta(delta, run_id=run_id)

    return ResolverResponse(
        resolver_id=RESOLVER_ID,
        status=snapshot.status,
        source=_source_label(sources_used, queue_tickets),
        observations=all_observations,
        section_aggregates=all_aggregates,
        deltas=all_deltas,
        warnings=warnings,
        blocks=blocks,
        queue_tickets=queue_tickets,
        model_metadata=metadata.model_dump(mode="json"),
        pit_summary=_pit_summary(all_observations),
        rights_summary=_rights_summary(all_observations),
        validation_summary=_validation_summary(all_observations),
        package_redaction_preview={
            "package_mode": request.package_mode,
            # Stage C implements the full redaction rules; Stage A surfaces
            # the policy intent so callers can already check non-advice boundary
            # behavior.
            "redact_bulk_raw_text": True,
            "include_derived_sentiment": True,
            "include_section_refs_and_hashes": True,
        },
        audit={
            "run_id": run_id,
            "resolver_cache_keys": [
                obs.cache_key for obs in all_observations
            ],
            "proof_checksum": snapshot.proof_checksum,
        },
    )


# ---- Helpers ---------------------------------------------------------------


def _disabled_response(
    *,
    reason: str,
    status: str = "disabled",
) -> ResolverResponse:
    return ResolverResponse(
        resolver_id=RESOLVER_ID,
        status=status,  # type: ignore[arg-type]
        source="none",
        warnings=[reason],
        audit={"reason": reason},
    )


def _blocked_response(
    *,
    blocks: list[dict],
    model_metadata: dict,
) -> ResolverResponse:
    return ResolverResponse(
        resolver_id=RESOLVER_ID,
        status="block",
        source="none",
        blocks=blocks,
        model_metadata=model_metadata,
        audit={"blocks": blocks},
    )


def _source_label(sources: set[str], tickets: list[QueueTicket]) -> str:
    if tickets and not sources - {"queued"}:
        return "queued"
    if sources == {"cache"}:
        return "cache"
    if sources == {"fresh_compute"}:
        return "fresh_compute"
    if not sources:
        return "none"
    return "fresh_compute"  # mixed (cache + fresh) presents as fresh; documented


def _overall_status(
    blocks: list[dict],
    warnings: list[str],
    observations: list[SentimentObservation],
    tickets: list[QueueTicket],
) -> str:
    if blocks:
        return "block"
    if tickets and not observations:
        return "queued"
    if tickets and observations:
        return "partial"
    if any(o.requires_human_review for o in observations):
        return "warn"
    if warnings and not observations:
        return "warn"
    if not observations:
        return "warn"
    return "pass"


def _pit_summary(observations: Iterable[SentimentObservation]) -> dict:
    obs = list(observations)
    if not obs:
        return {"observations": 0}
    risks = {o.lookahead_risk for o in obs}
    return {
        "observations": len(obs),
        "lookahead_risks": sorted(risks),
        "earliest_available_at": min(o.available_at for o in obs).isoformat(),
        "latest_available_at": max(o.available_at for o in obs).isoformat(),
    }


def _rights_summary(observations: Iterable[SentimentObservation]) -> dict:
    obs = list(observations)
    if not obs:
        return {}
    license_policies = sorted({
        o.rights_policy.get("license_policy", "unknown") for o in obs
    })
    return {
        "license_policies": license_policies,
        "redistribution_policy": obs[0].rights_policy.get(
            "redistribution_policy", "no_bulk_raw_filing_republication"
        ),
        "attribution_required": True,
    }


def _validation_summary(observations: Iterable[SentimentObservation]) -> dict:
    obs = list(observations)
    if not obs:
        return {"chunks": 0}
    return {
        "chunks": len(obs),
        "human_review_required_chunks": sum(
            1 for o in obs if o.requires_human_review
        ),
        "high_confidence_negative_chunks": sum(
            1 for o in obs if o.label == "negative" and o.confidence >= 0.85
        ),
    }


def _compute_proof_checksum(
    *,
    observations: list[SentimentObservation],
    aggregates: list[SectionAggregate],
    deltas: list[DeltaRecord],
) -> str:
    payload = {
        "observations": [obs.observation_id for obs in observations],
        "observation_cache_keys": [obs.cache_key for obs in observations],
        "aggregates": [agg.section_sentiment_id for agg in aggregates],
        "deltas": [d.delta_id for d in deltas],
    }
    return sha256_hex(canonical_json(payload))

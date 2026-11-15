"""Stage C service-layer convenience wrappers for the FastAPI router.

Mirrors the ``viza.equity.preview`` pattern: thin request/response shapes the
FastAPI handler can validate, plus a single entry point per endpoint that
delegates to the resolver / persistence / redaction layers.

Live SEC integration (replacing ``mock_parsed_sections``) is deferred to the
Stage C connector wiring. This module accepts the same ``ParsedSection``
records the test fixtures use so the FastAPI surface is exercisable today.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.package_redaction import (
    PackageRedactionBlocked,
    redact_for_package,
)
from viza.equity.text.persistence import get_sentiment_observation_store
from viza.equity.text.resolver import (
    RESOLVER_ID,
    RESOLVER_NAMESPACE,
    RESOLVER_VERSION,
    resolve_finance_text_sentiment,
)
from viza.equity.text.types import (
    AnalysisMode,
    CachePolicy,
    ModelPolicy,
    ParsedSection,
    ResolverFilingSelector,
    ResolverRequest,
    ResolverResponse,
    ResolverTarget,
    SectionId,
)


class FinanceTextSentimentResolveRequest(BaseModel):
    """API surface mirroring brief §13."""

    model_config = ConfigDict(extra="forbid")

    target: ResolverTarget
    filing: ResolverFilingSelector
    sections: list[SectionId]
    strategy_profile_id: str = "quality_value_long_only"
    cutoff_timestamp: datetime | None = None
    model_policy: ModelPolicy = "default"
    cache_policy: CachePolicy = "serve_or_compute"
    analysis_mode: AnalysisMode = "live_current"
    package_mode: Literal["white_box", "output_only", "marketplace_draft"] = "output_only"
    persist_run: bool = True
    mock_parsed_sections: list[ParsedSection] | None = None


def finance_text_sentiment_status_payload(
    *,
    config: EquityTextConfig | None = None,
) -> dict[str, Any]:
    active = config or EquityTextConfig.from_env()
    return {
        "resolver_id": RESOLVER_ID,
        "resolver_namespace": RESOLVER_NAMESPACE,
        "resolver_version": RESOLVER_VERSION,
        "feature_flags": active.masked_summary(),
        "enabled": not active.feature_off(),
        "section_extraction_enabled": not active.section_extraction_off(),
        "model_inference_enabled": not active.model_inference_off(),
        "implementations": ["local_finbert_mock", "local_finbert_transformers", "local_finbert_onnx"],
        "default_implementation": "local_finbert_mock",
    }


def resolve_finance_text_sentiment_endpoint(
    api_request: FinanceTextSentimentResolveRequest,
    *,
    config: EquityTextConfig | None = None,
) -> dict[str, Any]:
    """FastAPI handler entry point. Returns a JSON-serializable dict.

    Applies package redaction to the resolver response before returning so
    the API never leaks bulk raw text in restricted modes.
    """
    request = ResolverRequest(
        target=api_request.target,
        filing=api_request.filing,
        sections=api_request.sections,
        strategy_profile_id=api_request.strategy_profile_id,
        cutoff_timestamp=api_request.cutoff_timestamp,
        model_policy=api_request.model_policy,
        cache_policy=api_request.cache_policy,
        analysis_mode=api_request.analysis_mode,
        package_mode=api_request.package_mode,
        persist_run=api_request.persist_run,
        mock_parsed_sections=api_request.mock_parsed_sections,
    )
    response = resolve_finance_text_sentiment(request, config=config)
    try:
        redacted = redact_for_package(response, mode=api_request.package_mode)
    except PackageRedactionBlocked as blocked:
        return {
            "resolver_id": RESOLVER_ID,
            "status": "block",
            "blocks": [{"code": blocked.reason, "mode": blocked.mode}],
            "redacted_preview": None,
            "audit": response.audit,
            "non_advice_boundary": response.non_advice_boundary,
        }
    return {
        "resolver_id": RESOLVER_ID,
        "status": response.status,
        "source": response.source,
        "redacted_preview": redacted,
        "queue_tickets": [t.model_dump(mode="json") for t in response.queue_tickets],
        "warnings": response.warnings,
        "blocks": response.blocks,
        "model_metadata": response.model_metadata,
        "audit": response.audit,
        "non_advice_boundary": response.non_advice_boundary,
    }


def replay_finance_text_sentiment_endpoint(
    run_id: str,
    *,
    cutoff_timestamp: datetime | None = None,
    package_mode: Literal["white_box", "output_only", "marketplace_draft"] = "output_only",
    config: EquityTextConfig | None = None,
) -> dict[str, Any]:
    request = ResolverRequest(
        target=ResolverTarget(entity_id=run_id),
        filing=ResolverFilingSelector(),
        sections=[],
        analysis_mode="replay_from_stored_observations",
        cutoff_timestamp=cutoff_timestamp,
        package_mode=package_mode,
        persist_run=False,
        mock_parsed_sections=None,
    )
    response = resolve_finance_text_sentiment(request, config=config)
    try:
        redacted = redact_for_package(response, mode=package_mode)
    except PackageRedactionBlocked as blocked:
        return {
            "resolver_id": RESOLVER_ID,
            "status": "block",
            "blocks": [{"code": blocked.reason, "mode": blocked.mode}],
            "redacted_preview": None,
            "audit": response.audit,
            "non_advice_boundary": response.non_advice_boundary,
        }
    return {
        "resolver_id": RESOLVER_ID,
        "status": response.status,
        "source": response.source,
        "redacted_preview": redacted,
        "audit": response.audit,
        "non_advice_boundary": response.non_advice_boundary,
    }


def get_finance_text_sentiment_cache_payload(cache_key: str) -> dict[str, Any]:
    store = get_sentiment_observation_store()
    observations = store.lookup_by_cache_key(cache_key)
    return {
        "cache_key": cache_key,
        "hit": bool(observations),
        "observation_count": len(observations),
        "observation_ids": [obs.observation_id for obs in observations],
    }

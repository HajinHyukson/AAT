"""VIZA finance text sentiment resolver wedge.

This subpackage implements the model-agnostic resolver

    viza.finance.text.sentiment

with FinBERT as one implementation. All public behavior is feature-flag gated
through ``EquityTextConfig`` and is fully no-op when the flags default off.

Stage A (this commit) ships:
  * the resolver interface and registry,
  * SEC iXBRL section extraction,
  * deterministic sentence-level chunking,
  * a mocked model implementation,
  * the cache_key / run_id observation store,
  * section aggregation and delta-vs-prior-filing,
  * the look-ahead PIT audit gate.

It does NOT ship: real FinBERT inference (Stage B), the desktop UI (Stage C),
or active-scope prepopulation jobs (Stage D).
"""

from __future__ import annotations

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.resolver import (
    RESOLVER_ID,
    RESOLVER_NAMESPACE,
    resolve_finance_text_sentiment,
)
from viza.equity.text.types import (
    AnalysisMode,
    CachePolicy,
    ChunkRecord,
    DeltaRecord,
    ModelPolicy,
    ResolverRequest,
    ResolverResponse,
    RunSnapshot,
    SectionAggregate,
    SentimentObservation,
)

__all__ = [
    "AnalysisMode",
    "CachePolicy",
    "ChunkRecord",
    "DeltaRecord",
    "EquityTextConfig",
    "ModelPolicy",
    "RESOLVER_ID",
    "RESOLVER_NAMESPACE",
    "ResolverRequest",
    "ResolverResponse",
    "RunSnapshot",
    "SectionAggregate",
    "SentimentObservation",
    "resolve_finance_text_sentiment",
]

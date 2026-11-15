"""Pydantic types for the finance text sentiment resolver.

These models define the on-the-wire shape of every observation, aggregate,
delta, and resolver request/response. They are deliberately exhaustive so the
serializer (and proof checksum) is reproducible across machines.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---- Enumerations -----------------------------------------------------------

SectionId = Literal[
    "risk_factors",
    "mdna",
    "market_risk",
    "8k_2_02",
    "8k_7_01",
    "8k_8_01",
    "section_unparseable",
]


FormType = Literal["10-K", "10-Q", "8-K"]


# Three-class FinBERT label; matches ProsusAI/finbert outputs.
SentimentLabel = Literal["positive", "neutral", "negative"]


ConfidenceLabel = Literal[
    "requires_human_review",
    "model_supported_high",
    "model_supported_medium",
    "model_supported_low",
    "comparison_unreliable",
    "research_supported_experimental",
]


LookaheadRisk = Literal["low", "warning", "not_backtest_safe"]


AnalysisMode = Literal[
    "live_current",
    "live_historical_PIT",
    "retrospective_research",
    "replay_from_stored_observations",
]


CachePolicy = Literal[
    "serve_or_compute",
    "serve_only",
    "compute_only",
    "queue_if_missing",
]


ModelPolicy = Literal["default", "pinned", "latest_allowed", "replay_exact"]


ResolverStatus = Literal[
    "pass",
    "warn",
    "block",
    "queued",
    "disabled",
    "missing_model",
    "partial",
]


# ---- Records ----------------------------------------------------------------


class ParsedSection(BaseModel):
    """A single section extracted from an SEC filing, with PIT metadata."""

    model_config = ConfigDict(extra="forbid")

    filing_accession: str
    cik: str
    company_id: str | None = None
    form_type: FormType
    section_id: SectionId
    section_label: str
    section_text: str
    section_text_hash: str
    parser_version: str
    filing_accepted_at: datetime | None
    available_at: datetime | None
    retrieved_at: datetime
    document_url: str | None = None
    lookahead_risk: LookaheadRisk
    rights_policy: dict[str, Any] = Field(default_factory=dict)
    pit_policy: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ChunkRecord(BaseModel):
    """A deterministic chunk produced by the chunker."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    filing_accession: str
    section_id: SectionId
    chunk_index: int
    text: str
    text_hash: str
    char_start: int
    char_end: int
    sentence_count: int
    token_estimate: int
    chunking_policy: dict[str, Any]
    chunking_policy_hash: str
    parser_version: str
    section_text_hash: str
    created_at: datetime


class ModelMetadata(BaseModel):
    """Frozen metadata for a model implementation run.

    The combination (model_id, model_version, model_hash, tokenizer_hash,
    chunking_policy_hash, inference_config_hash, parser_version) defines the
    full provenance of any observation produced.
    """

    model_config = ConfigDict(extra="forbid")

    model_provider: str
    model_family: str
    implementation_id: str
    model_id: str
    model_version: str
    model_hash: str
    tokenizer_version: str | None = None
    tokenizer_hash: str
    runtime: str
    runtime_version: str
    inference_config_hash: str
    max_tokens_policy: str
    truncation_policy: str
    created_at: datetime


class SentimentObservation(BaseModel):
    """A per-chunk sentiment observation, persistable to the observation store.

    Identity invariants enforced by validators in the persistence layer:
      * ``available_at`` MUST equal the filing's accepted timestamp (or the
        conservative day-precision fallback), never ``retrieved_at``.
      * ``cache_key`` is computed from the 9-field hash composite.
    """

    model_config = ConfigDict(extra="forbid")

    observation_id: str
    run_id: str
    cache_key: str

    # Target identity (entity_id is the stable internal ID; ticker is alias only).
    entity_id: str
    cik: str
    ticker_alias: str | None = None

    # Filing identity.
    filing_accession: str
    section_id: SectionId
    chunk_id: str

    # Content identity.
    input_text_hash: str
    section_text_hash: str
    parser_version: str
    chunking_policy_hash: str

    # Model identity (denormalized for query convenience; full record in metadata).
    model_id: str
    model_version: str
    model_hash: str
    tokenizer_hash: str
    inference_config_hash: str

    # Sentiment output.
    attribute_key: str = "sec_text.sentiment.distribution"
    positive_prob: float
    neutral_prob: float
    negative_prob: float
    label: SentimentLabel
    confidence: float
    confidence_label: ConfidenceLabel

    # Human review gate (pin 2).
    requires_human_review: bool
    matched_human_review_terms: list[str] = Field(default_factory=list)
    human_review_term_set_version: str

    # PIT / rights.
    observed_at: datetime
    available_at: datetime
    retrieved_at: datetime
    inference_at: datetime
    source_id: str = "SEC_EDGAR"
    source_ref: str
    lookahead_risk: LookaheadRisk = "low"
    rights_policy: dict[str, Any] = Field(default_factory=dict)


class SectionAggregate(BaseModel):
    """Per-section aggregate over chunk observations."""

    model_config = ConfigDict(extra="forbid")

    section_sentiment_id: str
    run_id: str
    entity_id: str
    cik: str
    filing_accession: str
    section_id: SectionId

    chunk_observation_ids: list[str]
    chunks_count: int

    positive_prob_avg: float
    neutral_prob_avg: float
    negative_prob_avg: float
    net_sentiment: float
    negative_chunk_ratio: float
    high_confidence_negative_count: int
    sentiment_dispersion: float

    requires_human_review: bool
    matched_human_review_terms: list[str] = Field(default_factory=list)

    aggregation_method: str = "mean"
    aggregation_version: str = "section_aggregation_v1"

    available_at: datetime
    pit_policy: dict[str, Any] = Field(default_factory=dict)
    rights_policy: dict[str, Any] = Field(default_factory=dict)
    validation_status: Literal["pass", "warn", "block"] = "pass"


class DeltaRecord(BaseModel):
    """Tone delta vs prior filing for the same section."""

    model_config = ConfigDict(extra="forbid")

    delta_id: str
    entity_id: str
    cik: str
    current_filing_accession: str
    prior_filing_accession: str
    section_id: SectionId

    delta_method: Literal[
        "same_form_prior_period",
        "same_section_prior_filing",
        "configured",
    ]
    negative_tone_delta: float
    net_sentiment_delta: float
    new_negative_language_flag: bool
    removed_positive_language_flag: bool
    novel_sentence_count: int

    prior_available_at: datetime
    current_available_at: datetime
    model_metadata_match: bool
    warnings: list[str] = Field(default_factory=list)
    confidence_label: ConfidenceLabel = "research_supported_experimental"


class RunSnapshot(BaseModel):
    """A run record snapshot of resolver provenance for replay/proof.

    A run is the unit of replay: given a run_id, replay returns exactly the
    observations recorded under it, with the parser/model/chunking metadata
    that produced them. The snapshot is frozen at run end and never mutated.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    resolver_id: str
    resolver_version: str
    analysis_mode: AnalysisMode
    model_policy: ModelPolicy
    cache_policy: CachePolicy
    parser_version: str
    chunking_policy: dict[str, Any]
    chunking_policy_hash: str
    model_metadata: dict[str, Any]
    inference_config_hash: str
    cutoff_timestamp: datetime | None = None
    created_at: datetime
    status: ResolverStatus
    partial_resolution_reasons: list[dict[str, Any]] = Field(default_factory=list)
    proof_checksum: str


class QueueTicket(BaseModel):
    """Pin-7 queued-status ticket returned when cache_policy=queue_if_missing
    finds no cache hit. The methodology graph receives the ticket; the
    prepopulation job (Stage D) fulfills it asynchronously.
    """

    model_config = ConfigDict(extra="forbid")

    queue_ticket_id: str
    job_id: str | None = None
    filing_accession: str
    section_id: SectionId
    requested_at: datetime
    resolver_request_hash: str


# ---- Resolver request/response ---------------------------------------------


class ResolverFilingSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accession: str | None = None
    form_type: FormType | None = None
    latest: bool = False


class ResolverTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cik: str | None = None
    ticker_alias: str | None = None
    entity_id: str | None = None


class ResolverRequest(BaseModel):
    """The single public input to ``resolve_finance_text_sentiment``."""

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
    # Stage A only accepts mocked filings; the live SEC client is wired in
    # Stage C alongside the FastAPI surface.
    mock_parsed_sections: list[ParsedSection] | None = None


class ResolverResponse(BaseModel):
    """The single public output of ``resolve_finance_text_sentiment``."""

    model_config = ConfigDict(extra="forbid")

    resolver_id: str
    status: ResolverStatus
    source: Literal["cache", "fresh_compute", "queued", "stored_replay", "none"] = "none"
    observations: list[SentimentObservation] = Field(default_factory=list)
    section_aggregates: list[SectionAggregate] = Field(default_factory=list)
    deltas: list[DeltaRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    queue_tickets: list[QueueTicket] = Field(default_factory=list)
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    pit_summary: dict[str, Any] = Field(default_factory=dict)
    rights_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    package_redaction_preview: dict[str, Any] = Field(default_factory=dict)
    non_advice_boundary: str = (
        "Research preview only. FinBERT-derived sentiment is text evidence, "
        "not a recommendation. Negative tone does not imply sell/short. "
        "This output is not personalized investment advice."
    )
    audit: dict[str, Any] = Field(default_factory=dict)

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Float,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def utc_datetime() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False)


class Company(Base):
    __tablename__ = "company"

    company_id: Mapped[uuid.UUID] = uuid_pk()
    cik: Mapped[str | None] = mapped_column(String(20), unique=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = utc_datetime()

    securities: Mapped[list["Security"]] = relationship(back_populates="company")


class Security(Base):
    __tablename__ = "security"

    security_id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.company_id"), nullable=False
    )
    figi: Mapped[str | None] = mapped_column(String(32), unique=True)
    isin: Mapped[str | None] = mapped_column(String(16), unique=True)
    cusip: Mapped[str | None] = mapped_column(String(16), unique=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    share_class: Mapped[str | None] = mapped_column(String(64))
    active_from: Mapped[datetime] = utc_datetime()
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="securities")


class SecurityTickerHistory(Base):
    __tablename__ = "security_ticker_history"

    ticker_history_id: Mapped[uuid.UUID] = uuid_pk()
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    active_from: Mapped[datetime] = utc_datetime()
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("security_id", "ticker", "active_from", name="uq_ticker_history"),
        Index("ix_ticker_history_ticker_dates", "ticker", "active_from", "active_to"),
    )


class TimestampedMixin:
    event_time: Mapped[datetime] = utc_datetime()
    ingestion_time: Mapped[datetime] = utc_datetime()
    timestamp_available: Mapped[datetime] = utc_datetime()


class HypertableTimestampedMixin:
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    ingestion_time: Mapped[datetime] = utc_datetime()
    timestamp_available: Mapped[datetime] = utc_datetime()


class PriceBar(HypertableTimestampedMixin, Base):
    __tablename__ = "price_bar"

    price_bar_id: Mapped[uuid.UUID] = uuid_pk()
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    open: Mapped[float | None] = mapped_column(Numeric(18, 6))
    high: Mapped[float | None] = mapped_column(Numeric(18, 6))
    low: Mapped[float | None] = mapped_column(Numeric(18, 6))
    close: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    adjusted_close: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("security_id", "event_time", "source", name="uq_price_bar_source_time"),
        Index("ix_price_bar_security_time", "security_id", "event_time"),
        Index("ix_price_bar_available", "security_id", "timestamp_available"),
        CheckConstraint("close > 0", name="ck_price_bar_close_positive"),
        CheckConstraint("adjusted_close > 0", name="ck_price_bar_adjusted_close_positive"),
    )


class FactorReturn(HypertableTimestampedMixin, Base):
    __tablename__ = "factor_return"

    factor_return_id: Mapped[uuid.UUID] = uuid_pk()
    factor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    factor_family: Mapped[str] = mapped_column(String(64), nullable=False)
    return_bps: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("factor_name", "event_time", "source", name="uq_factor_return_source_time"),
        Index("ix_factor_return_name_time", "factor_name", "event_time"),
        Index("ix_factor_return_available", "factor_name", "timestamp_available"),
    )


class FactorDefinition(Base):
    __tablename__ = "factor_definition"

    factor_definition_id: Mapped[uuid.UUID] = uuid_pk()
    factor_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    factor_family: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    transform: Mapped[str] = mapped_column(String(128), nullable=False)
    default_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    license_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    active_from: Mapped[datetime] = utc_datetime()
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = utc_datetime()

    __table_args__ = (
        Index("ix_factor_definition_family", "factor_family"),
    )


class FactorObservation(HypertableTimestampedMixin, Base):
    __tablename__ = "factor_observation"

    factor_observation_id: Mapped[uuid.UUID] = uuid_pk()
    factor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_value: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    raw_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    vintage: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint(
            "factor_name",
            "source",
            "event_time",
            "vintage",
            name="uq_factor_observation_source_time",
        ),
        Index("ix_factor_observation_available", "factor_name", "timestamp_available"),
    )


class SecurityFactorExposure(TimestampedMixin, Base):
    __tablename__ = "security_factor_exposure"

    security_factor_exposure_id: Mapped[uuid.UUID] = uuid_pk()
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    factor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    exposure_value: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    exposure_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    exposure_method: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    diagnostics: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "factor_name",
            "model_version",
            "event_time",
            name="uq_security_factor_exposure_model_time",
        ),
        Index("ix_security_factor_exposure_available", "security_id", "timestamp_available"),
        Index("ix_security_factor_exposure_factor", "factor_name", "event_time"),
    )


class SectorClassificationHistory(TimestampedMixin, Base):
    __tablename__ = "sector_classification_history"

    sector_classification_history_id: Mapped[uuid.UUID] = uuid_pk()
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    sector: Mapped[str] = mapped_column(String(128), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(128))
    subindustry: Mapped[str | None] = mapped_column(String(128))
    classification_source: Mapped[str] = mapped_column(String(128), nullable=False)
    classification_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "classification_source",
            "classification_version",
            "event_time",
            name="uq_sector_classification_version_time",
        ),
        Index("ix_sector_classification_available", "security_id", "timestamp_available"),
    )


class PeerBasket(TimestampedMixin, Base):
    __tablename__ = "peer_basket"

    peer_basket_id: Mapped[uuid.UUID] = uuid_pk()
    target_security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    basket_name: Mapped[str] = mapped_column(String(128), nullable=False)
    basket_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active_from: Mapped[datetime] = utc_datetime()
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "target_security_id",
            "basket_name",
            "basket_version",
            name="uq_peer_basket_target_version",
        ),
        Index("ix_peer_basket_available", "target_security_id", "timestamp_available"),
    )


class PeerBasketMember(TimestampedMixin, Base):
    __tablename__ = "peer_basket_member"

    peer_basket_member_id: Mapped[uuid.UUID] = uuid_pk()
    peer_basket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("peer_basket.peer_basket_id"), nullable=False
    )
    peer_security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    active_from: Mapped[datetime] = utc_datetime()
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("peer_basket_id", "peer_security_id", name="uq_peer_basket_member"),
        Index("ix_peer_basket_member_available", "peer_basket_id", "timestamp_available"),
        CheckConstraint("weight >= 0", name="ck_peer_basket_member_weight_nonnegative"),
    )


class MacroSeries(HypertableTimestampedMixin, Base):
    __tablename__ = "macro_series"

    macro_series_id: Mapped[uuid.UUID] = uuid_pk()
    series_name: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    vintage: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("series_name", "event_time", "vintage", name="uq_macro_series_vintage"),
        Index("ix_macro_series_name_time", "series_name", "event_time"),
        Index("ix_macro_series_available", "series_name", "timestamp_available"),
    )


class Event(TimestampedMixin, Base):
    __tablename__ = "event"

    event_id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.company_id"), nullable=False
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id")
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_uri: Mapped[str | None] = mapped_column(Text)
    structured_payload: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_event_source_id"),
        Index("ix_event_company_available", "company_id", "timestamp_available"),
        Index("ix_event_security_available", "security_id", "timestamp_available"),
    )


class EventFeature(TimestampedMixin, Base):
    __tablename__ = "event_feature"

    event_feature_id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event.event_id"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.company_id"), nullable=False
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id")
    )
    relevance: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    novelty: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    sentiment: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    magnitude: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    source_credibility: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    exposure_match: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    surprise: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    evidence_span: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", "model_version", name="uq_event_feature_model"),
        Index("ix_event_feature_company_available", "company_id", "timestamp_available"),
        Index("ix_event_feature_event", "event_id"),
        CheckConstraint("relevance >= 0 AND relevance <= 1", name="ck_event_feature_relevance"),
        CheckConstraint("novelty >= 0 AND novelty <= 1", name="ck_event_feature_novelty"),
        CheckConstraint("sentiment >= -1 AND sentiment <= 1", name="ck_event_feature_sentiment"),
        CheckConstraint("magnitude >= 0 AND magnitude <= 1", name="ck_event_feature_magnitude"),
        CheckConstraint(
            "source_credibility >= 0 AND source_credibility <= 1",
            name="ck_event_feature_source_credibility",
        ),
        CheckConstraint("exposure_match >= 0 AND exposure_match <= 1", name="ck_event_feature_exposure_match"),
        CheckConstraint("surprise >= -1 AND surprise <= 1", name="ck_event_feature_surprise"),
    )


class EventTaxonomy(TimestampedMixin, Base):
    __tablename__ = "event_taxonomy"

    event_taxonomy_id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event.event_id"), nullable=False
    )
    event_category: Mapped[str] = mapped_column(String(128), nullable=False)
    event_subtype: Mapped[str] = mapped_column(String(128), nullable=False)
    event_direction: Mapped[str] = mapped_column(String(64), nullable=False)
    materiality: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_payload: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint("event_id", "taxonomy_version", name="uq_event_taxonomy_version"),
        Index("ix_event_taxonomy_available", "event_id", "timestamp_available"),
        CheckConstraint("materiality >= 0 AND materiality <= 1", name="ck_event_taxonomy_materiality"),
    )


class EventSurprise(TimestampedMixin, Base):
    __tablename__ = "event_surprise"

    event_surprise_id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event.event_id"), nullable=False
    )
    surprise_name: Mapped[str] = mapped_column(String(128), nullable=False)
    surprise_value: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    surprise_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_value: Mapped[float | None] = mapped_column(Numeric(18, 8))
    actual_value: Mapped[float | None] = mapped_column(Numeric(18, 8))
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_payload: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "surprise_name",
            "model_version",
            name="uq_event_surprise_model",
        ),
        Index("ix_event_surprise_available", "event_id", "timestamp_available"),
    )


class CompanyExposure(TimestampedMixin, Base):
    __tablename__ = "company_exposure"

    company_exposure_id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.company_id"), nullable=False
    )
    exposure_name: Mapped[str] = mapped_column(String(128), nullable=False)
    exposure_value: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    exposure_type: Mapped[str | None] = mapped_column(String(128))
    exposure_bucket: Mapped[str | None] = mapped_column(String(32))
    exposure_sign: Mapped[str | None] = mapped_column(String(32))
    source_span: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(String(64))
    exposure_version: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event.event_id")
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_company_exposure_company_available", "company_id", "timestamp_available"),
    )


class ExposureUpdateDecision(Base):
    __tablename__ = "exposure_update_decision"

    exposure_update_decision_id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.company_id"), nullable=False
    )
    exposure_name: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    review_required: Mapped[bool] = mapped_column(nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_event_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluated_at: Mapped[datetime] = utc_datetime()

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "exposure_name",
            "model_version",
            "evaluated_at",
            name="uq_exposure_update_decision_eval",
        ),
        Index("ix_exposure_update_decision_company", "company_id", "evaluated_at"),
    )


class AttributionRun(Base):
    __tablename__ = "attribution_run"

    attribution_run_id: Mapped[uuid.UUID] = uuid_pk()
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    window_start: Mapped[datetime] = utc_datetime()
    window_end: Mapped[datetime] = utc_datetime()
    attribution_cutoff: Mapped[datetime] = utc_datetime()
    observed_return_bps: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unexplained_residual_bps: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    data_version: Mapped[str] = mapped_column(String(64), nullable=False)
    factor_basket_version: Mapped[str] = mapped_column(String(64), nullable=False)
    cadence: Mapped[str] = mapped_column(String(16), nullable=False, default="daily")
    created_at: Mapped[datetime] = utc_datetime()

    contributions: Mapped[list["AttributionContribution"]] = relationship(back_populates="run")

    __table_args__ = (
        Index("ix_attribution_run_security_window", "security_id", "window_end"),
        UniqueConstraint(
            "security_id",
            "window_start",
            "window_end",
            "model_version",
            "factor_basket_version",
            "cadence",
            name="uq_attribution_run_window_model",
        ),
        CheckConstraint("cadence IN ('daily', 'weekly', 'monthly')", name="ck_attribution_run_cadence"),
    )


class AttributionContribution(Base):
    __tablename__ = "attribution_contribution"

    attribution_contribution_id: Mapped[uuid.UUID] = uuid_pk()
    attribution_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attribution_run.attribution_run_id"), nullable=False
    )
    driver: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contribution_bps: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    share_of_move: Mapped[float | None] = mapped_column(Numeric(18, 8))
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[list | None] = mapped_column(JSONB)
    contribution_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="production")
    evidence_payload: Mapped[dict | None] = mapped_column(JSONB)

    run: Mapped[AttributionRun] = relationship(back_populates="contributions")

    __table_args__ = (
        Index("ix_attribution_contribution_run", "attribution_run_id"),
    )


class AnalystFeedback(Base):
    __tablename__ = "analyst_feedback"

    analyst_feedback_id: Mapped[uuid.UUID] = uuid_pk()
    attribution_contribution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attribution_contribution.attribution_contribution_id")
    )
    attribution_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attribution_run.attribution_run_id"), nullable=False
    )
    feedback: Mapped[str] = mapped_column(String(64), nullable=False)
    missing_driver_name: Mapped[str | None] = mapped_column(String(255))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = utc_datetime()

    __table_args__ = (
        Index("ix_analyst_feedback_run", "attribution_run_id", "created_at"),
    )


class BackfillRun(Base):
    __tablename__ = "backfill_run"

    backfill_run_id: Mapped[uuid.UUID] = uuid_pk()
    config_version: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_start: Mapped[datetime] = utc_datetime()
    analysis_end: Mapped[datetime] = utc_datetime()
    data_start: Mapped[datetime] = utc_datetime()
    data_end: Mapped[datetime] = utc_datetime()
    cadences: Mapped[list] = mapped_column(JSONB, nullable=False)
    lookback_days: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = utc_datetime()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_payload: Mapped[dict | None] = mapped_column(JSONB)
    error_payload: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_backfill_run_status_started", "status", "started_at"),
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_backfill_run_status"),
    )


class ModelUniverseMember(Base):
    __tablename__ = "model_universe_member"

    model_universe_member_id: Mapped[uuid.UUID] = uuid_pk()
    universe_name: Mapped[str] = mapped_column(String(128), nullable=False)
    universe_version: Mapped[str] = mapped_column(String(64), nullable=False)
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_asset.faustcalc_asset_id")
    )
    eligibility_status: Mapped[str] = mapped_column(String(32), nullable=False)
    first_price_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_price_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_bar_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    active_from: Mapped[datetime] = utc_datetime()
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    skip_reason: Mapped[str | None] = mapped_column(Text)
    member_payload: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = utc_datetime()
    updated_at: Mapped[datetime] = utc_datetime()

    __table_args__ = (
        UniqueConstraint(
            "universe_name",
            "universe_version",
            "security_id",
            name="uq_model_universe_member_security",
        ),
        Index(
            "ix_model_universe_member_universe_status",
            "universe_name",
            "universe_version",
            "eligibility_status",
            "ticker",
        ),
        Index("ix_model_universe_member_security", "security_id", "universe_name"),
    )


class AttributionBackfillTask(Base):
    __tablename__ = "attribution_backfill_task"

    attribution_backfill_task_id: Mapped[uuid.UUID] = uuid_pk()
    backfill_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backfill_run.backfill_run_id"), nullable=False
    )
    universe_name: Mapped[str] = mapped_column(String(128), nullable=False)
    universe_version: Mapped[str] = mapped_column(String(64), nullable=False)
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    cadence: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_windows: Mapped[int] = mapped_column(nullable=False, default=0)
    ran_windows: Mapped[int] = mapped_column(nullable=False, default=0)
    skipped_windows: Mapped[int] = mapped_column(nullable=False, default=0)
    last_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = utc_datetime()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = utc_datetime()

    __table_args__ = (
        UniqueConstraint(
            "backfill_run_id",
            "security_id",
            "cadence",
            name="uq_attribution_backfill_task_run_security",
        ),
        Index("ix_attribution_backfill_task_status", "backfill_run_id", "status", "cadence"),
        Index("ix_attribution_backfill_task_security", "security_id", "cadence"),
        CheckConstraint("cadence IN ('daily', 'weekly', 'monthly')", name="ck_backfill_task_cadence"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'skipped', 'failed')",
            name="ck_backfill_task_status",
        ),
    )


class SecurityAttributionSummary(Base):
    __tablename__ = "security_attribution_summary"

    security_attribution_summary_id: Mapped[uuid.UUID] = uuid_pk()
    universe_name: Mapped[str] = mapped_column(String(128), nullable=False)
    universe_version: Mapped[str] = mapped_column(String(64), nullable=False)
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security.security_id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.company_id"), nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    latest_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attribution_run.attribution_run_id")
    )
    latest_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_observed_return_bps: Mapped[float | None] = mapped_column(Numeric(18, 6))
    latest_residual_bps: Mapped[float | None] = mapped_column(Numeric(18, 6))
    latest_price_change_usd: Mapped[float | None] = mapped_column(Numeric(18, 6))
    top_driver: Mapped[str | None] = mapped_column(String(255))
    top_driver_confidence: Mapped[str | None] = mapped_column(String(32))
    contribution_count: Mapped[int] = mapped_column(nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False)
    first_price_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_price_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_bar_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    coverage_payload: Mapped[dict | None] = mapped_column(JSONB)
    refreshed_at: Mapped[datetime] = utc_datetime()

    __table_args__ = (
        UniqueConstraint(
            "universe_name",
            "universe_version",
            "security_id",
            name="uq_security_attribution_summary_universe",
        ),
        Index(
            "ix_security_attribution_summary_universe_status",
            "universe_name",
            "universe_version",
            "run_status",
            "ticker",
        ),
        Index("ix_security_attribution_summary_latest", "universe_name", "latest_window_end"),
        CheckConstraint("run_status IN ('available', 'missing')", name="ck_security_attr_summary_status"),
    )


class FaustcalcImportRun(Base):
    __tablename__ = "faustcalc_import_run"

    faustcalc_import_run_id: Mapped[uuid.UUID] = uuid_pk()
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    source_database_fingerprint: Mapped[str | None] = mapped_column(String(64))
    data_root: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = utc_datetime()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_counts: Mapped[dict | None] = mapped_column(JSONB)
    validation_payload: Mapped[dict | None] = mapped_column(JSONB)
    error_payload: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_faustcalc_import_run_status_started", "status", "started_at"),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'dry_run')",
            name="ck_faustcalc_import_run_status",
        ),
    )


class FaustcalcValidationIssue(Base):
    __tablename__ = "faustcalc_validation_issue"

    faustcalc_validation_issue_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id")
    )
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_table: Mapped[str | None] = mapped_column(String(128))
    source_key: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = utc_datetime()

    __table_args__ = (
        Index("ix_faustcalc_validation_issue_run", "faustcalc_import_run_id", "severity"),
        CheckConstraint("severity IN ('info', 'warning', 'error')", name="ck_faustcalc_issue_severity"),
    )


class FaustcalcAsset(Base):
    __tablename__ = "faustcalc_asset"

    faustcalc_asset_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id"), nullable=False
    )
    source_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    ticker_local: Mapped[str | None] = mapped_column(String(64))
    company_name: Mapped[str | None] = mapped_column(Text)
    asset_type: Mapped[str | None] = mapped_column(String(64))
    exchange: Mapped[str | None] = mapped_column(String(64))
    market: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_active: Mapped[bool | None] = mapped_column(Boolean)
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_ticker", name="uq_faustcalc_asset_source_ticker"),
        Index("ix_faustcalc_asset_canonical_ticker", "canonical_ticker"),
    )


class FaustcalcCompany(Base):
    __tablename__ = "faustcalc_company"

    faustcalc_company_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id"), nullable=False
    )
    source_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    cik: Mapped[str | None] = mapped_column(String(20))
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(64))
    source_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_ticker", name="uq_faustcalc_company_source_ticker"),
        Index("ix_faustcalc_company_cik", "cik"),
        Index("ix_faustcalc_company_canonical_ticker", "canonical_ticker"),
    )


class FaustcalcPrice(Base):
    __tablename__ = "faustcalc_price"

    faustcalc_price_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id"), nullable=False
    )
    source_price_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_price_id", name="uq_faustcalc_price_source_id"),
        Index("ix_faustcalc_price_ticker_date", "canonical_ticker", "price_date"),
        CheckConstraint("close > 0", name="ck_faustcalc_price_close_positive"),
    )


class FaustcalcFundamental(Base):
    __tablename__ = "faustcalc_fundamental"

    faustcalc_fundamental_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id"), nullable=False
    )
    source_fundamental_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_fundamental_id", name="uq_faustcalc_fundamental_source_id"),
        Index("ix_faustcalc_fundamental_ticker_date", "canonical_ticker", "as_of_date"),
    )


class FaustcalcPriceFeature(Base):
    __tablename__ = "faustcalc_price_feature"

    faustcalc_price_feature_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id"), nullable=False
    )
    source_price_feature_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_price_feature_id", name="uq_faustcalc_price_feature_source_id"),
        Index("ix_faustcalc_price_feature_ticker_date", "canonical_ticker", "as_of_date"),
    )


class FaustcalcThemeScore(Base):
    __tablename__ = "faustcalc_theme_score"

    faustcalc_theme_score_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id"), nullable=False
    )
    source_theme_score_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    theme_key: Mapped[str] = mapped_column(String(128), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_theme_score_id", name="uq_faustcalc_theme_score_source_id"),
        Index("ix_faustcalc_theme_score_ticker_date", "canonical_ticker", "as_of_date"),
    )


class FaustcalcFilingAnalysis(Base):
    __tablename__ = "faustcalc_filing_analysis"

    faustcalc_filing_analysis_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id"), nullable=False
    )
    source_filing_analysis_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    filing_type: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_filing_analysis_id", name="uq_faustcalc_filing_analysis_source_id"),
        Index("ix_faustcalc_filing_analysis_ticker_date", "canonical_ticker", "filing_date"),
    )


class FaustcalcPeerAnalysis(Base):
    __tablename__ = "faustcalc_peer_analysis"

    faustcalc_peer_analysis_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id"), nullable=False
    )
    source_peer_analysis_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_peer_analysis_id", name="uq_faustcalc_peer_analysis_source_id"),
        Index("ix_faustcalc_peer_analysis_ticker_date", "canonical_ticker", "as_of_date"),
    )


class FaustcalcSecFiling(Base):
    __tablename__ = "faustcalc_sec_filing"

    faustcalc_sec_filing_id: Mapped[uuid.UUID] = uuid_pk()
    faustcalc_import_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faustcalc_import_run.faustcalc_import_run_id"), nullable=False
    )
    accession_number: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    source_tickers: Mapped[list] = mapped_column(JSONB, nullable=False)
    form_type: Mapped[str] = mapped_column(String(64), nullable=False)
    filing_date: Mapped[date | None] = mapped_column(Date)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = utc_datetime()
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text_path: Mapped[str | None] = mapped_column(Text)
    source_content_hash: Mapped[str | None] = mapped_column(String(128))
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("accession_number", name="uq_faustcalc_sec_filing_accession"),
        Index("ix_faustcalc_sec_filing_ticker_available", "canonical_ticker", "available_at"),
        CheckConstraint("status IN ('valid', 'rejected')", name="ck_faustcalc_sec_filing_status"),
    )

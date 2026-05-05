from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


ONE_BASIS_POINT = 1.0


class ConfidenceLevel(StrEnum):
    HIGH = "High"
    MEDIUM_HIGH = "Medium-High"
    MEDIUM = "Medium"
    LOW_MEDIUM = "Low-Medium"
    LOW = "Low"


class DriverType(StrEnum):
    MARKET = "market"
    SECTOR = "sector"
    PEER = "peer"
    STYLE = "style"
    MACRO = "macro"
    POSITIONING = "positioning"
    EVENT = "event"
    UNEXPLAINED_RESIDUAL = "unexplained_residual"


class ContributionStage(StrEnum):
    RESEARCH = "research"
    EVIDENCE_ONLY = "evidence_only"
    SHADOW = "shadow"
    PRODUCTION = "production"


class ExposureSign(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ExposureBucket(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimeWindow(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_order(self) -> TimeWindow:
        if self.end <= self.start:
            raise ValueError("window end must be after start")
        return self


class TimestampedRecord(BaseModel):
    event_time: datetime
    ingestion_time: datetime
    timestamp_available: datetime


class PriceBar(TimestampedRecord):
    security_id: UUID
    close: float = Field(gt=0)
    adjusted_close: float = Field(gt=0)
    volume: int | None = Field(default=None, ge=0)
    currency: str = "USD"


class FactorContributionInput(TimestampedRecord):
    security_id: UUID
    driver: DriverType
    name: str
    contribution_bps: float
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    evidence: list[str] = Field(default_factory=list)
    contribution_stage: ContributionStage = ContributionStage.PRODUCTION
    factor_move: float | None = None
    factor_move_unit: str | None = None
    exposure_value: float | None = None
    exposure_unit: str | None = None
    evidence_payload: dict = Field(default_factory=dict)


class FactorDefinition(BaseModel):
    factor_name: str
    factor_family: DriverType
    display_name: str
    description: str
    source: str
    transform: str
    default_unit: str
    license_tier: str
    active_from: datetime
    active_to: datetime | None = None


class FactorObservation(TimestampedRecord):
    factor_name: str
    source: str
    raw_value: float
    raw_unit: str
    vintage: str | None = None
    payload: dict = Field(default_factory=dict)


class SecurityFactorExposure(TimestampedRecord):
    security_id: UUID
    factor_name: str
    exposure_value: float
    exposure_unit: str
    exposure_method: str
    confidence: ConfidenceLevel
    model_version: str
    diagnostics: dict = Field(default_factory=dict)


class SectorClassification(TimestampedRecord):
    security_id: UUID
    sector: str
    industry: str | None = None
    subindustry: str | None = None
    classification_source: str
    classification_version: str


class PeerBasketMember(TimestampedRecord):
    basket_name: str
    basket_version: str
    target_security_id: UUID
    peer_security_id: UUID
    weight: float
    active_from: datetime
    active_to: datetime | None = None


class EventTaxonomyRecord(TimestampedRecord):
    event_id: UUID
    event_category: str
    event_subtype: str
    event_direction: str
    materiality: float = Field(ge=0, le=1)
    taxonomy_version: str
    evidence_payload: dict = Field(default_factory=dict)


class EventSurpriseRecord(TimestampedRecord):
    event_id: UUID
    surprise_name: str
    surprise_value: float
    surprise_unit: str
    expected_value: float | None = None
    actual_value: float | None = None
    model_version: str
    evidence_payload: dict = Field(default_factory=dict)


class AttributionContribution(BaseModel):
    driver: DriverType
    name: str
    contribution_bps: float
    share_of_move: float | None
    confidence: ConfidenceLevel
    evidence: list[str] = Field(default_factory=list)
    contribution_stage: ContributionStage = ContributionStage.PRODUCTION
    evidence_payload: dict = Field(default_factory=dict)


class AttributionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    security_id: UUID
    window: TimeWindow
    attribution_cutoff: datetime
    observed_return_bps: float
    contributions: list[AttributionContribution]
    unexplained_residual_bps: float
    model_version: str

    @model_validator(mode="after")
    def validate_reconciliation(self) -> AttributionResult:
        total = sum(item.contribution_bps for item in self.contributions)
        if abs(total - self.observed_return_bps) > ONE_BASIS_POINT:
            raise ValueError(
                "attribution contributions must reconcile to observed return within 1 bp"
            )
        residual_rows = [
            item for item in self.contributions if item.driver == DriverType.UNEXPLAINED_RESIDUAL
        ]
        if len(residual_rows) != 1:
            raise ValueError("exactly one unexplained_residual contribution is required")
        if abs(residual_rows[0].contribution_bps - self.unexplained_residual_bps) > 1e-9:
            raise ValueError("residual field must match unexplained_residual contribution")
        return self

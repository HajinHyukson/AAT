from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ContributionResponse(BaseModel):
    attribution_contribution_id: UUID
    driver: str
    name: str
    contribution_bps: float
    share_of_move: float | None
    confidence: str
    evidence: list
    contribution_stage: str = "production"
    evidence_payload: dict | None = None


class AttributionRunResponse(BaseModel):
    attribution_run_id: UUID
    ticker: str
    security_id: UUID
    window_start: datetime
    window_end: datetime
    attribution_cutoff: datetime
    observed_return_bps: float
    unexplained_residual_bps: float
    model_version: str
    data_version: str
    factor_basket_version: str
    cadence: str = "daily"
    narrative: str
    contributions: list[ContributionResponse]


class AttributionChartPricePoint(BaseModel):
    date: datetime
    adjusted_close: float
    cumulative_return_pct: float


class AttributionChartContributionPoint(BaseModel):
    driver: str
    name: str
    contribution_pct: float
    share_of_move: float | None


class AttributionChartPoint(BaseModel):
    date: datetime
    window_start: datetime
    window_end: datetime
    observed_return_pct: float
    contributions: list[AttributionChartContributionPoint]


class AttributionChartResponse(BaseModel):
    ticker: str
    range: str
    cadence: str
    start: datetime
    end: datetime
    price_points: list[AttributionChartPricePoint]
    attribution_points: list[AttributionChartPoint]
    driver_order: list[str]


class UniverseStockResponse(BaseModel):
    ticker: str
    company_name: str
    security_id: UUID
    company_id: UUID
    exchange: str
    sector: str | None = None
    industry: str | None = None
    latest_run_id: UUID | None = None
    latest_window_end: datetime | None = None
    latest_observed_return_bps: float | None = None
    latest_residual_bps: float | None = None
    latest_price_change_usd: float | None = None
    latest_residual_usd: float | None = None
    top_driver: str | None = None
    top_driver_confidence: str | None = None
    contribution_count: int = 0
    has_evidence: bool = False
    run_status: str


class UniverseCompanyOption(BaseModel):
    ticker: str
    company_name: str


class UniverseResponse(BaseModel):
    rows: list[UniverseStockResponse]
    total: int
    limit: int
    offset: int
    latest_run_date: datetime | None = None
    company_options: list[UniverseCompanyOption] = Field(default_factory=list)
    sector_options: list[str] = Field(default_factory=list)
    industry_options: list[str] = Field(default_factory=list)
    exchange_options: list[str] = Field(default_factory=list)


class ExposureUpdateDecisionResponse(BaseModel):
    exposure_update_decision_id: UUID
    ticker: str | None
    company_id: UUID
    exposure_name: str
    decision: str
    review_required: bool
    confidence: str
    rationale: str
    evidence_event_ids: list[str]
    model_version: str
    evaluated_at: datetime


class AnalystFeedbackRequest(BaseModel):
    attribution_run_id: UUID
    attribution_contribution_id: UUID | None = None
    feedback: str
    missing_driver_name: str | None = None
    comment: str | None = None


class AnalystFeedbackResponse(BaseModel):
    analyst_feedback_id: UUID
    attribution_run_id: UUID
    attribution_contribution_id: UUID | None
    feedback: str
    missing_driver_name: str | None
    comment: str | None
    created_at: datetime

from __future__ import annotations

import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, Query
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert

from api.schemas import (
    AttributionChartContributionPoint,
    AttributionChartPoint,
    AttributionChartPricePoint,
    AttributionChartResponse,
    AttributionEnsureLatestResponse,
    AttributionJobResponse,
    AttributionMethodologyResponse,
    AttributionRunResponse,
    AnalystFeedbackRequest,
    AnalystFeedbackResponse,
    ContributionResponse,
    ExposureUpdateDecisionResponse,
    UniverseCompanyOption,
    UniverseResponse,
    UniverseStockResponse,
)
from db import models
from db.session import session_scope
from engine.attribution.diagnostics import is_share_stable
from engine.contracts import AttributionContribution, AttributionResult, ConfidenceLevel, DriverType, TimeWindow
from engine.narrative import build_deterministic_narrative
from jobs.attribution_methodologies import (
    DEFAULT_ATTRIBUTION_METHODOLOGY,
    VALID_ATTRIBUTION_METHODOLOGIES,
    load_methodology,
)
from jobs.attribution_windowing import candidate_windows_for_range, missing_windows_for_range
from jobs.faustcalc_common import DEFAULT_FAUSTCALC_UNIVERSE_NAME, DEFAULT_FAUSTCALC_UNIVERSE_VERSION

app = FastAPI(title="Single-Stock Attribution Engine", version="0.1.0")

LATEST_UNIVERSE_VERSION = "latest"


def default_universe_name() -> str:
    return os.getenv("AAT_DEFAULT_UNIVERSE_NAME", DEFAULT_FAUSTCALC_UNIVERSE_NAME)


def default_universe_version() -> str:
    return os.getenv("AAT_DEFAULT_UNIVERSE_VERSION", DEFAULT_FAUSTCALC_UNIVERSE_VERSION)


def resolve_universe_version(*, session, universe_name: str, universe_version: str) -> str:
    if universe_version != LATEST_UNIVERSE_VERSION:
        return universe_version
    resolved = session.execute(
        select(func.max(models.ModelUniverseMember.universe_version)).where(
            models.ModelUniverseMember.universe_name == universe_name
        )
    ).scalar_one_or_none()
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"universe {universe_name} has no versions")
    return resolved

CHART_RANGES = {"10d", "1m", "3m", "6m", "1y", "max"}
CHART_RANGE_DAYS = {
    "10d": 10,
    "1m": 31,
    "3m": 92,
    "6m": 183,
    "1y": 366,
}


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    expected_api_key = os.getenv("AAT_API_KEY")
    if expected_api_key and request.url.path != "/health":
        supplied_api_key = request.headers.get("x-aat-api-key", "")
        if not hmac.compare_digest(supplied_api_key, expected_api_key):
            return JSONResponse(status_code=401, content={"detail": "invalid API key"})
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": app.version}


@app.get("/attribution-methodologies", response_model=list[AttributionMethodologyResponse])
def attribution_methodologies(
    include_archived: bool = Query(default=True),
    prefer_compose_port: bool = Query(default=False),
) -> list[AttributionMethodologyResponse]:
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        stmt = select(models.AttributionMethodology)
        if not include_archived:
            stmt = stmt.where(models.AttributionMethodology.status == "active")
        rows = session.execute(
            stmt.order_by(
                models.AttributionMethodology.is_default.desc(),
                models.AttributionMethodology.status.asc(),
                models.AttributionMethodology.methodology.asc(),
            )
        ).scalars()
        return [
            AttributionMethodologyResponse(
                methodology=row.methodology,
                display_name=row.display_name,
                status=row.status,
                is_default=bool(row.is_default),
                model_version=row.model_version,
                factor_basket_version=row.factor_basket_version,
                supported_cadences=list(row.supported_cadences or []),
            )
            for row in rows
        ]


@app.get("/attribution-chart", response_model=AttributionChartResponse)
def attribution_chart(
    ticker: str,
    range_: str = Query(default="1m", alias="range", pattern="^(10d|1m|3m|6m|1y|max)$"),
    methodology: str = DEFAULT_ATTRIBUTION_METHODOLOGY,
    prefer_compose_port: bool = Query(default=False),
) -> AttributionChartResponse:
    normalized_ticker = ticker.upper()
    chart_range = range_.lower()
    cadence = chart_cadence(chart_range)
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        security = find_security_or_404(session=session, ticker=normalized_ticker)
        end = session.execute(
            select(func.max(models.PriceBar.event_time)).where(
                models.PriceBar.security_id == security.security_id
            )
        ).scalar_one_or_none()
        if end is None:
            raise HTTPException(status_code=404, detail="price history not found")
        if chart_range == "max":
            start = session.execute(
                select(func.min(models.PriceBar.event_time)).where(
                    models.PriceBar.security_id == security.security_id
                )
            ).scalar_one()
        else:
            start = end - timedelta(days=CHART_RANGE_DAYS[chart_range])

        price_rows = session.execute(
            select(models.PriceBar)
            .where(models.PriceBar.security_id == security.security_id)
            .where(models.PriceBar.event_time >= start)
            .where(models.PriceBar.event_time <= end)
            .order_by(models.PriceBar.event_time.asc(), models.PriceBar.timestamp_available.desc())
        ).scalars()
        price_points = build_chart_price_points(list(price_rows), cadence=cadence)

        run_rows = list(
            session.execute(
                select(models.AttributionRun)
                .where(models.AttributionRun.security_id == security.security_id)
                .where(models.AttributionRun.cadence == cadence)
                .where(models.AttributionRun.methodology == methodology)
                .where(models.AttributionRun.window_end >= start)
                .where(models.AttributionRun.window_end <= end)
                .order_by(models.AttributionRun.window_end.asc(), models.AttributionRun.created_at.desc())
            ).scalars()
        )
        run_ids = [run.attribution_run_id for run in run_rows]
        contribution_rows = (
            list(
                session.execute(
                    select(models.AttributionContribution)
                    .where(models.AttributionContribution.attribution_run_id.in_(run_ids))
                    .order_by(models.AttributionContribution.driver.asc(), models.AttributionContribution.name.asc())
                ).scalars()
            )
            if run_ids
            else []
        )
        attribution_points = build_chart_attribution_points(
            runs=run_rows,
            contributions=contribution_rows,
        )
        driver_order = chart_driver_order(attribution_points)

        return AttributionChartResponse(
            ticker=normalized_ticker,
            range=chart_range,
            cadence=cadence,
            start=start,
            end=end,
            price_points=price_points,
            attribution_points=attribution_points,
            driver_order=driver_order,
        )


@app.get("/universe", response_model=UniverseResponse)
def universe(
    search: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    exchange: str | None = None,
    status: str | None = Query(default=None, pattern="^(available|missing)$"),
    universe_name: str | None = None,
    universe_version: str | None = None,
    methodology: str = DEFAULT_ATTRIBUTION_METHODOLOGY,
    sort: str = Query(default="ticker"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    prefer_compose_port: bool = Query(default=False),
) -> UniverseResponse:
    universe_name = universe_name or default_universe_name()
    universe_version = universe_version or default_universe_version()
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        universe_version = resolve_universe_version(
            session=session,
            universe_name=universe_name,
            universe_version=universe_version,
        )
        row_stmt, sort_columns = build_universe_statement(
            search=search,
            sector=sector,
            industry=industry,
            exchange=exchange,
            status=status,
            universe_name=universe_name,
            universe_version=universe_version,
            methodology=methodology,
        )
        sort_column = sort_columns.get(sort, sort_columns["ticker"])
        ordered_sort = sort_column.desc().nullslast() if order == "desc" else sort_column.asc().nullslast()
        total = session.execute(select(func.count()).select_from(row_stmt.order_by(None).subquery())).scalar_one()
        rows = session.execute(
            row_stmt.order_by(ordered_sort, models.SecurityAttributionSummary.ticker.asc())
            .limit(limit)
            .offset(offset)
        ).mappings().all()
        universe_options = load_universe_options(
            session=session,
            search=search,
            sector=sector,
            industry=industry,
            exchange=exchange,
            status=status,
            universe_name=universe_name,
            universe_version=universe_version,
            methodology=methodology,
        )
        latest_run_date = latest_universe_run_date(
            session=session,
            search=search,
            sector=sector,
            industry=industry,
            exchange=exchange,
            status=status,
            universe_name=universe_name,
            universe_version=universe_version,
            methodology=methodology,
        )
        return UniverseResponse(
            rows=[
                UniverseStockResponse(
                    ticker=row["ticker"],
                    company_name=row["company_name"],
                    security_id=row["security_id"],
                    company_id=row["company_id"],
                    exchange=row["exchange"],
                    sector=row["sector"],
                    industry=row["industry"],
                    latest_run_id=row["latest_run_id"],
                    latest_window_end=row["latest_window_end"],
                    latest_observed_return_bps=(
                        float(row["latest_observed_return_bps"])
                        if row["latest_observed_return_bps"] is not None
                        else None
                    ),
                    latest_residual_bps=(
                        float(row["latest_residual_bps"]) if row["latest_residual_bps"] is not None else None
                    ),
                    latest_price_change_usd=float(row["latest_price_change_usd"])
                    if row["latest_price_change_usd"] is not None
                    else None,
                    latest_residual_usd=latest_residual_usd(
                        latest_residual_bps=row["latest_residual_bps"],
                        latest_observed_return_bps=row["latest_observed_return_bps"],
                        latest_price_change_usd=row["latest_price_change_usd"],
                    ),
                    methodology=row["methodology"],
                    top_driver=row["top_driver"],
                    top_driver_confidence=row["top_driver_confidence"],
                    contribution_count=int(row["contribution_count"] or 0),
                    has_evidence=bool(row["evidence_count"] or 0),
                    run_status="available" if row["latest_run_id"] is not None else "missing",
                )
                for row in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
            latest_run_date=latest_run_date,
            company_options=universe_options["company_options"],
            sector_options=universe_options["sector_options"],
            industry_options=universe_options["industry_options"],
            exchange_options=universe_options["exchange_options"],
        )


@app.get("/attribution-runs/latest", response_model=AttributionRunResponse)
def latest_attribution_run(
    ticker: str,
    cadence: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
    methodology: str = DEFAULT_ATTRIBUTION_METHODOLOGY,
    prefer_compose_port: bool = Query(default=False),
) -> AttributionRunResponse:
    normalized_ticker = ticker.upper()
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        security = session.execute(
            select(models.Security)
            .join(
                models.SecurityTickerHistory,
                models.Security.security_id == models.SecurityTickerHistory.security_id,
            )
            .where(models.SecurityTickerHistory.ticker == normalized_ticker)
            .where(models.SecurityTickerHistory.active_to.is_(None))
            .order_by(models.SecurityTickerHistory.active_from.desc())
            .limit(1)
        ).scalar_one_or_none()
        if security is None:
            raise HTTPException(status_code=404, detail="ticker not found")

        run = session.execute(
            select(models.AttributionRun)
            .where(models.AttributionRun.security_id == security.security_id)
            .where(models.AttributionRun.cadence == cadence)
            .where(models.AttributionRun.methodology == methodology)
            .order_by(models.AttributionRun.window_end.desc(), models.AttributionRun.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=404, detail="attribution run not found")

        return build_attribution_response(
            session=session,
            run=run,
            ticker=normalized_ticker,
        )


@app.post("/attribution-runs/ensure-latest", response_model=AttributionEnsureLatestResponse)
def ensure_latest_attribution_run(
    ticker: str,
    methodology: str = DEFAULT_ATTRIBUTION_METHODOLOGY,
    cadence: str | None = Query(default=None, pattern="^(daily|weekly|monthly)$"),
    range_: str = Query(default="1m", alias="range", pattern="^(10d|1m|3m|6m|1y|max)$"),
    prefer_compose_port: bool = Query(default=False),
) -> AttributionEnsureLatestResponse:
    if methodology not in VALID_ATTRIBUTION_METHODOLOGIES:
        raise HTTPException(status_code=400, detail="unsupported attribution methodology")
    normalized_ticker = ticker.upper()
    chart_range = range_.lower()
    requested_cadence = cadence if isinstance(cadence, str) else None
    resolved_cadence = requested_cadence or chart_cadence(chart_range)
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        security = find_security_or_404(session=session, ticker=normalized_ticker)
        target_window_end = latest_price_event_time(
            session=session,
            security_id=security.security_id,
        )
        if target_window_end is None:
            raise HTTPException(status_code=404, detail="price history not found")
        latest_run = latest_run_for_security(
            session=session,
            security_id=security.security_id,
            cadence=resolved_cadence,
            methodology=methodology,
        )

        target_range_start = target_start_for_range(
            session=session,
            security_id=security.security_id,
            chart_range=chart_range,
            target_window_end=target_window_end,
        )
        lookback_start = target_range_start - timedelta(
            days=methodology_lookback_days(session=session, methodology=methodology)
        )
        trading_dates = load_trading_dates_for_range(
            session=session,
            security_id=security.security_id,
            start=lookback_start,
            end=target_window_end,
        )
        candidate_windows = candidate_windows_for_range(
            trading_dates=trading_dates,
            cadence=resolved_cadence,
            target_range_start=target_range_start,
            target_range_end=target_window_end,
        )
        missing_windows = missing_windows_for_range(
            session=session,
            security_id=security.security_id,
            methodology=methodology,
            cadence=resolved_cadence,
            trading_dates=trading_dates,
            target_range_start=target_range_start,
            target_range_end=target_window_end,
            candidate_windows=candidate_windows,
        )
        latest_candidate_window_end = max(
            (window.end for window in candidate_windows),
            default=None,
        )
        latest_window_is_fresh = (
            latest_candidate_window_end is None
            or (latest_run is not None and latest_run.window_end >= latest_candidate_window_end)
        )
        if latest_run is not None and latest_window_is_fresh and not missing_windows:
            return AttributionEnsureLatestResponse(
                status="fresh",
                run=build_attribution_response(
                    session=session,
                    run=latest_run,
                    ticker=normalized_ticker,
                ),
                latest_existing_window_end=latest_run.window_end,
                target_window_end=target_window_end,
            )

        job = enqueue_or_reuse_on_demand_job(
            session=session,
            security=security,
            ticker=normalized_ticker,
            methodology=methodology,
            cadence=resolved_cadence,
            target_range_start=target_range_start,
            target_range_end=target_window_end,
            latest_existing_window_end=latest_run.window_end if latest_run is not None else None,
            target_window_end=target_window_end,
        )
        return AttributionEnsureLatestResponse(
            status=job.status,
            job_id=job.attribution_on_demand_job_id,
            latest_existing_window_end=job.latest_existing_window_end,
            target_window_end=job.target_window_end,
        )


@app.get("/attribution-jobs/{job_id}", response_model=AttributionJobResponse)
def attribution_job(
    job_id: UUID,
    prefer_compose_port: bool = Query(default=False),
) -> AttributionJobResponse:
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        job = session.get(models.AttributionOnDemandJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="attribution job not found")
        return build_attribution_job_response(session=session, job=job)


@app.get("/attribution-runs", response_model=list[AttributionRunResponse])
def attribution_runs(
    ticker: str,
    cadence: str | None = Query(default=None, pattern="^(daily|weekly|monthly)$"),
    methodology: str = DEFAULT_ATTRIBUTION_METHODOLOGY,
    limit: int = Query(default=25, ge=1, le=250),
    prefer_compose_port: bool = Query(default=False),
) -> list[AttributionRunResponse]:
    normalized_ticker = ticker.upper()
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        security = find_security_or_404(session=session, ticker=normalized_ticker)
        stmt = (
            select(models.AttributionRun)
            .where(models.AttributionRun.security_id == security.security_id)
            .where(models.AttributionRun.methodology == methodology)
        )
        if cadence is not None:
            stmt = stmt.where(models.AttributionRun.cadence == cadence)
        runs = session.execute(
            stmt.order_by(models.AttributionRun.window_end.desc(), models.AttributionRun.created_at.desc()).limit(limit)
        ).scalars()
        return [
            build_attribution_response(session=session, run=run, ticker=normalized_ticker)
            for run in runs
        ]


@app.get("/attribution-runs/{run_id}", response_model=AttributionRunResponse)
def attribution_run_by_id(
    run_id: UUID,
    prefer_compose_port: bool = Query(default=False),
) -> AttributionRunResponse:
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        run = session.execute(
            select(models.AttributionRun).where(models.AttributionRun.attribution_run_id == run_id)
        ).scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=404, detail="attribution run not found")
        ticker = session.execute(
            select(models.SecurityTickerHistory.ticker)
            .where(models.SecurityTickerHistory.security_id == run.security_id)
            .where(models.SecurityTickerHistory.active_to.is_(None))
        ).scalar_one_or_none()
        return build_attribution_response(session=session, run=run, ticker=ticker or "")


def latest_price_event_time(*, session, security_id: UUID) -> datetime | None:
    return session.execute(
        select(func.max(models.PriceBar.event_time)).where(models.PriceBar.security_id == security_id)
    ).scalar_one_or_none()


def latest_run_for_security(*, session, security_id: UUID, cadence: str, methodology: str):
    return session.execute(
        select(models.AttributionRun)
        .where(models.AttributionRun.security_id == security_id)
        .where(models.AttributionRun.cadence == cadence)
        .where(models.AttributionRun.methodology == methodology)
        .order_by(models.AttributionRun.window_end.desc(), models.AttributionRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def load_trading_dates_for_range(
    *,
    session,
    security_id: UUID,
    start: datetime,
    end: datetime,
) -> list[datetime]:
    rows = session.execute(
        select(models.PriceBar.event_time)
        .distinct()
        .where(models.PriceBar.security_id == security_id)
        .where(models.PriceBar.event_time >= start)
        .where(models.PriceBar.event_time <= end)
        .order_by(models.PriceBar.event_time.asc())
    )
    return [row[0] for row in rows]


def methodology_lookback_days(*, session, methodology: str) -> int:
    methodology_row = load_methodology(session=session, methodology=methodology)
    runner_config = methodology_row.runner_config if methodology_row is not None else {}
    return int((runner_config or {}).get("lookback_days", 252))


def target_start_for_range(
    *,
    session,
    security_id: UUID,
    chart_range: str,
    target_window_end: datetime,
) -> datetime:
    if chart_range == "max":
        start = session.execute(
            select(func.min(models.PriceBar.event_time)).where(models.PriceBar.security_id == security_id)
        ).scalar_one_or_none()
        return start or target_window_end
    return target_window_end - timedelta(days=CHART_RANGE_DAYS[chart_range])


def enqueue_or_reuse_on_demand_job(
    *,
    session,
    security: models.Security,
    ticker: str,
    methodology: str,
    cadence: str,
    target_range_start: datetime,
    target_range_end: datetime,
    latest_existing_window_end: datetime | None,
    target_window_end: datetime,
) -> models.AttributionOnDemandJob:
    active_job = session.execute(
        select(models.AttributionOnDemandJob)
        .where(models.AttributionOnDemandJob.security_id == security.security_id)
        .where(models.AttributionOnDemandJob.methodology == methodology)
        .where(models.AttributionOnDemandJob.cadence == cadence)
        .where(models.AttributionOnDemandJob.target_range_start == target_range_start)
        .where(models.AttributionOnDemandJob.target_range_end == target_range_end)
        .where(models.AttributionOnDemandJob.status.in_(("queued", "running")))
        .order_by(models.AttributionOnDemandJob.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    if active_job is not None:
        return active_job

    now = datetime.now(timezone.utc)
    job_id = uuid.uuid4()
    stmt = insert(models.AttributionOnDemandJob).values(
        attribution_on_demand_job_id=job_id,
        security_id=security.security_id,
        ticker=ticker,
        methodology=methodology,
        cadence=cadence,
        target_range_start=target_range_start,
        target_range_end=target_range_end,
        latest_existing_window_end=latest_existing_window_end,
        target_window_end=target_window_end,
        status="queued",
        expected_windows=0,
        ran_windows=0,
        skipped_windows=0,
        latest_run_id=None,
        error_payload=None,
        created_at=now,
        started_at=None,
        finished_at=None,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_nothing(
        index_elements=[
            models.AttributionOnDemandJob.security_id,
            models.AttributionOnDemandJob.methodology,
            models.AttributionOnDemandJob.cadence,
            models.AttributionOnDemandJob.target_range_start,
            models.AttributionOnDemandJob.target_range_end,
        ],
        index_where=models.AttributionOnDemandJob.status.in_(("queued", "running")),
    ).returning(models.AttributionOnDemandJob.attribution_on_demand_job_id)
    inserted_id = session.execute(stmt).scalar_one_or_none()
    return session.get(models.AttributionOnDemandJob, inserted_id or job_id) or session.execute(
        select(models.AttributionOnDemandJob)
        .where(models.AttributionOnDemandJob.security_id == security.security_id)
        .where(models.AttributionOnDemandJob.methodology == methodology)
        .where(models.AttributionOnDemandJob.cadence == cadence)
        .where(models.AttributionOnDemandJob.target_range_start == target_range_start)
        .where(models.AttributionOnDemandJob.target_range_end == target_range_end)
        .where(models.AttributionOnDemandJob.status.in_(("queued", "running")))
        .limit(1)
    ).scalar_one()


def build_attribution_job_response(*, session, job: models.AttributionOnDemandJob) -> AttributionJobResponse:
    run_response = None
    if job.latest_run_id is not None:
        run = session.get(models.AttributionRun, job.latest_run_id)
        if run is not None:
            run_response = build_attribution_response(session=session, run=run, ticker=job.ticker)
    return AttributionJobResponse(
        job_id=job.attribution_on_demand_job_id,
        ticker=job.ticker,
        security_id=job.security_id,
        methodology=job.methodology,
        cadence=job.cadence,
        status=job.status,
        target_range_start=job.target_range_start,
        target_range_end=job.target_range_end,
        latest_existing_window_end=job.latest_existing_window_end,
        target_window_end=job.target_window_end,
        expected_windows=int(job.expected_windows or 0),
        ran_windows=int(job.ran_windows or 0),
        skipped_windows=int(job.skipped_windows or 0),
        latest_run_id=job.latest_run_id,
        error_payload=job.error_payload,
        run=run_response,
    )


def find_security_or_404(*, session, ticker: str) -> models.Security:
    security = session.execute(
        select(models.Security)
        .join(
            models.SecurityTickerHistory,
            models.Security.security_id == models.SecurityTickerHistory.security_id,
        )
        .where(models.SecurityTickerHistory.ticker == ticker)
        .where(models.SecurityTickerHistory.active_to.is_(None))
        .order_by(models.SecurityTickerHistory.active_from.desc())
        .limit(1)
    ).scalar_one_or_none()
    if security is None:
        raise HTTPException(status_code=404, detail="ticker not found")
    return security


def dedupe_universe_rows(rows):
    by_ticker = {}
    for row in rows:
        ticker = row["ticker"]
        current = by_ticker.get(ticker)
        if current is None or universe_row_rank(row) > universe_row_rank(current):
            by_ticker[ticker] = row
    return list(by_ticker.values())


def universe_row_rank(row) -> tuple:
    return (
        1 if row["latest_run_id"] is not None else 0,
        row["latest_window_end"] or datetime.min.replace(tzinfo=timezone.utc),
        1 if row["sector"] else 0,
        1 if row["industry"] else 0,
    )


def build_universe_options(rows) -> dict[str, list]:
    company_options = [
        UniverseCompanyOption(ticker=row["ticker"], company_name=row["company_name"])
        for row in sorted(rows, key=lambda item: item["ticker"])
    ]
    return {
        "company_options": company_options,
        "sector_options": sorted({row["sector"] for row in rows if row["sector"]}),
        "industry_options": sorted({row["industry"] for row in rows if row["industry"]}),
        "exchange_options": sorted({row["exchange"] for row in rows if row["exchange"]}),
    }


def latest_residual_usd(
    *,
    latest_residual_bps,
    latest_observed_return_bps,
    latest_price_change_usd,
) -> float | None:
    if (
        latest_residual_bps is None
        or latest_observed_return_bps is None
        or latest_price_change_usd is None
        or not is_share_stable(float(latest_observed_return_bps))
    ):
        return None
    return float(latest_residual_bps) / float(latest_observed_return_bps) * float(latest_price_change_usd)


def display_share_of_move(*, share_of_move, observed_return_bps) -> float | None:
    if share_of_move is None or not is_share_stable(float(observed_return_bps)):
        return None
    return float(share_of_move)


def chart_cadence(chart_range: str) -> str:
    return "weekly" if chart_range in {"6m", "1y", "max"} else "daily"


def build_chart_price_points(
    price_bars: list[models.PriceBar],
    *,
    cadence: str = "daily",
) -> list[AttributionChartPricePoint]:
    bars_by_date = {}
    for bar in price_bars:
        if bar.event_time not in bars_by_date:
            bars_by_date[bar.event_time] = bar
    bars = sorted(bars_by_date.values(), key=lambda item: item.event_time)
    if cadence == "weekly":
        bars = sample_weekly_price_bars(bars)
    if not bars:
        return []
    base_price = float(bars[0].adjusted_close)
    return [
        AttributionChartPricePoint(
            date=bar.event_time,
            adjusted_close=float(bar.adjusted_close),
            cumulative_return_pct=((float(bar.adjusted_close) / base_price) - 1.0) * 100,
        )
        for bar in bars
    ]


def sample_weekly_price_bars(price_bars: list[models.PriceBar]) -> list[models.PriceBar]:
    bars_by_week = {}
    for bar in price_bars:
        iso = bar.event_time.isocalendar()
        bars_by_week[(iso.year, iso.week)] = bar
    return list(bars_by_week.values())


def build_chart_attribution_points(
    *,
    runs: list[models.AttributionRun],
    contributions: list[models.AttributionContribution],
) -> list[AttributionChartPoint]:
    contributions_by_run = {}
    for contribution in contributions:
        contributions_by_run.setdefault(contribution.attribution_run_id, []).append(contribution)
    points = []
    for run in runs:
        run_contributions = contributions_by_run.get(run.attribution_run_id, [])
        points.append(
            AttributionChartPoint(
                date=run.window_end,
                window_start=run.window_start,
                window_end=run.window_end,
                observed_return_pct=float(run.observed_return_bps) / 100,
                contributions=[
                    AttributionChartContributionPoint(
                        driver=contribution.driver,
                        name=contribution.name,
                        contribution_pct=float(contribution.contribution_bps) / 100,
                        share_of_move=display_share_of_move(
                            share_of_move=contribution.share_of_move,
                            observed_return_bps=run.observed_return_bps,
                        ),
                    )
                    for contribution in run_contributions
                ],
            )
        )
    return points


def chart_driver_order(points: list[AttributionChartPoint]) -> list[str]:
    preferred = [
        "market",
        "sector",
        "industry",
        "peer",
        "style",
        "macro",
        "positioning",
        "event",
        "unexplained_residual",
    ]
    present = {
        contribution.driver
        for point in points
        for contribution in point.contributions
    }
    ordered = [driver for driver in preferred if driver in present]
    ordered.extend(sorted(present.difference(ordered)))
    return ordered


def average_attribute_shares(points: list[AttributionChartPoint]) -> list[dict[str, float | str]]:
    totals: dict[tuple[str, str], float] = {}
    counts: dict[tuple[str, str], int] = {}
    for point in points:
        for contribution in point.contributions:
            if contribution.share_of_move is None:
                continue
            key = (contribution.driver, contribution.name)
            totals[key] = totals.get(key, 0.0) + contribution.share_of_move
            counts[key] = counts.get(key, 0) + 1
    averaged = [
        {
            "driver": driver,
            "name": name,
            "average_share_of_move": totals[(driver, name)] / counts[(driver, name)],
        }
        for driver, name in totals
    ]
    return sorted(
        averaged,
        key=lambda item: abs(float(item["average_share_of_move"])),
        reverse=True,
    )


def build_universe_statement(
    *,
    search: str | None,
    sector: str | None,
    industry: str | None,
    exchange: str | None,
    status: str | None,
    universe_name: str = DEFAULT_FAUSTCALC_UNIVERSE_NAME,
    universe_version: str = DEFAULT_FAUSTCALC_UNIVERSE_VERSION,
    methodology: str = DEFAULT_ATTRIBUTION_METHODOLOGY,
):
    stmt = (
        select(
            models.SecurityAttributionSummary.ticker.label("ticker"),
            models.SecurityAttributionSummary.company_name.label("company_name"),
            models.SecurityAttributionSummary.methodology.label("methodology"),
            models.SecurityAttributionSummary.security_id.label("security_id"),
            models.SecurityAttributionSummary.company_id.label("company_id"),
            models.SecurityAttributionSummary.exchange.label("exchange"),
            models.SecurityAttributionSummary.sector.label("sector"),
            models.SecurityAttributionSummary.industry.label("industry"),
            models.SecurityAttributionSummary.latest_run_id.label("latest_run_id"),
            models.SecurityAttributionSummary.latest_window_end.label("latest_window_end"),
            models.SecurityAttributionSummary.latest_observed_return_bps.label("latest_observed_return_bps"),
            models.SecurityAttributionSummary.latest_residual_bps.label("latest_residual_bps"),
            models.SecurityAttributionSummary.latest_price_change_usd.label("latest_price_change_usd"),
            models.SecurityAttributionSummary.top_driver.label("top_driver"),
            models.SecurityAttributionSummary.top_driver_confidence.label("top_driver_confidence"),
            models.SecurityAttributionSummary.contribution_count.label("contribution_count"),
            models.SecurityAttributionSummary.evidence_count.label("evidence_count"),
        )
        .where(models.SecurityAttributionSummary.universe_name == universe_name)
        .where(models.SecurityAttributionSummary.universe_version == universe_version)
        .where(models.SecurityAttributionSummary.methodology == methodology)
    )
    stmt = apply_universe_summary_filters(
        stmt=stmt,
        search=search,
        sector=sector,
        industry=industry,
        exchange=exchange,
        status=status,
    )

    sort_columns = {
        "ticker": models.SecurityAttributionSummary.ticker,
        "company": models.SecurityAttributionSummary.company_name,
        "exchange": models.SecurityAttributionSummary.exchange,
        "sector": models.SecurityAttributionSummary.sector,
        "industry": models.SecurityAttributionSummary.industry,
        "latest_run": models.SecurityAttributionSummary.latest_window_end,
        "move": models.SecurityAttributionSummary.latest_observed_return_bps,
        "residual": models.SecurityAttributionSummary.latest_residual_bps,
        "status": models.SecurityAttributionSummary.run_status,
        "top_driver": models.SecurityAttributionSummary.top_driver,
        "confidence": models.SecurityAttributionSummary.top_driver_confidence,
        "contributions": models.SecurityAttributionSummary.contribution_count,
        "evidence": models.SecurityAttributionSummary.evidence_count,
        "_literal": literal(1),
    }
    return stmt, sort_columns


def apply_universe_summary_filters(
    *,
    stmt,
    search: str | None,
    sector: str | None,
    industry: str | None,
    exchange: str | None,
    status: str | None,
):
    if search:
        normalized_search = f"%{search.upper()}%"
        stmt = stmt.where(
            (func.upper(models.SecurityAttributionSummary.ticker).like(normalized_search))
            | (func.upper(models.SecurityAttributionSummary.company_name).like(normalized_search))
        )
    if sector:
        stmt = stmt.where(models.SecurityAttributionSummary.sector == sector)
    if industry:
        stmt = stmt.where(models.SecurityAttributionSummary.industry == industry)
    if exchange:
        stmt = stmt.where(func.upper(models.SecurityAttributionSummary.exchange) == exchange.upper())
    if status == "available":
        stmt = stmt.where(models.SecurityAttributionSummary.run_status == "available")
    elif status == "missing":
        stmt = stmt.where(models.SecurityAttributionSummary.run_status == "missing")
    return stmt


def load_universe_options(
    *,
    session,
    search: str | None,
    sector: str | None,
    industry: str | None,
    exchange: str | None,
    status: str | None,
    universe_name: str,
    universe_version: str,
    methodology: str,
) -> dict[str, list]:
    stmt = (
        select(
            models.SecurityAttributionSummary.ticker.label("ticker"),
            models.SecurityAttributionSummary.company_name.label("company_name"),
            models.SecurityAttributionSummary.sector.label("sector"),
            models.SecurityAttributionSummary.industry.label("industry"),
            models.SecurityAttributionSummary.exchange.label("exchange"),
        )
        .where(models.SecurityAttributionSummary.universe_name == universe_name)
        .where(models.SecurityAttributionSummary.universe_version == universe_version)
        .where(models.SecurityAttributionSummary.methodology == methodology)
    )
    stmt = apply_universe_summary_filters(
        stmt=stmt,
        search=search,
        sector=sector,
        industry=industry,
        exchange=exchange,
        status=status,
    )
    rows = session.execute(stmt.order_by(models.SecurityAttributionSummary.ticker.asc())).mappings().all()
    return build_universe_options(rows)


def latest_universe_run_date(
    *,
    session,
    search: str | None,
    sector: str | None,
    industry: str | None,
    exchange: str | None,
    status: str | None,
    universe_name: str,
    universe_version: str,
    methodology: str,
) -> datetime | None:
    stmt = (
        select(func.max(models.SecurityAttributionSummary.latest_window_end))
        .where(models.SecurityAttributionSummary.universe_name == universe_name)
        .where(models.SecurityAttributionSummary.universe_version == universe_version)
        .where(models.SecurityAttributionSummary.methodology == methodology)
    )
    stmt = apply_universe_summary_filters(
        stmt=stmt,
        search=search,
        sector=sector,
        industry=industry,
        exchange=exchange,
        status=status,
    )
    return session.execute(stmt).scalar_one_or_none()


def build_attribution_response(
    *,
    session,
    run: models.AttributionRun,
    ticker: str,
) -> AttributionRunResponse:
    contributions = list(session.execute(
        select(models.AttributionContribution)
        .where(models.AttributionContribution.attribution_run_id == run.attribution_run_id)
        .order_by(models.AttributionContribution.driver)
    ).scalars())

    return AttributionRunResponse(
        attribution_run_id=run.attribution_run_id,
        ticker=ticker,
        security_id=run.security_id,
        window_start=run.window_start,
        window_end=run.window_end,
        attribution_cutoff=run.attribution_cutoff,
        observed_return_bps=float(run.observed_return_bps),
        unexplained_residual_bps=float(run.unexplained_residual_bps),
        methodology=run.methodology,
        model_version=run.model_version,
        data_version=run.data_version,
        factor_basket_version=run.factor_basket_version,
        cadence=run.cadence,
        contributions=[
            ContributionResponse(
                attribution_contribution_id=item.attribution_contribution_id,
                driver=item.driver,
                name=item.name,
                contribution_bps=float(item.contribution_bps),
                share_of_move=display_share_of_move(
                    share_of_move=item.share_of_move,
                    observed_return_bps=run.observed_return_bps,
                ),
                confidence=item.confidence,
                evidence=item.evidence or [],
                contribution_stage=item.contribution_stage,
                evidence_payload=item.evidence_payload,
            )
            for item in contributions
        ],
        narrative=build_narrative_from_run(run=run, contributions=contributions),
    )


def build_narrative_from_run(*, run: models.AttributionRun, contributions: list[models.AttributionContribution]) -> str:
    result = AttributionResult(
        security_id=run.security_id,
        window=TimeWindow(start=run.window_start, end=run.window_end),
        attribution_cutoff=run.attribution_cutoff,
        observed_return_bps=float(run.observed_return_bps),
        unexplained_residual_bps=float(run.unexplained_residual_bps),
        model_version=run.model_version,
        contributions=[
            AttributionContribution(
                driver=DriverType(item.driver),
                name=item.name,
                contribution_bps=float(item.contribution_bps),
                share_of_move=display_share_of_move(
                    share_of_move=item.share_of_move,
                    observed_return_bps=run.observed_return_bps,
                ),
                confidence=ConfidenceLevel(item.confidence),
                evidence=item.evidence or [],
                evidence_payload=item.evidence_payload or {},
            )
            for item in contributions
        ],
    )
    return build_deterministic_narrative(result)


@app.post("/analyst-feedback", response_model=AnalystFeedbackResponse)
def create_analyst_feedback(
    request: AnalystFeedbackRequest,
    prefer_compose_port: bool = Query(default=False),
) -> AnalystFeedbackResponse:
    allowed = {"correct", "partially_correct", "wrong", "missing_driver"}
    if request.feedback not in allowed:
        raise HTTPException(status_code=422, detail=f"feedback must be one of {sorted(allowed)}")
    if request.feedback == "missing_driver" and not request.missing_driver_name:
        raise HTTPException(status_code=422, detail="missing_driver feedback requires missing_driver_name")
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        run = session.execute(
            select(models.AttributionRun)
            .where(models.AttributionRun.attribution_run_id == request.attribution_run_id)
        ).scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=404, detail="attribution run not found")
        if request.attribution_contribution_id is not None:
            contribution = session.execute(
                select(models.AttributionContribution)
                .where(models.AttributionContribution.attribution_contribution_id == request.attribution_contribution_id)
                .where(models.AttributionContribution.attribution_run_id == request.attribution_run_id)
            ).scalar_one_or_none()
            if contribution is None:
                raise HTTPException(status_code=404, detail="contribution not found for run")
        feedback = models.AnalystFeedback(
            analyst_feedback_id=uuid.uuid4(),
            attribution_run_id=request.attribution_run_id,
            attribution_contribution_id=request.attribution_contribution_id,
            feedback=request.feedback,
            missing_driver_name=request.missing_driver_name,
            comment=request.comment,
            created_at=datetime.now(timezone.utc),
        )
        session.add(feedback)
        session.flush()
        return AnalystFeedbackResponse(
            analyst_feedback_id=feedback.analyst_feedback_id,
            attribution_run_id=feedback.attribution_run_id,
            attribution_contribution_id=feedback.attribution_contribution_id,
            feedback=feedback.feedback,
            missing_driver_name=feedback.missing_driver_name,
            comment=feedback.comment,
            created_at=feedback.created_at,
        )


@app.get("/exposure-update-decisions", response_model=list[ExposureUpdateDecisionResponse])
def exposure_update_decisions(
    ticker: str | None = None,
    prefer_compose_port: bool = Query(default=False),
) -> list[ExposureUpdateDecisionResponse]:
    normalized_ticker = ticker.upper() if ticker else None
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        stmt = select(models.ExposureUpdateDecision)
        if normalized_ticker:
            stmt = (
                stmt.join(
                    models.Security,
                    models.ExposureUpdateDecision.company_id == models.Security.company_id,
                )
                .join(
                    models.SecurityTickerHistory,
                    models.Security.security_id == models.SecurityTickerHistory.security_id,
                )
                .where(models.SecurityTickerHistory.ticker == normalized_ticker)
                .where(models.SecurityTickerHistory.active_to.is_(None))
            )
        stmt = stmt.order_by(models.ExposureUpdateDecision.evaluated_at.desc()).limit(25)
        decisions = session.execute(stmt).scalars()
        return [
            ExposureUpdateDecisionResponse(
                exposure_update_decision_id=decision.exposure_update_decision_id,
                ticker=normalized_ticker,
                company_id=decision.company_id,
                exposure_name=decision.exposure_name,
                decision=decision.decision,
                review_required=decision.review_required,
                confidence=decision.confidence,
                rationale=decision.rationale,
                evidence_event_ids=decision.evidence_event_ids,
                model_version=decision.model_version,
                evaluated_at=decision.evaluated_at,
            )
            for decision in decisions
        ]

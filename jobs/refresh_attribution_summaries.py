from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from engine.contracts import DriverType
from jobs.faustcalc_common import (
    DEFAULT_FAUSTCALC_UNIVERSE_NAME,
    DEFAULT_FAUSTCALC_UNIVERSE_VERSION,
    stable_uuid,
)


@dataclass
class SummaryRefreshReport:
    universe_name: str
    universe_version: str
    refreshed: int = 0
    available: int = 0
    missing: int = 0

    def render(self) -> str:
        return (
            "refreshed attribution summaries "
            f"universe={self.universe_name} version={self.universe_version} "
            f"rows={self.refreshed} available={self.available} missing={self.missing}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh frontend-ready attribution summaries")
    parser.add_argument("--universe-name", default=DEFAULT_FAUSTCALC_UNIVERSE_NAME)
    parser.add_argument("--universe-version", default=DEFAULT_FAUSTCALC_UNIVERSE_VERSION)
    parser.add_argument("--ticker", action="append", help="Limit refresh to one ticker; may be repeated")
    parser.add_argument("--limit", type=int, help="Maximum members to refresh")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        report = refresh_attribution_summaries(
            session=session,
            universe_name=args.universe_name,
            universe_version=args.universe_version,
            tickers=tuple(args.ticker or ()),
            limit=args.limit,
        )
    print(report.render())


def refresh_attribution_summaries(
    *,
    session,
    universe_name: str = DEFAULT_FAUSTCALC_UNIVERSE_NAME,
    universe_version: str = DEFAULT_FAUSTCALC_UNIVERSE_VERSION,
    tickers: tuple[str, ...] = (),
    limit: int | None = None,
) -> SummaryRefreshReport:
    report = SummaryRefreshReport(universe_name=universe_name, universe_version=universe_version)
    stmt = (
        select(
            models.ModelUniverseMember,
            models.Security,
            models.Company,
        )
        .join(models.Security, models.Security.security_id == models.ModelUniverseMember.security_id)
        .join(models.Company, models.Company.company_id == models.Security.company_id)
        .where(models.ModelUniverseMember.universe_name == universe_name)
        .where(models.ModelUniverseMember.universe_version == universe_version)
        .where(models.ModelUniverseMember.eligibility_status == "eligible")
        .where(models.ModelUniverseMember.active_to.is_(None))
        .order_by(models.ModelUniverseMember.ticker)
    )
    if tickers:
        stmt = stmt.where(models.ModelUniverseMember.ticker.in_([ticker.upper() for ticker in tickers]))
    if limit is not None:
        stmt = stmt.limit(limit)

    for member, security, company in session.execute(stmt).all():
        summary = build_summary_row(
            session=session,
            member=member,
            security=security,
            company=company,
        )
        upsert_summary_row(session=session, summary=summary)
        report.refreshed += 1
        if summary["run_status"] == "available":
            report.available += 1
        else:
            report.missing += 1
    session.flush()
    return report


def build_summary_row(*, session, member, security, company) -> dict:
    refreshed_at = datetime.now(timezone.utc)
    classification = latest_classification(session=session, security_id=security.security_id)
    run = latest_daily_run(session=session, security_id=security.security_id)
    contribution_count = 0
    evidence_count = 0
    top_driver = None
    top_driver_confidence = None
    price_change = None

    if run is not None:
        contributions = list(
            session.execute(
                select(models.AttributionContribution).where(
                    models.AttributionContribution.attribution_run_id == run.attribution_run_id
                )
            ).scalars()
        )
        contribution_count = len(contributions)
        evidence_count = sum(1 for item in contributions if item.evidence or item.evidence_payload)
        top_contribution = max(
            [
                item
                for item in contributions
                if item.driver != DriverType.UNEXPLAINED_RESIDUAL.value
            ],
            key=lambda item: abs(float(item.contribution_bps)),
            default=None,
        )
        if top_contribution is not None:
            top_driver = top_contribution.name
            top_driver_confidence = top_contribution.confidence
        start_close = latest_adjusted_close(
            session=session,
            security_id=security.security_id,
            event_time=run.window_start,
            attribution_cutoff=run.attribution_cutoff,
        )
        end_close = latest_adjusted_close(
            session=session,
            security_id=security.security_id,
            event_time=run.window_end,
            attribution_cutoff=run.attribution_cutoff,
        )
        if start_close is not None and end_close is not None:
            price_change = end_close - start_close

    return {
        "security_attribution_summary_id": stable_uuid(
            f"security-summary:{member.universe_name}:{member.universe_version}:{member.security_id}"
        ),
        "universe_name": member.universe_name,
        "universe_version": member.universe_version,
        "security_id": member.security_id,
        "ticker": member.ticker,
        "company_id": security.company_id,
        "company_name": company.legal_name,
        "exchange": security.exchange,
        "sector": classification.sector if classification is not None else None,
        "industry": classification.industry if classification is not None else None,
        "latest_run_id": run.attribution_run_id if run is not None else None,
        "latest_window_start": run.window_start if run is not None else None,
        "latest_window_end": run.window_end if run is not None else None,
        "latest_observed_return_bps": run.observed_return_bps if run is not None else None,
        "latest_residual_bps": run.unexplained_residual_bps if run is not None else None,
        "latest_price_change_usd": price_change,
        "top_driver": top_driver,
        "top_driver_confidence": top_driver_confidence,
        "contribution_count": contribution_count,
        "evidence_count": evidence_count,
        "run_status": "available" if run is not None else "missing",
        "first_price_time": member.first_price_time,
        "last_price_time": member.last_price_time,
        "price_bar_count": member.price_bar_count,
        "coverage_payload": {
            "eligibility_status": member.eligibility_status,
            "skip_reason": member.skip_reason,
            "source": member.source,
        },
        "refreshed_at": refreshed_at,
    }


def upsert_summary_row(*, session, summary: dict) -> None:
    stmt = insert(models.SecurityAttributionSummary).values(**summary)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_security_attribution_summary_universe",
        set_={
            key: getattr(stmt.excluded, key)
            for key in summary
            if key != "security_attribution_summary_id"
        },
    )
    session.execute(stmt)


def latest_classification(*, session, security_id):
    return session.execute(
        select(models.SectorClassificationHistory)
        .where(models.SectorClassificationHistory.security_id == security_id)
        .order_by(
            models.SectorClassificationHistory.timestamp_available.desc(),
            models.SectorClassificationHistory.event_time.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def latest_daily_run(*, session, security_id):
    return session.execute(
        select(models.AttributionRun)
        .where(models.AttributionRun.security_id == security_id)
        .where(models.AttributionRun.cadence == "daily")
        .order_by(models.AttributionRun.window_end.desc(), models.AttributionRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def latest_adjusted_close(*, session, security_id, event_time: datetime, attribution_cutoff: datetime) -> float | None:
    value = session.execute(
        select(models.PriceBar.adjusted_close)
        .where(models.PriceBar.security_id == security_id)
        .where(models.PriceBar.event_time == event_time)
        .where(models.PriceBar.timestamp_available <= attribution_cutoff)
        .order_by(models.PriceBar.timestamp_available.desc(), models.PriceBar.source.asc())
        .limit(1)
    ).scalar_one_or_none()
    return float(value) if value is not None else None


def summary_count(*, session, universe_name: str, universe_version: str, status: str | None = None) -> int:
    stmt = (
        select(func.count(models.SecurityAttributionSummary.security_attribution_summary_id))
        .where(models.SecurityAttributionSummary.universe_name == universe_name)
        .where(models.SecurityAttributionSummary.universe_version == universe_version)
    )
    if status is not None:
        stmt = stmt.where(models.SecurityAttributionSummary.run_status == status)
    return int(session.execute(stmt).scalar_one())


if __name__ == "__main__":
    main()

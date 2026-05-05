from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from engine.events.features import EventFeature
from engine.exposures.update_policy import (
    MODEL_VERSION,
    ExposureUpdateDecision,
    decide_exposure_updates,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate conservative exposure update decisions")
    parser.add_argument("--ticker")
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    evaluated_at = datetime.now(timezone.utc)
    since = evaluated_at - timedelta(days=args.lookback_days)
    total = 0
    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        companies = load_companies(session=session, ticker=args.ticker)
        for company in companies:
            features, event_types = load_event_features(
                session=session,
                company_id=company.company_id,
                since=since,
                evaluated_at=evaluated_at,
            )
            decisions = decide_exposure_updates(
                company_id=company.company_id,
                event_features=features,
                event_types_by_id=event_types,
                evaluated_at=evaluated_at,
            )
            for decision in decisions:
                insert_decision(session=session, decision=decision)
                total += 1

    print(f"wrote {total} exposure update decision(s) with model {MODEL_VERSION}")


def load_companies(*, session, ticker: str | None) -> list[models.Company]:
    if ticker:
        company = session.execute(
            select(models.Company)
            .join(models.Security, models.Company.company_id == models.Security.company_id)
            .join(
                models.SecurityTickerHistory,
                models.Security.security_id == models.SecurityTickerHistory.security_id,
            )
            .where(models.SecurityTickerHistory.ticker == ticker.upper())
            .where(models.SecurityTickerHistory.active_to.is_(None))
        ).scalar_one_or_none()
        return [company] if company else []
    return list(session.execute(select(models.Company)).scalars())


def load_event_features(
    *,
    session,
    company_id: uuid.UUID,
    since: datetime,
    evaluated_at: datetime,
) -> tuple[list[EventFeature], dict[uuid.UUID, str]]:
    rows = list(
        session.execute(
            select(models.EventFeature, models.Event.event_type)
            .join(models.Event, models.EventFeature.event_id == models.Event.event_id)
            .where(models.EventFeature.company_id == company_id)
            .where(models.EventFeature.timestamp_available >= since)
            .where(models.EventFeature.timestamp_available <= evaluated_at)
        )
    )
    features = [
        EventFeature(
            event_id=row.EventFeature.event_id,
            company_id=row.EventFeature.company_id,
            security_id=row.EventFeature.security_id,
            event_time=row.EventFeature.event_time,
            ingestion_time=row.EventFeature.ingestion_time,
            timestamp_available=row.EventFeature.timestamp_available,
            relevance=float(row.EventFeature.relevance),
            novelty=float(row.EventFeature.novelty),
            sentiment=float(row.EventFeature.sentiment),
            magnitude=float(row.EventFeature.magnitude),
            source_credibility=float(row.EventFeature.source_credibility),
            exposure_match=float(row.EventFeature.exposure_match),
            surprise=float(row.EventFeature.surprise),
            evidence_span=row.EventFeature.evidence_span,
            model_version=row.EventFeature.model_version,
        )
        for row in rows
    ]
    event_types = {row.EventFeature.event_id: row.event_type for row in rows}
    return features, event_types


def insert_decision(*, session, decision: ExposureUpdateDecision) -> None:
    stmt = insert(models.ExposureUpdateDecision).values(
        exposure_update_decision_id=uuid.uuid4(),
        company_id=decision.company_id,
        exposure_name=decision.exposure_name,
        decision=decision.decision,
        review_required=decision.review_required,
        confidence=decision.confidence.value,
        rationale=decision.rationale,
        evidence_event_ids=[str(event_id) for event_id in decision.evidence_event_ids],
        model_version=decision.model_version,
        evaluated_at=decision.evaluated_at,
    )
    session.execute(stmt)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from engine.events.features import MODEL_VERSION, EventFeature, build_edgar_event_feature
from engine.events.taxonomy import classify_event
from jobs.run_attribution import upsert_event_taxonomy


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate structured event features")
    parser.add_argument("--source", default="sec_edgar")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        generated = generate_event_features_for_source(session=session, source=args.source)

    print(f"generated {generated} event features with model {MODEL_VERSION}")


def generate_event_features_for_source(*, session, source: str = "sec_edgar") -> int:
    generated = 0
    events = session.execute(
        select(models.Event)
        .where(models.Event.source == source)
        .order_by(models.Event.timestamp_available)
    ).scalars()
    for event in events:
        feature = build_edgar_event_feature(
            event_id=event.event_id,
            company_id=event.company_id,
            security_id=event.security_id,
            event_type=event.event_type,
            source=event.source,
            source_id=event.source_id,
            event_time=event.event_time,
            ingestion_time=datetime.now(timezone.utc),
            timestamp_available=event.timestamp_available,
        )
        upsert_event_feature(session=session, feature=feature)
        taxonomy = classify_event(
            event_id=event.event_id,
            event_type=event.event_type,
            structured_payload=event.structured_payload,
            event_time=event.event_time,
            ingestion_time=datetime.now(timezone.utc),
            timestamp_available=event.timestamp_available,
        )
        upsert_event_taxonomy(session=session, taxonomy=taxonomy)
        generated += 1
    return generated


def upsert_event_feature(*, session, feature: EventFeature) -> None:
    stmt = insert(models.EventFeature).values(
        event_feature_id=uuid.uuid4(),
        event_id=feature.event_id,
        company_id=feature.company_id,
        security_id=feature.security_id,
        relevance=feature.relevance,
        novelty=feature.novelty,
        sentiment=feature.sentiment,
        magnitude=feature.magnitude,
        source_credibility=feature.source_credibility,
        exposure_match=feature.exposure_match,
        surprise=feature.surprise,
        evidence_span=feature.evidence_span,
        model_version=feature.model_version,
        event_time=feature.event_time,
        ingestion_time=feature.ingestion_time,
        timestamp_available=feature.timestamp_available,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_event_feature_model",
        set_={
            "relevance": stmt.excluded.relevance,
            "novelty": stmt.excluded.novelty,
            "sentiment": stmt.excluded.sentiment,
            "magnitude": stmt.excluded.magnitude,
            "source_credibility": stmt.excluded.source_credibility,
            "exposure_match": stmt.excluded.exposure_match,
            "surprise": stmt.excluded.surprise,
            "evidence_span": stmt.excluded.evidence_span,
            "ingestion_time": stmt.excluded.ingestion_time,
            "timestamp_available": stmt.excluded.timestamp_available,
        },
    )
    session.execute(stmt)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from jobs.seed_mvp_universe import load_config, stable_uuid, find_security_id, _parse_datetime


DEFAULT_CONFIG = Path("config/mvp_universe.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MVP sector, peer, and exposure mappings")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    payload = load_config(Path(args.config))
    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        classifications, baskets, exposures = seed_mappings(session=session, payload=payload)

    print(
        "seeded MVP mappings "
        f"classifications={classifications} peer_baskets={baskets} exposures={exposures}"
    )


def seed_mappings(*, session, payload: dict) -> tuple[int, int, int]:
    active_from = _parse_datetime(payload["active_from"])
    available_at = _parse_datetime(payload["timestamp_available"])
    version = payload["version"]
    classifications = 0
    baskets = 0
    exposures = 0
    for item in payload["securities"]:
        security_id = find_security_id(session=session, ticker=item["ticker"])
        session.execute(
            insert(models.SectorClassificationHistory)
            .values(
                sector_classification_history_id=stable_uuid(f"classification:{version}:{item['ticker']}"),
                security_id=security_id,
                sector=item["sector"],
                industry=item["industry"],
                subindustry=item["subindustry"],
                classification_source=payload["source"],
                classification_version=version,
                event_time=active_from,
                ingestion_time=available_at,
                timestamp_available=available_at,
            )
            .on_conflict_do_update(
                constraint="uq_sector_classification_version_time",
                set_={
                    "sector": item["sector"],
                    "industry": item["industry"],
                    "subindustry": item["subindustry"],
                    "ingestion_time": available_at,
                    "timestamp_available": available_at,
                },
            )
        )
        classifications += 1

        basket_id = stable_uuid(f"peer-basket:{version}:{item['ticker']}")
        session.execute(
            insert(models.PeerBasket)
            .values(
                peer_basket_id=basket_id,
                target_security_id=security_id,
                basket_name="default_peer_basket",
                basket_version=version,
                source=payload["source"],
                description=f"Curated MVP peer basket for {item['ticker']}",
                active_from=active_from,
                active_to=None,
                event_time=active_from,
                ingestion_time=available_at,
                timestamp_available=available_at,
            )
            .on_conflict_do_update(
                constraint="uq_peer_basket_target_version",
                set_={
                    "description": f"Curated MVP peer basket for {item['ticker']}",
                    "ingestion_time": available_at,
                    "timestamp_available": available_at,
                },
            )
        )
        peer_tickers = []
        for peer in item["peers"]:
            if peer == item["ticker"]:
                continue
            try:
                find_security_id(session=session, ticker=peer)
            except RuntimeError:
                continue
            peer_tickers.append(peer)
        if not peer_tickers:
            continue
        weight = 1.0 / len(peer_tickers)
        for peer in peer_tickers:
            peer_security_id = find_security_id(session=session, ticker=peer)
            session.execute(
                insert(models.PeerBasketMember)
                .values(
                    peer_basket_member_id=stable_uuid(f"peer-member:{version}:{item['ticker']}:{peer}"),
                    peer_basket_id=basket_id,
                    peer_security_id=peer_security_id,
                    weight=weight,
                    active_from=active_from,
                    active_to=None,
                    event_time=active_from,
                    ingestion_time=available_at,
                    timestamp_available=available_at,
                )
                .on_conflict_do_update(
                    constraint="uq_peer_basket_member",
                    set_={
                        "weight": weight,
                        "ingestion_time": available_at,
                        "timestamp_available": available_at,
                    },
                )
            )
        baskets += 1

        company_id = session.execute(
            select(models.Security.company_id).where(models.Security.security_id == security_id)
        ).scalar_one()
        for exposure_name, exposure_value in item.get("exposures", {}).items():
            session.execute(
                insert(models.CompanyExposure)
                .values(
                    company_exposure_id=stable_uuid(f"exposure:{version}:{item['ticker']}:{exposure_name}"),
                    company_id=company_id,
                    exposure_name=exposure_name,
                    exposure_value=float(exposure_value),
                    exposure_type="mvp_curated_gate",
                    exposure_bucket=_bucket(float(exposure_value)),
                    exposure_sign="positive",
                    source_span=f"config/mvp_universe.json:{item['ticker']}:{exposure_name}",
                    review_status="curated_seed",
                    exposure_version=version,
                    confidence="Medium",
                    evidence_event_id=None,
                    model_version="mvp-curated-exposure-v0",
                    event_time=active_from,
                    ingestion_time=available_at,
                    timestamp_available=available_at,
                )
                .on_conflict_do_nothing(index_elements=["company_exposure_id"])
            )
            exposures += 1
    session.flush()
    return classifications, baskets, exposures


def _bucket(value: float) -> str:
    if value <= 0:
        return "none"
    if value < 0.35:
        return "low"
    if value < 0.65:
        return "medium"
    if value < 0.90:
        return "high"
    return "critical"


if __name__ == "__main__":
    main()

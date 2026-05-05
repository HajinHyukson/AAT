from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from jobs.faustcalc_common import (
    DEFAULT_FAUSTCALC_UNIVERSE_NAME,
    DEFAULT_FAUSTCALC_UNIVERSE_VERSION,
    FAUSTCALC_AUTO_MAPPING_SOURCE,
    FAUSTCALC_AUTO_MAPPING_VERSION,
    stable_uuid,
)


AUTO_EXPOSURE_MODEL_VERSION = "faustcalc-auto-exposure-v0"


@dataclass(frozen=True)
class MappingCandidate:
    security_id: UUID
    company_id: UUID
    ticker: str
    sector: str | None
    industry: str | None
    first_price_time: datetime | None
    price_bar_count: int


@dataclass
class AutoMappingReport:
    universe_name: str
    universe_version: str
    candidates: int = 0
    classifications: int = 0
    peer_baskets: int = 0
    peer_members: int = 0
    exposures: int = 0

    def render(self) -> str:
        return (
            "seeded FaustCalc auto mappings "
            f"universe={self.universe_name} version={self.universe_version} "
            f"candidates={self.candidates} classifications={self.classifications} "
            f"peer_baskets={self.peer_baskets} peer_members={self.peer_members} "
            f"exposures={self.exposures}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed generated mappings for the FaustCalc universe")
    parser.add_argument("--universe-name", default=DEFAULT_FAUSTCALC_UNIVERSE_NAME)
    parser.add_argument("--universe-version", default=DEFAULT_FAUSTCALC_UNIVERSE_VERSION)
    parser.add_argument("--max-peers", type=int, default=20)
    parser.add_argument("--min-peers", type=int, default=3)
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        report = seed_faustcalc_auto_mappings(
            session=session,
            universe_name=args.universe_name,
            universe_version=args.universe_version,
            max_peers=args.max_peers,
            min_peers=args.min_peers,
        )
    print(report.render())


def seed_faustcalc_auto_mappings(
    *,
    session,
    universe_name: str = DEFAULT_FAUSTCALC_UNIVERSE_NAME,
    universe_version: str = DEFAULT_FAUSTCALC_UNIVERSE_VERSION,
    max_peers: int = 20,
    min_peers: int = 3,
) -> AutoMappingReport:
    report = AutoMappingReport(universe_name=universe_name, universe_version=universe_version)
    candidates = load_mapping_candidates(
        session=session,
        universe_name=universe_name,
        universe_version=universe_version,
    )
    report.candidates = len(candidates)
    now = datetime.now(timezone.utc)

    existing_classifications = set(
        session.execute(select(models.SectorClassificationHistory.security_id)).scalars()
    )
    curated_peer_targets = set(
        session.execute(
            select(models.PeerBasket.target_security_id).where(
                models.PeerBasket.source != FAUSTCALC_AUTO_MAPPING_SOURCE
            )
        ).scalars()
    )
    curated_exposures = {
        (row.company_id, row.exposure_name)
        for row in session.execute(
            select(models.CompanyExposure.company_id, models.CompanyExposure.exposure_name).where(
                models.CompanyExposure.model_version != AUTO_EXPOSURE_MODEL_VERSION
            )
        ).all()
    }

    for candidate in candidates:
        if candidate.security_id not in existing_classifications and candidate.sector:
            upsert_classification(session=session, candidate=candidate, now=now)
            report.classifications += 1

        if candidate.company_id is not None:
            for exposure_name, exposure_value in macro_exposure_gates(
                sector=candidate.sector,
                industry=candidate.industry,
            ).items():
                if (candidate.company_id, exposure_name) in curated_exposures:
                    continue
                upsert_company_exposure(
                    session=session,
                    candidate=candidate,
                    exposure_name=exposure_name,
                    exposure_value=exposure_value,
                    now=now,
                )
                report.exposures += 1

    peers_by_security = build_peer_candidates(
        candidates=candidates,
        max_peers=max_peers,
        min_peers=min_peers,
    )
    peer_basket_rows = []
    peer_member_rows = []
    for candidate in candidates:
        if candidate.security_id in curated_peer_targets:
            continue
        peers = peers_by_security.get(candidate.security_id, [])
        if len(peers) < min_peers:
            continue
        basket_id = stable_uuid(f"peer-basket:{FAUSTCALC_AUTO_MAPPING_VERSION}:{candidate.ticker}")
        peer_basket_rows.append(peer_basket_values(candidate=candidate, basket_id=basket_id, now=now))
        report.peer_baskets += 1
        weight = 1.0 / len(peers)
        for peer in peers:
            peer_member_rows.append(peer_member_values(
                target=candidate,
                peer=peer,
                basket_id=basket_id,
                weight=weight,
                now=now,
            ))
            report.peer_members += 1
    bulk_upsert_peer_baskets(session=session, rows=peer_basket_rows)
    bulk_upsert_peer_members(session=session, rows=peer_member_rows)

    session.flush()
    return report


def load_mapping_candidates(*, session, universe_name: str, universe_version: str) -> list[MappingCandidate]:
    rows = session.execute(
        select(
            models.ModelUniverseMember.security_id,
            models.Security.company_id,
            models.ModelUniverseMember.ticker,
            models.FaustcalcCompany.sector,
            models.FaustcalcCompany.industry,
            models.ModelUniverseMember.first_price_time,
            models.ModelUniverseMember.price_bar_count,
        )
        .join(models.Security, models.Security.security_id == models.ModelUniverseMember.security_id)
        .outerjoin(
            models.FaustcalcCompany,
            models.FaustcalcCompany.canonical_ticker == models.ModelUniverseMember.ticker,
        )
        .where(models.ModelUniverseMember.universe_name == universe_name)
        .where(models.ModelUniverseMember.universe_version == universe_version)
        .where(models.ModelUniverseMember.eligibility_status == "eligible")
        .where(models.ModelUniverseMember.active_to.is_(None))
        .order_by(models.ModelUniverseMember.ticker)
    ).all()
    return [
        MappingCandidate(
            security_id=row.security_id,
            company_id=row.company_id,
            ticker=row.ticker,
            sector=clean_label(row.sector),
            industry=clean_label(row.industry),
            first_price_time=row.first_price_time,
            price_bar_count=int(row.price_bar_count or 0),
        )
        for row in rows
    ]


def clean_label(value: str | None) -> str | None:
    if value is None:
        return None
    label = " ".join(str(value).strip().split())
    return label or None


def upsert_classification(*, session, candidate: MappingCandidate, now: datetime) -> None:
    event_time = candidate.first_price_time or now
    stmt = insert(models.SectorClassificationHistory).values(
        sector_classification_history_id=stable_uuid(
            f"classification:{FAUSTCALC_AUTO_MAPPING_VERSION}:{candidate.ticker}"
        ),
        security_id=candidate.security_id,
        sector=candidate.sector,
        industry=candidate.industry,
        subindustry=None,
        classification_source=FAUSTCALC_AUTO_MAPPING_SOURCE,
        classification_version=FAUSTCALC_AUTO_MAPPING_VERSION,
        event_time=event_time,
        ingestion_time=now,
        timestamp_available=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_sector_classification_version_time",
        set_={
            "sector": stmt.excluded.sector,
            "industry": stmt.excluded.industry,
            "ingestion_time": now,
            "timestamp_available": now,
        },
    )
    session.execute(stmt)


def build_peer_candidates(
    *,
    candidates: list[MappingCandidate],
    max_peers: int,
    min_peers: int,
) -> dict[UUID, list[MappingCandidate]]:
    by_industry: dict[str, list[MappingCandidate]] = {}
    by_sector: dict[str, list[MappingCandidate]] = {}
    for candidate in candidates:
        if candidate.industry:
            by_industry.setdefault(candidate.industry, []).append(candidate)
        if candidate.sector:
            by_sector.setdefault(candidate.sector, []).append(candidate)

    result: dict[UUID, list[MappingCandidate]] = {}
    for target in candidates:
        pool = []
        if target.industry:
            pool = [item for item in by_industry.get(target.industry, []) if item.security_id != target.security_id]
        if len(pool) < min_peers and target.sector:
            pool = [item for item in by_sector.get(target.sector, []) if item.security_id != target.security_id]
        ranked = sorted(pool, key=lambda item: (-item.price_bar_count, item.ticker))
        result[target.security_id] = ranked[:max_peers]
    return result


def upsert_peer_basket(*, session, candidate: MappingCandidate, now: datetime) -> UUID:
    basket_id = stable_uuid(f"peer-basket:{FAUSTCALC_AUTO_MAPPING_VERSION}:{candidate.ticker}")
    stmt = insert(models.PeerBasket).values(peer_basket_values(candidate=candidate, basket_id=basket_id, now=now))
    stmt = stmt.on_conflict_do_update(
        constraint="uq_peer_basket_target_version",
        set_={
            "description": stmt.excluded.description,
            "ingestion_time": stmt.excluded.ingestion_time,
            "timestamp_available": stmt.excluded.timestamp_available,
            "active_to": None,
        },
    )
    session.execute(stmt)
    return basket_id


def peer_basket_values(*, candidate: MappingCandidate, basket_id: UUID, now: datetime) -> dict:
    return {
        "peer_basket_id": basket_id,
        "target_security_id": candidate.security_id,
        "basket_name": "default_peer_basket",
        "basket_version": FAUSTCALC_AUTO_MAPPING_VERSION,
        "source": FAUSTCALC_AUTO_MAPPING_SOURCE,
        "description": f"Generated FaustCalc peer basket for {candidate.ticker}",
        "active_from": candidate.first_price_time or now,
        "active_to": None,
        "event_time": candidate.first_price_time or now,
        "ingestion_time": now,
        "timestamp_available": now,
    }


def bulk_upsert_peer_baskets(*, session, rows: list[dict]) -> None:
    for chunk in chunked(rows, 1_000):
        stmt = insert(models.PeerBasket).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_peer_basket_target_version",
            set_={
                "description": stmt.excluded.description,
                "ingestion_time": stmt.excluded.ingestion_time,
                "timestamp_available": stmt.excluded.timestamp_available,
                "active_to": None,
            },
        )
        session.execute(stmt)


def upsert_peer_member(
    *,
    session,
    target: MappingCandidate,
    peer: MappingCandidate,
    basket_id: UUID,
    weight: float,
    now: datetime,
) -> None:
    stmt = insert(models.PeerBasketMember).values(
        peer_member_values(target=target, peer=peer, basket_id=basket_id, weight=weight, now=now)
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_peer_basket_member",
        set_={
            "weight": stmt.excluded.weight,
            "active_to": None,
            "ingestion_time": stmt.excluded.ingestion_time,
            "timestamp_available": stmt.excluded.timestamp_available,
        },
    )
    session.execute(stmt)


def peer_member_values(
    *,
    target: MappingCandidate,
    peer: MappingCandidate,
    basket_id: UUID,
    weight: float,
    now: datetime,
) -> dict:
    return {
        "peer_basket_member_id": stable_uuid(
            f"peer-member:{FAUSTCALC_AUTO_MAPPING_VERSION}:{target.ticker}:{peer.ticker}"
        ),
        "peer_basket_id": basket_id,
        "peer_security_id": peer.security_id,
        "weight": weight,
        "active_from": target.first_price_time or now,
        "active_to": None,
        "event_time": target.first_price_time or now,
        "ingestion_time": now,
        "timestamp_available": now,
    }


def bulk_upsert_peer_members(*, session, rows: list[dict]) -> None:
    for chunk in chunked(rows, 5_000):
        stmt = insert(models.PeerBasketMember).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_peer_basket_member",
            set_={
                "weight": stmt.excluded.weight,
                "active_to": None,
                "ingestion_time": stmt.excluded.ingestion_time,
                "timestamp_available": stmt.excluded.timestamp_available,
            },
        )
        session.execute(stmt)


def macro_exposure_gates(*, sector: str | None, industry: str | None) -> dict[str, float]:
    text = f"{sector or ''} {industry or ''}".lower()
    rates = 0.65
    credit = 0.65
    inflation = 0.50
    if any(token in text for token in ["financial", "bank", "mortgage", "insurance", "real estate", "utility"]):
        rates = 0.90
        credit = 0.85
    if any(token in text for token in ["consumer discretionary", "retail", "auto", "airline", "hotel"]):
        rates = max(rates, 0.80)
        credit = max(credit, 0.75)
    if any(token in text for token in ["energy", "oil", "gas", "materials", "metals", "chemical"]):
        inflation = 0.85
        credit = max(credit, 0.75)
    if any(token in text for token in ["technology", "software", "semiconductor", "communication"]):
        credit = min(credit, 0.55)
    if any(token in text for token in ["health care", "pharmaceutical", "biotechnology"]):
        rates = min(rates, 0.55)
        credit = min(credit, 0.55)
    return {"rates": rates, "credit": credit, "inflation": inflation}


def upsert_company_exposure(
    *,
    session,
    candidate: MappingCandidate,
    exposure_name: str,
    exposure_value: float,
    now: datetime,
) -> None:
    stmt = insert(models.CompanyExposure).values(
        company_exposure_id=stable_uuid(
            f"exposure:{FAUSTCALC_AUTO_MAPPING_VERSION}:{candidate.company_id}:{exposure_name}"
        ),
        company_id=candidate.company_id,
        exposure_name=exposure_name,
        exposure_value=exposure_value,
        exposure_type="faustcalc_generated_macro_gate",
        exposure_bucket=bucket(exposure_value),
        exposure_sign="positive",
        source_span=f"{candidate.ticker}:{candidate.sector or 'Unknown'}:{candidate.industry or 'Unknown'}",
        review_status="generated_seed",
        exposure_version=FAUSTCALC_AUTO_MAPPING_VERSION,
        confidence="Low-Medium",
        evidence_event_id=None,
        model_version=AUTO_EXPOSURE_MODEL_VERSION,
        event_time=candidate.first_price_time or now,
        ingestion_time=now,
        timestamp_available=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["company_exposure_id"],
        set_={
            "exposure_value": exposure_value,
            "exposure_bucket": bucket(exposure_value),
            "source_span": stmt.excluded.source_span,
            "ingestion_time": now,
            "timestamp_available": now,
        },
    )
    session.execute(stmt)


def bucket(value: float) -> str:
    if value <= 0:
        return "none"
    if value < 0.35:
        return "low"
    if value < 0.65:
        return "medium"
    if value < 0.90:
        return "high"
    return "critical"


def chunked(rows: list[dict], size: int):
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


if __name__ == "__main__":
    main()

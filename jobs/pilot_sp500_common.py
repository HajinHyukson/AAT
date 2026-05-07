from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from db import models


PILOT_DATABASE_NAME = "aat_pilot_sp500"
PILOT_UNIVERSE_NAME = "pilot_sp500_static"
PILOT_DATA_VERSION_PREFIX = "pilot_fresh_vendor"
PILOT_MAPPING_SOURCE = "pilot_sp500_static_config"
PILOT_MAPPING_VERSION = "sp500_static_mapping_v0"
PILOT_PEER_BASKET_NAME = "pilot_peer_basket"
PILOT_PEER_BASKET_VERSION = "sp500_static_peer_v0"
PILOT_EXPOSURE_MODEL_VERSION = "pilot-sp500-exposure-v0"
DEFAULT_CONFIG = Path("config/pilot_sp500_universe.json")
NAMESPACE = uuid.UUID("b2d5b7ec-6c84-44d4-b46f-e9a0b4a9647f")


@dataclass(frozen=True)
class PilotSecurity:
    ticker: str
    name: str
    cik: str | None
    exchange: str
    sector: str
    industry: str
    subindustry: str
    vendor_aliases: tuple[str, ...]
    payload: dict


def stable_uuid(value: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, value)


def load_pilot_universe_config(path: Path = DEFAULT_CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pilot_securities(payload: dict) -> list[PilotSecurity]:
    rows = []
    for item in payload["securities"]:
        ticker = normalize_ticker(item["ticker"])
        rows.append(
            PilotSecurity(
                ticker=ticker,
                name=str(item["name"]),
                cik=normalize_cik(item.get("cik")),
                exchange=str(item.get("exchange") or "UNKNOWN"),
                sector=clean_label(item.get("sector")) or "Unknown",
                industry=clean_label(item.get("industry")) or "Unknown",
                subindustry=clean_label(item.get("subindustry")) or clean_label(item.get("industry")) or "Unknown",
                vendor_aliases=tuple(normalize_ticker(alias) for alias in item.get("vendor_aliases", [])),
                payload=item,
            )
        )
    return rows


def normalize_ticker(value: str) -> str:
    return " ".join(str(value).strip().upper().split())


def normalize_cik(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits.zfill(10) if digits else None


def clean_label(value: str | None) -> str | None:
    if value is None:
        return None
    label = " ".join(str(value).strip().split())
    return label or None


def ticker_fetch_attempts(security: PilotSecurity | str) -> tuple[str, ...]:
    if isinstance(security, str):
        ticker = normalize_ticker(security)
        aliases = generated_vendor_aliases(ticker)
    else:
        ticker = security.ticker
        aliases = (*security.vendor_aliases, *generated_vendor_aliases(security.ticker))
    ordered = []
    for item in (ticker, *aliases):
        if item and item not in ordered:
            ordered.append(item)
    return tuple(ordered)


def generated_vendor_aliases(ticker: str) -> tuple[str, ...]:
    if "." not in ticker:
        return ()
    return (ticker.replace(".", "-"), ticker.replace(".", "/"))


def pilot_database_url(*, database_name: str = PILOT_DATABASE_NAME) -> str:
    user = os.getenv("POSTGRES_USER", "attribution")
    password = quote(os.getenv("POSTGRES_PASSWORD", "attribution"), safe="")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_HOST_PORT", "55432")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database_name}"


def assert_pilot_database_url(database_url: str | None = None) -> None:
    raw_url = database_url or os.getenv("DATABASE_URL") or ""
    parsed = urlparse(raw_url)
    database_name = parsed.path.lstrip("/")
    if database_name != PILOT_DATABASE_NAME:
        raise RuntimeError(
            "pilot jobs must target the local aat_pilot_sp500 database; "
            f"got database={database_name or '<missing>'}"
        )


def ensure_pilot_database_url(database_url: str | None = None) -> str:
    raw_url = database_url or os.getenv("DATABASE_URL")
    if not raw_url:
        raw_url = pilot_database_url()
        os.environ["DATABASE_URL"] = raw_url
    assert_pilot_database_url(raw_url)
    return raw_url


def safe_database_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"unsafe database identifier {value!r}")
    return value


def seed_pilot_universe(*, session, payload: dict) -> int:
    securities = pilot_securities(payload)
    active_from = parse_datetime(payload["active_from"])
    available_at = parse_datetime(payload["timestamp_available"])
    version = str(payload["version"])
    now = datetime.now(timezone.utc)
    security_ids_by_ticker: dict[str, uuid.UUID] = {}

    for item in securities:
        company_id = stable_uuid(f"company:{item.cik or item.ticker}")
        if item.cik:
            existing_company_id = session.execute(
                select(models.Company.company_id).where(models.Company.cik == item.cik)
            ).scalar_one_or_none()
            company_id = existing_company_id or company_id
        session.execute(
            insert(models.Company)
            .values(
                company_id=company_id,
                cik=item.cik,
                legal_name=item.name,
                created_at=available_at,
            )
            .on_conflict_do_update(
                index_elements=["company_id"],
                set_={"legal_name": item.name},
            )
        )

        security_id = stable_uuid(f"security:{item.ticker}")
        security_ids_by_ticker[item.ticker] = security_id
        session.execute(
            insert(models.Security)
            .values(
                security_id=security_id,
                company_id=company_id,
                figi=None,
                isin=None,
                cusip=None,
                exchange=item.exchange,
                share_class=share_class_from_ticker(item.ticker),
                active_from=active_from,
                active_to=None,
            )
            .on_conflict_do_update(
                index_elements=["security_id"],
                set_={"exchange": item.exchange, "active_to": None},
            )
        )
        session.execute(
            insert(models.SecurityTickerHistory)
            .values(
                ticker_history_id=stable_uuid(f"ticker:{item.ticker}:current"),
                security_id=security_id,
                ticker=item.ticker,
                active_from=active_from,
                active_to=None,
            )
            .on_conflict_do_nothing(constraint="uq_ticker_history")
        )
        member_payload = {
            "source_url": payload.get("source_url"),
            "retrieved_at": payload.get("retrieved_at"),
            "vendor_aliases": list(item.vendor_aliases),
        }
        stmt = insert(models.ModelUniverseMember).values(
            model_universe_member_id=stable_uuid(f"member:{PILOT_UNIVERSE_NAME}:{version}:{item.ticker}"),
            universe_name=PILOT_UNIVERSE_NAME,
            universe_version=version,
            security_id=security_id,
            ticker=item.ticker,
            source=payload["source"],
            source_asset_id=None,
            eligibility_status="eligible",
            first_price_time=None,
            last_price_time=None,
            price_bar_count=0,
            active_from=active_from,
            active_to=None,
            skip_reason=None,
            member_payload=member_payload,
            created_at=now,
            updated_at=now,
        )
        session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_model_universe_member_security",
                set_={
                    "ticker": stmt.excluded.ticker,
                    "eligibility_status": stmt.excluded.eligibility_status,
                    "active_to": None,
                    "skip_reason": None,
                    "metadata": stmt.excluded.metadata,
                    "updated_at": now,
                },
            )
        )
        seed_classification(session=session, item=item, security_id=security_id, active_from=active_from, now=now)
        seed_company_exposures(session=session, item=item, company_id=company_id, active_from=active_from, now=now)

    seed_peer_baskets(
        session=session,
        securities=securities,
        security_ids_by_ticker=security_ids_by_ticker,
        active_from=active_from,
        now=now,
    )
    session.flush()
    return len(securities)


def share_class_from_ticker(ticker: str) -> str | None:
    return ticker.split(".", 1)[1] if "." in ticker else None


def seed_classification(
    *,
    session,
    item: PilotSecurity,
    security_id: uuid.UUID,
    active_from: datetime,
    now: datetime,
) -> None:
    stmt = insert(models.SectorClassificationHistory).values(
        sector_classification_history_id=stable_uuid(f"classification:{PILOT_MAPPING_VERSION}:{item.ticker}"),
        security_id=security_id,
        sector=item.sector,
        industry=item.industry,
        subindustry=item.subindustry,
        classification_source=PILOT_MAPPING_SOURCE,
        classification_version=PILOT_MAPPING_VERSION,
        event_time=active_from,
        ingestion_time=now,
        timestamp_available=now,
    )
    session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_sector_classification_version_time",
            set_={
                "sector": item.sector,
                "industry": item.industry,
                "subindustry": item.subindustry,
                "ingestion_time": now,
                "timestamp_available": now,
            },
        )
    )


def seed_peer_baskets(
    *,
    session,
    securities: list[PilotSecurity],
    security_ids_by_ticker: dict[str, uuid.UUID],
    active_from: datetime,
    now: datetime,
    max_peers: int = 20,
    min_peers: int = 3,
) -> None:
    for target in securities:
        peers = peer_candidates(target=target, securities=securities, max_peers=max_peers)
        if len(peers) < min_peers:
            continue
        basket_id = stable_uuid(f"peer-basket:{PILOT_PEER_BASKET_VERSION}:{target.ticker}")
        stmt = insert(models.PeerBasket).values(
            peer_basket_id=basket_id,
            target_security_id=security_ids_by_ticker[target.ticker],
            basket_name=PILOT_PEER_BASKET_NAME,
            basket_version=PILOT_PEER_BASKET_VERSION,
            source=PILOT_MAPPING_SOURCE,
            description=f"Static S&P 500 pilot peer basket for {target.ticker}",
            active_from=active_from,
            active_to=None,
            event_time=active_from,
            ingestion_time=now,
            timestamp_available=now,
        )
        session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_peer_basket_target_version",
                set_={"description": stmt.excluded.description, "timestamp_available": now},
            )
        )
        weight = 1.0 / len(peers)
        for peer in peers:
            member_stmt = insert(models.PeerBasketMember).values(
                peer_basket_member_id=stable_uuid(
                    f"peer-member:{PILOT_PEER_BASKET_VERSION}:{target.ticker}:{peer.ticker}"
                ),
                peer_basket_id=basket_id,
                peer_security_id=security_ids_by_ticker[peer.ticker],
                weight=weight,
                active_from=active_from,
                active_to=None,
                event_time=active_from,
                ingestion_time=now,
                timestamp_available=now,
            )
            session.execute(
                member_stmt.on_conflict_do_update(
                    constraint="uq_peer_basket_member",
                    set_={"weight": weight, "timestamp_available": now},
                )
            )


def peer_candidates(*, target: PilotSecurity, securities: list[PilotSecurity], max_peers: int) -> list[PilotSecurity]:
    same_subindustry = [
        item for item in securities if item.ticker != target.ticker and item.subindustry == target.subindustry
    ]
    same_sector = [
        item
        for item in securities
        if item.ticker != target.ticker
        and item.sector == target.sector
        and item not in same_subindustry
    ]
    ranked = [*sorted(same_subindustry, key=lambda item: item.ticker), *sorted(same_sector, key=lambda item: item.ticker)]
    return ranked[:max_peers]


def seed_company_exposures(
    *,
    session,
    item: PilotSecurity,
    company_id: uuid.UUID,
    active_from: datetime,
    now: datetime,
) -> None:
    for exposure_name, exposure_value in heuristic_exposures(item).items():
        stmt = insert(models.CompanyExposure).values(
            company_exposure_id=stable_uuid(f"exposure:{PILOT_EXPOSURE_MODEL_VERSION}:{item.ticker}:{exposure_name}"),
            company_id=company_id,
            exposure_name=exposure_name,
            exposure_value=exposure_value,
            exposure_type="pilot_sector_heuristic",
            exposure_bucket=exposure_bucket(exposure_value),
            exposure_sign="positive",
            source_span=f"{DEFAULT_CONFIG}:{item.ticker}:{exposure_name}",
            review_status="pilot_generated",
            exposure_version=PILOT_MAPPING_VERSION,
            confidence="Medium",
            evidence_event_id=None,
            model_version=PILOT_EXPOSURE_MODEL_VERSION,
            event_time=active_from,
            ingestion_time=now,
            timestamp_available=now,
        )
        session.execute(stmt.on_conflict_do_nothing(index_elements=["company_exposure_id"]))


def heuristic_exposures(item: PilotSecurity) -> dict[str, float]:
    sector = item.sector
    industry = item.industry
    exposures = {"rates": 0.5, "credit": 0.35, "inflation": 0.35}
    if sector in {"Financials", "Real Estate", "Utilities"}:
        exposures.update({"rates": 0.85, "credit": 0.75})
    if sector == "Energy":
        exposures.update({"wti": 0.9, "natural_gas": 0.6, "credit": 0.5})
    if sector in {"Consumer Staples", "Consumer Discretionary", "Materials"}:
        exposures.update({"inflation": 0.65})
    if "Bank" in industry or "Financial" in industry:
        exposures.update({"rates": 0.9, "credit": 0.9})
    return exposures


def exposure_bucket(value: float) -> str:
    if value <= 0:
        return "none"
    if value < 0.35:
        return "low"
    if value < 0.65:
        return "medium"
    if value < 0.9:
        return "high"
    return "critical"


def refresh_pilot_universe_price_coverage(*, session, universe_version: str) -> int:
    rows = session.execute(
        select(
            models.ModelUniverseMember.model_universe_member_id,
            func.min(models.PriceBar.event_time),
            func.max(models.PriceBar.event_time),
            func.count(models.PriceBar.price_bar_id),
        )
        .outerjoin(models.PriceBar, models.PriceBar.security_id == models.ModelUniverseMember.security_id)
        .where(models.ModelUniverseMember.universe_name == PILOT_UNIVERSE_NAME)
        .where(models.ModelUniverseMember.universe_version == universe_version)
        .group_by(models.ModelUniverseMember.model_universe_member_id)
    ).all()
    now = datetime.now(timezone.utc)
    for member_id, first_price, last_price, count in rows:
        member = session.get(models.ModelUniverseMember, member_id)
        member.first_price_time = first_price
        member.last_price_time = last_price
        member.price_bar_count = int(count or 0)
        member.eligibility_status = "eligible" if count else "missing_prices"
        member.skip_reason = None if count else "missing_price_bars"
        member.updated_at = now
    session.flush()
    return len(rows)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

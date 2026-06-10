"""Shared constants and helpers for the local KOSPI pilot track.

The KOSPI pilot mirrors the S&P 500 pilot: a separate local database
(`aat_pilot_kospi`) populated from the Acquin Railway snapshot, used for
methodology research without touching the server database.

See docs/ACQUIN_KOSPI_ADAPTER_DESIGN.md for the full design, including the
vintage policy and continuity guard implemented here.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from db import models


PILOT_KOSPI_DATABASE_NAME = "aat_pilot_kospi"
PILOT_KOSPI_UNIVERSE_NAME = "pilot_kospi_static"
PILOT_KOSPI_UNIVERSE_SOURCE = "acquin_railway_dim_stock_snapshot"
ACQUIN_PRICE_SOURCE = "acquin_pykrx"
KOSPI_MARKET_FACTOR_NAME = "kospi_market"
KOSPI_MARKET_FACTOR_FAMILY = "market_proxy"
KOSPI_INDEX_CODE = "1001"
DEFAULT_KOSPI_CONFIG = Path("config/pilot_kospi_universe.json")
NAMESPACE = uuid.UUID("7e0a3a9b-94c4-4b86-9c25-1f1f6dbd2f3a")

# KRX cash equities close at 15:30 KST (06:30 UTC).
KRX_CLOSE_UTC = time(6, 30)

# Acquin's bulk backfill wrote rows on 2026-06-01/02; per-day ingestion with
# honest created_at timestamps starts 2026-06-05. Rows created before this
# boundary get a conservative trade-date+1 availability.
ACQUIN_BULK_BACKFILL_BOUNDARY = datetime(2026, 6, 3, tzinfo=timezone.utc)

# Absolute one-day adjusted-close move that flags a continuity suspect
# (likely an unadjusted post-backfill corporate action). KRX daily price
# limits are +/-30%, so legitimate moves stay below this threshold.
CONTINUITY_GUARD_MAX_ABS_RETURN = 0.40

ISSUE_TYPE_CONTINUITY = "continuity_suspect"
ISSUE_TYPE_INVALID_CLOSE = "invalid_close"


def stable_uuid(value: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, value)


def normalize_kospi_ticker(value: str) -> str:
    """KRX codes are opaque strings (e.g. '005930', '33637L'); never reformat."""
    return str(value).strip().upper()


def pilot_kospi_database_url(*, database_name: str = PILOT_KOSPI_DATABASE_NAME) -> str:
    user = os.getenv("POSTGRES_USER", "attribution")
    password = quote(os.getenv("POSTGRES_PASSWORD", "attribution"), safe="")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_HOST_PORT", "55432")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database_name}"


def assert_pilot_kospi_database_url(database_url: str | None = None) -> None:
    raw_url = database_url or os.getenv("DATABASE_URL") or ""
    parsed = urlparse(raw_url)
    database_name = parsed.path.lstrip("/")
    if database_name != PILOT_KOSPI_DATABASE_NAME:
        raise RuntimeError(
            "KOSPI pilot jobs must target the local aat_pilot_kospi database; "
            f"got database={database_name or '<missing>'}"
        )


def ensure_pilot_kospi_database_url(database_url: str | None = None) -> str:
    raw_url = database_url or os.getenv("DATABASE_URL")
    if not raw_url:
        raw_url = pilot_kospi_database_url()
        os.environ["DATABASE_URL"] = raw_url
    assert_pilot_kospi_database_url(raw_url)
    return raw_url


@dataclass(frozen=True)
class VintageStamps:
    event_time: datetime
    ingestion_time: datetime
    timestamp_available: datetime


def acquin_vintage_stamps(
    *,
    trade_date: date,
    source_created_at: datetime | None,
    fallback_ingestion_time: datetime,
) -> VintageStamps:
    """Point-in-time stamps for an Acquin source row.

    Backfilled rows (written during the 2026-06-01/02 bulk load, or with no
    source timestamp) cannot prove when their values were truly publishable,
    so availability is pushed to the day after the trade date. Live rows use
    their real post-close ingestion timestamp.
    """
    event_time = datetime.combine(trade_date, KRX_CLOSE_UTC, tzinfo=timezone.utc)
    created_at = _coerce_utc(source_created_at)
    ingestion_time = created_at or fallback_ingestion_time
    if created_at is None or created_at < ACQUIN_BULK_BACKFILL_BOUNDARY:
        timestamp_available = datetime.combine(
            trade_date + timedelta(days=1), time.min, tzinfo=timezone.utc
        )
    else:
        timestamp_available = max(created_at, event_time)
    return VintageStamps(
        event_time=event_time,
        ingestion_time=ingestion_time,
        timestamp_available=timestamp_available,
    )


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ContinuityVerdict:
    promotable: list  # rows accepted for promotion
    suspect_key: str | None  # "ticker:date" of the first unresolved suspect
    suspect_return: float | None
    quarantined_count: int


def apply_continuity_guard(
    *,
    ticker: str,
    rows: list,
    resolved_keys: set[str],
    max_abs_return: float = CONTINUITY_GUARD_MAX_ABS_RETURN,
) -> ContinuityVerdict:
    """Walk date-ordered price rows; stop at the first unresolved extreme move.

    ``rows`` must be ordered by date, contain only valid positive closes
    (invalid rows are rejected by the caller before the guard runs), and
    expose ``price_date`` and ``adj_close``. A move whose absolute
    close-to-close return exceeds ``max_abs_return`` is a continuity suspect
    (likely an unadjusted corporate action): that bar and every later bar are
    withheld from promotion until the matching validation issue is resolved.
    Resolved suspects (key ``ticker:date``) pass through.
    """
    promotable = []
    previous_close: float | None = None
    for index, row in enumerate(rows):
        close = row.adj_close
        if previous_close is not None:
            one_day_return = close / previous_close - 1.0
            key = continuity_issue_key(ticker=ticker, trade_date=row.price_date)
            if abs(one_day_return) > max_abs_return and key not in resolved_keys:
                return ContinuityVerdict(
                    promotable=promotable,
                    suspect_key=key,
                    suspect_return=one_day_return,
                    quarantined_count=len(rows) - index,
                )
        promotable.append(row)
        previous_close = close
    return ContinuityVerdict(
        promotable=promotable,
        suspect_key=None,
        suspect_return=None,
        quarantined_count=0,
    )


def continuity_issue_key(*, ticker: str, trade_date: date) -> str:
    return f"{ticker}:{trade_date.isoformat()}"


def build_kospi_universe_payload(
    *,
    stocks: list,
    retrieved_at: datetime,
    version: str | None = None,
) -> dict:
    """Build the pilot universe config payload from staged Acquin stock rows.

    ``stocks`` rows must expose ``ticker``, ``market``, ``is_preferred`` and
    ``is_active``. Inactive rows are excluded.
    """
    snapshot_date = retrieved_at.date().isoformat().replace("-", "_")
    securities = [
        {
            "ticker": normalize_kospi_ticker(stock.ticker),
            "market": stock.market,
            "is_preferred": bool(stock.is_preferred),
        }
        for stock in sorted(stocks, key=lambda item: normalize_kospi_ticker(item.ticker))
        if stock.is_active
    ]
    return {
        "version": version or f"kospi_static_{snapshot_date}_v0",
        "universe_name": PILOT_KOSPI_UNIVERSE_NAME,
        "source": PILOT_KOSPI_UNIVERSE_SOURCE,
        "retrieved_at": retrieved_at.isoformat().replace("+00:00", "Z"),
        "active_from": retrieved_at.isoformat().replace("+00:00", "Z"),
        "timestamp_available": retrieved_at.isoformat().replace("+00:00", "Z"),
        "notes": [
            "Static KOSPI pilot universe for local methodology research only.",
            "Survivorship-biased: active listings only, no delistings since 2019.",
            "No sector/industry metadata in Phase 1; names are placeholders.",
            "Source data originates from pykrx via Acquin; development use only.",
        ],
        "securities": securities,
    }


def load_kospi_universe_config(path: Path = DEFAULT_KOSPI_CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_kospi_universe_config(payload: dict, path: Path = DEFAULT_KOSPI_CONFIG) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def placeholder_company_name(ticker: str) -> str:
    return f"KOSPI {ticker} (placeholder)"


def seed_pilot_kospi_universe(*, session, payload: dict) -> int:
    """Seed placeholder entities and universe membership from the config payload.

    Phase 1 has no metadata: company names are placeholders, ISIN/FIGI stay
    null, and share class comes from the Acquin preferred flag. company_id and
    security_id are stable across reruns; Phase 2 enrichment only updates
    metadata on these identities.
    """
    active_from = _parse_datetime(payload["active_from"])
    available_at = _parse_datetime(payload["timestamp_available"])
    version = str(payload["version"])
    now = datetime.now(timezone.utc)
    count = 0

    for item in payload["securities"]:
        ticker = normalize_kospi_ticker(item["ticker"])
        company_id = stable_uuid(f"kospi-company:{ticker}")
        session.execute(
            insert(models.Company)
            .values(
                company_id=company_id,
                cik=None,
                legal_name=placeholder_company_name(ticker),
                created_at=available_at,
            )
            .on_conflict_do_nothing(index_elements=["company_id"])
        )

        security_id = stable_uuid(f"kospi-security:{ticker}")
        share_class = "preferred" if item.get("is_preferred") else None
        session.execute(
            insert(models.Security)
            .values(
                security_id=security_id,
                company_id=company_id,
                figi=None,
                isin=None,
                cusip=None,
                exchange="KRX",
                share_class=share_class,
                active_from=active_from,
                active_to=None,
            )
            .on_conflict_do_update(
                index_elements=["security_id"],
                set_={"share_class": share_class, "active_to": None},
            )
        )
        # Insert ticker history only when no open row exists for this pair, so
        # a regenerated config with a new active_from cannot create duplicate
        # active rows.
        existing_open_ticker = session.execute(
            select(models.SecurityTickerHistory.ticker_history_id)
            .where(models.SecurityTickerHistory.security_id == security_id)
            .where(models.SecurityTickerHistory.ticker == ticker)
            .where(models.SecurityTickerHistory.active_to.is_(None))
            .limit(1)
        ).scalar_one_or_none()
        if existing_open_ticker is None:
            session.execute(
                insert(models.SecurityTickerHistory)
                .values(
                    ticker_history_id=stable_uuid(f"kospi-ticker:{ticker}:current"),
                    security_id=security_id,
                    ticker=ticker,
                    active_from=active_from,
                    active_to=None,
                )
                .on_conflict_do_nothing(constraint="uq_ticker_history")
            )

        member_stmt = insert(models.ModelUniverseMember).values(
            model_universe_member_id=stable_uuid(
                f"kospi-member:{PILOT_KOSPI_UNIVERSE_NAME}:{version}:{ticker}"
            ),
            universe_name=PILOT_KOSPI_UNIVERSE_NAME,
            universe_version=version,
            security_id=security_id,
            ticker=ticker,
            source=payload["source"],
            source_asset_id=None,
            eligibility_status="eligible",
            first_price_time=None,
            last_price_time=None,
            price_bar_count=0,
            active_from=active_from,
            active_to=None,
            skip_reason=None,
            member_payload={
                "market": item.get("market"),
                "is_preferred": bool(item.get("is_preferred")),
                "retrieved_at": payload.get("retrieved_at"),
            },
            created_at=now,
            updated_at=now,
        )
        session.execute(
            member_stmt.on_conflict_do_update(
                constraint="uq_model_universe_member_security",
                set_={
                    "ticker": member_stmt.excluded.ticker,
                    "eligibility_status": member_stmt.excluded.eligibility_status,
                    "active_to": None,
                    "skip_reason": None,
                    "metadata": member_stmt.excluded.metadata,
                    "updated_at": now,
                },
            )
        )
        count += 1
    session.flush()
    return count


def refresh_kospi_universe_price_coverage(*, session, universe_version: str) -> int:
    rows = session.execute(
        select(
            models.ModelUniverseMember.model_universe_member_id,
            func.min(models.PriceBar.event_time),
            func.max(models.PriceBar.event_time),
            func.count(models.PriceBar.price_bar_id),
        )
        .outerjoin(models.PriceBar, models.PriceBar.security_id == models.ModelUniverseMember.security_id)
        .where(models.ModelUniverseMember.universe_name == PILOT_KOSPI_UNIVERSE_NAME)
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


def load_acquin_db_url(env_path: Path = Path(".env")) -> str:
    """Load ACQUIN_DB_URL tolerantly (spaces around '=' are accepted).

    Returns a psycopg-compatible URL for the read-only Railway connection.
    """
    explicit = os.getenv("ACQUIN_DB_URL")
    if explicit:
        return _normalize_pg_url(explicit.strip())
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == "ACQUIN_DB_URL":
                return _normalize_pg_url(value.strip().strip('"').strip("'"))
    raise RuntimeError("ACQUIN_DB_URL is not set in the environment or .env")


def _normalize_pg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url[len("postgresql+psycopg://"):]
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

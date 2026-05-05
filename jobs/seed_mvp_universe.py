from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope


DEFAULT_CONFIG = Path("config/mvp_universe.json")
NAMESPACE = uuid.UUID("5b97a5a6-f701-4af6-954d-7f2197fd00a1")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the curated MVP 50-name universe")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    payload = load_config(Path(args.config))
    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        count = seed_universe(session=session, payload=payload)

    print(f"seeded {count} MVP securities from {args.config}")


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_universe(*, session, payload: dict) -> int:
    active_from = _parse_datetime(payload["active_from"])
    available_at = _parse_datetime(payload["timestamp_available"])
    count = 0
    for item in payload["securities"]:
        company_id = stable_uuid(f"company:{item['ticker']}")
        security_id = stable_uuid(f"security:{item['ticker']}")
        existing_company_id = None
        if item.get("cik"):
            existing_company_id = session.execute(
                select(models.Company.company_id).where(models.Company.cik == item["cik"])
            ).scalar_one_or_none()
        if existing_company_id is None:
            session.execute(
                insert(models.Company)
                .values(
                    company_id=company_id,
                    cik=item.get("cik"),
                    legal_name=item["name"],
                    created_at=available_at,
                )
                .on_conflict_do_update(
                    index_elements=["company_id"],
                    set_={
                        "legal_name": item["name"],
                    },
                )
            )
        else:
            company_id = existing_company_id
            session.execute(
                insert(models.Company)
                .values(
                    company_id=company_id,
                    cik=item.get("cik"),
                    legal_name=item["name"],
                    created_at=available_at,
                )
                .on_conflict_do_update(
                    index_elements=["company_id"],
                    set_={
                        "legal_name": item["name"],
                    },
                )
            )

        session.execute(
            insert(models.Security)
            .values(
                security_id=security_id,
                company_id=company_id,
                exchange=item["exchange"],
                share_class=None,
                active_from=active_from,
                active_to=None,
            )
            .on_conflict_do_nothing(index_elements=["security_id"])
        )
        session.execute(
            insert(models.SecurityTickerHistory)
            .values(
                ticker_history_id=stable_uuid(f"ticker:{item['ticker']}:current"),
                security_id=security_id,
                ticker=item["ticker"],
                active_from=active_from,
                active_to=None,
            )
            .on_conflict_do_nothing(constraint="uq_ticker_history")
        )
        count += 1
    session.flush()
    return count


def find_security_id(*, session, ticker: str) -> uuid.UUID:
    result = session.execute(
        select(models.Security.security_id)
        .join(
            models.SecurityTickerHistory,
            models.Security.security_id == models.SecurityTickerHistory.security_id,
        )
        .where(models.SecurityTickerHistory.ticker == ticker.upper())
        .where(models.SecurityTickerHistory.active_to.is_(None))
        .order_by(models.SecurityTickerHistory.active_from.desc())
        .limit(1)
    ).scalar_one_or_none()
    if result is None:
        raise RuntimeError(f"ticker {ticker} must be seeded before dependent mappings")
    return result


def stable_uuid(value: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, value)


def _parse_datetime(value: str) -> datetime:
    if "T" in value:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


if __name__ == "__main__":
    main()

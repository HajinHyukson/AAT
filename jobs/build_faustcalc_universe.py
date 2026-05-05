from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from jobs.faustcalc_common import (
    DEFAULT_FAUSTCALC_UNIVERSE_NAME,
    DEFAULT_FAUSTCALC_UNIVERSE_VERSION,
    FAUSTCALC_FEATURE_STORE_SOURCE,
    FAUSTCALC_PRICE_SOURCE,
    stable_uuid,
)
from jobs.refresh_attribution_summaries import refresh_attribution_summaries


@dataclass
class FaustcalcUniverseBuildReport:
    universe_name: str
    universe_version: str
    source_assets: int = 0
    eligible_members: int = 0
    min_price_bars: int = 2
    summaries_refreshed: int = 0
    dry_run: bool = False

    def render(self) -> str:
        mode = "dry-run " if self.dry_run else ""
        return (
            f"{mode}built FaustCalc universe "
            f"universe={self.universe_name} version={self.universe_version} "
            f"source_assets={self.source_assets} eligible_members={self.eligible_members} "
            f"min_price_bars={self.min_price_bars} summaries_refreshed={self.summaries_refreshed}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the FaustCalc active US equities universe")
    parser.add_argument("--universe-name", default=DEFAULT_FAUSTCALC_UNIVERSE_NAME)
    parser.add_argument("--universe-version", default=DEFAULT_FAUSTCALC_UNIVERSE_VERSION)
    parser.add_argument("--min-price-bars", type=int, default=2)
    parser.add_argument("--skip-summary-refresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    with session_scope(prefer_compose_port=args.prefer_compose_port) as session:
        report = build_faustcalc_universe(
            session=session,
            universe_name=args.universe_name,
            universe_version=args.universe_version,
            min_price_bars=args.min_price_bars,
            refresh_summaries=not args.skip_summary_refresh,
            dry_run=args.dry_run,
        )
    print(report.render())


def build_faustcalc_universe(
    *,
    session,
    universe_name: str = DEFAULT_FAUSTCALC_UNIVERSE_NAME,
    universe_version: str = DEFAULT_FAUSTCALC_UNIVERSE_VERSION,
    min_price_bars: int = 2,
    refresh_summaries: bool = True,
    dry_run: bool = False,
) -> FaustcalcUniverseBuildReport:
    report = FaustcalcUniverseBuildReport(
        universe_name=universe_name,
        universe_version=universe_version,
        min_price_bars=min_price_bars,
        dry_run=dry_run,
    )
    report.source_assets = count_active_us_stock_assets(session=session)
    rows = eligible_member_rows(session=session, min_price_bars=min_price_bars)
    report.eligible_members = len(rows)
    if dry_run:
        return report

    now = datetime.now(timezone.utc)
    for row in rows:
        upsert_member_row(
            session=session,
            row=row,
            universe_name=universe_name,
            universe_version=universe_version,
            now=now,
        )
    session.flush()
    if refresh_summaries:
        summary_report = refresh_attribution_summaries(
            session=session,
            universe_name=universe_name,
            universe_version=universe_version,
        )
        report.summaries_refreshed = summary_report.refreshed
    return report


def count_active_us_stock_assets(*, session) -> int:
    return int(session.execute(active_us_stock_assets_count_statement()).scalar_one())


def active_us_stock_assets_count_statement():
    return (
        select(func.count(models.FaustcalcAsset.faustcalc_asset_id))
        .where(func.lower(models.FaustcalcAsset.asset_type) == "stock")
        .where(func.upper(models.FaustcalcAsset.currency) == "USD")
        .where(models.FaustcalcAsset.is_active.is_(True))
    )


def eligible_member_rows(*, session, min_price_bars: int) -> list:
    return list(session.execute(eligible_member_statement(min_price_bars=min_price_bars)).mappings())


def eligible_member_statement(*, min_price_bars: int):
    price_coverage = (
        select(
            models.PriceBar.security_id.label("security_id"),
            func.count(models.PriceBar.price_bar_id).label("price_bar_count"),
            func.min(models.PriceBar.event_time).label("first_price_time"),
            func.max(models.PriceBar.event_time).label("last_price_time"),
        )
        .where(models.PriceBar.source == FAUSTCALC_PRICE_SOURCE)
        .group_by(models.PriceBar.security_id)
        .subquery()
    )
    return (
        select(
            models.FaustcalcAsset.faustcalc_asset_id.label("source_asset_id"),
            models.FaustcalcAsset.source_ticker.label("source_ticker"),
            models.FaustcalcAsset.canonical_ticker.label("canonical_ticker"),
            models.FaustcalcAsset.asset_type.label("asset_type"),
            models.FaustcalcAsset.exchange.label("source_exchange"),
            models.FaustcalcAsset.market.label("source_market"),
            models.Security.security_id.label("security_id"),
            models.SecurityTickerHistory.ticker.label("ticker"),
            price_coverage.c.price_bar_count.label("price_bar_count"),
            price_coverage.c.first_price_time.label("first_price_time"),
            price_coverage.c.last_price_time.label("last_price_time"),
        )
        .join(
            models.SecurityTickerHistory,
            and_(
                models.SecurityTickerHistory.ticker == models.FaustcalcAsset.canonical_ticker,
                models.SecurityTickerHistory.active_to.is_(None),
            ),
        )
        .join(models.Security, models.Security.security_id == models.SecurityTickerHistory.security_id)
        .join(price_coverage, price_coverage.c.security_id == models.Security.security_id)
        .where(models.Security.active_to.is_(None))
        .where(func.lower(models.FaustcalcAsset.asset_type) == "stock")
        .where(func.upper(models.FaustcalcAsset.currency) == "USD")
        .where(models.FaustcalcAsset.is_active.is_(True))
        .where(price_coverage.c.price_bar_count >= min_price_bars)
        .order_by(models.FaustcalcAsset.canonical_ticker)
    )


def upsert_member_row(*, session, row, universe_name: str, universe_version: str, now: datetime) -> None:
    payload = {
        "source_ticker": row["source_ticker"],
        "canonical_ticker": row["canonical_ticker"],
        "source_exchange": row["source_exchange"],
        "source_market": row["source_market"],
        "price_source": FAUSTCALC_PRICE_SOURCE,
    }
    values = {
        "model_universe_member_id": stable_uuid(
            f"universe-member:{universe_name}:{universe_version}:{row['security_id']}"
        ),
        "universe_name": universe_name,
        "universe_version": universe_version,
        "security_id": row["security_id"],
        "ticker": row["ticker"],
        "source": FAUSTCALC_FEATURE_STORE_SOURCE,
        "source_asset_id": row["source_asset_id"],
        "eligibility_status": "eligible",
        "first_price_time": row["first_price_time"],
        "last_price_time": row["last_price_time"],
        "price_bar_count": int(row["price_bar_count"]),
        "active_from": row["first_price_time"] or now,
        "active_to": None,
        "skip_reason": None,
        "member_payload": payload,
        "created_at": now,
        "updated_at": now,
    }
    stmt = insert(models.ModelUniverseMember).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_model_universe_member_security",
        set_={
            "ticker": stmt.excluded.ticker,
            "source": stmt.excluded.source,
            "source_asset_id": stmt.excluded.source_asset_id,
            "eligibility_status": stmt.excluded.eligibility_status,
            "first_price_time": stmt.excluded.first_price_time,
            "last_price_time": stmt.excluded.last_price_time,
            "price_bar_count": stmt.excluded.price_bar_count,
            "active_from": stmt.excluded.active_from,
            "active_to": None,
            "skip_reason": None,
            "metadata": stmt.excluded.metadata,
            "updated_at": now,
        },
    )
    session.execute(stmt)


if __name__ == "__main__":
    main()

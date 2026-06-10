"""Promote staged Acquin KOSPI data into canonical AAT tables.

Promotion order:

1. Generate (or load) the static KOSPI universe config from staged stocks.
2. Seed placeholder entities and universe membership.
3. Promote prices into ``price_bar`` (currency=KRW, source=acquin_pykrx)
   behind the continuity guard and the Acquin vintage policy.
4. Build ``kospi_market`` factor returns from the staged KOSPI index.
5. Refresh universe price coverage.

Rows rejected by validation or quarantined by the continuity guard stay in
staging and are recorded in ``acquin_validation_issue``. Resolving a
continuity issue (resolution_status='resolved') releases promotion past it on
the next run.
"""

from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import models
from db.session import session_scope
from jobs.pilot_kospi_common import (
    ACQUIN_PRICE_SOURCE,
    DEFAULT_KOSPI_CONFIG,
    ISSUE_TYPE_CONTINUITY,
    ISSUE_TYPE_INVALID_CLOSE,
    KOSPI_INDEX_CODE,
    KOSPI_MARKET_FACTOR_FAMILY,
    KOSPI_MARKET_FACTOR_NAME,
    acquin_vintage_stamps,
    apply_continuity_guard,
    build_kospi_universe_payload,
    continuity_issue_key,
    ensure_pilot_kospi_database_url,
    load_kospi_universe_config,
    normalize_kospi_ticker,
    refresh_kospi_universe_price_coverage,
    seed_pilot_kospi_universe,
    stable_uuid,
    write_kospi_universe_config,
)


@dataclass
class AcquinPromotionReport:
    universe_version: str = ""
    seeded_securities: int = 0
    tickers_processed: int = 0
    bars_promoted: int = 0
    bars_rejected: int = 0
    continuity_suspects: list[str] = field(default_factory=list)
    quarantined_bars: int = 0
    index_factor_rows: int = 0
    coverage_members_refreshed: int = 0

    def render(self) -> str:
        return (
            "Acquin promotion report\n"
            f"  universe_version={self.universe_version}\n"
            f"  seeded_securities={self.seeded_securities}\n"
            f"  tickers_processed={self.tickers_processed}\n"
            f"  bars_promoted={self.bars_promoted}\n"
            f"  bars_rejected={self.bars_rejected}\n"
            f"  continuity_suspects={self.continuity_suspects[:10]}"
            f"{' (+more)' if len(self.continuity_suspects) > 10 else ''}\n"
            f"  quarantined_bars={self.quarantined_bars}\n"
            f"  index_factor_rows={self.index_factor_rows}\n"
            f"  coverage_members_refreshed={self.coverage_members_refreshed}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote staged Acquin data into canonical AAT tables")
    parser.add_argument("--config", default=str(DEFAULT_KOSPI_CONFIG))
    parser.add_argument(
        "--refresh-universe-config",
        action="store_true",
        help="Regenerate the universe config from staged stocks even if the file exists",
    )
    parser.add_argument("--tickers", nargs="*", help="Optional ticker subset for price promotion")
    parser.add_argument("--skip-prices", action="store_true")
    parser.add_argument("--skip-index-factor", action="store_true")
    args = parser.parse_args()

    report = promote_acquin_data(
        config_path=Path(args.config),
        refresh_universe_config=args.refresh_universe_config,
        tickers=args.tickers,
        skip_prices=args.skip_prices,
        skip_index_factor=args.skip_index_factor,
    )
    print(report.render())


def promote_acquin_data(
    *,
    config_path: Path = DEFAULT_KOSPI_CONFIG,
    refresh_universe_config: bool = False,
    tickers: list[str] | None = None,
    skip_prices: bool = False,
    skip_index_factor: bool = False,
) -> AcquinPromotionReport:
    ensure_pilot_kospi_database_url()
    report = AcquinPromotionReport()

    payload = _ensure_universe_config(config_path=config_path, refresh=refresh_universe_config)
    report.universe_version = str(payload["version"])
    with session_scope() as session:
        report.seeded_securities = seed_pilot_kospi_universe(session=session, payload=payload)

    if not skip_prices:
        selected = (
            sorted({normalize_kospi_ticker(ticker) for ticker in tickers})
            if tickers
            else [item["ticker"] for item in payload["securities"]]
        )
        for ticker in selected:
            promoted, rejected, suspect, quarantined = _promote_ticker_prices(ticker=ticker)
            report.tickers_processed += 1
            report.bars_promoted += promoted
            report.bars_rejected += rejected
            report.quarantined_bars += quarantined
            if suspect:
                report.continuity_suspects.append(suspect)

    if not skip_index_factor:
        report.index_factor_rows = _promote_index_factor()

    with session_scope() as session:
        report.coverage_members_refreshed = refresh_kospi_universe_price_coverage(
            session=session,
            universe_version=report.universe_version,
        )
    return report


def _ensure_universe_config(*, config_path: Path, refresh: bool) -> dict:
    if config_path.exists() and not refresh:
        return load_kospi_universe_config(config_path)
    with session_scope() as session:
        stocks = session.execute(select(models.AcquinStock)).scalars().all()
        if not stocks:
            raise RuntimeError(
                "no staged Acquin stocks found; run jobs.import_acquin_snapshot first"
            )
        retrieved_at = max(
            (stock.source_updated_at for stock in stocks if stock.source_updated_at),
            default=datetime.now(timezone.utc),
        )
        payload = build_kospi_universe_payload(stocks=stocks, retrieved_at=retrieved_at)
    write_kospi_universe_config(payload, config_path)
    return payload


def _promote_ticker_prices(*, ticker: str) -> tuple[int, int, str | None, int]:
    """Promote one ticker's staged prices. Returns (promoted, rejected, suspect_key, quarantined)."""
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        security_id = _resolve_security_id(session=session, ticker=ticker)
        if security_id is None:
            return 0, 0, None, 0
        rows = (
            session.execute(
                select(models.AcquinPrice)
                .where(models.AcquinPrice.ticker == ticker)
                .order_by(models.AcquinPrice.price_date)
            )
            .scalars()
            .all()
        )
        if not rows:
            return 0, 0, None, 0

        valid_rows = []
        rejected = 0
        for row in rows:
            if row.adj_close is None or row.adj_close <= 0 or row.close is None or row.close <= 0:
                rejected += 1
                _record_issue_once(
                    session=session,
                    issue_type=ISSUE_TYPE_INVALID_CLOSE,
                    source_table="acquin_price",
                    source_key=continuity_issue_key(ticker=ticker, trade_date=row.price_date),
                    severity="warning",
                    details={
                        "ticker": ticker,
                        "price_date": row.price_date.isoformat(),
                        "close": row.close,
                        "adj_close": row.adj_close,
                    },
                )
                continue
            valid_rows.append(row)

        resolved_keys = _resolved_continuity_keys(session=session, ticker=ticker)
        verdict = apply_continuity_guard(ticker=ticker, rows=valid_rows, resolved_keys=resolved_keys)
        if verdict.suspect_key is not None:
            _record_issue_once(
                session=session,
                issue_type=ISSUE_TYPE_CONTINUITY,
                source_table="acquin_price",
                source_key=verdict.suspect_key,
                severity="error",
                details={
                    "ticker": ticker,
                    "one_day_return": verdict.suspect_return,
                    "quarantined_bars": verdict.quarantined_count,
                    "action": (
                        "verify whether this is a real move or an unadjusted corporate action; "
                        "mark resolution_status='resolved' to accept it, or re-import the "
                        "ticker's full adjusted history"
                    ),
                },
            )

        values = []
        for row in verdict.promotable:
            stamps = acquin_vintage_stamps(
                trade_date=row.price_date,
                source_created_at=row.source_created_at,
                fallback_ingestion_time=now,
            )
            values.append(
                {
                    "price_bar_id": uuid.uuid4(),
                    "security_id": security_id,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "adjusted_close": row.adj_close,
                    "volume": int(row.volume) if row.volume is not None else None,
                    "currency": "KRW",
                    "source": ACQUIN_PRICE_SOURCE,
                    "event_time": stamps.event_time,
                    "ingestion_time": stamps.ingestion_time,
                    "timestamp_available": stamps.timestamp_available,
                }
            )
        if values:
            stmt = insert(models.PriceBar)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_price_bar_source_time",
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "adjusted_close": stmt.excluded.adjusted_close,
                    "volume": stmt.excluded.volume,
                    "currency": stmt.excluded.currency,
                    "ingestion_time": stmt.excluded.ingestion_time,
                    "timestamp_available": stmt.excluded.timestamp_available,
                },
            )
            session.execute(stmt, values)
        return len(values), rejected, verdict.suspect_key, verdict.quarantined_count


def build_index_factor_values(*, rows: list, now: datetime) -> list[dict]:
    """Close-to-close ``kospi_market`` factor-return rows from staged index rows.

    ``rows`` must be ordered by date and expose ``index_date``, ``close`` and
    ``source_created_at``. The first usable row only seeds the baseline; rows
    with missing or non-positive closes are skipped without breaking the chain.
    """
    values = []
    previous_close: float | None = None
    for row in rows:
        close = row.close
        if close is None or close <= 0:
            continue
        if previous_close is not None:
            stamps = acquin_vintage_stamps(
                trade_date=row.index_date,
                source_created_at=row.source_created_at,
                fallback_ingestion_time=now,
            )
            values.append(
                {
                    "factor_return_id": uuid.uuid4(),
                    "factor_name": KOSPI_MARKET_FACTOR_NAME,
                    "factor_family": KOSPI_MARKET_FACTOR_FAMILY,
                    "return_bps": (close / previous_close - 1.0) * 10_000.0,
                    "source": ACQUIN_PRICE_SOURCE,
                    "event_time": stamps.event_time,
                    "ingestion_time": stamps.ingestion_time,
                    "timestamp_available": stamps.timestamp_available,
                }
            )
        previous_close = close
    return values


def _promote_index_factor(*, index_code: str = KOSPI_INDEX_CODE) -> int:
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        rows = (
            session.execute(
                select(models.AcquinIndex)
                .where(models.AcquinIndex.index_code == index_code)
                .order_by(models.AcquinIndex.index_date)
            )
            .scalars()
            .all()
        )
        values = build_index_factor_values(rows=rows, now=now)
        if values:
            stmt = insert(models.FactorReturn)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_factor_return_source_time",
                set_={
                    "return_bps": stmt.excluded.return_bps,
                    "factor_family": stmt.excluded.factor_family,
                    "ingestion_time": stmt.excluded.ingestion_time,
                    "timestamp_available": stmt.excluded.timestamp_available,
                },
            )
            session.execute(stmt, values)
        return len(values)


def _resolve_security_id(*, session, ticker: str) -> uuid.UUID | None:
    return session.execute(
        select(models.SecurityTickerHistory.security_id)
        .where(models.SecurityTickerHistory.ticker == ticker)
        .where(models.SecurityTickerHistory.active_to.is_(None))
        .order_by(models.SecurityTickerHistory.active_from.desc())
        .limit(1)
    ).scalar_one_or_none()


def _resolved_continuity_keys(*, session, ticker: str) -> set[str]:
    rows = session.execute(
        select(models.AcquinValidationIssue.source_key)
        .where(models.AcquinValidationIssue.issue_type == ISSUE_TYPE_CONTINUITY)
        .where(models.AcquinValidationIssue.resolution_status == "resolved")
        .where(models.AcquinValidationIssue.source_key.like(f"{ticker}:%"))
    )
    return {row[0] for row in rows if row[0]}


def _record_issue_once(
    *,
    session,
    issue_type: str,
    source_table: str,
    source_key: str,
    severity: str,
    details: dict,
) -> None:
    existing = session.execute(
        select(models.AcquinValidationIssue.acquin_validation_issue_id)
        .where(models.AcquinValidationIssue.issue_type == issue_type)
        .where(models.AcquinValidationIssue.source_key == source_key)
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return
    session.add(
        models.AcquinValidationIssue(
            acquin_validation_issue_id=stable_uuid(f"issue:{issue_type}:{source_key}"),
            acquin_import_run_id=None,
            severity=severity,
            issue_type=issue_type,
            source_table=source_table,
            source_key=source_key,
            resolution_status="open",
            details=details,
            created_at=datetime.now(timezone.utc),
        )
    )


if __name__ == "__main__":
    main()

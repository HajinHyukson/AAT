from __future__ import annotations

import argparse
import math
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import MetaData, Table, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine

from db import models
from db.session import session_scope
from jobs.faustcalc_common import (
    FAUSTCALC_PRICE_SOURCE,
    canonical_ticker,
    date_to_utc_datetime,
    fingerprint_database_url,
    get_faustcalc_database_url,
    jsonable_mapping,
    make_faustcalc_engine,
    normalize_cik,
    parse_optional_datetime,
    parse_required_date,
    stable_uuid,
)


SOURCE_TABLES = (
    "assets",
    "companies",
    "prices",
    "fundamentals",
    "price_features",
    "theme_scores",
    "filing_analysis",
    "peer_analysis",
)
POSTGRES_PARAMETER_LIMIT = 60_000


@dataclass
class FeatureStoreImportReport:
    source_counts: dict[str, dict[str, Any]] = field(default_factory=dict)
    staged_counts: dict[str, int] = field(default_factory=dict)
    promoted_companies: int = 0
    promoted_securities: int = 0
    promoted_price_rows: int = 0
    validation_issues: list[dict[str, Any]] = field(default_factory=list)
    import_run_id: str | None = None
    dry_run: bool = False

    def render(self) -> str:
        lines = [
            "FaustCalc feature-store import report",
            f"  dry_run={self.dry_run}",
            f"  import_run_id={self.import_run_id}",
            f"  source_tables={list(self.source_counts)}",
            f"  staged_counts={self.staged_counts}",
            f"  promoted_companies={self.promoted_companies}",
            f"  promoted_securities={self.promoted_securities}",
            f"  promoted_price_rows={self.promoted_price_rows}",
            f"  validation_issues={len(self.validation_issues)}",
        ]
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import FaustCalc feature-store data into AAT")
    parser.add_argument("--source-database-url", help="FaustCalc SQLAlchemy database URL")
    parser.add_argument("--tables", nargs="+", choices=SOURCE_TABLES, default=list(SOURCE_TABLES))
    parser.add_argument("--limit", type=int, help="Optional per-table source row limit for proving runs")
    parser.add_argument("--batch-size", type=int, default=5_000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-staging", action="store_true")
    parser.add_argument("--skip-promote", action="store_true")
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    report = run_feature_store_import(
        source_database_url=args.source_database_url,
        tables=tuple(args.tables),
        limit=args.limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        load_staging=not args.skip_staging,
        promote=not args.skip_promote,
        prefer_compose_port=args.prefer_compose_port,
    )
    print(report.render())


def run_feature_store_import(
    *,
    source_database_url: str | None = None,
    tables: tuple[str, ...] = SOURCE_TABLES,
    limit: int | None = None,
    batch_size: int = 5_000,
    dry_run: bool = False,
    load_staging: bool = True,
    promote: bool = True,
    prefer_compose_port: bool = False,
    source_engine: Engine | None = None,
) -> FeatureStoreImportReport:
    resolved_url = (
        "provided-source-engine"
        if source_engine is not None and source_database_url is None
        else get_faustcalc_database_url(source_database_url)
    )
    engine = source_engine or make_faustcalc_engine(resolved_url)
    started_at = datetime.now(timezone.utc)
    report = FeatureStoreImportReport(dry_run=dry_run)

    with engine.connect() as source_conn:
        report.source_counts = inventory_source(source_conn=source_conn, tables=tables)

        if dry_run:
            return report

        with session_scope(prefer_compose_port=prefer_compose_port) as session:
            import_run = create_import_run(
                session=session,
                mode="feature_store",
                source_database_url=resolved_url,
                started_at=started_at,
                source_counts=report.source_counts,
            )
            report.import_run_id = str(import_run.faustcalc_import_run_id)

        try:
            if load_staging:
                with session_scope(prefer_compose_port=prefer_compose_port) as session:
                    report.staged_counts = load_staging_tables(
                        source_conn=source_conn,
                        session=session,
                        import_run_id=uuid.UUID(report.import_run_id),
                        tables=tables,
                        limit=limit,
                        batch_size=batch_size,
                    )

            if promote:
                with session_scope(prefer_compose_port=prefer_compose_port) as session:
                    companies, securities = promote_identities(
                        session=session,
                        import_run_id=uuid.UUID(report.import_run_id),
                        imported_at=started_at,
                    )
                    report.promoted_companies = companies
                    report.promoted_securities = securities
                with session_scope(prefer_compose_port=prefer_compose_port) as session:
                    report.promoted_price_rows = promote_price_bars(
                        session=session,
                        imported_at=started_at,
                    )

            with session_scope(prefer_compose_port=prefer_compose_port) as session:
                finish_import_run(
                    session=session,
                    import_run_id=uuid.UUID(report.import_run_id),
                    status="completed",
                    validation_payload={
                        "staged_counts": report.staged_counts,
                        "promoted_companies": report.promoted_companies,
                        "promoted_securities": report.promoted_securities,
                        "promoted_price_rows": report.promoted_price_rows,
                    },
                )
            return report
        except Exception as exc:
            with session_scope(prefer_compose_port=prefer_compose_port) as session:
                finish_import_run(
                    session=session,
                    import_run_id=uuid.UUID(report.import_run_id),
                    status="failed",
                    error_payload={"error": str(exc)},
                )
            raise


def inventory_source(*, source_conn: Connection, tables: Iterable[str] = SOURCE_TABLES) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for table_name in tables:
        count = source_conn.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one()
        payload: dict[str, Any] = {"rows": int(count)}
        if table_name == "prices":
            row = source_conn.execute(
                text("SELECT min(date), max(date), count(distinct ticker) FROM prices")
            ).one()
            payload.update({"min_date": row[0], "max_date": row[1], "tickers": int(row[2])})
        elif table_name in {"fundamentals", "price_features", "theme_scores", "peer_analysis"}:
            date_column = "as_of_date"
            row = source_conn.execute(
                text(f"SELECT min({date_column}), max({date_column}), count(distinct ticker) FROM {table_name}")
            ).one()
            payload.update({"min_date": row[0], "max_date": row[1], "tickers": int(row[2])})
        elif table_name == "filing_analysis":
            row = source_conn.execute(
                text("SELECT min(filing_date), max(filing_date), count(distinct ticker) FROM filing_analysis")
            ).one()
            payload.update({"min_date": row[0], "max_date": row[1], "tickers": int(row[2])})
        inventory[table_name] = jsonable_mapping(payload)
    return inventory


def create_import_run(
    *,
    session,
    mode: str,
    source_database_url: str,
    started_at: datetime,
    source_counts: dict[str, dict[str, Any]],
) -> models.FaustcalcImportRun:
    import_run = models.FaustcalcImportRun(
        faustcalc_import_run_id=uuid.uuid4(),
        mode=mode,
        source_database_fingerprint=fingerprint_database_url(source_database_url),
        data_root=None,
        status="running",
        started_at=started_at,
        finished_at=None,
        source_counts=source_counts,
        validation_payload=None,
        error_payload=None,
    )
    session.add(import_run)
    session.flush()
    return import_run


def finish_import_run(
    *,
    session,
    import_run_id: uuid.UUID,
    status: str,
    validation_payload: dict | None = None,
    error_payload: dict | None = None,
) -> None:
    import_run = session.get(models.FaustcalcImportRun, import_run_id)
    if import_run is None:
        return
    import_run.status = status
    import_run.finished_at = datetime.now(timezone.utc)
    if validation_payload is not None:
        import_run.validation_payload = validation_payload
    if error_payload is not None:
        import_run.error_payload = error_payload


def load_staging_tables(
    *,
    source_conn: Connection,
    session,
    import_run_id: uuid.UUID,
    tables: Iterable[str],
    limit: int | None,
    batch_size: int,
) -> dict[str, int]:
    counts = {}
    for table_name in tables:
        counts[table_name] = load_staging_table(
            source_conn=source_conn,
            session=session,
            import_run_id=import_run_id,
            table_name=table_name,
            limit=limit,
            batch_size=batch_size,
        )
    if "prices" in tables and "assets" in tables:
        sync_price_currencies_from_assets(session=session)
    return counts


def load_staging_table(
    *,
    source_conn: Connection,
    session,
    import_run_id: uuid.UUID,
    table_name: str,
    limit: int | None,
    batch_size: int,
) -> int:
    metadata = MetaData()
    source_table = Table(table_name, metadata, autoload_with=source_conn)
    order_column = source_table.c.id if "id" in source_table.c else source_table.c.ticker
    stmt = select(source_table).order_by(order_column)
    if limit is not None:
        stmt = stmt.limit(limit)

    result = source_conn.execution_options(stream_results=True).execute(stmt)
    loaded = 0
    while True:
        rows = result.fetchmany(batch_size)
        if not rows:
            break
        values = [
            build_staging_value(
                import_run_id=import_run_id,
                source_table=table_name,
                row=dict(row._mapping),
            )
            for row in rows
        ]
        upsert_staging_values(session=session, source_table=table_name, values=values)
        session.commit()
        loaded += len(values)
    return loaded


def build_staging_value(*, import_run_id: uuid.UUID, source_table: str, row: dict[str, Any]) -> dict[str, Any]:
    if source_table == "assets":
        return build_asset_value(import_run_id=import_run_id, row=row)
    if source_table == "companies":
        return build_company_value(import_run_id=import_run_id, row=row)
    if source_table == "prices":
        return build_price_value(import_run_id=import_run_id, row=row)
    if source_table == "fundamentals":
        return build_source_row_value(
            import_run_id=import_run_id,
            row=row,
            pk_field="faustcalc_fundamental_id",
            stable_prefix="fc_fundamental",
            source_id_field="source_fundamental_id",
            date_field="as_of_date",
            extra={"source": str(row.get("source") or "")},
        )
    if source_table == "price_features":
        return build_source_row_value(
            import_run_id=import_run_id,
            row=row,
            pk_field="faustcalc_price_feature_id",
            stable_prefix="fc_price_feature",
            source_id_field="source_price_feature_id",
            date_field="as_of_date",
        )
    if source_table == "theme_scores":
        return build_source_row_value(
            import_run_id=import_run_id,
            row=row,
            pk_field="faustcalc_theme_score_id",
            stable_prefix="fc_theme_score",
            source_id_field="source_theme_score_id",
            date_field="as_of_date",
            extra={"theme_key": str(row.get("theme_key") or "")},
        )
    if source_table == "filing_analysis":
        return build_source_row_value(
            import_run_id=import_run_id,
            row=row,
            pk_field="faustcalc_filing_analysis_id",
            stable_prefix="fc_filing_analysis",
            source_id_field="source_filing_analysis_id",
            date_field="filing_date",
            extra={"filing_type": str(row.get("filing_type") or "")},
        )
    if source_table == "peer_analysis":
        return build_source_row_value(
            import_run_id=import_run_id,
            row=row,
            pk_field="faustcalc_peer_analysis_id",
            stable_prefix="fc_peer_analysis",
            source_id_field="source_peer_analysis_id",
            date_field="as_of_date",
        )
    raise ValueError(f"unsupported FaustCalc table: {source_table}")


def build_asset_value(*, import_run_id: uuid.UUID, row: dict[str, Any]) -> dict[str, Any]:
    source_ticker = str(row["ticker"]).upper()
    return {
        "faustcalc_asset_id": stable_uuid(f"fc_asset:{source_ticker}"),
        "faustcalc_import_run_id": import_run_id,
        "source_ticker": source_ticker,
        "canonical_ticker": canonical_ticker(source_ticker),
        "ticker_local": row.get("ticker_local"),
        "company_name": row.get("company_name_en") or row.get("company_name_ko") or row.get("ticker_display"),
        "asset_type": row.get("asset_type"),
        "exchange": row.get("exchange"),
        "market": row.get("market"),
        "currency": str(row.get("currency") or "USD")[:3].upper(),
        "is_active": row.get("is_active"),
        "source_created_at": parse_optional_datetime(row.get("created_at")),
        "source_last_updated": parse_optional_datetime(row.get("last_updated")),
        "raw_payload": jsonable_mapping(row),
    }


def build_company_value(*, import_run_id: uuid.UUID, row: dict[str, Any]) -> dict[str, Any]:
    source_ticker = str(row["ticker"]).upper()
    return {
        "faustcalc_company_id": stable_uuid(f"fc_company:{source_ticker}"),
        "faustcalc_import_run_id": import_run_id,
        "source_ticker": source_ticker,
        "canonical_ticker": canonical_ticker(source_ticker),
        "cik": normalize_cik(row.get("cik")),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "country": row.get("country"),
        "source_last_updated": parse_optional_datetime(row.get("last_updated")),
        "raw_payload": jsonable_mapping(row),
    }


def build_price_value(*, import_run_id: uuid.UUID, row: dict[str, Any]) -> dict[str, Any]:
    source_ticker = str(row["ticker"]).upper()
    close = float(row["close"])
    if not math.isfinite(close) or close <= 0:
        raise ValueError(f"non-positive FaustCalc close for source price {row.get('id')}")
    return {
        "faustcalc_price_id": stable_uuid(f"fc_price:{row['id']}"),
        "faustcalc_import_run_id": import_run_id,
        "source_price_id": int(row["id"]),
        "source_ticker": source_ticker,
        "canonical_ticker": canonical_ticker(source_ticker),
        "price_date": parse_required_date(row["date"]),
        "close": close,
        "volume": int(row["volume"]) if row.get("volume") is not None else None,
        "currency": "USD",
        "raw_payload": jsonable_mapping(row),
    }


def build_source_row_value(
    *,
    import_run_id: uuid.UUID,
    row: dict[str, Any],
    pk_field: str,
    stable_prefix: str,
    source_id_field: str,
    date_field: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_ticker = str(row["ticker"]).upper()
    value = {
        pk_field: stable_uuid(f"{stable_prefix}:{row['id']}"),
        "faustcalc_import_run_id": import_run_id,
        source_id_field: int(row["id"]),
        "source_ticker": source_ticker,
        "canonical_ticker": canonical_ticker(source_ticker),
        date_field: parse_required_date(row[date_field]),
        "raw_payload": jsonable_mapping(row),
    }
    value.update(extra or {})
    return value


def upsert_staging_values(*, session, source_table: str, values: list[dict[str, Any]]) -> None:
    if not values:
        return
    target_table, constraint, update_columns = staging_upsert_config(source_table)
    max_rows = max(1, POSTGRES_PARAMETER_LIMIT // len(target_table.columns))
    for start in range(0, len(values), max_rows):
        chunk = values[start : start + max_rows]
        stmt = insert(target_table).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint=constraint,
            set_={column: getattr(stmt.excluded, column) for column in update_columns},
        )
        session.execute(stmt)


def sync_price_currencies_from_assets(*, session) -> int:
    result = session.execute(
        text(
            """
            UPDATE faustcalc_price p
               SET currency = COALESCE(NULLIF(a.currency, ''), 'USD')
              FROM faustcalc_asset a
             WHERE a.source_ticker = p.source_ticker
               AND p.currency IS DISTINCT FROM COALESCE(NULLIF(a.currency, ''), 'USD')
            """
        )
    )
    return int(result.rowcount or 0)


def staging_upsert_config(source_table: str):
    if source_table == "assets":
        return (
            models.FaustcalcAsset.__table__,
            "uq_faustcalc_asset_source_ticker",
            [
                "faustcalc_import_run_id",
                "canonical_ticker",
                "ticker_local",
                "company_name",
                "asset_type",
                "exchange",
                "market",
                "currency",
                "is_active",
                "source_created_at",
                "source_last_updated",
                "raw_payload",
            ],
        )
    if source_table == "companies":
        return (
            models.FaustcalcCompany.__table__,
            "uq_faustcalc_company_source_ticker",
            [
                "faustcalc_import_run_id",
                "canonical_ticker",
                "cik",
                "sector",
                "industry",
                "country",
                "source_last_updated",
                "raw_payload",
            ],
        )
    configs = {
        "prices": (
            models.FaustcalcPrice.__table__,
            "uq_faustcalc_price_source_id",
            [
                "faustcalc_import_run_id",
                "source_ticker",
                "canonical_ticker",
                "price_date",
                "close",
                "volume",
                "currency",
                "raw_payload",
            ],
        ),
        "fundamentals": (
            models.FaustcalcFundamental.__table__,
            "uq_faustcalc_fundamental_source_id",
            ["faustcalc_import_run_id", "source_ticker", "canonical_ticker", "as_of_date", "source", "raw_payload"],
        ),
        "price_features": (
            models.FaustcalcPriceFeature.__table__,
            "uq_faustcalc_price_feature_source_id",
            ["faustcalc_import_run_id", "source_ticker", "canonical_ticker", "as_of_date", "raw_payload"],
        ),
        "theme_scores": (
            models.FaustcalcThemeScore.__table__,
            "uq_faustcalc_theme_score_source_id",
            [
                "faustcalc_import_run_id",
                "source_ticker",
                "canonical_ticker",
                "theme_key",
                "as_of_date",
                "raw_payload",
            ],
        ),
        "filing_analysis": (
            models.FaustcalcFilingAnalysis.__table__,
            "uq_faustcalc_filing_analysis_source_id",
            [
                "faustcalc_import_run_id",
                "source_ticker",
                "canonical_ticker",
                "filing_date",
                "filing_type",
                "raw_payload",
            ],
        ),
        "peer_analysis": (
            models.FaustcalcPeerAnalysis.__table__,
            "uq_faustcalc_peer_analysis_source_id",
            ["faustcalc_import_run_id", "source_ticker", "canonical_ticker", "as_of_date", "raw_payload"],
        ),
    }
    return configs[source_table]


def promote_identities(*, session, import_run_id: uuid.UUID, imported_at: datetime) -> tuple[int, int]:
    companies_by_ticker = {
        company.source_ticker: company
        for company in session.execute(select(models.FaustcalcCompany)).scalars()
    }
    min_price_dates = {
        ticker: min_date
        for ticker, min_date in session.execute(
            select(models.FaustcalcPrice.canonical_ticker, func.min(models.FaustcalcPrice.price_date)).group_by(
                models.FaustcalcPrice.canonical_ticker
            )
        )
    }
    existing_companies_by_cik = {
        cik: company_id
        for cik, company_id in session.execute(
            select(models.Company.cik, models.Company.company_id).where(models.Company.cik.is_not(None))
        )
    }
    existing_securities_by_ticker = {
        ticker: security_id
        for ticker, security_id in session.execute(
            select(models.SecurityTickerHistory.ticker, models.SecurityTickerHistory.security_id).where(
                models.SecurityTickerHistory.active_to.is_(None)
            )
        )
    }

    promoted_companies = 0
    promoted_securities = 0
    company_id_cache: dict[str, uuid.UUID] = {}

    assets = session.execute(select(models.FaustcalcAsset).order_by(models.FaustcalcAsset.canonical_ticker)).scalars()
    for asset in assets:
        company = companies_by_ticker.get(asset.source_ticker)
        cik = company.cik if company else None
        company_key = f"cik:{cik}" if cik else f"ticker:{asset.canonical_ticker}"
        company_id = company_id_cache.get(company_key)
        if company_id is None:
            company_id = existing_companies_by_cik.get(cik) if cik else None
            if company_id is None:
                company_id = stable_uuid(f"faustcalc_company:{company_key}")
                stmt = insert(models.Company).values(
                    company_id=company_id,
                    cik=cik,
                    legal_name=asset.company_name or asset.canonical_ticker,
                    created_at=imported_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["company_id"],
                    set_={
                        "legal_name": stmt.excluded.legal_name,
                    },
                )
                session.execute(stmt)
                promoted_companies += 1
            company_id_cache[company_key] = company_id

        existing_security_id = existing_securities_by_ticker.get(asset.canonical_ticker)
        if existing_security_id is not None:
            continue

        security_id = stable_uuid(f"faustcalc_security:{asset.canonical_ticker}")
        first_price_date = min_price_dates.get(asset.canonical_ticker)
        active_from = date_to_utc_datetime(first_price_date) if first_price_date else asset.source_created_at or imported_at
        stmt = insert(models.Security).values(
            security_id=security_id,
            company_id=company_id,
            figi=None,
            isin=None,
            cusip=None,
            exchange=asset.exchange or asset.market or "UNKNOWN",
            share_class=None,
            active_from=active_from,
            active_to=None,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["security_id"])
        session.execute(stmt)
        session.execute(
            insert(models.SecurityTickerHistory)
            .values(
                ticker_history_id=stable_uuid(f"faustcalc_ticker:{asset.canonical_ticker}:current"),
                security_id=security_id,
                ticker=asset.canonical_ticker,
                active_from=active_from,
                active_to=None,
            )
            .on_conflict_do_nothing(constraint="uq_ticker_history")
        )
        existing_securities_by_ticker[asset.canonical_ticker] = security_id
        promoted_securities += 1

    return promoted_companies, promoted_securities


def promote_price_bars(*, session, imported_at: datetime) -> int:
    bounds = session.execute(
        text(
            """
            SELECT min(price_date), max(price_date)
              FROM faustcalc_price
             WHERE close >= 0.000001
               AND close < 1000000000000
            """
        )
    ).one()
    if bounds[0] is None or bounds[1] is None:
        return 0

    promoted = 0
    for chunk_start, chunk_end in month_chunks(bounds[0], bounds[1]):
        result = session.execute(
            price_bar_promotion_sql(),
            {
                "source": FAUSTCALC_PRICE_SOURCE,
                "imported_at": imported_at,
                "date_start": chunk_start,
                "date_end": chunk_end,
            },
        )
        promoted += int(result.rowcount or 0)
        session.commit()
    return promoted


def month_chunks(start: date, end: date):
    current = date(start.year, start.month, 1)
    final_exclusive = _next_month(date(end.year, end.month, 1))
    while current < final_exclusive:
        next_month = _next_month(current)
        yield current, next_month
        current = next_month


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def price_bar_promotion_sql():
    sql = text(
        """
        INSERT INTO price_bar (
            price_bar_id,
            security_id,
            open,
            high,
            low,
            close,
            adjusted_close,
            volume,
            currency,
            source,
            event_time,
            ingestion_time,
            timestamp_available
        )
        SELECT
            CAST(
                substr(md5(:source || ':' || th.security_id::text || ':' || p.price_date::text), 1, 8) || '-' ||
                substr(md5(:source || ':' || th.security_id::text || ':' || p.price_date::text), 9, 4) || '-' ||
                substr(md5(:source || ':' || th.security_id::text || ':' || p.price_date::text), 13, 4) || '-' ||
                substr(md5(:source || ':' || th.security_id::text || ':' || p.price_date::text), 17, 4) || '-' ||
                substr(md5(:source || ':' || th.security_id::text || ':' || p.price_date::text), 21, 12)
                AS uuid
            ) AS price_bar_id,
            th.security_id,
            NULL,
            NULL,
            NULL,
            p.close,
            p.close,
            p.volume,
            COALESCE(NULLIF(p.currency, ''), 'USD'),
            :source,
            p.price_date::timestamp AT TIME ZONE 'UTC',
            :imported_at,
            :imported_at
        FROM faustcalc_price p
        JOIN LATERAL (
            SELECT th.security_id
              FROM security_ticker_history th
             WHERE th.ticker = p.canonical_ticker
               AND th.active_to IS NULL
             ORDER BY th.active_from DESC, th.security_id
             LIMIT 1
        ) th ON TRUE
        WHERE p.close >= 0.000001
          AND p.close < 1000000000000
          AND p.price_date >= :date_start
          AND p.price_date < :date_end
        ON CONFLICT ON CONSTRAINT uq_price_bar_source_time
        DO UPDATE SET
            close = EXCLUDED.close,
            adjusted_close = EXCLUDED.adjusted_close,
            volume = EXCLUDED.volume,
            currency = EXCLUDED.currency,
            ingestion_time = EXCLUDED.ingestion_time,
            timestamp_available = EXCLUDED.timestamp_available
        """
    )
    return sql


if __name__ == "__main__":
    main()

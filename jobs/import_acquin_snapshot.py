"""Import the Acquin Railway KOSPI snapshot into local acquin_* staging tables.

Reads the Acquin production Postgres (read-only, via ACQUIN_DB_URL) and stages
rows verbatim in the local KOSPI pilot database. Promotion into canonical AAT
tables happens separately in jobs.promote_acquin_data.

Incremental by default: only source rows with updated_at newer than the local
staging high-water mark are pulled. Use --full to re-pull everything.
"""

from __future__ import annotations

import argparse
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

import psycopg
from sqlalchemy.dialects.postgresql import insert

from adapters.source_policy import require_confirmed_production_source
from db import models
from db.session import session_scope
from jobs.pilot_kospi_common import (
    ensure_pilot_kospi_database_url,
    load_acquin_db_url,
    normalize_kospi_ticker,
)


DEFAULT_BATCH_SIZE = 5_000


@dataclass(frozen=True)
class TableSpec:
    name: str
    source_sql: str
    model: type
    conflict_constraint: str
    key_columns: tuple[str, ...]
    update_columns: tuple[str, ...]
    map_row: callable


def _map_stock(row: dict, run_id: uuid.UUID) -> dict:
    return {
        "acquin_stock_id": uuid.uuid4(),
        "acquin_import_run_id": run_id,
        "ticker": normalize_kospi_ticker(row["ticker"]),
        "market": row["market"],
        "is_preferred": bool(row["is_preferred"]),
        "is_active": bool(row["is_active"]),
        "source_created_at": _utc(row["created_at"]),
        "source_updated_at": _utc(row["updated_at"]),
        "raw_payload": {
            key: (value.isoformat() if isinstance(value, datetime) else value)
            for key, value in row.items()
        },
    }


def _map_price(row: dict, run_id: uuid.UUID) -> dict:
    return {
        "acquin_price_id": uuid.uuid4(),
        "acquin_import_run_id": run_id,
        "ticker": normalize_kospi_ticker(row["ticker"]),
        "price_date": row["date"],
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "adj_close": row["adj_close"],
        "volume": row["volume"],
        "trading_value": row["trading_value"],
        "market_cap": row["market_cap"],
        "shares_outstanding": row["shares_outstanding"],
        "return_1d": row["return_1d"],
        "source": row["source"],
        "freshness_state": row["freshness_state"],
        "source_created_at": _utc(row["created_at"]),
        "source_updated_at": _utc(row["updated_at"]),
    }


def _map_flow(row: dict, run_id: uuid.UUID) -> dict:
    return {
        "acquin_investor_flow_id": uuid.uuid4(),
        "acquin_import_run_id": run_id,
        "ticker": normalize_kospi_ticker(row["ticker"]),
        "flow_date": row["date"],
        "investor_group": row["investor_group"],
        "buy_volume": row["buy_volume"],
        "sell_volume": row["sell_volume"],
        "net_buy_volume": row["net_buy_volume"],
        "buy_amount": row["buy_amount"],
        "sell_amount": row["sell_amount"],
        "net_buy_amount": row["net_buy_amount"],
        "source": row["source"],
        "freshness_state": row["freshness_state"],
        "source_created_at": _utc(row["created_at"]),
        "source_updated_at": _utc(row["updated_at"]),
    }


def _map_holding(row: dict, run_id: uuid.UUID) -> dict:
    return {
        "acquin_foreign_holding_id": uuid.uuid4(),
        "acquin_import_run_id": run_id,
        "ticker": normalize_kospi_ticker(row["ticker"]),
        "holding_date": row["date"],
        "foreign_held_shares": row["foreign_held_shares"],
        "foreign_ownership_pct": row["foreign_ownership_pct"],
        "foreign_limit_shares": row["foreign_limit_shares"],
        "foreign_limit_exhaustion_pct": row["foreign_limit_exhaustion_pct"],
        "source": row["source"],
        "freshness_state": row["freshness_state"],
        "source_created_at": _utc(row["created_at"]),
        "source_updated_at": _utc(row["updated_at"]),
    }


def _map_index(row: dict, run_id: uuid.UUID) -> dict:
    return {
        "acquin_index_id": uuid.uuid4(),
        "acquin_import_run_id": run_id,
        "index_code": str(row["index_code"]).strip(),
        "index_date": row["date"],
        "name": row["name"],
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "return_1d": row["return_1d"],
        "source": row["source"],
        "freshness_state": row["freshness_state"],
        "source_created_at": _utc(row["created_at"]),
        "source_updated_at": _utc(row["updated_at"]),
    }


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        name="dim_stock",
        source_sql=(
            "select ticker, market, is_preferred, is_active, created_at, updated_at "
            "from dim_stock"
        ),
        model=models.AcquinStock,
        conflict_constraint="uq_acquin_stock_ticker",
        key_columns=("ticker",),
        update_columns=(
            "market",
            "is_preferred",
            "is_active",
            "source_created_at",
            "source_updated_at",
            "raw_payload",
            "acquin_import_run_id",
        ),
        map_row=_map_stock,
    ),
    TableSpec(
        name="fact_price_daily",
        source_sql=(
            "select ticker, date, open, high, low, close, adj_close, volume, trading_value, "
            "market_cap, shares_outstanding, return_1d, source, freshness_state, created_at, "
            "updated_at from fact_price_daily"
        ),
        model=models.AcquinPrice,
        conflict_constraint="uq_acquin_price_ticker_date",
        key_columns=("ticker", "price_date"),
        update_columns=(
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "trading_value",
            "market_cap",
            "shares_outstanding",
            "return_1d",
            "source",
            "freshness_state",
            "source_created_at",
            "source_updated_at",
            "acquin_import_run_id",
        ),
        map_row=_map_price,
    ),
    TableSpec(
        name="fact_investor_flow_daily",
        source_sql=(
            "select ticker, date, investor_group, buy_volume, sell_volume, net_buy_volume, "
            "buy_amount, sell_amount, net_buy_amount, source, freshness_state, created_at, "
            "updated_at from fact_investor_flow_daily"
        ),
        model=models.AcquinInvestorFlow,
        conflict_constraint="uq_acquin_investor_flow_ticker_date_group",
        key_columns=("ticker", "flow_date", "investor_group"),
        update_columns=(
            "buy_volume",
            "sell_volume",
            "net_buy_volume",
            "buy_amount",
            "sell_amount",
            "net_buy_amount",
            "source",
            "freshness_state",
            "source_created_at",
            "source_updated_at",
            "acquin_import_run_id",
        ),
        map_row=_map_flow,
    ),
    TableSpec(
        name="fact_foreign_holding_daily",
        source_sql=(
            "select ticker, date, foreign_held_shares, foreign_ownership_pct, "
            "foreign_limit_shares, foreign_limit_exhaustion_pct, source, freshness_state, "
            "created_at, updated_at from fact_foreign_holding_daily"
        ),
        model=models.AcquinForeignHolding,
        conflict_constraint="uq_acquin_foreign_holding_ticker_date",
        key_columns=("ticker", "holding_date"),
        update_columns=(
            "foreign_held_shares",
            "foreign_ownership_pct",
            "foreign_limit_shares",
            "foreign_limit_exhaustion_pct",
            "source",
            "freshness_state",
            "source_created_at",
            "source_updated_at",
            "acquin_import_run_id",
        ),
        map_row=_map_holding,
    ),
    TableSpec(
        name="fact_index_daily",
        source_sql=(
            "select index_code, date, name, open, high, low, close, return_1d, source, "
            "freshness_state, created_at, updated_at from fact_index_daily"
        ),
        model=models.AcquinIndex,
        conflict_constraint="uq_acquin_index_code_date",
        key_columns=("index_code", "index_date"),
        update_columns=(
            "name",
            "open",
            "high",
            "low",
            "close",
            "return_1d",
            "source",
            "freshness_state",
            "source_created_at",
            "source_updated_at",
            "acquin_import_run_id",
        ),
        map_row=_map_index,
    ),
)


@dataclass
class AcquinImportReport:
    run_id: uuid.UUID | None = None
    mode: str = "incremental"
    source_counts: dict[str, int] = field(default_factory=dict)
    imported_counts: dict[str, int] = field(default_factory=dict)
    skipped_rows: dict[str, int] = field(default_factory=dict)

    def render(self) -> str:
        lines = [
            "Acquin snapshot import report",
            f"  run_id={self.run_id}",
            f"  mode={self.mode}",
        ]
        for spec in TABLE_SPECS:
            lines.append(
                f"  {spec.name}: source={self.source_counts.get(spec.name, 0)} "
                f"imported={self.imported_counts.get(spec.name, 0)} "
                f"skipped={self.skipped_rows.get(spec.name, 0)}"
            )
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the Acquin KOSPI snapshot into staging")
    parser.add_argument("--tables", nargs="*", choices=[spec.name for spec in TABLE_SPECS])
    parser.add_argument("--full", action="store_true", help="Ignore the incremental high-water mark")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true", help="Count source rows without importing")
    args = parser.parse_args()

    report = import_acquin_snapshot(
        tables=args.tables,
        full=args.full,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    print(report.render())


def import_acquin_snapshot(
    *,
    tables: list[str] | None = None,
    full: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> AcquinImportReport:
    require_confirmed_production_source(
        source_name="acquin_pykrx",
        env_var="ACQUIN_PYKRX_PRODUCTION_LICENSE_CONFIRMED",
    )
    ensure_pilot_kospi_database_url()
    source_url = load_acquin_db_url()
    selected = [spec for spec in TABLE_SPECS if tables is None or spec.name in tables]
    mode = "dry_run" if dry_run else ("full" if full else "incremental")
    report = AcquinImportReport(mode=mode)

    run_id = uuid.uuid4()
    report.run_id = run_id
    with session_scope() as session:
        session.add(
            models.AcquinImportRun(
                acquin_import_run_id=run_id,
                mode=mode,
                source_database_fingerprint=_fingerprint(source_url),
                status="dry_run" if dry_run else "running",
                started_at=datetime.now(timezone.utc),
            )
        )

    try:
        with psycopg.connect(source_url, connect_timeout=30) as source_conn:
            source_conn.read_only = True
            for spec in selected:
                since = None if full else _high_water_mark(spec)
                where_sql, params = _since_clause(since)
                with source_conn.cursor() as count_cur:
                    count_cur.execute(
                        f"select count(*) from ({spec.source_sql}) src {where_sql}", params
                    )
                    report.source_counts[spec.name] = int(count_cur.fetchone()[0])
                if dry_run:
                    continue
                imported, skipped = _import_table(
                    source_conn=source_conn,
                    spec=spec,
                    run_id=run_id,
                    where_sql=where_sql,
                    params=params,
                    batch_size=batch_size,
                )
                report.imported_counts[spec.name] = imported
                report.skipped_rows[spec.name] = skipped
    except Exception as exc:
        _finish_run(run_id=run_id, status="failed", report=report, error=str(exc))
        raise

    _finish_run(run_id=run_id, status="dry_run" if dry_run else "completed", report=report, error=None)
    return report


def _import_table(
    *,
    source_conn,
    spec: TableSpec,
    run_id: uuid.UUID,
    where_sql: str,
    params: tuple,
    batch_size: int,
) -> tuple[int, int]:
    imported = 0
    skipped = 0
    cursor_name = f"acquin_import_{spec.name}"
    with source_conn.cursor(name=cursor_name) as cur:
        cur.itersize = batch_size
        cur.execute(f"select * from ({spec.source_sql}) src {where_sql} order by updated_at", params)
        columns = [desc.name for desc in cur.description]
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            mapped: list[dict] = []
            for raw in rows:
                row = dict(zip(columns, raw))
                if not str(row.get("ticker") or row.get("index_code") or "").strip():
                    skipped += 1
                    _record_issue(
                        run_id=run_id,
                        issue_type="missing_source_key",
                        source_table=spec.name,
                        details={"row": {k: str(v) for k, v in row.items()}},
                    )
                    continue
                mapped.append(spec.map_row(row, run_id))
            if mapped:
                _upsert_batch(spec=spec, mapped=mapped)
                imported += len(mapped)
    return imported, skipped


def _upsert_batch(*, spec: TableSpec, mapped: list[dict]) -> None:
    stmt = insert(spec.model)
    stmt = stmt.on_conflict_do_update(
        constraint=spec.conflict_constraint,
        set_={column: getattr(stmt.excluded, column) for column in spec.update_columns},
    )
    with session_scope() as session:
        session.execute(stmt, mapped)


def _high_water_mark(spec: TableSpec):
    from sqlalchemy import func, select

    with session_scope() as session:
        return session.execute(select(func.max(spec.model.source_updated_at))).scalar_one_or_none()


def _since_clause(since) -> tuple[str, tuple]:
    if since is None:
        return "", ()
    # Inclusive: a crash mid-batch can leave other source rows sharing the
    # high-water timestamp unimported; re-pulling them is safe (upsert).
    return "where src.updated_at >= %s", (since,)


def _record_issue(*, run_id: uuid.UUID, issue_type: str, source_table: str, details: dict) -> None:
    with session_scope() as session:
        session.add(
            models.AcquinValidationIssue(
                acquin_validation_issue_id=uuid.uuid4(),
                acquin_import_run_id=run_id,
                severity="warning",
                issue_type=issue_type,
                source_table=source_table,
                source_key=None,
                resolution_status="open",
                details=details,
                created_at=datetime.now(timezone.utc),
            )
        )


def _finish_run(*, run_id: uuid.UUID, status: str, report: AcquinImportReport, error: str | None) -> None:
    with session_scope() as session:
        run = session.get(models.AcquinImportRun, run_id)
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.source_counts = dict(report.source_counts)
        run.imported_counts = dict(report.imported_counts)
        run.error_payload = {"error": error} if error else None


def _fingerprint(url: str) -> str:
    parsed = urlparse(url)
    basis = f"{parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


if __name__ == "__main__":
    main()

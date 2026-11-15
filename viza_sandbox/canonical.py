"""Read-only view onto the canonical ``attribution`` database for the sandbox.

Later tasks materialize these frames into Parquet panels, so the column names
and dtypes produced here are contracts consumed downstream. See
``CanonicalSource`` for the protocol both implementations satisfy.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Protocol

import polars as pl
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Engine,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    select,
    text,
)

_metadata = MetaData()

security_t = Table(
    "security",
    _metadata,
    Column("security_id", String, primary_key=True),
    Column("company_id", String, nullable=False),
    Column("exchange", String, nullable=False),
    Column("active_from", DateTime(timezone=True), nullable=False),
    Column("active_to", DateTime(timezone=True)),
)

security_ticker_history_t = Table(
    "security_ticker_history",
    _metadata,
    Column("ticker_history_id", String, primary_key=True),
    Column("security_id", String, nullable=False),
    Column("ticker", String, nullable=False),
    Column("active_from", DateTime(timezone=True), nullable=False),
    Column("active_to", DateTime(timezone=True)),
)

faustcalc_company_t = Table(
    "faustcalc_company",
    _metadata,
    Column("faustcalc_company_id", String, primary_key=True),
    Column("source_ticker", String, nullable=False),
    Column("canonical_ticker", String, nullable=False),
    Column("sector", String),
    Column("industry", String),
    Column("source_last_updated", DateTime(timezone=True)),
)

price_bar_t = Table(
    "price_bar",
    _metadata,
    Column("price_bar_id", String, primary_key=True),
    Column("security_id", String, nullable=False),
    Column("event_time", DateTime(timezone=True), primary_key=True),
    Column("ingestion_time", DateTime(timezone=True), nullable=False),
    Column("timestamp_available", DateTime(timezone=True), nullable=False),
    Column("close", Numeric(18, 6), nullable=False),
    Column("adjusted_close", Numeric(18, 6), nullable=False),
    Column("volume", BigInteger),
    Column("currency", String, nullable=False),
    Column("source", String, nullable=False),
)


def _as_utc(value: datetime | None) -> datetime | None:
    """Treat naive datetimes as UTC (SQLite loses tzinfo on round-trip)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


SECURITIES_SCHEMA = {
    "security_id": pl.Utf8,
    "ticker": pl.Utf8,
    "exchange": pl.Utf8,
    "currency": pl.Utf8,
    "sector": pl.Utf8,
    "industry": pl.Utf8,
    "classification_as_of": pl.Datetime("us", "UTC"),
}

PRICE_BARS_SCHEMA = {
    "security_id": pl.Utf8,
    "event_date": pl.Date,
    "close": pl.Float64,
    "adjusted_close": pl.Float64,
    "volume": pl.Int64,
    "currency": pl.Utf8,
    "ingestion_time": pl.Datetime("us", "UTC"),
}


class CanonicalSource(Protocol):
    def securities(self) -> pl.DataFrame: ...

    def price_bars(
        self, start: date, end: date, *, source: str = "faustcalc_fmp_snapshot"
    ) -> pl.DataFrame: ...

    def snapshot_id(self, *, source: str = "faustcalc_fmp_snapshot") -> str: ...


def _empty_securities() -> pl.DataFrame:
    return pl.DataFrame(schema=SECURITIES_SCHEMA)


def _empty_price_bars() -> pl.DataFrame:
    return pl.DataFrame(schema=PRICE_BARS_SCHEMA)


def _security_record(row: Any) -> dict[str, Any]:
    """Build one `securities()` record from a row mapping.

    `security_id` is cast to ``str`` because PostgreSQL returns native
    ``uuid.UUID`` objects for the UUID-typed canonical column, while the
    frame's column is declared ``Utf8``.
    """
    return {
        "security_id": str(row["security_id"]),
        "ticker": row["ticker"],
        "exchange": row["exchange"],
        "currency": "USD",
        "sector": row["sector"],
        "industry": row["industry"],
        "classification_as_of": _as_utc(row["source_last_updated"]),
    }


def _price_bar_record(row: Any) -> dict[str, Any]:
    """Build one `price_bars()` record from a row mapping.

    `security_id` is cast to ``str`` for the same reason as in
    `_security_record`.
    """
    event_time = _as_utc(row["event_time"])
    return {
        "security_id": str(row["security_id"]),
        "event_date": event_time.date(),
        "close": float(row["close"]),
        "adjusted_close": float(row["adjusted_close"]),
        "volume": int(row["volume"]) if row["volume"] is not None else None,
        "currency": row["currency"],
        "ingestion_time": _as_utc(row["ingestion_time"]),
    }


class InMemoryCanonicalSource:
    """Fixture-backed ``CanonicalSource`` for tests and local development."""

    def __init__(self, securities: pl.DataFrame, price_bars: pl.DataFrame) -> None:
        self._securities = securities
        self._price_bars = price_bars

    def securities(self) -> pl.DataFrame:
        return self._securities

    def price_bars(
        self, start: date, end: date, *, source: str = "faustcalc_fmp_snapshot"
    ) -> pl.DataFrame:
        frame = self._price_bars
        if "source" in frame.columns:
            frame = frame.filter(pl.col("source") == source)
        return frame.filter(
            (pl.col("event_date") >= start) & (pl.col("event_date") <= end)
        )

    def snapshot_id(self, *, source: str = "faustcalc_fmp_snapshot") -> str:
        frame = self._price_bars
        if "source" in frame.columns:
            frame = frame.filter(pl.col("source") == source)
        if frame.is_empty() or "ingestion_time" not in frame.columns:
            return "empty"
        max_time = frame["ingestion_time"].max()
        if max_time is None:
            return "empty"
        utc_time = _as_utc(max_time)
        return utc_time.isoformat()


class PostgresCanonicalSource:
    """SQLAlchemy-Core-backed ``CanonicalSource`` against the canonical database."""

    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url)

    def _connect_read_only(self):
        conn = self._engine.connect()
        if self._engine.dialect.name == "postgresql":
            conn.execute(text("SET TRANSACTION READ ONLY"))
        return conn

    def securities(self) -> pl.DataFrame:
        query = (
            select(
                security_t.c.security_id,
                security_ticker_history_t.c.ticker,
                security_t.c.exchange,
                faustcalc_company_t.c.sector,
                faustcalc_company_t.c.industry,
                faustcalc_company_t.c.source_last_updated,
            )
            .select_from(security_t)
            .join(
                security_ticker_history_t,
                (security_ticker_history_t.c.security_id == security_t.c.security_id)
                & (security_ticker_history_t.c.active_to.is_(None)),
            )
            .outerjoin(
                faustcalc_company_t,
                faustcalc_company_t.c.canonical_ticker == security_ticker_history_t.c.ticker,
            )
        )
        with self._connect_read_only() as conn:
            rows = conn.execute(query).mappings().all()

        if not rows:
            return _empty_securities()

        records = [_security_record(row) for row in rows]
        return pl.DataFrame(records, schema=SECURITIES_SCHEMA)

    def price_bars(
        self, start: date, end: date, *, source: str = "faustcalc_fmp_snapshot"
    ) -> pl.DataFrame:
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        query = select(
            price_bar_t.c.security_id,
            price_bar_t.c.event_time,
            price_bar_t.c.close,
            price_bar_t.c.adjusted_close,
            price_bar_t.c.volume,
            price_bar_t.c.currency,
            price_bar_t.c.ingestion_time,
        ).where(
            price_bar_t.c.source == source,
            price_bar_t.c.event_time >= start_dt,
            price_bar_t.c.event_time <= end_dt,
        )
        with self._connect_read_only() as conn:
            rows = conn.execute(query).mappings().all()

        if not rows:
            return _empty_price_bars()

        records = [_price_bar_record(row) for row in rows]
        return pl.DataFrame(records, schema=PRICE_BARS_SCHEMA)

    def snapshot_id(self, *, source: str = "faustcalc_fmp_snapshot") -> str:
        query = select(price_bar_t.c.ingestion_time).where(price_bar_t.c.source == source)
        with self._connect_read_only() as conn:
            rows = [row[0] for row in conn.execute(query).all()]
        if not rows:
            return "empty"
        max_time = max(_as_utc(value) for value in rows)
        return max_time.isoformat()

    def create_tables_for_tests(self) -> None:
        if self._engine.dialect.name == "postgresql":
            raise RuntimeError("create_tables_for_tests is not permitted against postgresql")
        _metadata.create_all(self._engine)

    def insert_for_tests(self, table: Table, rows: list[dict[str, Any]]) -> None:
        if self._engine.dialect.name == "postgresql":
            raise RuntimeError("insert_for_tests is not permitted against postgresql")
        with self._engine.begin() as conn:
            conn.execute(table.insert(), rows)

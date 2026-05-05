from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260503_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.create_table(
        "company",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cik", sa.String(length=20), nullable=True),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id"),
        sa.UniqueConstraint("cik"),
    )
    op.create_table(
        "security",
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("figi", sa.String(length=32), nullable=True),
        sa.Column("isin", sa.String(length=16), nullable=True),
        sa.Column("cusip", sa.String(length=16), nullable=True),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("share_class", sa.String(length=64), nullable=True),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.company_id"]),
        sa.PrimaryKeyConstraint("security_id"),
        sa.UniqueConstraint("cusip"),
        sa.UniqueConstraint("figi"),
        sa.UniqueConstraint("isin"),
    )
    op.create_table(
        "security_ticker_history",
        sa.Column("ticker_history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("ticker_history_id"),
        sa.UniqueConstraint("security_id", "ticker", "active_from", name="uq_ticker_history"),
    )
    op.create_index(
        "ix_ticker_history_ticker_dates",
        "security_ticker_history",
        ["ticker", "active_from", "active_to"],
    )
    op.create_table(
        "price_bar",
        sa.Column("price_bar_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("open", sa.Numeric(18, 6), nullable=True),
        sa.Column("high", sa.Numeric(18, 6), nullable=True),
        sa.Column("low", sa.Numeric(18, 6), nullable=True),
        sa.Column("close", sa.Numeric(18, 6), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(18, 6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("adjusted_close > 0", name="ck_price_bar_adjusted_close_positive"),
        sa.CheckConstraint("close > 0", name="ck_price_bar_close_positive"),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("price_bar_id", "event_time"),
        sa.UniqueConstraint("security_id", "event_time", "source", name="uq_price_bar_source_time"),
    )
    op.create_index("ix_price_bar_available", "price_bar", ["security_id", "timestamp_available"])
    op.create_index("ix_price_bar_security_time", "price_bar", ["security_id", "event_time"])
    op.create_table(
        "factor_return",
        sa.Column("factor_return_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("factor_name", sa.String(length=128), nullable=False),
        sa.Column("factor_family", sa.String(length=64), nullable=False),
        sa.Column("return_bps", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("factor_return_id", "event_time"),
        sa.UniqueConstraint("factor_name", "event_time", "source", name="uq_factor_return_source_time"),
    )
    op.create_index("ix_factor_return_available", "factor_return", ["factor_name", "timestamp_available"])
    op.create_index("ix_factor_return_name_time", "factor_return", ["factor_name", "event_time"])
    op.create_table(
        "macro_series",
        sa.Column("macro_series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("series_name", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Numeric(24, 8), nullable=False),
        sa.Column("vintage", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("macro_series_id", "event_time"),
        sa.UniqueConstraint("series_name", "event_time", "vintage", name="uq_macro_series_vintage"),
    )
    op.create_index("ix_macro_series_available", "macro_series", ["series_name", "timestamp_available"])
    op.create_index("ix_macro_series_name_time", "macro_series", ["series_name", "event_time"])
    op.create_table(
        "event",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("payload_uri", sa.Text(), nullable=True),
        sa.Column("structured_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.company_id"]),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("source", "source_id", name="uq_event_source_id"),
    )
    op.create_index("ix_event_company_available", "event", ["company_id", "timestamp_available"])
    op.create_index("ix_event_security_available", "event", ["security_id", "timestamp_available"])
    op.create_table(
        "company_exposure",
        sa.Column("company_exposure_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exposure_name", sa.String(length=128), nullable=False),
        sa.Column("exposure_value", sa.Numeric(18, 8), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("evidence_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.company_id"]),
        sa.ForeignKeyConstraint(["evidence_event_id"], ["event.event_id"]),
        sa.PrimaryKeyConstraint("company_exposure_id"),
    )
    op.create_index(
        "ix_company_exposure_company_available",
        "company_exposure",
        ["company_id", "timestamp_available"],
    )
    op.create_table(
        "attribution_run",
        sa.Column("attribution_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attribution_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_return_bps", sa.Numeric(18, 6), nullable=False),
        sa.Column("unexplained_residual_bps", sa.Numeric(18, 6), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("data_version", sa.String(length=64), nullable=False),
        sa.Column("factor_basket_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("attribution_run_id"),
    )
    op.create_index("ix_attribution_run_security_window", "attribution_run", ["security_id", "window_end"])
    op.create_table(
        "attribution_contribution",
        sa.Column("attribution_contribution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attribution_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("contribution_bps", sa.Numeric(18, 6), nullable=False),
        sa.Column("share_of_move", sa.Numeric(18, 8), nullable=True),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["attribution_run_id"], ["attribution_run.attribution_run_id"]),
        sa.PrimaryKeyConstraint("attribution_contribution_id"),
    )
    op.create_index(
        "ix_attribution_contribution_run",
        "attribution_contribution",
        ["attribution_run_id"],
    )
    op.execute("SELECT create_hypertable('price_bar', 'event_time', if_not_exists => TRUE)")
    op.execute("SELECT create_hypertable('factor_return', 'event_time', if_not_exists => TRUE)")
    op.execute("SELECT create_hypertable('macro_series', 'event_time', if_not_exists => TRUE)")


def downgrade() -> None:
    op.drop_table("attribution_contribution")
    op.drop_table("attribution_run")
    op.drop_table("company_exposure")
    op.drop_table("event")
    op.drop_table("macro_series")
    op.drop_table("factor_return")
    op.drop_table("price_bar")
    op.drop_table("security_ticker_history")
    op.drop_table("security")
    op.drop_table("company")

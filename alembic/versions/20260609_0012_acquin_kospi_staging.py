from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260609_0012"
down_revision = "20260504_0011"
branch_labels = None
depends_on = None


JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "acquin_import_run",
        sa.Column("acquin_import_run_id", UUID, nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("source_database_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_counts", JSONB, nullable=True),
        sa.Column("imported_counts", JSONB, nullable=True),
        sa.Column("error_payload", JSONB, nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'dry_run')",
            name="ck_acquin_import_run_status",
        ),
        sa.PrimaryKeyConstraint("acquin_import_run_id"),
    )
    op.create_index(
        "ix_acquin_import_run_status_started",
        "acquin_import_run",
        ["status", "started_at"],
    )

    op.create_table(
        "acquin_validation_issue",
        sa.Column("acquin_validation_issue_id", UUID, nullable=False),
        sa.Column("acquin_import_run_id", UUID, nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("issue_type", sa.String(length=128), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=True),
        sa.Column("source_key", sa.Text(), nullable=True),
        sa.Column("resolution_status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("severity IN ('info', 'warning', 'error')", name="ck_acquin_issue_severity"),
        sa.CheckConstraint(
            "resolution_status IN ('open', 'resolved')",
            name="ck_acquin_issue_resolution_status",
        ),
        sa.ForeignKeyConstraint(["acquin_import_run_id"], ["acquin_import_run.acquin_import_run_id"]),
        sa.PrimaryKeyConstraint("acquin_validation_issue_id"),
    )
    op.create_index(
        "ix_acquin_validation_issue_run",
        "acquin_validation_issue",
        ["acquin_import_run_id", "severity"],
    )
    op.create_index(
        "ix_acquin_validation_issue_open",
        "acquin_validation_issue",
        ["issue_type", "resolution_status", "source_key"],
    )

    op.create_table(
        "acquin_stock",
        sa.Column("acquin_stock_id", UUID, nullable=False),
        sa.Column("acquin_import_run_id", UUID, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("is_preferred", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["acquin_import_run_id"], ["acquin_import_run.acquin_import_run_id"]),
        sa.PrimaryKeyConstraint("acquin_stock_id"),
        sa.UniqueConstraint("ticker", name="uq_acquin_stock_ticker"),
    )

    op.create_table(
        "acquin_price",
        sa.Column("acquin_price_id", UUID, nullable=False),
        sa.Column("acquin_import_run_id", UUID, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("adj_close", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("trading_value", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("shares_outstanding", sa.Float(), nullable=True),
        sa.Column("return_1d", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["acquin_import_run_id"], ["acquin_import_run.acquin_import_run_id"]),
        sa.PrimaryKeyConstraint("acquin_price_id"),
        sa.UniqueConstraint("ticker", "price_date", name="uq_acquin_price_ticker_date"),
    )
    op.create_index("ix_acquin_price_date", "acquin_price", ["price_date"])

    op.create_table(
        "acquin_investor_flow",
        sa.Column("acquin_investor_flow_id", UUID, nullable=False),
        sa.Column("acquin_import_run_id", UUID, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("flow_date", sa.Date(), nullable=False),
        sa.Column("investor_group", sa.String(length=32), nullable=False),
        sa.Column("buy_volume", sa.Float(), nullable=True),
        sa.Column("sell_volume", sa.Float(), nullable=True),
        sa.Column("net_buy_volume", sa.Float(), nullable=True),
        sa.Column("buy_amount", sa.Float(), nullable=True),
        sa.Column("sell_amount", sa.Float(), nullable=True),
        sa.Column("net_buy_amount", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["acquin_import_run_id"], ["acquin_import_run.acquin_import_run_id"]),
        sa.PrimaryKeyConstraint("acquin_investor_flow_id"),
        sa.UniqueConstraint(
            "ticker", "flow_date", "investor_group", name="uq_acquin_investor_flow_ticker_date_group"
        ),
    )
    op.create_index(
        "ix_acquin_investor_flow_ticker_date",
        "acquin_investor_flow",
        ["ticker", "flow_date"],
    )

    op.create_table(
        "acquin_foreign_holding",
        sa.Column("acquin_foreign_holding_id", UUID, nullable=False),
        sa.Column("acquin_import_run_id", UUID, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("holding_date", sa.Date(), nullable=False),
        sa.Column("foreign_held_shares", sa.Float(), nullable=True),
        sa.Column("foreign_ownership_pct", sa.Float(), nullable=True),
        sa.Column("foreign_limit_shares", sa.Float(), nullable=True),
        sa.Column("foreign_limit_exhaustion_pct", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["acquin_import_run_id"], ["acquin_import_run.acquin_import_run_id"]),
        sa.PrimaryKeyConstraint("acquin_foreign_holding_id"),
        sa.UniqueConstraint("ticker", "holding_date", name="uq_acquin_foreign_holding_ticker_date"),
    )
    op.create_index(
        "ix_acquin_foreign_holding_ticker_date",
        "acquin_foreign_holding",
        ["ticker", "holding_date"],
    )

    op.create_table(
        "acquin_index",
        sa.Column("acquin_index_id", UUID, nullable=False),
        sa.Column("acquin_import_run_id", UUID, nullable=False),
        sa.Column("index_code", sa.String(length=32), nullable=False),
        sa.Column("index_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("return_1d", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["acquin_import_run_id"], ["acquin_import_run.acquin_import_run_id"]),
        sa.PrimaryKeyConstraint("acquin_index_id"),
        sa.UniqueConstraint("index_code", "index_date", name="uq_acquin_index_code_date"),
    )
    op.create_index("ix_acquin_index_date", "acquin_index", ["index_code", "index_date"])


def downgrade() -> None:
    op.drop_table("acquin_index")
    op.drop_table("acquin_foreign_holding")
    op.drop_table("acquin_investor_flow")
    op.drop_table("acquin_price")
    op.drop_table("acquin_stock")
    op.drop_table("acquin_validation_issue")
    op.drop_table("acquin_import_run")

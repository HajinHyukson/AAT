from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260504_0011"
down_revision = "20260504_0010"
branch_labels = None
depends_on = None


JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "model_universe_member",
        sa.Column("model_universe_member_id", UUID, nullable=False),
        sa.Column("universe_name", sa.String(length=128), nullable=False),
        sa.Column("universe_version", sa.String(length=64), nullable=False),
        sa.Column("security_id", UUID, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_asset_id", UUID, nullable=True),
        sa.Column("eligibility_status", sa.String(length=32), nullable=False),
        sa.Column("first_price_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_price_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price_bar_count", sa.BigInteger(), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.ForeignKeyConstraint(["source_asset_id"], ["faustcalc_asset.faustcalc_asset_id"]),
        sa.PrimaryKeyConstraint("model_universe_member_id"),
        sa.UniqueConstraint(
            "universe_name",
            "universe_version",
            "security_id",
            name="uq_model_universe_member_security",
        ),
    )
    op.create_index(
        "ix_model_universe_member_universe_status",
        "model_universe_member",
        ["universe_name", "universe_version", "eligibility_status", "ticker"],
    )
    op.create_index(
        "ix_model_universe_member_security",
        "model_universe_member",
        ["security_id", "universe_name"],
    )

    op.create_table(
        "attribution_backfill_task",
        sa.Column("attribution_backfill_task_id", UUID, nullable=False),
        sa.Column("backfill_run_id", UUID, nullable=False),
        sa.Column("universe_name", sa.String(length=128), nullable=False),
        sa.Column("universe_version", sa.String(length=64), nullable=False),
        sa.Column("security_id", UUID, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expected_windows", sa.Integer(), nullable=False),
        sa.Column("ran_windows", sa.Integer(), nullable=False),
        sa.Column("skipped_windows", sa.Integer(), nullable=False),
        sa.Column("last_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cadence IN ('daily', 'weekly', 'monthly')", name="ck_backfill_task_cadence"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'skipped', 'failed')",
            name="ck_backfill_task_status",
        ),
        sa.ForeignKeyConstraint(["backfill_run_id"], ["backfill_run.backfill_run_id"]),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("attribution_backfill_task_id"),
        sa.UniqueConstraint(
            "backfill_run_id",
            "security_id",
            "cadence",
            name="uq_attribution_backfill_task_run_security",
        ),
    )
    op.create_index(
        "ix_attribution_backfill_task_status",
        "attribution_backfill_task",
        ["backfill_run_id", "status", "cadence"],
    )
    op.create_index(
        "ix_attribution_backfill_task_security",
        "attribution_backfill_task",
        ["security_id", "cadence"],
    )

    op.create_table(
        "security_attribution_summary",
        sa.Column("security_attribution_summary_id", UUID, nullable=False),
        sa.Column("universe_name", sa.String(length=128), nullable=False),
        sa.Column("universe_version", sa.String(length=64), nullable=False),
        sa.Column("security_id", UUID, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("latest_run_id", UUID, nullable=True),
        sa.Column("latest_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_observed_return_bps", sa.Numeric(18, 6), nullable=True),
        sa.Column("latest_residual_bps", sa.Numeric(18, 6), nullable=True),
        sa.Column("latest_price_change_usd", sa.Numeric(18, 6), nullable=True),
        sa.Column("top_driver", sa.String(length=255), nullable=True),
        sa.Column("top_driver_confidence", sa.String(length=32), nullable=True),
        sa.Column("contribution_count", sa.Integer(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("run_status", sa.String(length=32), nullable=False),
        sa.Column("first_price_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_price_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price_bar_count", sa.BigInteger(), nullable=False),
        sa.Column("coverage_payload", JSONB, nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("run_status IN ('available', 'missing')", name="ck_security_attr_summary_status"),
        sa.ForeignKeyConstraint(["company_id"], ["company.company_id"]),
        sa.ForeignKeyConstraint(["latest_run_id"], ["attribution_run.attribution_run_id"]),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("security_attribution_summary_id"),
        sa.UniqueConstraint(
            "universe_name",
            "universe_version",
            "security_id",
            name="uq_security_attribution_summary_universe",
        ),
    )
    op.create_index(
        "ix_security_attribution_summary_universe_status",
        "security_attribution_summary",
        ["universe_name", "universe_version", "run_status", "ticker"],
    )
    op.create_index(
        "ix_security_attribution_summary_latest",
        "security_attribution_summary",
        ["universe_name", "latest_window_end"],
    )

    op.create_index(
        "ix_price_bar_security_time_available",
        "price_bar",
        ["security_id", "event_time", "timestamp_available"],
    )
    op.create_index(
        "ix_attribution_run_security_cadence_latest",
        "attribution_run",
        ["security_id", "cadence", "window_end", "created_at"],
    )
    op.create_index(
        "ix_ticker_history_active_ticker",
        "security_ticker_history",
        ["ticker"],
        postgresql_where=sa.text("active_to IS NULL"),
    )
    op.create_index(
        "ix_faustcalc_asset_universe_eligibility",
        "faustcalc_asset",
        ["asset_type", "currency", "is_active", "canonical_ticker"],
    )


def downgrade() -> None:
    op.drop_index("ix_faustcalc_asset_universe_eligibility", table_name="faustcalc_asset")
    op.drop_index("ix_ticker_history_active_ticker", table_name="security_ticker_history")
    op.drop_index("ix_attribution_run_security_cadence_latest", table_name="attribution_run")
    op.drop_index("ix_price_bar_security_time_available", table_name="price_bar")
    op.drop_index("ix_security_attribution_summary_latest", table_name="security_attribution_summary")
    op.drop_index(
        "ix_security_attribution_summary_universe_status",
        table_name="security_attribution_summary",
    )
    op.drop_table("security_attribution_summary")
    op.drop_index("ix_attribution_backfill_task_security", table_name="attribution_backfill_task")
    op.drop_index("ix_attribution_backfill_task_status", table_name="attribution_backfill_task")
    op.drop_table("attribution_backfill_task")
    op.drop_index("ix_model_universe_member_security", table_name="model_universe_member")
    op.drop_index("ix_model_universe_member_universe_status", table_name="model_universe_member")
    op.drop_table("model_universe_member")

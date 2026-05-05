from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260504_0006"
down_revision = "20260504_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attribution_run",
        sa.Column("cadence", sa.String(length=16), nullable=False, server_default="daily"),
    )
    op.create_check_constraint(
        "ck_attribution_run_cadence",
        "attribution_run",
        "cadence IN ('daily', 'weekly', 'monthly')",
    )
    op.drop_constraint("uq_attribution_run_window_model", "attribution_run", type_="unique")
    op.create_unique_constraint(
        "uq_attribution_run_window_model",
        "attribution_run",
        [
            "security_id",
            "window_start",
            "window_end",
            "model_version",
            "factor_basket_version",
            "cadence",
        ],
    )

    op.create_table(
        "backfill_run",
        sa.Column("backfill_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config_version", sa.String(length=64), nullable=False),
        sa.Column("analysis_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analysis_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cadences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("coverage_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_backfill_run_status"),
        sa.PrimaryKeyConstraint("backfill_run_id"),
    )
    op.create_index("ix_backfill_run_status_started", "backfill_run", ["status", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_backfill_run_status_started", table_name="backfill_run")
    op.drop_table("backfill_run")

    op.drop_constraint("uq_attribution_run_window_model", "attribution_run", type_="unique")
    op.create_unique_constraint(
        "uq_attribution_run_window_model",
        "attribution_run",
        [
            "security_id",
            "window_start",
            "window_end",
            "model_version",
            "factor_basket_version",
        ],
    )
    op.drop_constraint("ck_attribution_run_cadence", "attribution_run", type_="check")
    op.drop_column("attribution_run", "cadence")

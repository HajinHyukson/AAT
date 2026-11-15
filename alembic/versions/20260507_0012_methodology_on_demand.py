from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260507_0012"
down_revision = "20260504_0011"
branch_labels = None
depends_on = None


JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    methodology_table = op.create_table(
        "attribution_methodology",
        sa.Column("methodology", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("factor_basket_version", sa.String(length=64), nullable=False),
        sa.Column("supported_cadences", JSONB, nullable=False),
        sa.Column("runner_config", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_attribution_methodology_status"),
        sa.PrimaryKeyConstraint("methodology"),
    )
    op.create_index(
        "ix_attribution_methodology_default",
        "attribution_methodology",
        ["is_default"],
        postgresql_where=sa.text("is_default IS TRUE"),
    )
    op.bulk_insert(
        methodology_table,
        [
            {
                "methodology": "legacy",
                "display_name": "Legacy Baseline",
                "status": "archived",
                "is_default": False,
                "model_version": "factor-baseline-v0",
                "factor_basket_version": "mvp_expanded_v0",
                "supported_cadences": ["daily", "weekly", "monthly"],
                "runner_config": {
                    "use_expanded_mvp": True,
                    "include_event_evidence": True,
                    "lookback_days": 252,
                },
                "created_at": now,
                "updated_at": now,
            },
            {
                "methodology": "residual_safety_v1",
                "display_name": "Residual Safety v1",
                "status": "active",
                "is_default": True,
                "model_version": "factor-baseline-residual-safety-v1",
                "factor_basket_version": "mvp_expanded_residual_safety_v1",
                "supported_cadences": ["daily", "weekly", "monthly"],
                "runner_config": {
                    "use_expanded_mvp": True,
                    "include_event_evidence": True,
                    "lookback_days": 252,
                },
                "created_at": now,
                "updated_at": now,
            },
            {
                "methodology": "hierarchical_market_first_v1",
                "display_name": "Hierarchical Market First v1",
                "status": "active",
                "is_default": False,
                "model_version": "factor-baseline-hierarchical-market-v1",
                "factor_basket_version": "mvp_expanded_hierarchical_market_v1",
                "supported_cadences": ["daily", "weekly", "monthly"],
                "runner_config": {
                    "use_expanded_mvp": True,
                    "include_event_evidence": True,
                    "lookback_days": 252,
                },
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    op.execute(
        """
        INSERT INTO attribution_methodology (
            methodology,
            display_name,
            status,
            is_default,
            model_version,
            factor_basket_version,
            supported_cadences,
            runner_config,
            created_at,
            updated_at
        )
        SELECT DISTINCT
            'archived_' || substr(md5(model_version || ':' || factor_basket_version), 1, 16),
            model_version || ' / ' || factor_basket_version,
            'archived',
            FALSE,
            model_version,
            factor_basket_version,
            jsonb_build_array('daily', 'weekly', 'monthly'),
            jsonb_build_object(
                'use_expanded_mvp', true,
                'include_event_evidence', true,
                'lookback_days', 252,
                'readonly_archive', true
            ),
            now(),
            now()
        FROM attribution_run
        WHERE NOT (
            (model_version = 'factor-baseline-v0' AND factor_basket_version = 'mvp_expanded_v0')
            OR (
                model_version = 'factor-baseline-residual-safety-v1'
                AND factor_basket_version = 'mvp_expanded_residual_safety_v1'
            )
            OR (
                model_version = 'factor-baseline-hierarchical-market-v1'
                AND factor_basket_version = 'mvp_expanded_hierarchical_market_v1'
            )
        )
        ON CONFLICT (methodology) DO NOTHING
        """
    )

    op.add_column("attribution_run", sa.Column("methodology", sa.String(length=64), nullable=True))
    op.execute(
        """
        UPDATE attribution_run
        SET methodology = CASE
            WHEN model_version = 'factor-baseline-residual-safety-v1'
             AND factor_basket_version = 'mvp_expanded_residual_safety_v1'
                THEN 'residual_safety_v1'
            WHEN model_version = 'factor-baseline-hierarchical-market-v1'
             AND factor_basket_version = 'mvp_expanded_hierarchical_market_v1'
                THEN 'hierarchical_market_first_v1'
            WHEN model_version = 'factor-baseline-v0'
             AND factor_basket_version = 'mvp_expanded_v0'
                THEN 'legacy'
            ELSE 'archived_' || substr(md5(model_version || ':' || factor_basket_version), 1, 16)
        END
        """
    )
    op.alter_column("attribution_run", "methodology", nullable=False)
    op.create_foreign_key(
        "fk_attribution_run_methodology",
        "attribution_run",
        "attribution_methodology",
        ["methodology"],
        ["methodology"],
    )
    op.drop_constraint("uq_attribution_run_window_model", "attribution_run", type_="unique")
    op.create_unique_constraint(
        "uq_attribution_run_window_model",
        "attribution_run",
        ["security_id", "window_start", "window_end", "cadence", "methodology"],
    )
    op.create_index(
        "ix_attribution_run_security_methodology_latest",
        "attribution_run",
        ["security_id", "methodology", "cadence", "window_end", "created_at"],
    )

    op.add_column(
        "security_attribution_summary",
        sa.Column("methodology", sa.String(length=64), nullable=False, server_default="residual_safety_v1"),
    )
    op.execute(
        """
        UPDATE security_attribution_summary AS summary
        SET methodology = run.methodology
        FROM attribution_run AS run
        WHERE summary.latest_run_id = run.attribution_run_id
        """
    )
    op.alter_column("security_attribution_summary", "methodology", server_default=None)
    op.create_foreign_key(
        "fk_security_attribution_summary_methodology",
        "security_attribution_summary",
        "attribution_methodology",
        ["methodology"],
        ["methodology"],
    )
    op.drop_constraint(
        "uq_security_attribution_summary_universe",
        "security_attribution_summary",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_security_attribution_summary_universe",
        "security_attribution_summary",
        ["universe_name", "universe_version", "methodology", "security_id"],
    )
    op.drop_index(
        "ix_security_attribution_summary_universe_status",
        table_name="security_attribution_summary",
    )
    op.create_index(
        "ix_security_attribution_summary_universe_status",
        "security_attribution_summary",
        ["universe_name", "universe_version", "methodology", "run_status", "ticker"],
    )
    op.drop_index("ix_security_attribution_summary_latest", table_name="security_attribution_summary")
    op.create_index(
        "ix_security_attribution_summary_latest",
        "security_attribution_summary",
        ["universe_name", "methodology", "latest_window_end"],
    )

    op.create_table(
        "attribution_on_demand_job",
        sa.Column("attribution_on_demand_job_id", UUID, nullable=False),
        sa.Column("security_id", UUID, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("methodology", sa.String(length=64), nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        sa.Column("target_range_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_range_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_existing_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expected_windows", sa.Integer(), nullable=False),
        sa.Column("ran_windows", sa.Integer(), nullable=False),
        sa.Column("skipped_windows", sa.Integer(), nullable=False),
        sa.Column("latest_run_id", UUID, nullable=True),
        sa.Column("error_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cadence IN ('daily', 'weekly', 'monthly')", name="ck_on_demand_job_cadence"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'skipped')",
            name="ck_on_demand_job_status",
        ),
        sa.ForeignKeyConstraint(["latest_run_id"], ["attribution_run.attribution_run_id"]),
        sa.ForeignKeyConstraint(["methodology"], ["attribution_methodology.methodology"]),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("attribution_on_demand_job_id"),
    )
    op.create_index(
        "ix_on_demand_job_status_created",
        "attribution_on_demand_job",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_on_demand_job_security_methodology",
        "attribution_on_demand_job",
        ["security_id", "methodology", "cadence"],
    )
    op.create_index(
        "uq_on_demand_job_active_request",
        "attribution_on_demand_job",
        ["security_id", "methodology", "cadence", "target_range_start", "target_range_end"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_on_demand_job_active_request", table_name="attribution_on_demand_job")
    op.drop_index("ix_on_demand_job_security_methodology", table_name="attribution_on_demand_job")
    op.drop_index("ix_on_demand_job_status_created", table_name="attribution_on_demand_job")
    op.drop_table("attribution_on_demand_job")

    op.drop_index("ix_security_attribution_summary_latest", table_name="security_attribution_summary")
    op.create_index(
        "ix_security_attribution_summary_latest",
        "security_attribution_summary",
        ["universe_name", "latest_window_end"],
    )
    op.drop_index(
        "ix_security_attribution_summary_universe_status",
        table_name="security_attribution_summary",
    )
    op.create_index(
        "ix_security_attribution_summary_universe_status",
        "security_attribution_summary",
        ["universe_name", "universe_version", "run_status", "ticker"],
    )
    op.drop_constraint(
        "uq_security_attribution_summary_universe",
        "security_attribution_summary",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_security_attribution_summary_universe",
        "security_attribution_summary",
        ["universe_name", "universe_version", "security_id"],
    )
    op.drop_constraint(
        "fk_security_attribution_summary_methodology",
        "security_attribution_summary",
        type_="foreignkey",
    )
    op.drop_column("security_attribution_summary", "methodology")

    op.drop_index("ix_attribution_run_security_methodology_latest", table_name="attribution_run")
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
    op.drop_constraint("fk_attribution_run_methodology", "attribution_run", type_="foreignkey")
    op.drop_column("attribution_run", "methodology")

    op.drop_index("ix_attribution_methodology_default", table_name="attribution_methodology")
    op.drop_table("attribution_methodology")

from __future__ import annotations

from alembic import op


revision = "20260503_0003"
down_revision = "20260503_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                attribution_run_id,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        security_id,
                        window_start,
                        window_end,
                        model_version,
                        factor_basket_version
                    ORDER BY created_at DESC, attribution_run_id DESC
                ) AS row_number
            FROM attribution_run
        ),
        duplicate_runs AS (
            SELECT attribution_run_id
            FROM ranked
            WHERE row_number > 1
        )
        DELETE FROM attribution_contribution
        WHERE attribution_run_id IN (SELECT attribution_run_id FROM duplicate_runs)
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                attribution_run_id,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        security_id,
                        window_start,
                        window_end,
                        model_version,
                        factor_basket_version
                    ORDER BY created_at DESC, attribution_run_id DESC
                ) AS row_number
            FROM attribution_run
        )
        DELETE FROM attribution_run
        WHERE attribution_run_id IN (
            SELECT attribution_run_id
            FROM ranked
            WHERE row_number > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_attribution_run_window_model",
        "attribution_run",
        ["security_id", "window_start", "window_end", "model_version", "factor_basket_version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_attribution_run_window_model", "attribution_run", type_="unique")

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_0005"
down_revision = "20260504_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "security_factor_exposure",
        "exposure_value",
        existing_type=sa.Numeric(18, 8),
        type_=sa.Numeric(24, 8),
        existing_nullable=False,
    )
    op.alter_column(
        "company_exposure",
        "exposure_value",
        existing_type=sa.Numeric(18, 8),
        type_=sa.Numeric(24, 8),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "company_exposure",
        "exposure_value",
        existing_type=sa.Numeric(24, 8),
        type_=sa.Numeric(18, 8),
        existing_nullable=False,
    )
    op.alter_column(
        "security_factor_exposure",
        "exposure_value",
        existing_type=sa.Numeric(24, 8),
        type_=sa.Numeric(18, 8),
        existing_nullable=False,
    )

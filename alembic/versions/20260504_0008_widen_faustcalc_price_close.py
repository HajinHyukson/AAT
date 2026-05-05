from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_0008"
down_revision = "20260504_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "faustcalc_price",
        "close",
        existing_type=sa.Numeric(18, 6),
        type_=sa.Numeric(24, 12),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "faustcalc_price",
        "close",
        existing_type=sa.Numeric(24, 12),
        type_=sa.Numeric(18, 6),
        existing_nullable=False,
    )

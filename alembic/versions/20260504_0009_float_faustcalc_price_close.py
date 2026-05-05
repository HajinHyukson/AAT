from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_0009"
down_revision = "20260504_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "faustcalc_price",
        "close",
        existing_type=sa.Numeric(24, 12),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="close::double precision",
    )


def downgrade() -> None:
    op.alter_column(
        "faustcalc_price",
        "close",
        existing_type=sa.Float(),
        type_=sa.Numeric(24, 12),
        existing_nullable=False,
        postgresql_using="close::numeric(24, 12)",
    )

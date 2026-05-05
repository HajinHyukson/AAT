from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260503_0002"
down_revision = "20260503_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_feature",
        sa.Column("event_feature_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("relevance", sa.Numeric(8, 6), nullable=False),
        sa.Column("novelty", sa.Numeric(8, 6), nullable=False),
        sa.Column("sentiment", sa.Numeric(8, 6), nullable=False),
        sa.Column("magnitude", sa.Numeric(8, 6), nullable=False),
        sa.Column("source_credibility", sa.Numeric(8, 6), nullable=False),
        sa.Column("exposure_match", sa.Numeric(8, 6), nullable=False),
        sa.Column("surprise", sa.Numeric(8, 6), nullable=False),
        sa.Column("evidence_span", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("exposure_match >= 0 AND exposure_match <= 1", name="ck_event_feature_exposure_match"),
        sa.CheckConstraint("magnitude >= 0 AND magnitude <= 1", name="ck_event_feature_magnitude"),
        sa.CheckConstraint("novelty >= 0 AND novelty <= 1", name="ck_event_feature_novelty"),
        sa.CheckConstraint("relevance >= 0 AND relevance <= 1", name="ck_event_feature_relevance"),
        sa.CheckConstraint(
            "source_credibility >= 0 AND source_credibility <= 1",
            name="ck_event_feature_source_credibility",
        ),
        sa.CheckConstraint("sentiment >= -1 AND sentiment <= 1", name="ck_event_feature_sentiment"),
        sa.CheckConstraint("surprise >= -1 AND surprise <= 1", name="ck_event_feature_surprise"),
        sa.ForeignKeyConstraint(["company_id"], ["company.company_id"]),
        sa.ForeignKeyConstraint(["event_id"], ["event.event_id"]),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("event_feature_id"),
        sa.UniqueConstraint("event_id", "model_version", name="uq_event_feature_model"),
    )
    op.create_index("ix_event_feature_company_available", "event_feature", ["company_id", "timestamp_available"])
    op.create_index("ix_event_feature_event", "event_feature", ["event_id"])

    op.create_table(
        "exposure_update_decision",
        sa.Column("exposure_update_decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exposure_name", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.company_id"]),
        sa.PrimaryKeyConstraint("exposure_update_decision_id"),
        sa.UniqueConstraint(
            "company_id",
            "exposure_name",
            "model_version",
            "evaluated_at",
            name="uq_exposure_update_decision_eval",
        ),
    )
    op.create_index(
        "ix_exposure_update_decision_company",
        "exposure_update_decision",
        ["company_id", "evaluated_at"],
    )


def downgrade() -> None:
    op.drop_table("exposure_update_decision")
    op.drop_table("event_feature")

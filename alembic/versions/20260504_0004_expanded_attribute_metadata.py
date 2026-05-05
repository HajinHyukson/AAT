from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260504_0004"
down_revision = "20260503_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factor_definition",
        sa.Column("factor_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("factor_name", sa.String(length=128), nullable=False),
        sa.Column("factor_family", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("transform", sa.String(length=128), nullable=False),
        sa.Column("default_unit", sa.String(length=32), nullable=False),
        sa.Column("license_tier", sa.String(length=64), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("factor_definition_id"),
        sa.UniqueConstraint("factor_name"),
    )
    op.create_index("ix_factor_definition_family", "factor_definition", ["factor_family"])

    op.create_table(
        "factor_observation",
        sa.Column("factor_observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("factor_name", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("raw_value", sa.Numeric(24, 8), nullable=False),
        sa.Column("raw_unit", sa.String(length=32), nullable=False),
        sa.Column("vintage", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("factor_observation_id", "event_time"),
        sa.UniqueConstraint(
            "factor_name",
            "source",
            "event_time",
            "vintage",
            name="uq_factor_observation_source_time",
        ),
    )
    op.create_index("ix_factor_observation_available", "factor_observation", ["factor_name", "timestamp_available"])

    op.create_table(
        "security_factor_exposure",
        sa.Column("security_factor_exposure_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("factor_name", sa.String(length=128), nullable=False),
        sa.Column("exposure_value", sa.Numeric(18, 8), nullable=False),
        sa.Column("exposure_unit", sa.String(length=32), nullable=False),
        sa.Column("exposure_method", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("security_factor_exposure_id"),
        sa.UniqueConstraint(
            "security_id",
            "factor_name",
            "model_version",
            "event_time",
            name="uq_security_factor_exposure_model_time",
        ),
    )
    op.create_index("ix_security_factor_exposure_available", "security_factor_exposure", ["security_id", "timestamp_available"])
    op.create_index("ix_security_factor_exposure_factor", "security_factor_exposure", ["factor_name", "event_time"])

    op.create_table(
        "sector_classification_history",
        sa.Column("sector_classification_history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sector", sa.String(length=128), nullable=False),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("subindustry", sa.String(length=128), nullable=True),
        sa.Column("classification_source", sa.String(length=128), nullable=False),
        sa.Column("classification_version", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("sector_classification_history_id"),
        sa.UniqueConstraint(
            "security_id",
            "classification_source",
            "classification_version",
            "event_time",
            name="uq_sector_classification_version_time",
        ),
    )
    op.create_index("ix_sector_classification_available", "sector_classification_history", ["security_id", "timestamp_available"])

    op.create_table(
        "peer_basket",
        sa.Column("peer_basket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("basket_name", sa.String(length=128), nullable=False),
        sa.Column("basket_version", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["target_security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("peer_basket_id"),
        sa.UniqueConstraint(
            "target_security_id",
            "basket_name",
            "basket_version",
            name="uq_peer_basket_target_version",
        ),
    )
    op.create_index("ix_peer_basket_available", "peer_basket", ["target_security_id", "timestamp_available"])

    op.create_table(
        "peer_basket_member",
        sa.Column("peer_basket_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("peer_basket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("peer_security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weight", sa.Numeric(18, 8), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("weight >= 0", name="ck_peer_basket_member_weight_nonnegative"),
        sa.ForeignKeyConstraint(["peer_basket_id"], ["peer_basket.peer_basket_id"]),
        sa.ForeignKeyConstraint(["peer_security_id"], ["security.security_id"]),
        sa.PrimaryKeyConstraint("peer_basket_member_id"),
        sa.UniqueConstraint("peer_basket_id", "peer_security_id", name="uq_peer_basket_member"),
    )
    op.create_index("ix_peer_basket_member_available", "peer_basket_member", ["peer_basket_id", "timestamp_available"])

    op.create_table(
        "event_taxonomy",
        sa.Column("event_taxonomy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_category", sa.String(length=128), nullable=False),
        sa.Column("event_subtype", sa.String(length=128), nullable=False),
        sa.Column("event_direction", sa.String(length=64), nullable=False),
        sa.Column("materiality", sa.Numeric(8, 6), nullable=False),
        sa.Column("taxonomy_version", sa.String(length=64), nullable=False),
        sa.Column("evidence_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("materiality >= 0 AND materiality <= 1", name="ck_event_taxonomy_materiality"),
        sa.ForeignKeyConstraint(["event_id"], ["event.event_id"]),
        sa.PrimaryKeyConstraint("event_taxonomy_id"),
        sa.UniqueConstraint("event_id", "taxonomy_version", name="uq_event_taxonomy_version"),
    )
    op.create_index("ix_event_taxonomy_available", "event_taxonomy", ["event_id", "timestamp_available"])

    op.create_table(
        "event_surprise",
        sa.Column("event_surprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("surprise_name", sa.String(length=128), nullable=False),
        sa.Column("surprise_value", sa.Numeric(18, 8), nullable=False),
        sa.Column("surprise_unit", sa.String(length=32), nullable=False),
        sa.Column("expected_value", sa.Numeric(18, 8), nullable=True),
        sa.Column("actual_value", sa.Numeric(18, 8), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("evidence_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_available", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["event.event_id"]),
        sa.PrimaryKeyConstraint("event_surprise_id"),
        sa.UniqueConstraint("event_id", "surprise_name", "model_version", name="uq_event_surprise_model"),
    )
    op.create_index("ix_event_surprise_available", "event_surprise", ["event_id", "timestamp_available"])

    op.add_column("company_exposure", sa.Column("exposure_type", sa.String(length=128), nullable=True))
    op.add_column("company_exposure", sa.Column("exposure_bucket", sa.String(length=32), nullable=True))
    op.add_column("company_exposure", sa.Column("exposure_sign", sa.String(length=32), nullable=True))
    op.add_column("company_exposure", sa.Column("source_span", sa.Text(), nullable=True))
    op.add_column("company_exposure", sa.Column("review_status", sa.String(length=64), nullable=True))
    op.add_column("company_exposure", sa.Column("exposure_version", sa.String(length=64), nullable=True))

    op.add_column(
        "attribution_contribution",
        sa.Column("contribution_stage", sa.String(length=32), nullable=False, server_default="production"),
    )
    op.add_column(
        "attribution_contribution",
        sa.Column("evidence_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "analyst_feedback",
        sa.Column("analyst_feedback_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attribution_contribution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attribution_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feedback", sa.String(length=64), nullable=False),
        sa.Column("missing_driver_name", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attribution_contribution_id"], ["attribution_contribution.attribution_contribution_id"]),
        sa.ForeignKeyConstraint(["attribution_run_id"], ["attribution_run.attribution_run_id"]),
        sa.PrimaryKeyConstraint("analyst_feedback_id"),
    )
    op.create_index("ix_analyst_feedback_run", "analyst_feedback", ["attribution_run_id", "created_at"])


def downgrade() -> None:
    op.drop_table("analyst_feedback")
    op.drop_column("attribution_contribution", "evidence_payload")
    op.drop_column("attribution_contribution", "contribution_stage")
    op.drop_column("company_exposure", "exposure_version")
    op.drop_column("company_exposure", "review_status")
    op.drop_column("company_exposure", "source_span")
    op.drop_column("company_exposure", "exposure_sign")
    op.drop_column("company_exposure", "exposure_bucket")
    op.drop_column("company_exposure", "exposure_type")
    op.drop_table("event_surprise")
    op.drop_table("event_taxonomy")
    op.drop_table("peer_basket_member")
    op.drop_table("peer_basket")
    op.drop_table("sector_classification_history")
    op.drop_table("security_factor_exposure")
    op.drop_table("factor_observation")
    op.drop_table("factor_definition")

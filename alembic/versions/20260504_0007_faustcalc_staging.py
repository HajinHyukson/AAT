from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260504_0007"
down_revision = "20260504_0006"
branch_labels = None
depends_on = None


JSONB = postgresql.JSONB(astext_type=sa.Text())
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "faustcalc_import_run",
        sa.Column("faustcalc_import_run_id", UUID, nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("source_database_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("data_root", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_counts", JSONB, nullable=True),
        sa.Column("validation_payload", JSONB, nullable=True),
        sa.Column("error_payload", JSONB, nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'dry_run')",
            name="ck_faustcalc_import_run_status",
        ),
        sa.PrimaryKeyConstraint("faustcalc_import_run_id"),
    )
    op.create_index(
        "ix_faustcalc_import_run_status_started",
        "faustcalc_import_run",
        ["status", "started_at"],
    )

    op.create_table(
        "faustcalc_validation_issue",
        sa.Column("faustcalc_validation_issue_id", UUID, nullable=False),
        sa.Column("faustcalc_import_run_id", UUID, nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("issue_type", sa.String(length=128), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=True),
        sa.Column("source_key", sa.Text(), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("severity IN ('info', 'warning', 'error')", name="ck_faustcalc_issue_severity"),
        sa.ForeignKeyConstraint(["faustcalc_import_run_id"], ["faustcalc_import_run.faustcalc_import_run_id"]),
        sa.PrimaryKeyConstraint("faustcalc_validation_issue_id"),
    )
    op.create_index(
        "ix_faustcalc_validation_issue_run",
        "faustcalc_validation_issue",
        ["faustcalc_import_run_id", "severity"],
    )

    op.create_table(
        "faustcalc_asset",
        sa.Column("faustcalc_asset_id", UUID, nullable=False),
        sa.Column("faustcalc_import_run_id", UUID, nullable=False),
        sa.Column("source_ticker", sa.String(length=64), nullable=False),
        sa.Column("canonical_ticker", sa.String(length=64), nullable=False),
        sa.Column("ticker_local", sa.String(length=64), nullable=True),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("asset_type", sa.String(length=64), nullable=True),
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column("market", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["faustcalc_import_run_id"], ["faustcalc_import_run.faustcalc_import_run_id"]),
        sa.PrimaryKeyConstraint("faustcalc_asset_id"),
        sa.UniqueConstraint("source_ticker", name="uq_faustcalc_asset_source_ticker"),
    )
    op.create_index("ix_faustcalc_asset_canonical_ticker", "faustcalc_asset", ["canonical_ticker"])

    op.create_table(
        "faustcalc_company",
        sa.Column("faustcalc_company_id", UUID, nullable=False),
        sa.Column("faustcalc_import_run_id", UUID, nullable=False),
        sa.Column("source_ticker", sa.String(length=64), nullable=False),
        sa.Column("canonical_ticker", sa.String(length=64), nullable=False),
        sa.Column("cik", sa.String(length=20), nullable=True),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("source_last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["faustcalc_import_run_id"], ["faustcalc_import_run.faustcalc_import_run_id"]),
        sa.PrimaryKeyConstraint("faustcalc_company_id"),
        sa.UniqueConstraint("source_ticker", name="uq_faustcalc_company_source_ticker"),
    )
    op.create_index("ix_faustcalc_company_cik", "faustcalc_company", ["cik"])
    op.create_index("ix_faustcalc_company_canonical_ticker", "faustcalc_company", ["canonical_ticker"])

    op.create_table(
        "faustcalc_price",
        sa.Column("faustcalc_price_id", UUID, nullable=False),
        sa.Column("faustcalc_import_run_id", UUID, nullable=False),
        sa.Column("source_price_id", sa.BigInteger(), nullable=False),
        sa.Column("source_ticker", sa.String(length=64), nullable=False),
        sa.Column("canonical_ticker", sa.String(length=64), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.CheckConstraint("close > 0", name="ck_faustcalc_price_close_positive"),
        sa.ForeignKeyConstraint(["faustcalc_import_run_id"], ["faustcalc_import_run.faustcalc_import_run_id"]),
        sa.PrimaryKeyConstraint("faustcalc_price_id"),
        sa.UniqueConstraint("source_price_id", name="uq_faustcalc_price_source_id"),
    )
    op.create_index("ix_faustcalc_price_ticker_date", "faustcalc_price", ["canonical_ticker", "price_date"])

    _create_source_row_table(
        "faustcalc_fundamental",
        "faustcalc_fundamental_id",
        "source_fundamental_id",
        "as_of_date",
        unique_name="uq_faustcalc_fundamental_source_id",
        index_name="ix_faustcalc_fundamental_ticker_date",
        extra_columns=[sa.Column("source", sa.String(length=64), nullable=False)],
    )
    _create_source_row_table(
        "faustcalc_price_feature",
        "faustcalc_price_feature_id",
        "source_price_feature_id",
        "as_of_date",
        unique_name="uq_faustcalc_price_feature_source_id",
        index_name="ix_faustcalc_price_feature_ticker_date",
    )
    _create_source_row_table(
        "faustcalc_theme_score",
        "faustcalc_theme_score_id",
        "source_theme_score_id",
        "as_of_date",
        unique_name="uq_faustcalc_theme_score_source_id",
        index_name="ix_faustcalc_theme_score_ticker_date",
        extra_columns=[sa.Column("theme_key", sa.String(length=128), nullable=False)],
    )
    _create_source_row_table(
        "faustcalc_filing_analysis",
        "faustcalc_filing_analysis_id",
        "source_filing_analysis_id",
        "filing_date",
        unique_name="uq_faustcalc_filing_analysis_source_id",
        index_name="ix_faustcalc_filing_analysis_ticker_date",
        extra_columns=[sa.Column("filing_type", sa.String(length=64), nullable=False)],
    )
    _create_source_row_table(
        "faustcalc_peer_analysis",
        "faustcalc_peer_analysis_id",
        "source_peer_analysis_id",
        "as_of_date",
        unique_name="uq_faustcalc_peer_analysis_source_id",
        index_name="ix_faustcalc_peer_analysis_ticker_date",
    )

    op.create_table(
        "faustcalc_sec_filing",
        sa.Column("faustcalc_sec_filing_id", UUID, nullable=False),
        sa.Column("faustcalc_import_run_id", UUID, nullable=False),
        sa.Column("accession_number", sa.String(length=64), nullable=False),
        sa.Column("canonical_ticker", sa.String(length=64), nullable=False),
        sa.Column("source_tickers", JSONB, nullable=False),
        sa.Column("form_type", sa.String(length=64), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("cleaned_text_path", sa.Text(), nullable=True),
        sa.Column("source_content_hash", sa.String(length=128), nullable=True),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.CheckConstraint("status IN ('valid', 'rejected')", name="ck_faustcalc_sec_filing_status"),
        sa.ForeignKeyConstraint(["faustcalc_import_run_id"], ["faustcalc_import_run.faustcalc_import_run_id"]),
        sa.PrimaryKeyConstraint("faustcalc_sec_filing_id"),
        sa.UniqueConstraint("accession_number", name="uq_faustcalc_sec_filing_accession"),
    )
    op.create_index(
        "ix_faustcalc_sec_filing_ticker_available",
        "faustcalc_sec_filing",
        ["canonical_ticker", "available_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_faustcalc_sec_filing_ticker_available", table_name="faustcalc_sec_filing")
    op.drop_table("faustcalc_sec_filing")
    op.drop_index("ix_faustcalc_peer_analysis_ticker_date", table_name="faustcalc_peer_analysis")
    op.drop_table("faustcalc_peer_analysis")
    op.drop_index("ix_faustcalc_filing_analysis_ticker_date", table_name="faustcalc_filing_analysis")
    op.drop_table("faustcalc_filing_analysis")
    op.drop_index("ix_faustcalc_theme_score_ticker_date", table_name="faustcalc_theme_score")
    op.drop_table("faustcalc_theme_score")
    op.drop_index("ix_faustcalc_price_feature_ticker_date", table_name="faustcalc_price_feature")
    op.drop_table("faustcalc_price_feature")
    op.drop_index("ix_faustcalc_fundamental_ticker_date", table_name="faustcalc_fundamental")
    op.drop_table("faustcalc_fundamental")
    op.drop_index("ix_faustcalc_price_ticker_date", table_name="faustcalc_price")
    op.drop_table("faustcalc_price")
    op.drop_index("ix_faustcalc_company_canonical_ticker", table_name="faustcalc_company")
    op.drop_index("ix_faustcalc_company_cik", table_name="faustcalc_company")
    op.drop_table("faustcalc_company")
    op.drop_index("ix_faustcalc_asset_canonical_ticker", table_name="faustcalc_asset")
    op.drop_table("faustcalc_asset")
    op.drop_index("ix_faustcalc_validation_issue_run", table_name="faustcalc_validation_issue")
    op.drop_table("faustcalc_validation_issue")
    op.drop_index("ix_faustcalc_import_run_status_started", table_name="faustcalc_import_run")
    op.drop_table("faustcalc_import_run")


def _create_source_row_table(
    table_name: str,
    pk_name: str,
    source_id_name: str,
    date_column_name: str,
    *,
    unique_name: str,
    index_name: str,
    extra_columns: list[sa.Column] | None = None,
) -> None:
    columns = [
        sa.Column(pk_name, UUID, nullable=False),
        sa.Column("faustcalc_import_run_id", UUID, nullable=False),
        sa.Column(source_id_name, sa.BigInteger(), nullable=False),
        sa.Column("source_ticker", sa.String(length=64), nullable=False),
        sa.Column("canonical_ticker", sa.String(length=64), nullable=False),
        sa.Column(date_column_name, sa.Date(), nullable=False),
        *(extra_columns or []),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["faustcalc_import_run_id"], ["faustcalc_import_run.faustcalc_import_run_id"]),
        sa.PrimaryKeyConstraint(pk_name),
        sa.UniqueConstraint(source_id_name, name=unique_name),
    ]
    op.create_table(table_name, *columns)
    op.create_index(index_name, table_name, ["canonical_ticker", date_column_name])

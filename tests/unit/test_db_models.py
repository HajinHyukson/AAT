from __future__ import annotations

from db import models  # noqa: F401
from db.base import Base


def test_canonical_tables_exist() -> None:
    expected = {
        "company",
        "security",
        "security_ticker_history",
        "price_bar",
        "factor_return",
        "factor_definition",
        "factor_observation",
        "security_factor_exposure",
        "sector_classification_history",
        "peer_basket",
        "peer_basket_member",
        "macro_series",
        "event",
        "event_feature",
        "event_taxonomy",
        "event_surprise",
        "company_exposure",
        "exposure_update_decision",
        "attribution_run",
        "attribution_contribution",
        "analyst_feedback",
        "backfill_run",
        "model_universe_member",
        "attribution_backfill_task",
        "security_attribution_summary",
        "faustcalc_import_run",
        "faustcalc_validation_issue",
        "faustcalc_asset",
        "faustcalc_company",
        "faustcalc_price",
        "faustcalc_fundamental",
        "faustcalc_price_feature",
        "faustcalc_theme_score",
        "faustcalc_filing_analysis",
        "faustcalc_peer_analysis",
        "faustcalc_sec_filing",
    }

    assert expected.issubset(Base.metadata.tables)


def test_attribution_run_tracks_cadence_in_unique_key() -> None:
    table = Base.metadata.tables["attribution_run"]
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if constraint.name == "uq_attribution_run_window_model"
    }

    assert "cadence" in table.columns
    assert (
        "security_id",
        "window_start",
        "window_end",
        "model_version",
        "factor_basket_version",
        "cadence",
    ) in unique_columns


def test_timestamped_tables_have_point_in_time_columns() -> None:
    for table_name in [
        "price_bar",
        "factor_return",
        "factor_observation",
        "security_factor_exposure",
        "sector_classification_history",
        "peer_basket",
        "peer_basket_member",
        "macro_series",
        "event",
        "event_feature",
        "event_taxonomy",
        "event_surprise",
        "company_exposure",
    ]:
        columns = Base.metadata.tables[table_name].columns
        assert "event_time" in columns
        assert "ingestion_time" in columns
        assert "timestamp_available" in columns


def test_ticker_is_not_primary_key() -> None:
    for table in Base.metadata.tables.values():
        pk_columns = {column.name for column in table.primary_key.columns}
        assert "ticker" not in pk_columns

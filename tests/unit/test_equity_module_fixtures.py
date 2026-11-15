from __future__ import annotations

import json
from pathlib import Path

from viza.equity import DEFAULT_EQUITY_MODULE_DIR, load_equity_module


FIXTURES = DEFAULT_EQUITY_MODULE_DIR / "fixtures"


def test_first_wedge_sec_quality_value_fixture_contract() -> None:
    fixture = json.loads(
        (FIXTURES / "first_wedge_sec_quality_value" / "fixture.json").read_text(encoding="utf-8")
    )

    assert fixture["fixture_strategy_profile_id"] == "quality_value_long_only"
    assert fixture["entities"]["company"]["immutable_keys"] == ["company_id"]
    security = fixture["entities"]["equity_security"]
    assert security["immutable_keys"] == ["security_id"]
    assert "ticker" not in security["identifiers"]
    assert security["identifiers"]["ticker_display"] == "EXAMPLE.US"
    assert fixture["entities"]["filing"]["pit"]["available_at"] <= fixture["fixture_decision_timestamp"]
    assert fixture["entities"]["decision"]["pit_status"]["PIT_safe"] is True
    assert "non_advice_boundary" in fixture
    assert "thesis_tracker" in fixture["entities"]["decision"]["output_views"]
    assert "source_rights_report" in fixture["entities"]["decision"]["output_views"]


def test_three_profile_pilots_are_loadable_and_have_expected_gates() -> None:
    quality = json.loads(
        (FIXTURES / "first_wedge_sec_quality_value" / "fixture.json").read_text(encoding="utf-8")
    )
    portfolio = json.loads(
        (FIXTURES / "portfolio_risk_radar_pilot" / "fixture.json").read_text(encoding="utf-8")
    )
    earnings = json.loads(
        (FIXTURES / "earnings_revision_momentum_pilot" / "fixture.json").read_text(
            encoding="utf-8"
        )
    )

    assert quality["fixture_strategy_profile_id"] == "quality_value_long_only"
    assert portfolio["fixture_strategy_profile_id"] == "portfolio_risk_radar"
    assert earnings["fixture_strategy_profile_id"] == "earnings_revision_momentum"

    assert portfolio["portfolio"]["rights"]["export_policy"] == "blocked"
    assert portfolio["package_behavior"]["marketplace_draft"]["marketplace_endpoint_supported"] is False
    assert earnings["path_a_license_gated"]["license_status"] == "missing"
    assert "locked" in earnings["path_a_license_gated"]["validation_outcome"]
    assert "event_catalyst_board" in earnings["required_output_views"]
    assert earnings["pit_report"]["PIT_safe"] is True


def test_package_redaction_matrix_covers_requested_modes() -> None:
    matrix = json.loads(
        (FIXTURES / "package_redaction_tests" / "package_redaction_test_matrix.json").read_text(
            encoding="utf-8"
        )
    )

    modes = set(matrix["package_modes"])
    assert {"white_box", "output_only", "marketplace_draft"}.issubset(modes)

    cells = matrix["per_cell_test_matrix"]
    assert any(
        cell["package_mode"] == "marketplace_draft"
        and cell["expected"]["blocked"] is True
        and cell["data_id"] == "d11_raw_social_news_unclear_rights"
        for cell in cells
    )
    assert any(
        cell["expected"]["entitlement_locked"] is True
        for cell in cells
        if cell["data_id"] == "d07_licensed_analyst_estimates"
    )


def test_manifest_checksums_cover_all_registry_artifacts() -> None:
    module = load_equity_module()
    artifact_paths = {
        artifact["path"]
        for artifact in module.manifest["registry_artifacts"].values()
        if isinstance(artifact, dict) and "path" in artifact
    }

    for required in (
        "registries/equity_entity_types.json",
        "registries/equity_attribute_registry_seed.csv",
        "registries/equity_event_registry_seed.json",
        "registries/equity_insight_registry_seed.json",
        "registries/equity_strategy_profiles.json",
        "registries/equity_output_views.json",
        "registries/equity_validation_rules.json",
        "registries/equity_source_rights_matrix.csv",
        "registries/equity_PIT_matrix.csv",
        "registries/equity_research_traceability_matrix.csv",
        "registries/equity_rejection_and_downgrade_log.csv",
    ):
        assert required in artifact_paths

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from viza.equity import (
    DEFAULT_EQUITY_REGISTRIES_DIR,
    EQUITY_MODULE_ID,
    load_equity_module,
)


def test_equity_module_registry_artifacts_load_and_validate() -> None:
    module = load_equity_module()
    report = module.validate()

    assert module.manifest["module_id"] == EQUITY_MODULE_ID
    assert report.status == "pass"
    assert module.artifact("entity_types").record_count >= 52
    assert module.artifact("node_types").record_count >= 226
    assert module.artifact("attributes").record_count >= 387
    assert module.artifact("strategy_profiles").require("quality_value_long_only")
    assert module.artifact("validation_rules").require("EQ-VAL-001")
    assert module.artifact("validation_rules").require("EQ-VAL-012")


def test_equity_module_required_entities_edges_profiles_and_views_resolve() -> None:
    module = load_equity_module()

    for entity_id in {
        "equity_security",
        "company",
        "issuer",
        "share_class",
        "listing",
        "portfolio",
        "position",
        "recommendation",
        "audit_proof",
        "package",
    }:
        assert module.artifact("entity_types").require(entity_id)

    for edge_id in {
        "company_issues_security",
        "security_has_listing",
        "company_belongs_to_industry",
        "holder_owns_security",
        "event_affects_security",
        "valuation_model_uses_assumption",
    }:
        assert module.artifact("edge_types").require(edge_id)

    for profile_id in {
        "quality_value_long_only",
        "portfolio_risk_radar",
        "earnings_revision_momentum",
    }:
        profile = module.artifact("strategy_profiles").require(profile_id)
        assert profile["output_views"]

    for output_id in {
        "equity_radar",
        "investment_memo",
        "trade_plan",
        "risk_dashboard",
        "validation_report",
        "source_rights_report",
        "event_catalyst_board",
        "valuation_matrix",
        "factor_exposure_report",
    }:
        assert module.artifact("output_views").require(output_id)


def test_equity_module_package_decisions_fail_closed() -> None:
    module = load_equity_module()

    restricted = module.package_decision(
        license_policy="restricted_or_unclear",
        package_mode="marketplace_draft",
    )
    assert restricted.blocked is True
    assert restricted.redacted is True

    unknown = module.package_decision(
        license_policy="unknown",
        package_mode="white_box",
        rights_unknown=True,
    )
    assert unknown.blocked is True

    licensed = module.package_decision(
        license_policy="licensed_provider_required",
        package_mode="output_only",
        entitlement_present=False,
    )
    assert licensed.entitlement_locked is True
    assert licensed.included is False

    private = module.package_decision(
        license_policy="internal_research_only",
        package_mode="marketplace_draft",
        user_private=True,
    )
    assert private.blocked is True
    assert private.redacted is True

    public = module.package_decision(
        license_policy="public_official",
        package_mode="white_box",
    )
    assert public.included is True
    assert public.blocked is False


def test_equity_module_invalid_artifact_fails_closed(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "registries"
    shutil.copytree(DEFAULT_EQUITY_REGISTRIES_DIR, fixture_dir)

    entity_path = fixture_dir / "equity_entity_types.json"
    payload = json.loads(entity_path.read_text(encoding="utf-8"))
    payload["records"][0]["family_specific"]["immutable_keys"].append("ticker")
    entity_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    module = load_equity_module(fixture_dir)
    report = module.validate()

    assert report.status == "block"
    assert any(issue.code == "no_ticker_as_primary_key" for issue in report.issues)


def test_equity_attribute_registry_has_required_pit_and_rights_columns() -> None:
    with (DEFAULT_EQUITY_REGISTRIES_DIR / "equity_attribute_registry_seed.csv").open(
        encoding="utf-8", newline=""
    ) as fh:
        rows = list(csv.DictReader(fh))

    required_columns = {
        "observed_at_policy",
        "available_at_policy",
        "retrieved_at_policy",
        "source_version_policy",
        "data_version_policy",
        "model_version_policy",
        "vintage_required",
        "lookahead_risk",
        "entitlement_policy",
        "export_policy",
        "redistribution_policy",
        "marketplace_policy",
    }
    assert rows
    assert required_columns.issubset(rows[0])
    assert all(row["observed_at_policy"] for row in rows)
    assert all(row["available_at_policy"] for row in rows)
    assert all(row["retrieved_at_policy"] for row in rows)
    assert all(row["marketplace_policy"] for row in rows)


def test_equity_output_views_enforce_non_advice_boundary() -> None:
    module = load_equity_module()
    for output_id in (
        "equity_radar",
        "investment_memo",
        "trade_plan",
        "risk_dashboard",
        "portfolio_impact_report",
    ):
        output = module.artifact("output_views").require(output_id)
        specific = output["family_specific"]
        assert specific["binding"]["non_advice_boundary_required"] is True
        assert "non_advice_boundary" in specific["required_sections"]

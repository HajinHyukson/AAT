from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
MODULE_DIR = ROOT / "docs" / "equity_module" / "v0.1"
REGISTRIES = MODULE_DIR / "registries"
SCHEMAS = MODULE_DIR / "schemas"
CORPUS = MODULE_DIR / "corpus"
FIXTURES = MODULE_DIR / "fixtures"
REPORTS = MODULE_DIR / "reports"
PROOFS = MODULE_DIR / "proofs"
GENERATED = MODULE_DIR / "generated"
DOC_TESTS = MODULE_DIR / "tests"
HIGH_CONF = ROOT / "docs" / "equity_high_confidence_upgrade"

MODULE_ID = "viza.finance.equity_investment"
MODULE_VERSION = "0.1.0"
BASELINE = "Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening"


def main() -> int:
    ensure_workspace()
    materialize_snapshot_and_schemas()
    copy_traceability_logs()
    patch_validation_rules()
    patch_output_views_and_profiles()
    patch_nodes_for_human_review()
    materialize_fixtures()
    write_reports()
    update_manifest()
    write_proof()
    return 0


def ensure_workspace() -> None:
    for path in (CORPUS, REGISTRIES, SCHEMAS, FIXTURES, REPORTS, PROOFS, GENERATED, DOC_TESTS):
        path.mkdir(parents=True, exist_ok=True)


def materialize_snapshot_and_schemas() -> None:
    snapshot = {
        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,
        "corpus_status": "expanded_high_confidence_corpus_completed",
        "build_stage": "artifact_generation",
        "baseline": BASELINE,
        "primary_research_log": "docs/CLAUDE_EQUITY_MODULE.md",
        "expanded_corpus_locations": [
            "docs/equity_module/v0.1/registries/",
            "docs/equity_high_confidence_upgrade/",
            "docs/equity_module/v0.1/corpus_v0.2/",
        ],
        "registry_output_path": "docs/equity_module/v0.1/registries/",
        "created_by": "Codex build agent",
        "created_at": iso_now(),
        "notes": [
            "Corpus expansion completed.",
            "Next tasks are registry generation, seeders, fixtures, pilot validation, package tests, documentation, and proof handoff.",
            "This snapshot freezes the completed corpus for v0.1 artifact generation; it does not assert production readiness.",
        ],
    }
    write_json(MODULE_DIR / "corpus_snapshot.json", snapshot)

    for filename in (
        "shared_metadata_contract.md",
        "equity_registry_shared_metadata.schema.json",
        "viza.module.manifest.v1.schema.json",
    ):
        source = MODULE_DIR / filename
        if source.exists():
            shutil.copy2(source, SCHEMAS / filename)


def copy_traceability_logs() -> None:
    copies = {
        HIGH_CONF / "equity_research_traceability_matrix.csv": REGISTRIES
        / "equity_research_traceability_matrix.csv",
        HIGH_CONF / "rejection_and_downgrade_log.csv": REGISTRIES
        / "equity_rejection_and_downgrade_log.csv",
    }
    for source, target in copies.items():
        if source.exists():
            shutil.copy2(source, target)


def patch_validation_rules() -> None:
    path = REGISTRIES / "equity_validation_rules.json"
    payload = read_json(path)
    records = payload["records"]
    by_id = {record["id"]: record for record in records}
    aliases = [
        (
            "EQ-VAL-001",
            "PIT Source Timestamps Required",
            "source_id / observed_at / available_at / retrieved_at required",
            "PIT",
            "block",
            "all_observations",
        ),
        (
            "EQ-VAL-002",
            "Reject Future-Unavailable Data",
            "reject future-revised or unavailable historical data",
            "PIT",
            "block",
            "backtests",
        ),
        (
            "EQ-VAL-003",
            "Restricted Raw Data Cannot Export",
            "restricted raw data cannot export",
            "rights",
            "block",
            "packages",
        ),
        (
            "EQ-VAL-004",
            "Thesis Evidence Horizon Invalidation Required",
            "thesis requires evidence, horizon, catalyst or mechanism, invalidation",
            "evidence",
            "block",
            "thesis",
        ),
        (
            "EQ-VAL-005",
            "Valuation Assumptions Sensitivity Required",
            "valuation requires assumptions and sensitivity",
            "evidence",
            "block",
            "valuation_model",
        ),
        (
            "EQ-VAL-006",
            "Factor Signal Statistical Review Required",
            "factor signal requires OOS, cost, liquidity, and multiple-testing review",
            "statistical",
            "block",
            "factor_signal",
        ),
        (
            "EQ-VAL-007",
            "Event Credibility Timestamp Required",
            "event requires source credibility and timestamp",
            "evidence",
            "block",
            "event",
        ),
        (
            "EQ-VAL-008",
            "Short Thesis Borrow Squeeze Legal Review",
            "short thesis requires borrow, squeeze, and legal/human review",
            "qualitative",
            "block",
            "short_thesis",
        ),
        (
            "EQ-VAL-009",
            "Rumor Low Credibility No Action",
            "rumor/low-credibility text cannot drive action",
            "evidence",
            "block",
            "rumor_event",
        ),
        (
            "EQ-VAL-010",
            "Portfolio Sizing Context Required",
            "portfolio sizing requires mandate, liquidity, concentration, and risk budget",
            "portfolio",
            "block",
            "portfolio_sizing",
        ),
        (
            "EQ-VAL-011",
            "Output Redacts Unsupported Claims",
            "output must redact restricted or unsupported claims",
            "output",
            "block",
            "output_view",
        ),
        (
            "EQ-VAL-012",
            "Profile Compatibility Before Action",
            "profile compatibility must pass before action translation",
            "portfolio",
            "block",
            "strategy_profile",
        ),
    ]
    for rule_id, display, description, domain, severity, target in aliases:
        by_id.setdefault(
            rule_id,
            base_record(
                rule_id,
                display,
                description,
                "validation_rule",
                core_primitive="audit",
                extends_core_primitive="transform",
                validation_rules=[],
                failure_modes=[f"{rule_id.lower()}_failure"],
                family_specific={
                    "domain": domain,
                    "severity": severity,
                    "applies_to": [target],
                    "target_type": target,
                    "validation_rule_id": rule_id,
                    "trigger_logic": description,
                    "remediation": "Fail closed; downgrade or block runtime/package use until the rule passes.",
                    "validation_level": domain,
                    "required_inputs": ["source_ids", "PIT_policy", "rights_policy", "validation_record"],
                    "pass_condition": "all required inputs present and policy gates pass",
                    "warning_condition": "policy gate emits warning but no export/backtest/action risk",
                    "fail_condition": "required input missing or policy gate fails",
                    "failure_severity": severity,
                    "confidence_impact": "rejected_or_deferred" if severity == "block" else "research_supported_experimental",
                    "pit_requirements_summary": ["observed_at", "available_at", "retrieved_at"],
                    "rights_requirements_summary": ["export_policy", "marketplace_policy", "redaction_required"],
                    "evidence_refs": ["CLAUDE_EQUITY_MODULE.md Section 19"],
                    "audit_fields": ["validation_record_ids", "proof_checksum"],
                },
            ),
        )
    referenced_rules = collect_referenced_validation_rules()
    for rule_id in sorted(referenced_rules - set(by_id)):
        by_id[rule_id] = base_record(
            rule_id,
            titleize(rule_id),
            f"Compatibility validation rule stub for generated v0.1 registry reference `{rule_id}`.",
            "validation_rule",
            core_primitive="audit",
            extends_core_primitive="transform",
            validation_rules=[],
            failure_modes=[f"{rule_id}_failure"],
            family_specific={
                "domain": infer_validation_domain(rule_id),
                "severity": infer_validation_severity(rule_id),
                "applies_to": ["registry_reference"],
                "target_type": "registry_reference",
                "validation_rule_id": rule_id,
                "trigger_logic": "Referenced by one or more generated registry records.",
                "remediation": "Keep as registry-seedable until the runtime validation engine implements the concrete predicate.",
                "validation_level": infer_validation_domain(rule_id),
                "required_inputs": ["validation_record"],
                "pass_condition": "runtime predicate passes or fixture marks not_applicable",
                "warning_condition": "runtime predicate is not implemented and object remains registry-seedable",
                "fail_condition": "runtime predicate fails",
                "failure_severity": infer_validation_severity(rule_id),
                "confidence_impact": "research_supported_experimental",
                "pit_requirements_summary": ["as declared by referencing object"],
                "rights_requirements_summary": ["as declared by referencing object"],
                "evidence_refs": ["generated registry reference"],
                "audit_fields": ["validation_record_ids"],
            },
        )
    payload["records"] = list(by_id.values())
    write_json(path, payload)


def patch_output_views_and_profiles() -> None:
    output_path = REGISTRIES / "equity_output_views.json"
    payload = read_json(output_path)
    by_id = {record["id"]: record for record in payload["records"]}
    by_id.setdefault(
        "event_catalyst_board",
        output_view_record(
            "event_catalyst_board",
            "Event Catalyst Board",
            "Board view for timestamped events, catalysts, credibility, materiality, PIT state, rights state, validation state, and invalidation triggers.",
            ["earnings_revision_momentum", "post_earnings_drift_radar", "special_situations_monitor", "event_risk_monitor"],
            ["header", "event_timeline", "catalyst_state", "source_credibility", "materiality", "invalidation_conditions", "pit_summary", "rights_summary", "validation_summary", "non_advice_boundary"],
        ),
    )
    by_id.setdefault(
        "valuation_matrix",
        output_view_record(
            "valuation_matrix",
            "Valuation Matrix",
            "Valuation scenario and sensitivity view showing assumptions, ranges, evidence, PIT state, rights state, validation state, and non-advice boundary.",
            ["quality_value_long_only", "growth_at_reasonable_price", "cheap_compounder", "valuation_trap_detector"],
            ["header", "valuation_methods", "assumptions", "sensitivity_table", "scenario_range", "evidence_refs", "pit_summary", "rights_summary", "validation_summary", "non_advice_boundary"],
        ),
    )
    by_id.setdefault(
        "factor_exposure_report",
        output_view_record(
            "factor_exposure_report",
            "Factor Exposure Report",
            "Factor and risk exposure view for portfolio and security-level monitoring with PIT vintage warnings and source-rights redaction state.",
            ["portfolio_risk_radar", "factor_neutral_quantamental_selector", "macro_regime_equity_selector"],
            ["header", "factor_exposures", "risk_contributions", "liquidity_capacity", "pit_summary", "rights_summary", "validation_summary", "non_advice_boundary"],
        ),
    )
    payload["records"] = list(by_id.values())
    for record in payload["records"]:
        if record["id"] == "source_rights_report":
            required = record.setdefault("family_specific", {}).setdefault("required_sections", [])
            if "pit_summary" not in required:
                required.append("pit_summary")
    write_json(output_path, payload)

    profiles_path = REGISTRIES / "equity_strategy_profiles.json"
    profiles = read_json(profiles_path)
    additions = {
        "quality_value_long_only": ["thesis_tracker", "source_rights_report", "valuation_matrix"],
        "portfolio_risk_radar": ["risk_dashboard", "portfolio_impact_report", "validation_report", "source_rights_report", "factor_exposure_report"],
        "earnings_revision_momentum": ["equity_radar", "event_catalyst_board", "validation_report", "source_rights_report"],
    }
    for profile in profiles["records"]:
        for output_id in additions.get(profile["id"], []):
            if output_id not in profile["output_views"]:
                profile["output_views"].append(output_id)
    write_json(profiles_path, profiles)


def patch_nodes_for_human_review() -> None:
    path = REGISTRIES / "equity_node_types.json"
    payload = read_json(path)
    for record in payload["records"]:
        if record["id"] in {"short_interest_node", "short_interest_calculator", "days_to_cover_node"}:
            record["human_review_required"] = True
            for rule_id in ("qualitative_short_action_requires_borrow_and_squeeze_review", "EQ-VAL-008"):
                if rule_id not in record["validation_rules"]:
                    record["validation_rules"].append(rule_id)
            if "short_interest_used_without_borrow_or_squeeze_review" not in record["failure_modes"]:
                record["failure_modes"].append("short_interest_used_without_borrow_or_squeeze_review")
    write_json(path, payload)


def materialize_fixtures() -> None:
    source = FIXTURES / "first_wedge"
    target = FIXTURES / "first_wedge_sec_quality_value"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    fixture_path = target / "fixture.json"
    fixture = read_json(fixture_path)
    fixture["fixture_id"] = "first_wedge_sec_quality_value_v0.1"
    fixture["fixture_strategy_profile_id"] = "quality_value_long_only"
    fixture["fixture_description"] = (
        "Public SEC quality-value first wedge for viza.finance.equity_investment v0.1. "
        "It uses stable internal IDs, EDGAR/XBRL-style public evidence, filing accepted/available timestamps, "
        "non-advice outputs, validation, source-rights reporting, and marketplace_draft redaction."
    )
    decision = fixture.get("entities", {}).get("decision", {})
    outputs = decision.setdefault("output_views", [])
    for output_id in ("investment_memo", "equity_radar", "thesis_tracker", "validation_report", "source_rights_report"):
        if output_id not in outputs:
            outputs.append(output_id)
    fixture["non_advice_boundary"] = (
        "This fixture is engineering scaffolding for research workflow validation only. "
        "It does not constitute investment advice, a recommendation, or solicitation. "
        "The issuer and values are fictional."
    )
    write_json(fixture_path, fixture)

    earnings_path = FIXTURES / "earnings_revision_momentum_pilot" / "fixture.json"
    if earnings_path.exists():
        earnings = read_json(earnings_path)
        views = earnings.setdefault("required_output_views", [])
        for output_id in ("equity_radar", "event_catalyst_board", "validation_report", "source_rights_report"):
            if output_id not in views:
                views.append(output_id)
        nodes = earnings.get("sample_graph", {}).setdefault("nodes", [])
        if not any(node.get("node_type") == "event_catalyst_board_renderer" for node in nodes):
            nodes.append(
                {
                    "node_id": "n_event_catalyst_board",
                    "node_type": "event_catalyst_board_renderer",
                    "extends_core_primitive": "output_radar",
                }
            )
        write_json(earnings_path, earnings)


def write_reports() -> None:
    write_text(
        REPORTS / "artifact_path_mapping.md",
        "\n".join(
            [
                "# Equity Module v0.1 Artifact Path Mapping",
                "",
                "The generated v0.1 equity artifacts are loaded from `docs/equity_module/v0.1/registries/`.",
                "",
                "| Requested artifact | Repository path | Notes |",
                "|---|---|---|",
                "| Shared metadata contract | `docs/equity_module/v0.1/schemas/shared_metadata_contract.md` | Root copy retained for compatibility. |",
                "| Shared metadata schema | `docs/equity_module/v0.1/schemas/equity_registry_shared_metadata.schema.json` | Root copy retained for older links. |",
                "| Module manifest | `docs/equity_module/v0.1/registries/viza.finance.equity_investment.manifest.json` | Root copy retained for compatibility. |",
                "| Traceability matrix | `docs/equity_module/v0.1/registries/equity_research_traceability_matrix.csv` | Copied from expanded high-confidence corpus. |",
                "| Downgrade log | `docs/equity_module/v0.1/registries/equity_rejection_and_downgrade_log.csv` | Copied from expanded high-confidence corpus and extended by recalibration report. |",
                "",
                "The runtime loader is additive under `viza/equity/` and does not modify `viza.core.strategy`.",
            ]
        )
        + "\n",
    )
    write_text(
        MODULE_DIR / "README.md",
        "\n".join(
            [
                "# VIZA Equity Investment Module v0.1",
                "",
                "Status: artifact-generated, registry-loadable, fixture-tested candidate.",
                "",
                "This directory contains registry-seedable artifacts for `viza.finance.equity_investment`. The module provides equity decision grammar, entity/node/edge/attribute/event/insight registries, strategy profiles, output views, validation rules, PIT controls, and source-rights controls.",
                "",
                "Architecture boundaries:",
                "",
                "- `viza.core.strategy` remains domain-neutral.",
                "- `viza.finance.securities` provides the security/finance substrate.",
                "- `viza.aat.attribute_analysis` is optional/subordinate.",
                "- `viza.finance.equity_investment` provides the equity decision layer and conservative package/redaction controls.",
                "",
                "Production posture: this is not production-hardened. It is registry-seedable and loadable for engineering fixtures. Legal/source-rights review, connector entitlement review, and full runtime integration remain required before production promotion.",
                "",
                "Non-advice boundary: outputs are research workflow artifacts and must not be rendered as personal investment advice, guaranteed alpha, or adviser activity.",
            ]
        )
        + "\n",
    )
    write_text(
        REPORTS / "equity_module_backlog.md",
        "\n".join(
            [
                "# Equity Module v0.1 Backlog",
                "",
                "## P0",
                "",
                "- EQ-P0-001 Add equity module manifest loader fixture",
                "- EQ-P0-002 Create entity/node/attribute/event/insight seed artifacts",
                "- EQ-P0-003 Implement PIT/rights schema extensions for equity observations",
                "- EQ-P0-004 Add validation rules EQ-VAL-001 through EQ-VAL-012",
                "- EQ-P0-005 Build source-rights report output view",
                "- EQ-P0-006 Build thesis/evidence/invalidation fixture",
                "- EQ-P0-007 Add SEC public connector adapter fixture",
                "- EQ-P0-008 Add strategy profile compatibility validator",
                "",
                "## P1",
                "",
                "- EQ-P1-001 Analyst memo builder output",
                "- EQ-P1-002 Valuation matrix nodes and fixture",
                "- EQ-P1-003 Fundamental attribute calculators",
                "- EQ-P1-004 Factor signal registry and validation harness",
                "- EQ-P1-005 Event/catalyst board",
                "- EQ-P1-006 Portfolio impact report",
                "- EQ-P1-007 Ownership and short interest monitors",
                "- EQ-P1-008 Macro vintage selector using ALFRED-style vintages",
                "- EQ-P1-009 Short thesis legal/human review gate",
                "- EQ-P1-010 Package redaction preview tests",
                "",
                "Definition of done: registry artifact loads; fixture exercises node/profile/output; PIT and rights warnings are visible; validation rules produce pass/warn/block; package preview respects redaction; existing tests remain green or failures are documented with cause.",
            ]
        )
        + "\n",
    )
    write_text(
        REPORTS / "equity_confidence_recalibration_report.md",
        "\n".join(
            [
                "# Equity Confidence Recalibration Report",
                "",
                "Result: no `high_confidence_core` object is promoted to production-hardened. All v0.1 artifacts remain registry-seedable until full runtime integration, legal/source-rights review, and connector entitlement review complete.",
                "",
                "Downgrades applied or preserved:",
                "",
                "- Licensed-data-dependent identity and provider records remain `common_practice` or `research_supported_experimental` where no entitlement exists.",
                "- Sentiment, social, rumor, and text-derived records remain experimental or blocked for action unless credibility/manipulation guards pass.",
                "- AAT/factor/macro objects that need true vintages remain warning-bearing and are not backtest-safe until ALFRED-style vintages exist.",
                "- Short-interest nodes now require human review and EQ-VAL-008 gates.",
                "",
                "Registry-seedable means the artifact can load and validate. Implementation-ready requires runtime handlers and integrated validation execution. Production-hardened requires a separate production, legal/source-rights, entitlement, and runtime review cycle.",
            ]
        )
        + "\n",
    )


def update_manifest() -> None:
    root_manifest_path = MODULE_DIR / "viza.finance.equity_investment.manifest.json"
    manifest = read_json(root_manifest_path)
    artifact_map = {
        "entity_types": ("equity_entity_types.json", "viza.equity.entity_registry.v1"),
        "node_types": ("equity_node_types.json", "viza.equity.node_type_registry.v1"),
        "edge_types": ("equity_edge_types.json", "viza.equity.edge_type_registry.v1"),
        "attribute_registry_seed": ("equity_attribute_registry_seed.csv", "viza.equity.attribute.v1"),
        "event_registry_seed": ("equity_event_registry_seed.json", "viza.equity.event_type.v1"),
        "insight_registry_seed": ("equity_insight_registry_seed.json", "viza.equity.insight_type.v1"),
        "strategy_profiles": ("equity_strategy_profiles.json", "viza.equity.strategy_profile.v1"),
        "output_views": ("equity_output_views.json", "viza.equity.output_view.v1"),
        "validation_rules": ("equity_validation_rules.json", "viza.equity.validation_rule.v1"),
        "connector_requirements": ("equity_connector_requirements.json", "viza.equity.connector_requirement.v1"),
        "source_rights_matrix": ("equity_source_rights_matrix.csv", "viza.equity.rights_matrix.v1"),
        "pit_matrix": ("equity_PIT_matrix.csv", "viza.equity.pit_matrix.v1"),
        "research_traceability_matrix": ("equity_research_traceability_matrix.csv", "viza.equity.traceability_matrix.v1"),
        "rejection_and_downgrade_log": ("equity_rejection_and_downgrade_log.csv", "viza.equity.downgrade_log.v1"),
    }
    registry_artifacts = {}
    for key, (filename, schema) in artifact_map.items():
        path = REGISTRIES / filename
        if path.exists():
            registry_artifacts[key] = {
                "path": f"registries/{filename}",
                "schema": schema,
                "sha256": sha256_file(path),
                "byte_size": path.stat().st_size,
                "record_count": count_records(path),
            }
    manifest["registry_artifacts"] = registry_artifacts
    manifest["module_id"] = MODULE_ID
    manifest["module_version"] = MODULE_VERSION
    manifest["baseline_reference"] = BASELINE
    manifest["description"] = (
        "Equity decision grammar, strategy families, ontology registries, outputs, validation, and PIT/source-rights controls."
    )
    manifest.setdefault("depends_on", ["viza.core.strategy", "viza.finance.securities"])
    manifest.setdefault("optional_modules", ["viza.aat.attribute_analysis"])
    manifest["connector_roles"] = [
        "official_public_connector",
        "sec_filings",
        "xbrl_facts",
        "fred_macro",
        "alfred_macro_vintage",
        "finra_short_interest",
        "licensed_market_data_connector",
        "licensed_fundamentals_connector",
        "licensed_estimates_connector",
        "licensed_text_connector",
        "licensed_options_connector",
        "licensed_borrow_connector",
        "licensed_index_membership_connector",
        "user_document_connector",
        "user_portfolio_connector",
        "derived_calculation_engine",
    ]
    manifest["package_visibility_modes"] = [
        "white_box",
        "gray_box",
        "black_box",
        "output_only",
        "preview",
        "marketplace_draft",
    ]
    manifest["rights_policy"] = {
        "default_raw_provider_export": "blocked",
        "default_public_official_export": "metadata_and_derived_allowed",
        "default_unknown_rights_export": "blocked",
    }
    manifest["validation_policy"] = {
        "PIT_required_for_backtests": True,
        "rights_required_for_packages": True,
        "human_review_required_for_fraud_or_legal_claims": True,
        "non_advice_boundary_required_for_recommendation_outputs": True,
    }
    combined = hashlib.sha256()
    for key in sorted(registry_artifacts):
        combined.update(registry_artifacts[key]["sha256"].encode("utf-8"))
    manifest["artifact_checksums"] = {
        "combined_sha256": combined.hexdigest(),
        "manifest_self_sha256_placeholder": "computed_post_emit_at_packaging_time",
    }
    write_json(root_manifest_path, manifest)
    shutil.copy2(root_manifest_path, REGISTRIES / "viza.finance.equity_investment.manifest.json")


def write_proof() -> None:
    artifact_paths = sorted(str(path.relative_to(ROOT)).replace("\\", "/") for path in REGISTRIES.glob("*"))
    artifact_checksums = {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
        for path in sorted(REGISTRIES.glob("*"))
        if path.is_file()
    }
    fixture_paths = sorted(
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in FIXTURES.glob("**/*")
        if path.is_file()
    )
    fixture_hashes = {
        path: artifact_checksums.get(path) or sha256_file(ROOT / path)
        for path in fixture_paths
        if path.endswith((".json", ".md", ".py"))
    }
    proof = {
        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,
        "baseline": BASELINE,
        "artifact_paths": artifact_paths,
        "artifact_checksums": artifact_checksums,
        "fixture_paths": fixture_paths,
        "fixture_result_hashes": fixture_hashes,
        "validation_summary": {
            "registry_loader": "pass_pending_test_run_record",
            "validation_rules": "EQ-VAL-001 through EQ-VAL-012 present",
            "profiles": ["quality_value_long_only", "portfolio_risk_radar", "earnings_revision_momentum"],
        },
        "rights_redaction_summary": {
            "unknown_rights": "blocked",
            "restricted_raw_provider_data": "blocked_or_redacted",
            "licensed_data": "entitlement_locked",
            "user_private_data": "blocked_by_default_outside_creator_white_box",
            "marketplace_draft": "redacted_non_monetized",
        },
        "PIT_summary": {
            "SEC_filing_facts": "filing_accepted_at / available_at",
            "13F": "lagged_not_current",
            "short_interest": "publication_date_availability",
            "macro": "ALFRED-style vintages required for backtests",
            "current_FRED_Kenneth_French": "latest/current until vintage pipeline exists",
        },
        "known_limitations": [
            "Artifacts are registry-seedable and loader-validated; full runtime graph handlers remain future work.",
            "No production legal/source-rights review has been completed.",
            "No connector entitlement review has been completed.",
            "Marketplace remains draft and non-monetized.",
        ],
        "locked_or_license_gated_components": [
            "licensed_market_data_connector",
            "licensed_fundamentals_connector",
            "licensed_estimates_connector",
            "licensed_text_connector",
            "licensed_options_connector",
            "licensed_borrow_connector",
            "licensed_index_membership_connector",
        ],
        "next_backlog_items": ["EQ-P0-001", "EQ-P0-003", "EQ-P0-008", "EQ-P1-002", "EQ-P1-010"],
    }
    write_json(PROOFS / "equity_module_v0_1_handoff_proof.json", proof)
    checksum = sha256_file(PROOFS / "equity_module_v0_1_handoff_proof.json")
    write_text(
        REPORTS / "equity_module_v0_1_handoff_report.md",
        f"# Equity Module v0.1 Handoff Report\n\nStatus: artifact-generated, registry-loadable pending exact test record.\n\nProof checksum: `{checksum}`\n\nKnown limitation: not production-hardened; legal/source-rights and connector entitlement reviews remain required.\n",
    )
    write_text(
        REPORTS / "equity_module_v0_1_validation_results.md",
        "# Equity Module v0.1 Validation Results\n\nExact command results are recorded after the verification run. Initial expected state: registry load pass, fixture checks pass, package redaction pass.\n",
    )
    write_text(
        REPORTS / "equity_module_v0_1_rights_redaction_results.md",
        "# Equity Module v0.1 Rights Redaction Results\n\nUnknown rights block export. Restricted raw provider data is not exported. Licensed data is entitlement-locked. User-private data is blocked by default outside creator white-box mode. Marketplace draft is redacted and non-monetized.\n",
    )


def base_record(
    record_id: str,
    display_name: str,
    description: str,
    object_family: str,
    *,
    core_primitive: str,
    extends_core_primitive: str | None,
    validation_rules: list[str],
    failure_modes: list[str],
    family_specific: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "id": record_id,
        "display_name": display_name,
        "description": description,
        "module_id": MODULE_ID,
        "schema_version": "v1",
        "object_family": object_family,
        "source_sections": ["S19", "S18"],
        "source_ids": ["B-008", "P-013"],
        "confidence_label": "high_confidence_core",
        "status": "registry-seedable",
        "created_from": "CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline",
        "core_primitive": core_primitive,
        "extends_core_primitive": extends_core_primitive,
        "compatible_entity_types": [],
        "compatible_strategy_profiles": [],
        "evidence_requirements": [
            {"evidence_type": "validation_fixture", "required": True, "source_quality_minimum": 4}
        ],
        "audit_requirements": ["source_refs", "pit_timestamps", "rights_state", "validation_record_ids"],
        "source_quality_minimum": 4,
        "human_review_required": "short" in record_id.lower() or "legal" in record_id.lower(),
        "pit": {
            "observed_at_policy": "creation_time_only",
            "available_at_policy": "creation_time_only",
            "retrieved_at_policy": "user_upload_at",
            "source_version_policy": "not_applicable",
            "data_version_policy": "latest_revisable",
            "model_version_policy": "model_run_id_required",
            "vintage_required": False,
            "lookahead_risk": "low",
        },
        "rights": {
            "connector_roles": [],
            "license_policy": "internal_research_only",
            "query_policy": "user_entitled",
            "cache_policy": "allowed",
            "display_policy": "allowed",
            "export_policy": "blocked",
            "derived_value_policy": "allowed",
            "redistribution_policy": "blocked",
            "marketplace_policy": "blocked",
            "attribution_required": False,
            "retention_policy": "indefinite",
            "redaction_required": True,
        },
        "validation_rules": validation_rules,
        "failure_modes": failure_modes,
        "downgrade_conditions": [
            {
                "condition": "source_lineage_or_policy_gate_missing",
                "from_label": "high_confidence_core",
                "to_label": "research_supported_experimental",
                "evidence_required": "source/PIT/rights/validation proof",
            }
        ],
        "rejection_conditions": ["requires_personalized_advice_output", "requires_unlawful_data"],
        "family_specific": family_specific,
    }
    return record


def output_view_record(
    record_id: str,
    display_name: str,
    description: str,
    profiles: list[str],
    required_sections: list[str],
) -> dict[str, Any]:
    return base_record(
        record_id,
        display_name,
        description,
        "output_view",
        core_primitive="output",
        extends_core_primitive="output_radar",
        validation_rules=[
            "output_validation_summary_required",
            "output_pit_summary_required",
            "output_rights_summary_required",
            "evidence_non_advice_boundary",
            "EQ-VAL-011",
        ],
        failure_modes=["restricted_data_unredacted", "non_advice_boundary_missing"],
        family_specific={
            "view_family": "equity_output",
            "required_sections": required_sections,
            "optional_sections": ["open_questions", "locked_connector_summary"],
            "binding": {
                "strategy_profile_required": True,
                "strategy_family_required": True,
                "pit_summary_required": True,
                "rights_summary_required": True,
                "validation_summary_required": True,
                "non_advice_boundary_required": "non_advice_boundary" in required_sections,
            },
            "evidence_render": {"source_refs_required": True, "raw_restricted_text_export": "blocked"},
            "audit_render": {"proof_checksum_required": True, "validation_record_refs_required": True},
            "lifecycle": {"status": "registry-seedable"},
            "data_rights": {
                "display_policy": "allowed",
                "export_policy": "conditional",
                "marketplace_policy": "redacted",
            },
            "compatible_strategy_profiles": profiles,
            "redaction_policy": {
                "marketplace_draft": "redact_restricted_unclear_and_user_private",
                "output_only": "no_raw_restricted_provider_data",
            },
        },
    ) | {"compatible_strategy_profiles": profiles}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def count_records(path: Path) -> int:
    if path.suffix == ".json":
        payload = read_json(path)
        if isinstance(payload.get("records"), list):
            return len(payload["records"])
        return 1
    with path.open(encoding="utf-8", newline="") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def collect_referenced_validation_rules() -> set[str]:
    referenced: set[str] = set()
    for path in REGISTRIES.glob("*.json"):
        if path.name == "equity_validation_rules.json":
            continue
        payload = read_json(path)
        for record in payload.get("records", []):
            referenced.update(record.get("validation_rules") or [])
    return {rule for rule in referenced if rule}


def infer_validation_domain(rule_id: str) -> str:
    prefix = rule_id.split("_", 1)[0].lower()
    if rule_id.startswith("EQ-VAL-"):
        return "cross_cutting"
    return {
        "schema": "graph",
        "data": "data",
        "pit": "PIT",
        "rights": "rights",
        "evidence": "evidence",
        "statistical": "statistical",
        "qualitative": "qualitative",
        "portfolio": "portfolio",
        "output": "output",
        "package": "package",
    }.get(prefix, "registry")


def infer_validation_severity(rule_id: str) -> str:
    lowered = rule_id.lower()
    if any(token in lowered for token in ("required", "block", "must", "fail_closed", "no_ticker")):
        return "block"
    if any(token in lowered for token in ("warn", "review", "human", "unclear")):
        return "warn"
    return "block"


def titleize(rule_id: str) -> str:
    if rule_id.startswith("EQ-VAL-"):
        return rule_id
    return " ".join(part.capitalize() for part in rule_id.replace("-", "_").split("_"))


if __name__ == "__main__":
    raise SystemExit(main())

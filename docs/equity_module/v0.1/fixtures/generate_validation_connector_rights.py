#!/usr/bin/env python3
"""
Generator for:
  - docs/equity_module/v0.1/registries/equity_validation_rules.json
  - docs/equity_module/v0.1/registries/equity_connector_requirements.json
  - docs/equity_module/v0.1/registries/equity_source_rights_matrix.csv

Source of truth: docs/CLAUDE_EQUITY_MODULE.md.
Primary sections: §18 (data architecture / source rights / PIT), §19 (validation framework),
§40 (success criteria / acceptance gate), §§6-17 (domain-specific validation).

Restrictive defaults:
  - Unclear / unknown rights -> export blocked, marketplace redacted, redaction required.
  - License missing -> connector fails closed (no query).
  - Validation severity escalates to block when CLAUDE.md project rules are violated.
"""

import csv
import json
from copy import deepcopy
from pathlib import Path

OUT_VR = Path("C:/Users/gkwls/AAT/docs/equity_module/v0.1/registries/equity_validation_rules.json")
OUT_CR = Path("C:/Users/gkwls/AAT/docs/equity_module/v0.1/registries/equity_connector_requirements.json")
OUT_SR = Path("C:/Users/gkwls/AAT/docs/equity_module/v0.1/registries/equity_source_rights_matrix.csv")


# ---------- Common helpers ----------
def _rights_validation():
    return {
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
    }


def _rights_for_connector(license_policy, connector_roles):
    if license_policy == "public_official":
        return {
            "connector_roles": connector_roles,
            "license_policy": "public_official",
            "query_policy": "allowed",
            "cache_policy": "allowed",
            "display_policy": "allowed",
            "export_policy": "allowed",
            "derived_value_policy": "allowed",
            "redistribution_policy": "allowed",
            "marketplace_policy": "allowed",
            "attribution_required": False,
            "retention_policy": "indefinite",
            "redaction_required": False,
        }
    if license_policy == "public_professional":
        return {
            "connector_roles": connector_roles,
            "license_policy": "public_professional",
            "query_policy": "allowed",
            "cache_policy": "allowed",
            "display_policy": "allowed",
            "export_policy": "conditional",
            "derived_value_policy": "allowed",
            "redistribution_policy": "conditional",
            "marketplace_policy": "conditional",
            "attribution_required": True,
            "retention_policy": "indefinite",
            "redaction_required": False,
        }
    if license_policy == "academic_public":
        return {
            "connector_roles": connector_roles,
            "license_policy": "academic_public",
            "query_policy": "allowed",
            "cache_policy": "allowed",
            "display_policy": "allowed",
            "export_policy": "allowed",
            "derived_value_policy": "allowed",
            "redistribution_policy": "allowed",
            "marketplace_policy": "allowed",
            "attribution_required": True,
            "retention_policy": "indefinite",
            "redaction_required": False,
        }
    if license_policy == "licensed_provider_required":
        return {
            "connector_roles": connector_roles,
            "license_policy": "licensed_provider_required",
            "query_policy": "user_entitled",
            "cache_policy": "conditional",
            "display_policy": "conditional",
            "export_policy": "conditional",
            "derived_value_policy": "conditional",
            "redistribution_policy": "blocked",
            "marketplace_policy": "redacted",
            "attribution_required": True,
            "retention_policy": "until_license_expires",
            "redaction_required": True,
        }
    if license_policy == "restricted_or_unclear":
        return {
            "connector_roles": connector_roles,
            "license_policy": "restricted_or_unclear",
            "query_policy": "blocked",
            "cache_policy": "blocked",
            "display_policy": "conditional",
            "export_policy": "blocked",
            "derived_value_policy": "blocked",
            "redistribution_policy": "blocked",
            "marketplace_policy": "blocked",
            "attribution_required": True,
            "retention_policy": "delete_on_user_revocation",
            "redaction_required": True,
        }
    if license_policy == "internal_research_only":
        return {
            "connector_roles": connector_roles,
            "license_policy": "internal_research_only",
            "query_policy": "user_entitled",
            "cache_policy": "allowed",
            "display_policy": "allowed",
            "export_policy": "blocked",
            "derived_value_policy": "conditional",
            "redistribution_policy": "blocked",
            "marketplace_policy": "blocked",
            "attribution_required": False,
            "retention_policy": "delete_on_user_revocation",
            "redaction_required": True,
        }
    if license_policy == "user_entitled_provider":
        return {
            "connector_roles": connector_roles,
            "license_policy": "user_entitled_provider",
            "query_policy": "user_entitled",
            "cache_policy": "allowed",
            "display_policy": "allowed",
            "export_policy": "conditional",
            "derived_value_policy": "allowed",
            "redistribution_policy": "conditional",
            "marketplace_policy": "conditional",
            "attribution_required": True,
            "retention_policy": "until_license_expires",
            "redaction_required": False,
        }
    if license_policy == "derived_only":
        return {
            "connector_roles": connector_roles,
            "license_policy": "derived_only",
            "query_policy": "user_entitled",
            "cache_policy": "conditional",
            "display_policy": "allowed",
            "export_policy": "conditional",
            "derived_value_policy": "allowed",
            "redistribution_policy": "blocked",
            "marketplace_policy": "redacted",
            "attribution_required": True,
            "retention_policy": "until_license_expires",
            "redaction_required": True,
        }
    raise SystemExit(f"unknown license_policy: {license_policy}")


def _pit_creation():
    return {
        "observed_at_policy": "creation_time_only",
        "available_at_policy": "creation_time_only",
        "retrieved_at_policy": "user_upload_at",
        "source_version_policy": "not_applicable",
        "data_version_policy": "latest_revisable",
        "model_version_policy": "model_run_id_required",
        "vintage_required": False,
        "lookahead_risk": "low",
    }


# ---------- VALIDATION RULES ----------
VRULES = []


def VR(rid, name, level, domain, applies_to, severity, *,
       description, target_type, test_method, pass_condition, warning_condition, fail_condition,
       confidence_impact, required_inputs, evidence_refs, audit_fields,
       pit_summary, rights_summary, target_id_or_family,
       source_sections, source_ids, confidence_label="high_confidence_core",
       human_review=False):
    VRULES.append({
        "id": rid,
        "name": name,
        "description": description,
        "level": level,
        "domain": domain,
        "applies_to": applies_to,
        "severity": severity,
        "target_type": target_type,
        "target_id_or_family": target_id_or_family,
        "required_inputs": required_inputs,
        "test_method": test_method,
        "pass_condition": pass_condition,
        "warning_condition": warning_condition,
        "fail_condition": fail_condition,
        "confidence_impact": confidence_impact,
        "evidence_refs": evidence_refs,
        "audit_fields": audit_fields,
        "pit_requirements_summary": pit_summary,
        "rights_requirements_summary": rights_summary,
        "source_sections": source_sections,
        "source_ids": source_ids,
        "confidence_label": confidence_label,
        "human_review": human_review,
    })


# Schema-level (graph) rules
VR("schema_graph_schema_supported", "Graph schema_version supported", "schema", "graph",
   ["graph"], "block",
   description="Graph schema_version must equal viza_graph_v0.",
   target_type="graph", target_id_or_family=["viza_graph_v0"],
   required_inputs=["graph.schema_version"],
   test_method="equal",
   pass_condition="schema_version == 'viza_graph_v0'",
   warning_condition="schema_version is missing or empty",
   fail_condition="schema_version not in {'viza_graph_v0'}",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§19.4 graph_validation", "§21"],
   audit_fields=["methodology_graph_hash"],
   pit_summary=["not_applicable"],
   rights_summary=["not_applicable"],
   source_sections=["§19.4", "§21"], source_ids=["P-013"])

VR("schema_node_types_in_palette", "Node types in palette", "schema", "graph",
   ["graph", "node_type"], "block",
   description="Every graph node must reference a registered node_type in equity_node_types.json.",
   target_type="graph", target_id_or_family=["graph"],
   required_inputs=["graph.nodes", "registries.equity_node_types"],
   test_method="set_membership",
   pass_condition="every graph node's type is registered",
   warning_condition="one or more node types are unregistered",
   fail_condition="any graph node references an unregistered node type",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§19.4 graph_validation"],
   audit_fields=["methodology_graph_hash"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§19.4"], source_ids=["P-013"])

VR("schema_edge_types_in_palette", "Edge types in palette", "schema", "graph",
   ["graph", "edge_type"], "block",
   description="Every graph edge must reference a registered edge_type.",
   target_type="graph", target_id_or_family=["graph"],
   required_inputs=["graph.edges", "registries.equity_edge_types"],
   test_method="set_membership",
   pass_condition="every edge's type is registered",
   warning_condition="one or more edges have unregistered types",
   fail_condition="any edge references an unregistered edge type",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§19.4 graph_validation"], audit_fields=["methodology_graph_hash"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§19.4"], source_ids=["P-013"])

VR("schema_no_cycles_in_data_flow", "No cycles in data_flow", "schema", "graph",
   ["graph"], "block",
   description="The data_flow subgraph must be acyclic.",
   target_type="graph", target_id_or_family=["graph"],
   required_inputs=["graph.edges"],
   test_method="dag_check",
   pass_condition="data_flow subgraph is acyclic",
   warning_condition="cycle detected and broken by deduplication",
   fail_condition="cycle remains in data_flow subgraph",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§19.4 graph_validation"],
   audit_fields=["methodology_graph_hash"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§19.4"], source_ids=["P-013"])

VR("schema_output_radar_reachable", "Output Radar reachable from Universe", "schema", "graph",
   ["graph"], "block",
   description="At least one Universe node must reach at least one Output Radar node.",
   target_type="graph", target_id_or_family=["graph"],
   required_inputs=["graph.nodes", "graph.edges"],
   test_method="reachability",
   pass_condition="output_radar is reachable from a universe node via data_flow",
   warning_condition="output_radar reachable via relationship edges only",
   fail_condition="no path from universe to output_radar",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§19.4 graph_validation"],
   audit_fields=["methodology_graph_hash"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§19.4"], source_ids=["P-013"])

# Data-level rules
VR("data_source_id_required", "Source ID required", "data", "data",
   ["attribute", "event_type", "filing", "evidence", "validation_record"], "block",
   description="Every observation-bearing record must carry a non-empty source_id traceable to the corpus.",
   target_type="any", target_id_or_family=["attribute", "event_type", "filing"],
   required_inputs=["record.source_id"],
   test_method="non_empty_string",
   pass_condition="record.source_id is a non-empty string traceable to the source corpus",
   warning_condition="record.source_id is empty but record is preview-only",
   fail_condition="record.source_id is empty for a production record",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§19.4 data_validation"],
   audit_fields=["source_refs", "evidence_checksum"],
   pit_summary=["available_at_required"], rights_summary=["display_policy_required"],
   source_sections=["§19.4", "§2.5"], source_ids=["P-013"])

VR("data_observed_at_required", "observed_at required", "data", "PIT",
   ["attribute", "event_type"], "block",
   description="Observation-bearing records must declare observed_at_policy.",
   target_type="attribute", target_id_or_family=["attribute", "event_type"],
   required_inputs=["record.pit.observed_at_policy"],
   test_method="enum_membership",
   pass_condition="observed_at_policy is one of the registered enum values and not not_applicable for observations",
   warning_condition="observed_at_policy is set to unknown",
   fail_condition="observed_at_policy is missing or not_applicable on an observation-bearing record",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§18.6"], audit_fields=["pit_timestamps"],
   pit_summary=["observed_at_required"], rights_summary=["not_applicable"],
   source_sections=["§18.6", "§19.4"], source_ids=["P-013"])

VR("data_available_at_required", "available_at required", "data", "PIT",
   ["attribute", "event_type"], "block",
   description="Observation-bearing records must declare available_at_policy.",
   target_type="attribute", target_id_or_family=["attribute", "event_type"],
   required_inputs=["record.pit.available_at_policy"],
   test_method="enum_membership",
   pass_condition="available_at_policy declared and concrete",
   warning_condition="available_at_policy set to unknown",
   fail_condition="available_at_policy missing or not_applicable on observation",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§18.6"], audit_fields=["pit_timestamps"],
   pit_summary=["available_at_required"], rights_summary=["not_applicable"],
   source_sections=["§18.6"], source_ids=["P-013"])

VR("data_retrieved_at_required", "retrieved_at required", "data", "PIT",
   ["attribute", "event_type", "connector_requirement"], "warn",
   description="Records ingested via connector must declare retrieved_at_policy.",
   target_type="any", target_id_or_family=["attribute", "event_type", "connector_requirement"],
   required_inputs=["record.pit.retrieved_at_policy"],
   test_method="enum_membership",
   pass_condition="retrieved_at_policy set to vendor_retrieval_at or connector_ingest_at",
   warning_condition="retrieved_at_policy set to user_upload_at on a connector-bound record",
   fail_condition="retrieved_at_policy missing",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§18.6"], audit_fields=["pit_timestamps"],
   pit_summary=["retrieved_at_required"], rights_summary=["not_applicable"],
   source_sections=["§18.6"], source_ids=["P-013"])

VR("data_no_ticker_as_primary_key", "No ticker as primary key", "data", "data",
   ["entity_type", "attribute", "edge_type"], "block",
   description="ticker is display-only and must never be the primary key.",
   target_type="entity_type", target_id_or_family=["equity_security", "company", "share_class"],
   required_inputs=["record.family_specific.immutable_keys"],
   test_method="set_disjoint",
   pass_condition="immutable_keys does not contain 'ticker'",
   warning_condition="ticker present in identifiers but not immutable_keys",
   fail_condition="immutable_keys contains 'ticker' or any ticker-derived alias",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["CLAUDE.md project rule", "§20.4"],
   audit_fields=["source_refs"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§20.4", "CLAUDE.md"], source_ids=["B-008"])

# PIT-level rules
VR("pit_no_lookahead", "No lookahead", "PIT", "PIT",
   ["graph", "attribute", "event_type", "strategy_profile", "validation_record"], "block",
   description="Every scoring/gating input used by a decision must have available_at <= decision_timestamp.",
   target_type="graph", target_id_or_family=["graph"],
   required_inputs=["graph.execution_inputs", "decision.decision_timestamp"],
   test_method="temporal_inequality",
   pass_condition="every scoring input available_at <= decision_timestamp",
   warning_condition="latest_only inputs used and explicitly labeled not_backtest_safe",
   fail_condition="any scoring input has available_at > decision_timestamp",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§3.18", "§18.6"],
   audit_fields=["pit_timestamps", "validation_record_ids"],
   pit_summary=["available_at_required", "vintage_required_when_data_version_policy_unknown"],
   rights_summary=["not_applicable"],
   source_sections=["§3.18", "§18.6"], source_ids=["P-013"])

VR("pit_vintage_required_for_backtest", "Vintage required for backtest", "PIT", "PIT",
   ["attribute", "event_type", "strategy_profile"], "block",
   description="Backtest inputs requiring vintage (macro, factor, consensus, restatement) must use vintaged data.",
   target_type="any", target_id_or_family=["macro", "factor_exposure", "fundamental_growth"],
   required_inputs=["record.pit.data_version_policy", "record.pit.vintage_required"],
   test_method="conditional",
   pass_condition="vintage_required=true AND data_version_policy in {vintaged, event_pit}",
   warning_condition="vintage_required=true AND data_version_policy=latest_revisable AND record is display-only",
   fail_condition="vintage_required=true AND data_version_policy in {latest_only, latest_revisable, unknown} for a backtest input",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§16.10", "§18.8"], audit_fields=["pit_timestamps", "data_version_policy"],
   pit_summary=["vintage_required", "data_version_policy_must_be_vintaged_or_event_pit"],
   rights_summary=["not_applicable"],
   source_sections=["§16.10", "§18.8"], source_ids=["MA-001", "DA-003"])

VR("pit_restatement_revintage_required", "Restatement re-vintage required", "PIT", "PIT",
   ["fundamental_growth", "fundamental_margin", "cash_flow", "balance_sheet", "accounting_quality"], "error",
   description="Restated filings must use the amendment chain; original values cannot be silently overwritten.",
   target_type="attribute", target_id_or_family=["financial_statement"],
   required_inputs=["record.pit.source_version_policy"],
   test_method="enum_membership",
   pass_condition="source_version_policy=filing_amendment_chain",
   warning_condition="restatement detected but amendment chain incomplete",
   fail_condition="restated value used without amendment chain",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§6.10", "§18.8"], audit_fields=["pit_timestamps", "source_refs"],
   pit_summary=["source_version_policy=filing_amendment_chain"],
   rights_summary=["not_applicable"],
   source_sections=["§6.10", "§18.8"], source_ids=["F-014"])

VR("pit_thirteenf_lag", "13F 45-day lag", "PIT", "PIT",
   ["ownership", "event_type"], "block",
   description="13F holdings are 45-day-lagged. They must never be used as current positioning.",
   target_type="attribute", target_id_or_family=["institutional_ownership_pct", "top10_institutional_pct"],
   required_inputs=["record.family_specific.timestamp_policy"],
   test_method="conditional",
   pass_condition="13F-derived attribute used only with filing_accepted_at as available_at and never as 'current' positioning",
   warning_condition="13F attribute used for cross-sectional ranking but explicitly labeled as 45-day-lagged",
   fail_condition="13F-derived attribute treated as current positioning",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§14.9"], audit_fields=["pit_timestamps"],
   pit_summary=["13f_45_day_lag_never_current_positioning"],
   rights_summary=["not_applicable"],
   source_sections=["§14.9", "§18.8"], source_ids=["OW-022"])

VR("pit_short_interest_publication_date", "Short interest uses publication date", "PIT", "PIT",
   ["short_interest"], "block",
   description="Short interest uses FINRA publication date (not settlement date) and must never be interpolated.",
   target_type="attribute", target_id_or_family=["short_interest_pct_float", "days_to_cover"],
   required_inputs=["record.family_specific.timestamp_policy"],
   test_method="conditional",
   pass_condition="short_interest available_at = FINRA release_date and not interpolated",
   warning_condition="short_interest displayed as continuous series with visible interpolation warning",
   fail_condition="short_interest used as continuous series without warning, or interpolated for backtest",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§12.12", "§14.9"], audit_fields=["pit_timestamps"],
   pit_summary=["short_interest_uses_publication_date_for_available_at"],
   rights_summary=["not_applicable"],
   source_sections=["§12.12", "§14.9"], source_ids=["TE-030"])

VR("pit_alfred_macro_required_for_backtest", "ALFRED required for macro backtest", "PIT", "PIT",
   ["macro"], "block",
   description="Macro backtests require ALFRED-style vintages. FRED current/latest data is not PIT-safe.",
   target_type="attribute", target_id_or_family=["macro"],
   required_inputs=["record.pit.data_version_policy"],
   test_method="conditional",
   pass_condition="macro backtest uses ALFRED vintages with data_version_policy=vintaged",
   warning_condition="macro backtest uses FRED current data and is explicitly labeled latest_only / not_backtest_safe",
   fail_condition="macro backtest uses FRED current data without vintaged flag",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§16.10", "§18.8"], audit_fields=["pit_timestamps"],
   pit_summary=["alfred_pipeline_required"], rights_summary=["public_official"],
   source_sections=["§16.10", "§18.8"], source_ids=["MA-001", "DA-003"])

# Rights-level rules
VR("rights_rights_policy_required", "Rights policy required", "rights", "rights",
   ["attribute", "event_type", "insight_type", "connector_requirement"], "block",
   description="Every observation-bearing record must declare a complete rights block.",
   target_type="any", target_id_or_family=["attribute", "event_type", "insight_type"],
   required_inputs=["record.rights"],
   test_method="schema_required_block",
   pass_condition="record.rights has all 12 required fields",
   warning_condition="rights present but one or more optional fields missing",
   fail_condition="record.rights missing or any required field absent",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§18.7"], audit_fields=["rights_state"],
   pit_summary=["not_applicable"], rights_summary=["all_12_fields_required"],
   source_sections=["§18.7"], source_ids=["DA-007"])

VR("rights_restricted_no_export", "Restricted raw data cannot export", "rights", "rights",
   ["attribute", "event_type", "package"], "block",
   description="Records with restricted_or_unclear or licensed_provider_required raw data cannot be exported in raw form.",
   target_type="package", target_id_or_family=["package", "attribute", "event_type"],
   required_inputs=["record.rights.license_policy", "record.rights.export_policy"],
   test_method="conditional",
   pass_condition="license=restricted_or_unclear OR licensed_provider_required => export_policy in {blocked, conditional}",
   warning_condition="license=licensed_provider_required with export_policy=conditional and explicit user opt-in",
   fail_condition="license restricted/licensed but export_policy=allowed",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§18.5", "§18.14"], audit_fields=["rights_state"],
   pit_summary=["not_applicable"],
   rights_summary=["license_unknown_blocks_export", "licensed_blocks_redistribution"],
   source_sections=["§18.5", "§18.14"], source_ids=["DA-020"])

VR("rights_production_connector_fail_closed", "Production connector fails closed without credentials", "rights", "rights",
   ["connector_requirement"], "block",
   description="Production-required connectors must fail closed (query_policy=blocked) when license_status=missing.",
   target_type="connector_requirement", target_id_or_family=["connector_requirement"],
   required_inputs=["connector.production_required", "connector.entitlement_metadata.license_status", "connector.rights.query_policy"],
   test_method="conditional",
   pass_condition="production_required=true AND license_status=missing => query_policy=blocked",
   warning_condition="license_status=pending and runtime is dev-mode",
   fail_condition="production_required=true AND license_status=missing AND query_policy != blocked",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["CLAUDE.md project rule", "§18.10"], audit_fields=["rights_state", "connector_entitlement_record"],
   pit_summary=["not_applicable"], rights_summary=["fail_closed_on_missing_license"],
   source_sections=["§18.10", "CLAUDE.md"], source_ids=["B-008"])

VR("rights_unclear_defaults_restrictive", "Unclear rights default to restrictive policies", "rights", "rights",
   ["attribute", "event_type", "insight_type", "package"], "warn",
   description="When license_policy is unknown or restricted_or_unclear, export, redistribution, and marketplace must be blocked or redacted.",
   target_type="any", target_id_or_family=["attribute", "event_type", "insight_type", "package"],
   required_inputs=["record.rights"],
   test_method="conditional",
   pass_condition="license_policy in {unknown, restricted_or_unclear} => export_policy in {blocked, conditional} AND marketplace_policy in {redacted, blocked} AND redaction_required=true",
   warning_condition="rights remain unclear after first ingestion",
   fail_condition="rights remain unclear and any of the restrictive defaults are bypassed",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§18.5"], audit_fields=["rights_state"],
   pit_summary=["not_applicable"],
   rights_summary=["unknown_or_restricted_blocks_export_and_redacts_marketplace"],
   source_sections=["§18.5"], source_ids=["DA-020"])

# Evidence-level rules
VR("evidence_thesis_requires_evidence_horizon_invalidation", "Thesis requires evidence, horizon, and invalidation", "evidence", "evidence",
   ["thesis", "decision"], "block",
   description="Every thesis must reference supporting evidence, declare horizon, and carry invalidation conditions.",
   target_type="thesis", target_id_or_family=["thesis"],
   required_inputs=["thesis.supporting_evidence_ids", "thesis.horizon", "thesis.invalidation_conditions"],
   test_method="non_empty_checks",
   pass_condition="all three fields non-empty",
   warning_condition="invalidation_conditions present but vague (1 entry)",
   fail_condition="any of evidence, horizon, invalidation is missing or empty",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§3.12", "§5.6"], audit_fields=["source_refs", "validation_record_ids"],
   pit_summary=["evidence_available_at_required"], rights_summary=["evidence_rights_required"],
   source_sections=["§3.12", "§5.6"], source_ids=["G-001"])

VR("evidence_valuation_requires_assumptions_and_sensitivity", "Valuation requires assumptions and sensitivity", "evidence", "evidence",
   ["valuation_model"], "block",
   description="Every DCF must carry explicit assumptions + sensitivity table; every relative valuation must carry a peer set with rationale.",
   target_type="valuation_model", target_id_or_family=["valuation_model"],
   required_inputs=["model.assumptions", "model.sensitivity_table", "model.peer_selection_evidence"],
   test_method="non_empty_checks",
   pass_condition="dcf has assumptions + sensitivity; relative valuation has peer set with rationale",
   warning_condition="sensitivity present but covers fewer than 3 dimensions",
   fail_condition="missing assumptions, missing sensitivity table, or missing peer rationale",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§7.13"], audit_fields=["methodology_graph_hash", "source_refs"],
   pit_summary=["not_applicable"], rights_summary=["consensus_inputs_license_required_when_used"],
   source_sections=["§7.13"], source_ids=["V-001"])

VR("evidence_event_requires_source_credibility_and_timestamp", "Event requires source credibility and timestamp", "evidence", "evidence",
   ["event_type"], "block",
   description="Every event must carry source credibility (1-5) and observed_at + available_at timestamps.",
   target_type="event_type", target_id_or_family=["event_type"],
   required_inputs=["event.source_credibility", "event.observed_at", "event.available_at"],
   test_method="non_empty_checks",
   pass_condition="credibility in 1-5; observed_at and available_at concrete",
   warning_condition="credibility = 1 (anonymous social) but explicit unverified flag present",
   fail_condition="missing credibility or any timestamp",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§13.6"], audit_fields=["source_refs", "pit_timestamps"],
   pit_summary=["available_at_required"], rights_summary=["news_provider_license_required_when_applicable"],
   source_sections=["§13.6"], source_ids=["EV-001"])

VR("evidence_rumor_no_direct_action", "Rumor cannot drive direct action", "evidence", "evidence",
   ["event_type", "decision"], "block",
   description="Events with status=rumored OR credibility<3 can only generate watch/alert_only, never direct action.",
   target_type="decision", target_id_or_family=["decision"],
   required_inputs=["decision.action", "decision.evidence.event_status", "decision.evidence.source_credibility"],
   test_method="conditional",
   pass_condition="rumor evidence -> decision.action in {watch, alert_only, research_deeper}",
   warning_condition="rumor evidence triangulated with one filing source; decision elevated to watch",
   fail_condition="rumor evidence used to generate buy/short/sell/hedge action",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§13.6", "§3.4"], audit_fields=["source_refs"],
   pit_summary=["available_at_required"], rights_summary=["not_applicable"],
   source_sections=["§13.6", "§3.4"], source_ids=["G-001"], human_review=True)

VR("evidence_non_advice_boundary", "Non-advice boundary required", "evidence", "output",
   ["recommendation", "output_view", "decision"], "block",
   description="Every recommendation-like output must surface a non-advice boundary statement.",
   target_type="output_view", target_id_or_family=["investment_memo", "trade_plan", "equity_radar", "risk_dashboard", "recommendation"],
   required_inputs=["output.sections.non_advice_boundary"],
   test_method="section_present",
   pass_condition="non_advice_boundary section present with profile-specific language",
   warning_condition="non_advice_boundary present but generic",
   fail_condition="non_advice_boundary section absent on a recommendation-bearing output",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§3.4", "§5.5", "§26"], audit_fields=["validation_record_ids"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§3.4", "§26"], source_ids=["G-001", "ANL-013"])

# Statistical-level rules
VR("statistical_factor_oos_required", "Factor signal requires OOS test", "statistical", "statistical",
   ["attribute", "strategy_profile"], "error",
   description="Factor-based scoring inputs must satisfy out-of-sample testing in addition to in-sample.",
   target_type="strategy_profile", target_id_or_family=["factor_neutral_quantamental_selector", "earnings_revision_momentum", "post_earnings_drift_radar"],
   required_inputs=["validation.oos_period", "validation.walk_forward_folds"],
   test_method="length_and_disjointness",
   pass_condition="OOS period >= 2y AND disjoint from discovery sample",
   warning_condition="OOS period < 2y but documented capacity warning attached",
   fail_condition="no OOS period or OOS overlaps discovery sample",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§10.6", "§19.5"], audit_fields=["validation_record_ids"],
   pit_summary=["vintaged_inputs_required_when_pit_safe_required"], rights_summary=["not_applicable"],
   source_sections=["§10.6"], source_ids=["FA-040"])

VR("statistical_factor_costs_required", "Factor signal requires transaction-cost adjustment", "statistical", "statistical",
   ["strategy_profile"], "error",
   description="Factor-based backtests must apply realistic transaction costs (Frazzini-Israel-Moskowitz or Novy-Marx-Velikov).",
   target_type="strategy_profile", target_id_or_family=["factor_neutral_quantamental_selector", "earnings_revision_momentum"],
   required_inputs=["validation.cost_adjustment_method"],
   test_method="enum_membership",
   pass_condition="cost adjustment method in {fim, nmv, broker_quote, custom_documented}",
   warning_condition="costs applied but capacity not estimated",
   fail_condition="no transaction-cost adjustment applied to backtest",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§10.6"], audit_fields=["validation_record_ids"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§10.6"], source_ids=["FA-047", "FA-049"])

VR("statistical_factor_liquidity_capacity_required", "Factor signal requires liquidity / capacity check", "statistical", "statistical",
   ["strategy_profile"], "error",
   description="Factor-based strategies must declare capacity vs strategy AUM.",
   target_type="strategy_profile", target_id_or_family=["factor_neutral_quantamental_selector"],
   required_inputs=["validation.capacity_estimate"],
   test_method="value_check",
   pass_condition="capacity_estimate > current_strategy_aum",
   warning_condition="capacity_estimate within 2x of strategy_aum",
   fail_condition="capacity_estimate missing or below strategy_aum",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§10.6"], audit_fields=["validation_record_ids"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§10.6"], source_ids=["FA-039"])

VR("statistical_deflated_sharpe_required", "Deflated Sharpe / multiple-testing control required", "statistical", "statistical",
   ["strategy_profile"], "error",
   description="Factor / quant strategies must apply Bailey-López de Prado deflation or Harvey-Liu-Zhu threshold.",
   target_type="strategy_profile", target_id_or_family=["factor_neutral_quantamental_selector"],
   required_inputs=["validation.deflated_sharpe", "validation.hypotheses_tested"],
   test_method="value_check",
   pass_condition="deflated_sharpe_p < 0.05 OR adjusted_t_stat > Harvey-Liu-Zhu threshold (~3.0)",
   warning_condition="strategy passes nominal Sharpe but borderline after deflation",
   fail_condition="strategy fails deflated Sharpe / HLZ threshold",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§10.6", "§19.5"], audit_fields=["validation_record_ids"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§10.6", "§19.5"], source_ids=["FA-040", "FA-034"])

VR("statistical_survivorship_bias_required", "Survivorship bias check required", "statistical", "statistical",
   ["strategy_profile"], "error",
   description="Backtests must use a universe reconstruction that includes delisted/dead names.",
   target_type="strategy_profile", target_id_or_family=["factor_neutral_quantamental_selector", "earnings_revision_momentum"],
   required_inputs=["validation.universe_reconstruction_method"],
   test_method="enum_membership",
   pass_condition="universe includes delisted names per as-of methodology",
   warning_condition="universe excludes delistings prior to a documented cutoff",
   fail_condition="universe omits delisted names without documentation",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§10.6"], audit_fields=["validation_record_ids"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§10.6"], source_ids=["FA-040"])

# Qualitative-level rules
VR("qualitative_human_review_fraud_legal_short", "Human review required for fraud / legal / short claims", "qualitative", "qualitative",
   ["short_thesis", "insight_type", "output_view"], "block",
   description="Outputs containing fraud, legal-sensitive, or short claims must pass a human-review gate before export.",
   target_type="any", target_id_or_family=["fraud_risk_flag", "short_red_flag_monitor", "manipulation_risk_warning"],
   required_inputs=["record.human_review_required", "record.review_record"],
   test_method="boolean_and_record_check",
   pass_condition="human_review_required=true AND review_record present and cleared",
   warning_condition="human_review_required=true but review record is pending",
   fail_condition="output produced without cleared review record",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§17.7", "§19.9"], audit_fields=["human_review_record"],
   pit_summary=["not_applicable"], rights_summary=["fraud_language_blocks_export_until_review"],
   source_sections=["§17.7", "§19.9"], source_ids=["SH-018"], human_review=True)

VR("qualitative_short_action_requires_borrow_and_squeeze_review", "Short action requires borrow + squeeze review", "qualitative", "qualitative",
   ["strategy_profile", "decision"], "block",
   description="Any short-side action requires a borrow availability record AND a squeeze-risk review record.",
   target_type="decision", target_id_or_family=["short_red_flag_monitor"],
   required_inputs=["decision.borrow_review", "decision.squeeze_risk_review"],
   test_method="non_empty_checks",
   pass_condition="borrow_review present with status in {available, hard_to_borrow} AND squeeze_risk_review present",
   warning_condition="borrow=hard_to_borrow but fee documented",
   fail_condition="missing borrow review or squeeze review",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§17.6"], audit_fields=["source_refs"],
   pit_summary=["borrow_data_pit_required"], rights_summary=["borrow_data_licensed"],
   source_sections=["§17.6"], source_ids=["SH-018"], human_review=True)

VR("qualitative_sentiment_social_credibility_review", "Sentiment / social signals require credibility + manipulation review", "qualitative", "qualitative",
   ["attribute", "insight_type"], "error",
   description="Social-sentiment-derived signals require credibility scoring and manipulation-risk review before promotion.",
   target_type="attribute", target_id_or_family=["social_mention_count_24h", "social_sentiment_score", "manipulation_alert_flag"],
   required_inputs=["record.credibility", "record.manipulation_review_record"],
   test_method="non_empty_checks",
   pass_condition="credibility scored AND manipulation review record present",
   warning_condition="credibility=2 (single-source wire) and manipulation review absent",
   fail_condition="signal used in production without credibility + manipulation review",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§15.6", "§15.9"], audit_fields=["human_review_record"],
   pit_summary=["sentiment_publication_at_required"], rights_summary=["social_data_platform_tos_restricted"],
   source_sections=["§15.6"], source_ids=["BE-014"], human_review=True)

# Portfolio-level rules
VR("portfolio_sizing_requires_portfolio_context", "Sizing requires portfolio context", "portfolio", "portfolio",
   ["decision", "strategy_profile"], "block",
   description="Any size_adjustment or hedge_candidate action requires a portfolio_context object.",
   target_type="decision", target_id_or_family=["portfolio_risk_radar", "merger_arbitrage_watchlist"],
   required_inputs=["decision.portfolio_context"],
   test_method="non_empty",
   pass_condition="portfolio_context present with positions, mandate, benchmark resolved",
   warning_condition="portfolio_context present but liquidity capacity not validated",
   fail_condition="size or hedge action emitted without portfolio_context",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§11.14"], audit_fields=["source_refs"],
   pit_summary=["portfolio_state_pit_required"], rights_summary=["portfolio_state_internal_only"],
   source_sections=["§11.14"], source_ids=["PC-001"])

VR("portfolio_caps_enforced", "Caps enforced (position/sector/issuer)", "portfolio", "portfolio",
   ["decision", "strategy_profile"], "block",
   description="Sizing engine must enforce position / sector / industry / issuer caps as declared in the strategy profile.",
   target_type="strategy_profile", target_id_or_family=["any_profile_with_sizing"],
   required_inputs=["profile.constraints.max_position_pct", "profile.constraints.max_sector_pct"],
   test_method="value_check",
   pass_condition="all declared caps respected by sized weights",
   warning_condition="cap breached by <1% during rebalance window",
   fail_condition="cap breached and not auto-corrected",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§11.14"], audit_fields=["validation_record_ids"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§11.14"], source_ids=["PC-001"])

VR("portfolio_tracking_error_budget", "Tracking error within budget", "portfolio", "portfolio",
   ["decision"], "warn",
   description="Active risk must remain within the profile's tracking_error_budget_bps.",
   target_type="strategy_profile", target_id_or_family=["earnings_revision_momentum", "growth_at_reasonable_price", "factor_neutral_quantamental_selector"],
   required_inputs=["portfolio.tracking_error_total_bps", "profile.mandate.tracking_error_budget_bps"],
   test_method="value_check",
   pass_condition="tracking_error_total_bps <= mandate.tracking_error_budget_bps",
   warning_condition="tracking error within 10% of budget",
   fail_condition="tracking error exceeds budget",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§11.14"], audit_fields=["validation_record_ids"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§11.14"], source_ids=["PC-001"])

# Output-level rules
VR("output_validation_summary_required", "Validation summary required on outputs", "output", "output",
   ["output_view"], "block",
   description="Outputs must include a validation_summary section listing pass/warn/fail counts and key warnings.",
   target_type="output_view", target_id_or_family=["equity_radar", "investment_memo", "trade_plan", "risk_dashboard", "validation_report"],
   required_inputs=["output.sections.validation_summary"],
   test_method="section_present",
   pass_condition="validation_summary section present with counts and key warnings",
   warning_condition="validation_summary present but warnings missing",
   fail_condition="validation_summary missing",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§26.4"], audit_fields=["validation_record_ids"],
   pit_summary=["data_cutoff_required"], rights_summary=["rights_summary_required"],
   source_sections=["§26.4"], source_ids=["G-001"])

VR("output_pit_summary_required", "PIT summary required on outputs", "output", "output",
   ["output_view"], "block",
   description="Outputs must include a pit_summary section with the data_cutoff and any PIT warnings.",
   target_type="output_view", target_id_or_family=["equity_radar", "investment_memo", "trade_plan", "risk_dashboard", "validation_report"],
   required_inputs=["output.sections.pit_summary"],
   test_method="section_present",
   pass_condition="pit_summary section present with data_cutoff and warnings",
   warning_condition="pit_summary present but data_cutoff missing",
   fail_condition="pit_summary missing",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§26.4"], audit_fields=["pit_timestamps"],
   pit_summary=["data_cutoff_required"], rights_summary=["not_applicable"],
   source_sections=["§26.4"], source_ids=["P-013"])

VR("output_rights_summary_required", "Rights summary required on outputs", "output", "output",
   ["output_view"], "block",
   description="Outputs must include a rights_summary section listing per-source rights state.",
   target_type="output_view", target_id_or_family=["equity_radar", "investment_memo", "trade_plan", "risk_dashboard", "validation_report", "source_rights_report"],
   required_inputs=["output.sections.rights_summary"],
   test_method="section_present",
   pass_condition="rights_summary section present with per-source rights state",
   warning_condition="rights_summary present but redaction state missing",
   fail_condition="rights_summary missing",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§26.4"], audit_fields=["rights_state"],
   pit_summary=["not_applicable"], rights_summary=["rights_state_per_field"],
   source_sections=["§26.4"], source_ids=["DA-007"])

VR("output_invalidation_display_for_recommendations", "Invalidation display required on recommendation outputs", "output", "output",
   ["output_view"], "error",
   description="Outputs that carry recommendation-like content (memo, trade_plan, equity_radar) must display invalidation_conditions.",
   target_type="output_view", target_id_or_family=["investment_memo", "trade_plan", "equity_radar"],
   required_inputs=["output.sections.invalidation_conditions"],
   test_method="section_present",
   pass_condition="invalidation_conditions section present with at least one entry",
   warning_condition="invalidation_conditions section empty",
   fail_condition="section absent",
   confidence_impact="downgrade_one_step",
   evidence_refs=["§26.4", "§5.5"], audit_fields=["validation_record_ids"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§26.4"], source_ids=["ANL-001"])

# Package / marketplace_draft-level rules
VR("package_marketplace_draft_redact_restricted", "Marketplace_draft must redact restricted or unclear rights", "package", "package",
   ["package", "output_view"], "block",
   description="When packaging as marketplace_draft, restricted_or_unclear and licensed_provider_required evidence must be redacted by default.",
   target_type="package", target_id_or_family=["package"],
   required_inputs=["package.redaction_state", "package.rights_per_section"],
   test_method="conditional",
   pass_condition="every restricted_or_unclear / licensed_provider_required evidence redacted in marketplace_draft",
   warning_condition="creator explicitly enables a derived value with documented license",
   fail_condition="restricted raw value rendered in marketplace_draft package",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§18.14", "§26.5"], audit_fields=["rights_state", "proof_checksum"],
   pit_summary=["not_applicable"],
   rights_summary=["marketplace_default_redacted_when_rights_unclear"],
   source_sections=["§18.14", "§26.5"], source_ids=["B-002", "B-006"])

VR("package_proof_checksum_required", "Proof checksum required on exported package", "package", "package",
   ["package"], "block",
   description="Every exported package must carry a proof_checksum binding evidence + validation records.",
   target_type="package", target_id_or_family=["package"],
   required_inputs=["package.proof_checksum"],
   test_method="non_empty_string",
   pass_condition="proof_checksum present and valid",
   warning_condition="proof_checksum present but tied to a partial run",
   fail_condition="proof_checksum missing on exported package",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§30.3", "§36.2"], audit_fields=["proof_checksum"],
   pit_summary=["not_applicable"], rights_summary=["not_applicable"],
   source_sections=["§30.3"], source_ids=["P-013"])

VR("package_no_monetized_endpoints", "No monetized marketplace endpoints", "package", "package",
   ["package"], "block",
   description="VIZA v0.1 does not support monetized marketplace endpoints; only marketplace_draft packaging is allowed.",
   target_type="package", target_id_or_family=["package"],
   required_inputs=["package.marketplace_endpoint"],
   test_method="enum_disjoint",
   pass_condition="no marketplace_endpoint references buy/sell/checkout/payment/subscription",
   warning_condition="marketplace_draft creator metadata present without endpoint",
   fail_condition="package references a monetized marketplace endpoint",
   confidence_impact="rejected_or_deferred",
   evidence_refs=["§1.5", "§27.2"], audit_fields=["proof_checksum"],
   pit_summary=["not_applicable"], rights_summary=["marketplace_draft_only"],
   source_sections=["§27.2"], source_ids=["B-002"])

print(f"defined {len(VRULES)} validation rules")


# ---------- CONNECTOR REQUIREMENTS ----------
CONNECTORS = []


def CR(cid, name, provider, license_status, data_types, required_for_nodes, required_for_profiles,
       license_policy, pit_support, production_required, fallback_allowed,
       fallback_behavior, production_status,
       sections, sources, confidence_label="high_confidence_core",
       human_review=False, description=None):
    CONNECTORS.append({
        "id": cid,
        "name": name,
        "provider": provider,
        "license_status": license_status,
        "data_types": data_types,
        "required_for_nodes": required_for_nodes,
        "required_for_profiles": required_for_profiles,
        "license_policy": license_policy,
        "pit_support_required": pit_support,
        "production_required": production_required,
        "fallback_allowed": fallback_allowed,
        "fallback_behavior": fallback_behavior,
        "production_status": production_status,
        "sections": sections,
        "sources": sources,
        "confidence_label": confidence_label,
        "human_review": human_review,
        "description": description or name,
    })


CR("official_public_connector", "Official Public Connector (umbrella)", "viza.internal", "public",
   data_types=["public_official_aggregate"],
   required_for_nodes=["edgar_filings_intake", "fundamentals_as_reported_connector", "xbrl_facts_intake"],
   required_for_profiles=["quality_value_long_only", "cheap_compounder", "growth_at_reasonable_price"],
   license_policy="public_official", pit_support=True, production_required=False,
   fallback_allowed=True, fallback_behavior="block_with_warning",
   production_status="production_ready",
   sections=["§18.4", "§18.5"], sources=["DA-001", "DA-040"])

CR("sec_filings", "SEC EDGAR Filings", "SEC EDGAR", "public",
   data_types=["sec_filings", "form_4", "13f", "13d", "13g", "def_14a", "8k", "10k", "10q"],
   required_for_nodes=["edgar_filings_intake", "fundamentals_as_reported_connector", "insider_transaction_analyzer", "ownership_intake"],
   required_for_profiles=["quality_value_long_only", "earnings_revision_momentum", "merger_arbitrage_watchlist", "activism_vulnerability_radar", "short_red_flag_monitor", "cheap_compounder", "growth_at_reasonable_price"],
   license_policy="public_official", pit_support=True, production_required=False,
   fallback_allowed=False, fallback_behavior="block_with_warning",
   production_status="production_ready",
   sections=["§18.4", "§18.5"], sources=["DA-001", "DA-034"])

CR("xbrl_facts", "EDGAR XBRL Facts", "SEC EDGAR XBRL", "public",
   data_types=["xbrl_facts"],
   required_for_nodes=["xbrl_facts_intake", "fundamental_snapshot"],
   required_for_profiles=["quality_value_long_only", "cheap_compounder", "growth_at_reasonable_price"],
   license_policy="public_official", pit_support=True, production_required=False,
   fallback_allowed=True, fallback_behavior="fall_back_to_as_reported_text",
   production_status="production_ready",
   sections=["§18.4"], sources=["DA-002"])

CR("fred_macro", "FRED Macro (current snapshot)", "FRED (FRBSL)", "public",
   data_types=["macro_official_latest_only"],
   required_for_nodes=["macro_snapshot_loader"],
   required_for_profiles=["macro_regime_equity_selector", "dividend_sustainability_radar", "portfolio_risk_radar"],
   license_policy="public_official", pit_support=False, production_required=False,
   fallback_allowed=True, fallback_behavior="latest_only_with_pit_warning",
   production_status="production_pending_pit_pipeline",
   sections=["§16.10", "§18.8"], sources=["MA-001"],
   confidence_label="common_practice",
   description="FRED current-snapshot connector. PROJECT_STATUS.md notes ingestion is timestamped at load, not vintaged. Use only for display / latest-only signals until ALFRED pipeline ships.")

CR("alfred_macro_vintage", "ALFRED Macro Vintaged", "ALFRED (FRBSL)", "public",
   data_types=["macro_official_vintaged"],
   required_for_nodes=["macro_snapshot_loader"],
   required_for_profiles=["macro_regime_equity_selector"],
   license_policy="public_official", pit_support=True, production_required=True,
   fallback_allowed=False, fallback_behavior="block_with_warning",
   production_status="production_pending_pit_pipeline",
   sections=["§16.10", "§18.8"], sources=["MA-001", "DA-003"],
   description="ALFRED vintaged macro connector. Required for PIT-safe macro backtests. Not yet implemented in AAT; treat as production_pending_pit_pipeline until shipped.")

CR("finra_short_interest", "FINRA Short Interest", "FINRA", "public",
   data_types=["short_interest_finra"],
   required_for_nodes=["short_interest_node", "short_interest_calculator", "days_to_cover_node"],
   required_for_profiles=["short_red_flag_monitor", "merger_arbitrage_watchlist", "portfolio_risk_radar"],
   license_policy="public_official", pit_support=True, production_required=False,
   fallback_allowed=False, fallback_behavior="block_with_warning",
   production_status="production_ready",
   sections=["§12.12", "§14.9"], sources=["TE-030"])

CR("licensed_market_data_connector", "Licensed Market Data (prices, real-time)", "FMP / Polygon / NYSE / Nasdaq", "pending",
   data_types=["prices_ohlcv_eod", "prices_ohlcv_realtime", "corporate_actions"],
   required_for_nodes=["prices_ohlcv_connector_node", "moving_average_node", "rsi_node", "abnormal_volume_node", "breakout_breakdown_node"],
   required_for_profiles=["rsi_swing_catalyst_confirmation", "post_earnings_drift_radar", "earnings_revision_momentum", "factor_neutral_quantamental_selector"],
   license_policy="licensed_provider_required", pit_support=True, production_required=True,
   fallback_allowed=True, fallback_behavior="fall_back_to_delayed_eod_public_when_available",
   production_status="production_pending_license",
   sections=["§18.4", "§12.12"], sources=["DA-007", "DA-032"],
   description="Production market data. FMP is dev-only unless FMP_PRODUCTION_LICENSE_CONFIRMED=true. Real-time NYSE/Nasdaq feeds require exchange license.")

CR("licensed_fundamentals_connector", "Licensed Fundamentals (standardized)", "Compustat / S&P CIQ / Refinitiv", "pending",
   data_types=["fundamentals_standardized"],
   required_for_nodes=["fundamentals_standardized_connector", "fundamental_snapshot"],
   required_for_profiles=["quality_value_long_only", "growth_at_reasonable_price", "cheap_compounder", "dividend_sustainability_radar", "short_red_flag_monitor"],
   license_policy="licensed_provider_required", pit_support=True, production_required=True,
   fallback_allowed=True, fallback_behavior="fall_back_to_as_reported_xbrl",
   production_status="production_pending_license",
   sections=["§6.10", "§18.5"], sources=["DA-012", "DA-013"])

CR("licensed_estimates_connector", "Licensed Estimates (I/B/E/S)", "I/B/E/S / FactSet / Bloomberg", "pending",
   data_types=["analyst_estimates", "consensus_snapshot", "rating_change"],
   required_for_nodes=["revisions_aggregator", "earnings_surprise_calculator", "analyst_coverage_node"],
   required_for_profiles=["earnings_revision_momentum", "post_earnings_drift_radar", "growth_at_reasonable_price"],
   license_policy="licensed_provider_required", pit_support=True, production_required=True,
   fallback_allowed=False, fallback_behavior="open_locked_preserve_config",
   production_status="production_pending_license",
   sections=["§18.5", "§13.4"], sources=["DA-011", "EV-032"])

CR("licensed_text_connector", "Licensed Text (news / transcripts)", "RavenPack / Reuters / Bloomberg / Refinitiv StreetEvents", "pending",
   data_types=["news_provider", "transcripts"],
   required_for_nodes=["news_sentiment_intake", "transcripts_connector", "news_events_connector"],
   required_for_profiles=["earnings_revision_momentum", "event_risk_monitor", "merger_arbitrage_watchlist"],
   license_policy="licensed_provider_required", pit_support=True, production_required=True,
   fallback_allowed=True, fallback_behavior="fall_back_to_lm_dictionary_on_edgar",
   production_status="production_pending_license",
   sections=["§13.4", "§15"], sources=["DA-018", "EV-031", "EV-046"])

CR("licensed_options_connector", "Licensed Options (OPRA)", "OPRA / CBOE", "pending",
   data_types=["options_opra"],
   required_for_nodes=["implied_volatility_node", "put_call_ratio_node", "volatility_spread_node", "options_positioning_node"],
   required_for_profiles=["event_risk_monitor", "merger_arbitrage_watchlist", "short_red_flag_monitor"],
   license_policy="licensed_provider_required", pit_support=True, production_required=True,
   fallback_allowed=False, fallback_behavior="open_locked_preserve_config",
   production_status="production_pending_license",
   sections=["§12.4", "§14.10"], sources=["DA-005", "DA-006"])

CR("licensed_borrow_connector", "Licensed Borrow (S3 / Markit / IB)", "S3 Partners / Markit Securities Finance / IB", "pending",
   data_types=["borrow_availability_cost"],
   required_for_nodes=["borrow_status_node", "borrow_status_node_link", "borrow_status_node_short_link"],
   required_for_profiles=["short_red_flag_monitor", "merger_arbitrage_watchlist"],
   license_policy="licensed_provider_required", pit_support=True, production_required=True,
   fallback_allowed=True, fallback_behavior="block_short_action_with_warning",
   production_status="production_pending_license",
   sections=["§12.12", "§14.10", "§17.6"], sources=["DA-025", "DA-026"], human_review=True)

CR("licensed_index_membership_connector", "Licensed Index Membership (S&P / MSCI / FTSE / Russell)", "S&P / MSCI / FTSE Russell", "pending",
   data_types=["index_membership"],
   required_for_nodes=["index_membership_tracker", "index_calendar_tracker"],
   required_for_profiles=["special_situations_monitor", "portfolio_risk_radar"],
   license_policy="licensed_provider_required", pit_support=True, production_required=True,
   fallback_allowed=True, fallback_behavior="block_index_event_signals_with_warning",
   production_status="production_pending_license",
   sections=["§13.4", "§14"], sources=["DA-027", "DA-028", "OW-028"])

CR("user_document_connector", "User Document Upload", "viza.user_upload", "user_entitled",
   data_types=["user_memo", "user_research_memo", "user_upload_pdf"],
   required_for_nodes=["thesis_writer", "investment_memo_renderer", "research_intake"],
   required_for_profiles=["quality_value_long_only", "cheap_compounder", "growth_at_reasonable_price", "short_red_flag_monitor"],
   license_policy="internal_research_only", pit_support=False, production_required=False,
   fallback_allowed=True, fallback_behavior="latest_only_user_state",
   production_status="production_ready",
   sections=["§5", "§20.3"], sources=["ANL-001"])

CR("user_portfolio_connector", "User Portfolio Upload", "viza.user_upload", "user_entitled",
   data_types=["user_portfolio_data"],
   required_for_nodes=["portfolio_context_loader", "sizing_engine", "tracking_error_calculator", "risk_contribution_calculator"],
   required_for_profiles=["portfolio_risk_radar"],
   license_policy="internal_research_only", pit_support=False, production_required=False,
   fallback_allowed=True, fallback_behavior="latest_only_user_state",
   production_status="production_ready",
   sections=["§11.3", "§20.3"], sources=["PC-001"])

CR("derived_calculation_engine", "Derived Calculation Engine", "viza.runtime", "public",
   data_types=["derived_attributes", "scores", "transforms"],
   required_for_nodes=["dcf_model_node", "relative_valuation_node", "factor_score_calculator", "factor_residual_calculator", "amihud_illiquidity_node", "spread_estimator"],
   required_for_profiles=["quality_value_long_only", "cheap_compounder", "factor_neutral_quantamental_selector"],
   license_policy="derived_only", pit_support=True, production_required=False,
   fallback_allowed=True, fallback_behavior="block_when_inputs_missing",
   production_status="production_ready",
   sections=["§18.3", "§19"], sources=["DA-040"])


print(f"defined {len(CONNECTORS)} connector requirement records")


# ---------- BUILDERS ----------
def build_validation_rule(spec):
    record = {
        "id": spec["id"],
        "display_name": spec["name"],
        "description": spec["description"],
        "module_id": "viza.finance.equity_investment",
        "schema_version": "v1",
        "object_family": "validation_rule",
        "source_sections": list(spec["source_sections"]),
        "source_ids": list(spec["source_ids"]),
        "confidence_label": spec["confidence_label"],
        "status": "registry-seedable",
        "created_from": "CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline",
        "core_primitive": "audit",
        "extends_core_primitive": "transform",
        "compatible_entity_types": [],
        "compatible_strategy_profiles": [],
        "evidence_requirements": [
            {"evidence_type": "rule_test_output", "required": True, "source_quality_minimum": 3},
        ],
        "audit_requirements": list(spec["audit_fields"]) or ["source_refs", "validation_record_ids"],
        "source_quality_minimum": 4,
        "human_review_required": spec["human_review"],
        "pit": _pit_creation(),
        "rights": _rights_validation(),
        "validation_rules": [],
        "failure_modes": [spec["id"] + "_failure"],
        "downgrade_conditions": [],
        "rejection_conditions": [],
        "family_specific": {
            "domain": spec["domain"],
            "severity": spec["severity"],
            "applies_to": list(spec["applies_to"]),
            "trigger_logic": spec["fail_condition"],
            "remediation": "block / downgrade per failure_severity; see test_method and confidence_impact for runtime handling.",
            "validation_level": spec["level"],
            "validation_rule_id": spec["id"],
            "target_type": spec["target_type"],
            "target_id_or_family": list(spec["target_id_or_family"]),
            "required_inputs": list(spec["required_inputs"]),
            "test_method": spec["test_method"],
            "pass_condition": spec["pass_condition"],
            "warning_condition": spec["warning_condition"],
            "fail_condition": spec["fail_condition"],
            "failure_severity": spec["severity"],
            "confidence_impact": spec["confidence_impact"],
            "pit_requirements_summary": list(spec["pit_requirements_summary"]),
            "rights_requirements_summary": list(spec["rights_requirements_summary"]),
            "evidence_refs": list(spec["evidence_refs"]),
            "audit_fields": list(spec["audit_fields"]),
        },
    }
    return record


def build_connector(spec):
    rights = _rights_for_connector(spec["license_policy"], [spec["id"]])
    record = {
        "id": spec["id"],
        "display_name": spec["name"],
        "description": spec["description"],
        "module_id": "viza.finance.equity_investment",
        "schema_version": "v1",
        "object_family": "connector_requirement",
        "source_sections": list(spec["sections"]),
        "source_ids": list(spec["sources"]),
        "confidence_label": spec["confidence_label"],
        "status": "registry-seedable",
        "created_from": "CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline",
        "core_primitive": "entity",
        "extends_core_primitive": "attribute",
        "compatible_entity_types": ["connector"],
        "compatible_strategy_profiles": list(spec["required_for_profiles"]),
        "evidence_requirements": [
            {"evidence_type": "connector_configuration_record", "required": True, "source_quality_minimum": 4},
        ],
        "audit_requirements": ["source_refs", "connector_entitlement_record", "rights_state"],
        "source_quality_minimum": 4,
        "human_review_required": spec["human_review"],
        "pit": _pit_creation(),
        "rights": rights,
        "validation_rules": [
            "rights_production_connector_fail_closed",
            "rights_rights_policy_required",
            "data_retrieved_at_required",
        ],
        "failure_modes": [
            "production_run_with_missing_license",
            "provider_load_time_used_as_available_at",
            "rights_drift_silently",
        ],
        "downgrade_conditions": [],
        "rejection_conditions": [],
        "family_specific": {
            "provider": spec["provider"],
            "credential_ref": f"vault:credentials/{spec['id']}",
            "entitlement_metadata": {
                "license_status": spec["license_status"],
                "license_expires": None,
                "seats_or_quota": None,
                "product_class": spec["license_policy"],
            },
            "rate_limits": {},
            "retry_policy": {"max_retries": 3, "backoff": "exponential"},
            "production_required": spec["production_required"],
            "data_types": list(spec["data_types"]),
            "required_for_nodes": list(spec["required_for_nodes"]),
            "required_for_profiles": list(spec["required_for_profiles"]),
            "pit_support_required": spec["pit_support_required"],
            "fallback_allowed": spec["fallback_allowed"],
            "fallback_behavior": spec["fallback_behavior"],
            "production_status": spec["production_status"],
            "connector_role_id": spec["id"],
        },
    }
    return record


# ---------- WRITE ----------
v_records = [build_validation_rule(s) for s in VRULES]
c_records = [build_connector(s) for s in CONNECTORS]

OUT_VR.write_text(json.dumps({
    "$schema": "../equity_registry_shared_metadata.schema.json",
    "registry_name": "equity_validation_rules",
    "module_id": "viza.finance.equity_investment",
    "module_version": "0.1.0",
    "registry_version": "v1",
    "baseline": "Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening",
    "created_from": "CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline",
    "notes": "Validation rules covering 10 levels (schema, data, PIT, rights, evidence, statistical, qualitative, portfolio, output, package). Records conform to docs/equity_module/v0.1/equity_registry_shared_metadata.schema.json (object_family=validation_rule). Every CLAUDE.md project-rule violation (ticker as primary key, missing PIT, missing rights, marketplace_draft without redaction) maps to a block-severity rule. Fraud / legal / short / sentiment / social rules carry human_review_required=true.",
    "records": v_records,
}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {len(v_records)} validation_rule records to {OUT_VR}")

OUT_CR.write_text(json.dumps({
    "$schema": "../equity_registry_shared_metadata.schema.json",
    "registry_name": "equity_connector_requirements",
    "module_id": "viza.finance.equity_investment",
    "module_version": "0.1.0",
    "registry_version": "v1",
    "baseline": "Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening",
    "created_from": "CLAUDE_EQUITY_MODULE.md@v0.1-research-baseline",
    "notes": "Connector requirement records (object_family=connector_requirement). PROJECT_STATUS.md notes: FRED current ingest is latest-only / not vintaged; FMP market data is dev-only unless FMP_PRODUCTION_LICENSE_CONFIRMED=true. Licensed connectors ship as production_pending_license with documented fallback behaviour. Borrow / short / fraud paths carry human_review_required=true.",
    "records": c_records,
}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {len(c_records)} connector_requirement records to {OUT_CR}")


# ---------- SOURCE RIGHTS MATRIX (CSV) ----------
RIGHTS_COLUMNS = [
    "data_type", "source_type", "connector_role", "license_policy",
    "query_policy", "cache_policy", "display_policy", "export_policy",
    "derived_value_policy", "redistribution_policy", "marketplace_policy",
    "attribution_required", "retention_policy", "default_package_behavior", "notes",
]


def RR(data_type, source_type, connector_role, license_policy, default_package_behavior, notes):
    r = _rights_for_connector(license_policy, [connector_role])
    return [
        data_type, source_type, connector_role, license_policy,
        r["query_policy"], r["cache_policy"], r["display_policy"], r["export_policy"],
        r["derived_value_policy"], r["redistribution_policy"], r["marketplace_policy"],
        "true" if r["attribution_required"] else "false",
        r["retention_policy"], default_package_behavior, notes,
    ]


RIGHTS_ROWS = [
    RR("identifier_mapping_figi", "public_professional_provider", "official_public_connector",
       "public_professional", "include_with_attribution",
       "OpenFIGI mapping. Public professional; attribution required for redistribution."),
    RR("identifier_mapping_cusip_isin", "licensed_provider", "official_public_connector",
       "licensed_provider_required", "redacted",
       "CUSIP / ISIN are licensed. Display allowed under license; redistribution blocked."),
    RR("security_master_provider", "licensed_provider", "licensed_market_data_connector",
       "licensed_provider_required", "redacted",
       "Provider-curated security master (FMP / Polygon / Refinitiv). License required."),
    RR("prices_ohlcv_eod_public", "public_professional_provider", "licensed_market_data_connector",
       "public_professional", "include_with_attribution",
       "Public EOD prices (free tier). Available with attribution; redistribution conditional."),
    RR("prices_ohlcv_eod_licensed", "licensed_provider", "licensed_market_data_connector",
       "licensed_provider_required", "redacted",
       "FMP / Polygon licensed EOD prices. Dev-only unless production license confirmed."),
    RR("prices_ohlcv_realtime", "licensed_provider", "licensed_market_data_connector",
       "licensed_provider_required", "redacted",
       "Real-time exchange feeds (NYSE/Nasdaq). License + entitlement required."),
    RR("corporate_actions_filings", "filing", "sec_filings",
       "public_official", "include",
       "Splits / dividends / spinoffs / M&A from SEC filings. Public official; redistribute freely with attribution."),
    RR("fundamentals_standardized_compustat", "licensed_provider", "licensed_fundamentals_connector",
       "licensed_provider_required", "redacted",
       "Compustat / S&P CIQ / Refinitiv standardized fundamentals. Licensed."),
    RR("fundamentals_as_reported_edgar", "filing", "sec_filings",
       "public_official", "include",
       "EDGAR as-reported fundamentals. Public official."),
    RR("xbrl_facts_edgar", "filing", "xbrl_facts",
       "public_official", "include",
       "EDGAR XBRL facts. Public official; redistribute freely."),
    RR("proxy_statement_def_14a", "filing", "sec_filings",
       "public_official", "include",
       "DEF 14A proxy disclosures. Public official."),
    RR("insider_transactions_form_4", "filing", "sec_filings",
       "public_official", "include",
       "Form 3 / 4 / 5 insider transactions. Public official."),
    RR("ownership_13f", "filing", "sec_filings",
       "public_official", "include",
       "13F-HR institutional holdings. Public official. NEVER use as current positioning (45-day lag)."),
    RR("ownership_13d_13g", "filing", "sec_filings",
       "public_official", "include",
       "Schedule 13D / 13G beneficial ownership. Public official."),
    RR("earnings_release_press", "press_release", "sec_filings",
       "public_professional", "include_with_attribution",
       "IR-issued earnings press release. Public professional. Attribution recommended."),
    RR("transcripts_provider", "licensed_provider", "licensed_text_connector",
       "licensed_provider_required", "redacted",
       "Earnings call transcripts via Refinitiv / FactSet / StreetEvents. Licensed."),
    RR("news_provider", "licensed_provider", "licensed_text_connector",
       "licensed_provider_required", "redacted",
       "Provider news (RavenPack / Reuters / Bloomberg / Dow Jones). Licensed."),
    RR("analyst_estimates_ibes", "licensed_provider", "licensed_estimates_connector",
       "licensed_provider_required", "redacted",
       "I/B/E/S consensus and individual estimates. Licensed; PIT vintage required for backtest."),
    RR("rating_changes_provider", "licensed_provider", "licensed_estimates_connector",
       "licensed_provider_required", "redacted",
       "Provider analyst rating changes. Licensed."),
    RR("short_interest_finra", "regulator", "finra_short_interest",
       "public_official", "include",
       "FINRA bi-weekly short interest. Public official. ALWAYS use publication date for available_at; never interpolate."),
    RR("borrow_availability_cost", "licensed_provider", "licensed_borrow_connector",
       "licensed_provider_required", "redacted",
       "Borrow rates / availability (S3 Partners / Markit / IB). Licensed; live state."),
    RR("options_opra", "licensed_provider", "licensed_options_connector",
       "licensed_provider_required", "redacted",
       "OPRA options chain / IV / OI. Licensed; block options-derived signals without OPRA license."),
    RR("index_membership_methodology", "licensed_provider", "licensed_index_membership_connector",
       "licensed_provider_required", "redacted",
       "S&P / MSCI / FTSE / Russell index methodology + membership. Licensed."),
    RR("macro_official_vintaged_alfred", "regulator", "alfred_macro_vintage",
       "public_official", "include",
       "ALFRED vintaged macro series. Public official. REQUIRED for PIT-safe macro backtests."),
    RR("macro_official_latest_only_fred", "regulator", "fred_macro",
       "public_official", "include_with_pit_warning",
       "FRED current snapshot. Public official. PROJECT_STATUS.md notes current AAT ingest is ingestion-timestamped, not vintaged; use as latest_only until ALFRED ships."),
    RR("macro_provider_consensus", "licensed_provider", "licensed_text_connector",
       "licensed_provider_required", "redacted",
       "Provider consensus economic forecasts (Bloomberg / Refinitiv). Licensed."),
    RR("credit_spreads_ice_bofa", "public_professional_provider", "official_public_connector",
       "public_professional", "include_with_attribution",
       "ICE BofA US Corp OAS series. Public professional."),
    RR("factor_data_public_kenneth_french", "academic_public", "official_public_connector",
       "academic_public", "include_with_attribution",
       "Kenneth French data library. Academic public with attribution. PROJECT_STATUS.md notes current AAT ingest is ingestion-timestamped — use as latest_only until vintaged pipeline ships."),
    RR("factor_data_licensed_barra", "licensed_provider", "licensed_market_data_connector",
       "licensed_provider_required", "redacted",
       "Barra / Axioma / MSCI factor models. Licensed."),
    RR("industry_classification_gics_icb", "licensed_provider", "official_public_connector",
       "licensed_provider_required", "redacted",
       "GICS / ICB industry classification. Licensed; redact when packaging."),
    RR("industry_classification_naics_sic", "regulator", "official_public_connector",
       "public_official", "include",
       "NAICS / SIC public classification. Public official."),
    RR("sentiment_social_platform_tos", "restricted_or_unclear_platform", "licensed_text_connector",
       "restricted_or_unclear", "redact_or_block",
       "Twitter / X / Reddit / StockTwits sentiment. Platform TOS restricts redistribution. Default-locked. Hindsight labels blocked."),
    RR("attention_public_google_trends_wikipedia", "public_professional_provider", "official_public_connector",
       "public_professional", "include_with_attribution",
       "Google Trends / Wikipedia pageviews. Public professional; revisable, so available_at = retrieval_date."),
    RR("user_portfolio_data", "user_upload", "user_portfolio_connector",
       "internal_research_only", "redact",
       "User-supplied portfolio data. User-private; never marketplace export without explicit user action + redaction."),
    RR("user_research_memo", "user_upload", "user_document_connector",
       "internal_research_only", "redact",
       "User-authored memos / theses. Private by default."),
    RR("derived_attributes", "computed", "derived_calculation_engine",
       "derived_only", "redact",
       "Derived attribute values (factor scores, valuation gaps). Inherit upstream rights. When upstream is licensed, derived value defaults to redacted in marketplace_draft."),
]

with OUT_SR.open("w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(RIGHTS_COLUMNS)
    w.writerows(RIGHTS_ROWS)
print(f"wrote {len(RIGHTS_ROWS)} rights-matrix rows to {OUT_SR}")

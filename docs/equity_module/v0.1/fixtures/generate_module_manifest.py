#!/usr/bin/env python3
"""
Generator for docs/equity_module/v0.1/viza.finance.equity_investment.manifest.json.

Source of truth: docs/CLAUDE_EQUITY_MODULE.md §27 + all generated registry artifacts.
Conformance: docs/equity_module/v0.1/viza.module.manifest.v1.schema.json.

This generator:
  - Resolves every registry artifact path.
  - Computes SHA-256 + byte size + record count for each artifact.
  - Collects entity, node, edge, attribute family, event family, insight family,
    profile, output view, connector role, and validation rule IDs from the artifacts.
  - Cross-checks: every connector role referenced by a node appears in connector_requirements.
  - Computes a combined SHA-256 over all artifact checksums.
  - Sets release_state=alpha (conservative) until acceptance tests run end-to-end.
"""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path("C:/Users/gkwls/AAT/docs/equity_module/v0.1")
OUT = ROOT / "viza.finance.equity_investment.manifest.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _byte_size(path: Path) -> int:
    return path.stat().st_size


def _count_json_records(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "records" in data:
        return len(data["records"])
    return 0


def _count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return sum(1 for _ in csv.reader(fh)) - 1  # subtract header


ART_DEFS = [
    ("entity_types", "registries/equity_entity_types.json",
     "viza.equity.entity_registry.v1"),
    ("node_types", "registries/equity_node_types.json",
     "viza.equity.node_type.v1"),
    ("edge_types", "registries/equity_edge_types.json",
     "viza.equity.edge_registry.v1"),
    ("attribute_registry_seed", "registries/equity_attribute_registry_seed.csv",
     "viza.equity.attribute.v1"),
    ("event_registry_seed", "registries/equity_event_registry_seed.json",
     "viza.equity.event_type.v1"),
    ("insight_registry_seed", "registries/equity_insight_registry_seed.json",
     "viza.equity.insight_type.v1"),
    ("strategy_profiles", "registries/equity_strategy_profiles.json",
     "viza.equity.strategy_profile.v1"),
    ("output_views", "registries/equity_output_views.json",
     "viza.equity.output_view.v1"),
    ("validation_rules", "registries/equity_validation_rules.json",
     "viza.equity.validation_record.v1"),
    ("connector_requirements", "registries/equity_connector_requirements.json",
     "viza.equity.connector_config.v1"),
    ("source_rights_matrix", "registries/equity_source_rights_matrix.csv",
     "viza.equity.rights_matrix.v1"),
    ("pit_matrix", "registries/equity_PIT_matrix.csv",
     "viza.equity.pit_matrix.v1"),
]

# Resolve every artifact, compute checksums + sizes + record counts
artifacts = {}
combined = hashlib.sha256()
missing = []
for key, rel_path, schema_id in ART_DEFS:
    p = ROOT / rel_path
    if not p.exists():
        missing.append(rel_path)
        continue
    sha = _sha256(p)
    combined.update(sha.encode("utf-8"))
    size = _byte_size(p)
    rcount = _count_csv_rows(p) if p.suffix == ".csv" else _count_json_records(p)
    artifacts[key] = {
        "path": rel_path,
        "schema": schema_id,
        "sha256": sha,
        "byte_size": size,
        "record_count": rcount,
    }
if missing:
    raise SystemExit(f"missing artifacts: {missing}")

combined_sha = combined.hexdigest()


# Helper to load JSON registry records
def _load_records(rel_path):
    data = json.loads((ROOT / rel_path).read_text(encoding="utf-8"))
    return data["records"]


def _load_csv_rows(rel_path):
    with (ROOT / rel_path).open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# Collect identifiers from each registry
entity_records = _load_records("registries/equity_entity_types.json")
entity_types = [r["id"] for r in entity_records]

node_records = _load_records("registries/equity_node_types.json")
node_types = [r["id"] for r in node_records]

edge_records = _load_records("registries/equity_edge_types.json")
edge_types = [r["id"] for r in edge_records]

attr_rows = _load_csv_rows("registries/equity_attribute_registry_seed.csv")
attribute_families = sorted(set(r["family"] for r in attr_rows))

event_records = _load_records("registries/equity_event_registry_seed.json")
event_families = sorted(set(r["family_specific"]["event_family"] for r in event_records))

insight_records = _load_records("registries/equity_insight_registry_seed.json")
insight_families = sorted(set(r["family_specific"]["insight_family"] for r in insight_records))

profile_records = _load_records("registries/equity_strategy_profiles.json")
strategy_profiles = [r["id"] for r in profile_records]

view_records = _load_records("registries/equity_output_views.json")
output_views = [r["id"] for r in view_records]

connector_records = _load_records("registries/equity_connector_requirements.json")
connector_roles = [r["id"] for r in connector_records]

validation_records = _load_records("registries/equity_validation_rules.json")
validation_rules = [r["id"] for r in validation_records]

# Rights policies: derive from the source_rights_matrix license_policy column
rights_rows = _load_csv_rows("registries/equity_source_rights_matrix.csv")
rights_policies = sorted(set(r["license_policy"] for r in rights_rows))


# Cross-check: every connector role referenced by a node must resolve to a connector_requirement.
# A node's rights.connector_roles entry resolves if it matches:
#   - a connector_requirement's id directly, OR
#   - any data_type listed in any connector_requirement's family_specific.data_types
connector_roles_set = set(connector_roles)
data_type_to_connector = {}
for cr_rec in connector_records:
    for dt in cr_rec.get("family_specific", {}).get("data_types", []):
        data_type_to_connector.setdefault(dt, set()).add(cr_rec["id"])
node_connector_refs = set()
for node in node_records:
    for r in node.get("rights", {}).get("connector_roles", []):
        node_connector_refs.add(r)
def _resolved(role):
    return role in connector_roles_set or role in data_type_to_connector
unresolved_connector_refs = [r for r in node_connector_refs if not _resolved(r)]
if unresolved_connector_refs:
    print(f"WARNING: {len(unresolved_connector_refs)} connector roles referenced by nodes not in connector_requirements:")
    for r in sorted(unresolved_connector_refs)[:20]:
        print(f"  - {r}")
    # Acceptance criterion: every node-referenced role must be in connector_requirements.
    # We allow the manifest to still emit so the engineering team can fix; but flag in production_boundaries.

# Hash the shared metadata contract (for traceability)
shared_contract_path = ROOT / "equity_registry_shared_metadata.schema.json"
shared_contract_sha = _sha256(shared_contract_path)


manifest = {
    "$schema": "./viza.module.manifest.v1.schema.json",
    "schema": "viza.module.manifest.v1",
    "module_id": "viza.finance.equity_investment",
    "module_version": "0.1.0",
    "display_name": "VIZA Equity Investment Module",
    "description": (
        "Domain module for equity investing on the VIZA platform. Ships entity / node / edge / "
        "attribute / event / insight / strategy_profile / output_view / validation / connector / "
        "rights / PIT registries that extend viza.core.strategy primitives and wrap viza.finance.securities. "
        "No monetized marketplace; marketplace_draft is the only export-shareable surface. "
        "All records ship at status=registry-seedable until runtime loaders validate them end-to-end."
    ),
    "domain": "finance.equity_investment",
    "release_state": "alpha",
    "baseline_reference": "Phase 35 + post-phase remediation + 2026-05-13 packaged-engine/runtime hardening",
    "depends_on": [
        {
            "module_id": "viza.core.strategy",
            "version": ">=1.0.0",
            "optional": False,
            "missing_behavior": "block_module_load",
            "notes": "Universal strategy primitives. Equity-specific objects extend universal core primitives (entity / candidate_set / attribute / event / evidence / assumption / transform / gate / score / relationship / scenario / decision / output / audit). Module load is blocked without it."
        },
        {
            "module_id": "viza.finance.securities",
            "version": ">=1.0.0",
            "optional": False,
            "missing_behavior": "block_module_load",
            "notes": "Legacy finance/securities wrapper. Required for v0.1 hard dependency per CLAUDE §27.2; viza.finance.equity_investment ships its own entity types but interoperates with the legacy wrapper."
        }
    ],
    "optional_modules": [
        {
            "module_id": "viza.aat.attribute_analysis",
            "version": ">=0.1.0",
            "missing_behavior": "degrade_gracefully",
            "notes": "AAT factor + event attribution submodule. Per CLAUDE §1.4, AAT is the canonical factor-residual provider but is NOT the whole equity module. When missing, factor_attribution_node opens locked-preserve-config and the factor_residual_calculator emits a warn-only signal."
        }
    ],
    "registry_artifacts": artifacts,
    "artifact_checksums": {
        "combined_sha256": combined_sha,
        "manifest_self_sha256_placeholder": "computed_post_emit_at_packaging_time"
    },
    "entity_types": entity_types,
    "node_types": node_types,
    "edge_types": edge_types,
    "attribute_families": attribute_families,
    "event_families": event_families,
    "insight_families": insight_families,
    "strategy_profiles": strategy_profiles,
    "output_views": output_views,
    "connector_roles": connector_roles,
    "validation_rules": validation_rules,
    "rights_policies": rights_policies,
    "audit_requirements": [
        "source_refs",
        "pit_timestamps",
        "rights_state",
        "methodology_graph_hash",
        "strategy_profile_hash",
        "validation_record_ids",
        "proof_checksum",
        "connector_entitlement_record",
        "human_review_record"
    ],
    "package_visibility_modes": [
        "white_box",
        "gray_box",
        "black_box",
        "output_only",
        "preview",
        "marketplace_draft"
    ],
    "missing_module_behavior": {
        "default_node_behavior": "open_locked_preserve_config",
        "default_connector_behavior": "fail_closed",
        "default_profile_behavior": "block_profile_use",
        "notes": (
            "Missing optional modules (AAT) degrade gracefully via open_locked_preserve_config on dependent nodes. "
            "Missing hard dependencies block module load. Missing licensed connectors fail closed (query_policy=blocked); "
            "dependent nodes open as locked placeholders and dependent profiles block_profile_use. No silent fallback to bad data."
        )
    },
    "production_boundaries": [
        {
            "boundary_id": "fmp_dev_only_unless_license_confirmed",
            "description": "FMP price data is development-only unless FMP_PRODUCTION_LICENSE_CONFIRMED=true (PROJECT_STATUS.md).",
            "severity": "block",
            "remediation": "Set FMP_PRODUCTION_LICENSE_CONFIRMED=true after legal sign-off; otherwise fall back to the licensed_market_data_connector and disable dependent nodes.",
            "source_refs": ["PROJECT_STATUS.md", "§18.5"]
        },
        {
            "boundary_id": "faustcalc_dev_only_unless_rights_confirmed",
            "description": "FaustCalc / FMP-derived snapshot data remains development / proving data unless source rights are confirmed.",
            "severity": "block",
            "remediation": "Confirm derived-value rights with provider; otherwise treat FaustCalc snapshots as derived_only and never package raw values.",
            "source_refs": ["PROJECT_STATUS.md"]
        },
        {
            "boundary_id": "fred_kenneth_french_not_vintaged",
            "description": "Current FRED and Kenneth French rows are timestamped at ingestion time, not as true PIT vintages.",
            "severity": "warn",
            "remediation": "Backtests that depend on vintaged macro / factor data must wait for the ALFRED-style vintaged pipeline to ship. Until then, factor_score_calculator and macro_snapshot_loader emit pit_safe_label=latest_only and refuse backtest promotion.",
            "source_refs": ["PROJECT_STATUS.md", "§16.10", "§10.17"]
        },
        {
            "boundary_id": "edgar_event_evidence_only",
            "description": "EDGAR event rows and return-based style descriptors are evidence-only unless a calibrated production contribution method exists.",
            "severity": "warn",
            "remediation": "Mark dependent attributes as evidence_only=true and exclude from production scoring inputs until calibration is documented.",
            "source_refs": ["PROJECT_STATUS.md"]
        },
        {
            "boundary_id": "qualitative_confidence_only",
            "description": "Confidence labels are qualitative data/model-quality labels, not calibrated probabilities.",
            "severity": "info",
            "remediation": "Confidence labels remain qualitative until a deflated-Sharpe / calibration framework is shipped.",
            "source_refs": ["PROJECT_STATUS.md", "§19.5"]
        },
        {
            "boundary_id": "no_monetized_marketplace",
            "description": "VIZA v0.1 supports marketplace_draft packaging only. Buy / sell / checkout / payment / subscription endpoints are out of scope.",
            "severity": "block",
            "remediation": "Block any package that references a monetized marketplace endpoint at packaging time.",
            "source_refs": ["§1.5", "§27.2"]
        },
        {
            "boundary_id": "non_advice_boundary_required_for_recommendations",
            "description": "Every recommendation-bearing output must surface a non-advice boundary statement.",
            "severity": "block",
            "remediation": "Block memo / trade_plan / equity_radar / risk_dashboard rendering without non_advice_boundary section.",
            "source_refs": ["§3.4", "§5.5", "§26"]
        },
        {
            "boundary_id": "short_fraud_legal_require_human_review",
            "description": "Short, fraud, and legal-sensitive claims require human review before export.",
            "severity": "block",
            "remediation": "Block export of fraud / legal / short outputs without a cleared human_review_record.",
            "source_refs": ["§17.7", "§19.9"]
        },
        {
            "boundary_id": "13f_not_current_positioning",
            "description": "13F holdings are 45-day-lagged; never use as current positioning.",
            "severity": "block",
            "remediation": "13F-derived attributes must mark filing_13f_data_must_not_be_used_as_current_positioning validation rule; runtime blocks current-positioning use.",
            "source_refs": ["§14.9"]
        },
        {
            "boundary_id": "ticker_never_primary_key",
            "description": "ticker is display-only; primary keys must be immutable company_id / security_id / share_class_id.",
            "severity": "block",
            "remediation": "Reject any registry entry whose immutable_keys contain ticker or a ticker-derived alias.",
            "source_refs": ["§20.4", "CLAUDE.md"]
        }
    ],
    "rights_policy": {
        "default_license_policy": "public_official",
        "raw_provider_export": "blocked",
        "unknown_rights_default": "blocked",
        "marketplace_draft_default": "redacted",
        "fail_closed_on_missing_license": True,
        "notes": (
            "Raw provider data export is blocked by default. Unknown rights default to blocked export + redacted marketplace + redaction_required=true. "
            "Public official metadata + derived values are allowed only where terms permit (e.g., EDGAR filings allow, Kenneth French requires attribution, GICS is licensed)."
        )
    },
    "pit_policy": {
        "pit_required_for_backtest": True,
        "vintage_required_for_macro": True,
        "vintage_required_for_factor": True,
        "13f_lag_acknowledged": True,
        "short_interest_release_date_used": True,
        "notes": (
            "Backtests require PIT-safe inputs. Macro inputs require ALFRED vintages; FRED current is latest-only until vintaged pipeline ships. "
            "Factor inputs (Kenneth French) currently ingest-timestamped; mark factor_score_calculator pit_safe_label=latest_only until vintaged. "
            "13F has 45-day lag and is never used as current positioning. Short interest uses FINRA publication date for available_at, never interpolated."
        )
    },
    "validation_policy": {
        "pit_required_for_backtest": True,
        "rights_required_for_packages": True,
        "human_review_required_for_fraud_legal_short": True,
        "non_advice_boundary_required_for_recommendation_outputs": True,
        "validation_levels": [
            "schema",
            "data",
            "PIT",
            "rights",
            "evidence",
            "statistical",
            "qualitative",
            "portfolio",
            "output",
            "package"
        ]
    },
    "marketplace_policy": {
        "monetized_marketplace_supported": False,
        "marketplace_draft_supported": True,
        "redaction_default": "restricted_provider_evidence_and_user_private_content",
        "creator_record_required": True,
        "non_advice_acknowledgement_required": True
    },
    "capabilities": {
        "graph_schema": "viza_graph_v0",
        "attribute_registry_version": "v1",
        "supported_actions": [
            "buy_candidate",
            "hold",
            "sell_candidate",
            "short_candidate",
            "avoid",
            "watch",
            "research_deeper",
            "hedge_candidate",
            "size_adjustment",
            "monitor",
            "alert_only"
        ]
    },
    "release_metadata": {
        "requires_engine_version": ">=2026.05.13",
        "license": "see_repo_LICENSE",
        "authors": ["VIZA AAT Team"],
        "shared_metadata_contract_ref": "./equity_registry_shared_metadata.schema.json",
        "shared_metadata_contract_sha256": shared_contract_sha
    },
    "compatibility_policy": {
        "additive_by_default": True,
        "missing_node_policy": "open_locked_preserve_config",
        "deprecation_window_minor_versions": 2
    }
}

# Add an unresolved-connector-refs production boundary if any were found
if unresolved_connector_refs:
    manifest["production_boundaries"].append({
        "boundary_id": "node_connector_refs_unresolved",
        "description": f"{len(unresolved_connector_refs)} connector roles referenced by node_types are not present in connector_requirements: {sorted(unresolved_connector_refs)}.",
        "severity": "block",
        "remediation": "Add the missing connector_requirement records OR remove the unresolved references from node_types before manifest promotion to beta.",
        "source_refs": ["§18.4", "§21"]
    })

OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote manifest to {OUT}")
print(f"  entity_types         : {len(entity_types)}")
print(f"  node_types           : {len(node_types)}")
print(f"  edge_types           : {len(edge_types)}")
print(f"  attribute_families   : {len(attribute_families)}")
print(f"  event_families       : {len(event_families)}")
print(f"  insight_families     : {len(insight_families)}")
print(f"  strategy_profiles    : {len(strategy_profiles)}")
print(f"  output_views         : {len(output_views)}")
print(f"  connector_roles      : {len(connector_roles)}")
print(f"  validation_rules     : {len(validation_rules)}")
print(f"  rights_policies      : {len(rights_policies)}")
print(f"  artifact_checksums   : {len(artifacts)} files, combined sha256={combined_sha[:16]}...")
if unresolved_connector_refs:
    print(f"  WARNING: {len(unresolved_connector_refs)} unresolved connector refs added to production_boundaries")

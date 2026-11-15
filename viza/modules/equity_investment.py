from __future__ import annotations

from viza.equity.registry import EQUITY_MODULE_ID, EQUITY_MODULE_VERSION, load_equity_module
from viza.modules.core_strategy import CORE_MODULE_ID
from viza.modules.models import (
    EntityTypeDefinition,
    NodeTypeDefinition,
    OutputViewDefinition,
    PaletteGroupDefinition,
    VizaModuleManifest,
)


EQUITY_INVESTMENT_MODULE_ID = EQUITY_MODULE_ID


def build_equity_investment_module() -> VizaModuleManifest:
    load_equity_module().validate().require_pass()
    node_types = {
        "viza.finance.equity_investment.sec_identity_resolver": _node(
            "sec_identity_resolver",
            "SEC Identity Resolver",
            "entity",
            "Resolves CIK-backed equity identity for the SEC first-wedge path.",
            "viza.equity.runtime.resolve_equity_identity",
        ),
        "viza.finance.equity_investment.sec_filing_evidence_bundle": _node(
            "sec_filing_evidence_bundle",
            "SEC Filing Evidence Bundle",
            "evidence",
            "Loads SEC submissions and companyfacts evidence with PIT and rights labels.",
            "viza.equity.runtime.build_sec_filing_evidence_bundle",
        ),
        "viza.finance.equity_investment.sec_public_fundamental_attributes": _node(
            "sec_public_fundamental_attributes",
            "SEC Public Fundamental Attributes",
            "attribute",
            "Derives the limited public SEC first-wedge fundamental attributes.",
            "viza.equity.runtime.derive_sec_public_fundamental_attributes",
        ),
        "viza.finance.equity_investment.fmp_market_snapshot_optional": _node(
            "fmp_market_snapshot_optional",
            "FMP Market Snapshot Optional",
            "attribute",
            "Optionally loads FMP price/market-cap support when feature flag and credential are present.",
            "viza.equity.runtime.fetch_fmp_market_snapshot_optional",
        ),
        "viza.finance.equity_investment.fred_macro_context_optional": _node(
            "fred_macro_context_optional",
            "FRED Macro Context Optional",
            "attribute",
            "Optionally loads FRED macro context with latest-only PIT warning unless vintage handling is enabled.",
            "viza.equity.runtime.fetch_fred_macro_context_optional",
        ),
        "viza.finance.equity_investment.quality_value_profile_compatibility": _node(
            "quality_value_profile_compatibility",
            "Quality Value Profile Compatibility",
            "gate",
            "Checks quality_value_long_only profile compatibility before output translation.",
            "viza.equity.runtime.run_quality_value_profile_compatibility",
        ),
        "viza.finance.equity_investment.equity_radar_preview": _node(
            "equity_radar_preview",
            "Equity Radar Preview",
            "output",
            "Renders non-advice equity radar preview with PIT, rights, validation, and missing-data warnings.",
            "viza.equity.runtime.render_equity_radar_preview",
        ),
        "viza.finance.equity_investment.validation_report": _node(
            "validation_report",
            "Validation Report",
            "audit",
            "Renders EQ-VAL first-wedge validation report.",
            "viza.equity.runtime.render_validation_report",
        ),
        "viza.finance.equity_investment.source_rights_report": _node(
            "source_rights_report",
            "Source Rights Report",
            "audit",
            "Renders source rights, entitlement, and redaction status.",
            "viza.equity.runtime.render_source_rights_report",
        ),
        "viza.finance.equity_investment.package_redaction_preview": _node(
            "package_redaction_preview",
            "Package Redaction Preview",
            "audit",
            "Previews white_box, output_only, and marketplace_draft package behavior.",
            "viza.equity.runtime.preview_package_redaction",
        ),
    }
    return VizaModuleManifest(
        module_id=EQUITY_MODULE_ID,
        module_version=EQUITY_MODULE_VERSION,
        display_name="VIZA Equity Investment",
        domain="finance.equity_investment",
        description=(
            "Feature-flagged equity investment runtime wedge for SEC public evidence, optional "
            "FMP/FRED context, quality-value profile compatibility, and package redaction previews."
        ),
        entity_types={
            "company": EntityTypeDefinition(
                type_id="viza.finance.equity_investment.company",
                display_name="Company",
                description="CIK-backed company identity for equity research previews.",
                identifiers=["viza_entity_id", "company_id", "cik"],
            ),
            "equity_security": EntityTypeDefinition(
                type_id="viza.finance.equity_investment.equity_security",
                display_name="Equity Security",
                description="Equity security whose ticker is an alias, not a primary key.",
                identifiers=["security_id", "listing_id", "cik", "ticker_alias"],
            ),
        },
        node_types=node_types,
        edge_types={
            "data_flow": {"display_name": "Data Flow"},
            "evidence": {"display_name": "Evidence"},
            "audit": {"display_name": "Audit"},
        },
        output_views={
            "equity_radar": OutputViewDefinition(
                view_id="equity_radar",
                display_name="Equity Radar",
                result_key="outputs.equity_radar",
            ),
            "validation_report": OutputViewDefinition(
                view_id="validation_report",
                display_name="Validation Report",
                result_key="outputs.validation_report",
            ),
            "source_rights_report": OutputViewDefinition(
                view_id="source_rights_report",
                display_name="Source Rights Report",
                result_key="outputs.source_rights_report",
            ),
            "package_redaction_preview": OutputViewDefinition(
                view_id="package_redaction_preview",
                display_name="Package Redaction Preview",
                result_key="outputs.package_redaction_preview",
            ),
        },
        data_connectors=["sec_edgar", "fmp", "fred", "local_viza_workspace"],
        validation_rules=[f"EQ-VAL-{index:03d}" for index in range(1, 13)],
        runtime_handlers={
            node_type_id: node_type.runtime_handler or ""
            for node_type_id, node_type in node_types.items()
        },
        palette_groups=[
            PaletteGroupDefinition(
                group_id="equity_sec_first_wedge",
                display_name="Equity SEC First Wedge",
                node_types=list(node_types),
            )
        ],
    )


def _node(
    key: str,
    display_name: str,
    core_primitive: str,
    description: str,
    runtime_handler: str,
) -> NodeTypeDefinition:
    return NodeTypeDefinition(
        type_id=f"{EQUITY_MODULE_ID}.{key}",
        display_name=display_name,
        category="finance.equity_investment",
        extends=f"{CORE_MODULE_ID}.{core_primitive}",
        description=description,
        inspector_schema={"type": "object", "additionalProperties": True},
        allowed_incoming_edges=["data_flow", "evidence", "audit"],
        allowed_outgoing_edges=["data_flow", "evidence", "audit"],
        runtime_handler=runtime_handler,
        visual={"label": display_name},
    )

from __future__ import annotations

from viza.graph_schema import VizaNodeType
from viza.modules.core_strategy import CORE_MODULE_ID
from viza.modules.models import (
    EntityTypeDefinition,
    NodeTypeDefinition,
    OutputViewDefinition,
    PaletteGroupDefinition,
    VizaModuleManifest,
)


FINANCE_MODULE_ID = "viza.finance.securities"
FINANCE_MODULE_VERSION = "0.1.0"

LEGACY_TO_FINANCE_TYPE = {
    VizaNodeType.UNIVERSE.value: f"{FINANCE_MODULE_ID}.universe",
    VizaNodeType.ATTRIBUTE.value: f"{FINANCE_MODULE_ID}.attribute",
    VizaNodeType.TRANSFORM.value: f"{FINANCE_MODULE_ID}.transform",
    VizaNodeType.FILTER.value: f"{FINANCE_MODULE_ID}.filter",
    VizaNodeType.SCORE.value: f"{FINANCE_MODULE_ID}.score",
    VizaNodeType.RELATIONSHIP.value: f"{FINANCE_MODULE_ID}.relationship",
    VizaNodeType.OUTPUT_RADAR.value: f"{FINANCE_MODULE_ID}.output_radar",
}
FINANCE_TO_LEGACY_TYPE = {value: key for key, value in LEGACY_TO_FINANCE_TYPE.items()}

_NODE_META = {
    "universe": ("Universe", "candidate_set", "Selects the investable securities universe."),
    "attribute": ("Attribute", "attribute", "Loads or derives a finance attribute."),
    "transform": ("Transform", "transform", "Transforms attribute values for scoring."),
    "filter": ("Filter", "gate", "Filters securities by configured rules."),
    "score": ("Score", "score", "Combines inputs into a ranking score."),
    "relationship": ("Relationship", "relationship", "Builds relationship/evidence views."),
    "output_radar": ("Output Radar", "output", "Emits the radar table output."),
}


def build_finance_securities_module() -> VizaModuleManifest:
    node_types = {
        module_type: _node_definition(legacy_type, module_type)
        for legacy_type, module_type in LEGACY_TO_FINANCE_TYPE.items()
    }
    node_types[f"{FINANCE_MODULE_ID}.asset_resolver"] = NodeTypeDefinition(
        type_id=f"{FINANCE_MODULE_ID}.asset_resolver",
        display_name="Asset Resolver",
        category="finance",
        extends="viza.core.strategy.entity",
        description="Resolves finance tickers to canonical VIZA entity and asset IDs.",
        inspector_schema={"type": "object", "additionalProperties": True},
        allowed_incoming_edges=["data_flow"],
        allowed_outgoing_edges=["data_flow"],
        runtime_handler="implicit_runtime.asset_resolver",
        visual={"label": "Asset Resolver"},
    )
    node_types[f"{FINANCE_MODULE_ID}.event_catalyst"] = NodeTypeDefinition(
        type_id=f"{FINANCE_MODULE_ID}.event_catalyst",
        display_name="Event Catalyst",
        category="finance",
        extends="viza.core.strategy.attribute",
        description="Filters and emits first-class catalyst/event objects for securities.",
        inspector_schema={
            "type": "object",
            "properties": {
                "event_types": {"type": "array", "items": {"type": "string"}},
                "min_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "min_source_credibility": {"type": "number", "minimum": 0, "maximum": 1},
                "time_window": {"type": "string"},
                "require_point_in_time_safe": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
        allowed_incoming_edges=["data_flow", "evidence"],
        allowed_outgoing_edges=["data_flow", "relationship", "evidence"],
        runtime_handler="event_runtime.extract_catalysts",
        visual={"label": "Event Catalyst"},
    )
    node_types[f"{FINANCE_MODULE_ID}.insight_extractor"] = NodeTypeDefinition(
        type_id=f"{FINANCE_MODULE_ID}.insight_extractor",
        display_name="Insight Extractor",
        category="finance",
        extends="viza.core.strategy.transform",
        description="Extracts first-class insight objects from events, attributes, and evidence.",
        inspector_schema={
            "type": "object",
            "properties": {
                "enabled_insight_types": {"type": "array", "items": {"type": "string"}},
                "min_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "require_evidence_refs": {"type": "boolean"},
                "require_point_in_time_safe": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
        allowed_incoming_edges=["data_flow", "relationship", "evidence"],
        allowed_outgoing_edges=["data_flow", "relationship", "evidence"],
        runtime_handler="insight_runtime.extract",
        visual={"label": "Insight Extractor"},
    )
    node_types[f"{FINANCE_MODULE_ID}.strategy_profile"] = NodeTypeDefinition(
        type_id=f"{FINANCE_MODULE_ID}.strategy_profile",
        display_name="Strategy Profile",
        category="finance",
        extends="viza.core.strategy.strategy_profile",
        description="Selects or defines the strategy lens used for insight translation.",
        inspector_schema={
            "type": "object",
            "properties": {
                "strategy_profile_id": {"type": "string"},
                "template_id": {"type": "string"},
                "action_thresholds": {"type": "object"},
            },
            "additionalProperties": True,
        },
        allowed_incoming_edges=["data_flow"],
        allowed_outgoing_edges=["data_flow", "relationship", "evidence"],
        runtime_handler="strategy_profile_runtime.select",
        visual={"label": "Strategy Profile"},
    )
    return VizaModuleManifest(
        module_id=FINANCE_MODULE_ID,
        module_version=FINANCE_MODULE_VERSION,
        display_name="Finance / Securities",
        domain="finance.securities",
        description="Finance securities domain module wrapping the current VIZA graph vocabulary.",
        entity_types={
            "security": EntityTypeDefinition(
                type_id=f"{FINANCE_MODULE_ID}.security",
                display_name="Security",
                description="Tradable finance security.",
                identifiers=["ticker", "figi", "cusip", "isin"],
            ),
            "company": EntityTypeDefinition(
                type_id=f"{FINANCE_MODULE_ID}.company",
                display_name="Company",
                description="Issuer or operating company.",
                identifiers=["ticker", "cik", "lei"],
            ),
        },
        node_types=node_types,
        edge_types={
            "data_flow": {"display_name": "Data Flow"},
            "relationship": {"display_name": "Relationship"},
            "evidence": {"display_name": "Evidence"},
        },
        output_views={
            "radar_table": OutputViewDefinition(
                view_id="radar_table",
                display_name="Radar Table",
                result_key="rows",
            )
        },
        data_connectors=["local_viza_workspace"],
        validation_rules=["legacy_graph_shape", "finance_runtime_supported"],
        runtime_handlers={
            module_type: f"legacy_runtime.{legacy_type}"
            for legacy_type, module_type in LEGACY_TO_FINANCE_TYPE.items()
        },
        palette_groups=[
            PaletteGroupDefinition(
                group_id="finance_methodology",
                display_name="Finance Methodology",
                node_types=[
                    LEGACY_TO_FINANCE_TYPE[VizaNodeType.UNIVERSE.value],
                    LEGACY_TO_FINANCE_TYPE[VizaNodeType.ATTRIBUTE.value],
                    LEGACY_TO_FINANCE_TYPE[VizaNodeType.TRANSFORM.value],
                    LEGACY_TO_FINANCE_TYPE[VizaNodeType.FILTER.value],
                    LEGACY_TO_FINANCE_TYPE[VizaNodeType.SCORE.value],
                    f"{FINANCE_MODULE_ID}.event_catalyst",
                    f"{FINANCE_MODULE_ID}.insight_extractor",
                    f"{FINANCE_MODULE_ID}.strategy_profile",
                    LEGACY_TO_FINANCE_TYPE[VizaNodeType.OUTPUT_RADAR.value],
                    LEGACY_TO_FINANCE_TYPE[VizaNodeType.RELATIONSHIP.value],
                ],
            )
        ],
    )


def finance_module_type_for_legacy(legacy_type: str) -> str:
    if legacy_type not in LEGACY_TO_FINANCE_TYPE:
        raise KeyError(f"unknown legacy finance node type: {legacy_type}")
    return LEGACY_TO_FINANCE_TYPE[legacy_type]


def legacy_type_for_finance_module(module_type: str) -> str:
    if module_type not in FINANCE_TO_LEGACY_TYPE:
        raise KeyError(f"unknown finance module node type: {module_type}")
    return FINANCE_TO_LEGACY_TYPE[module_type]


def _node_definition(legacy_type: str, module_type: str) -> NodeTypeDefinition:
    display_name, core_primitive, description = _NODE_META[legacy_type]
    return NodeTypeDefinition(
        type_id=module_type,
        display_name=display_name,
        category="finance",
        extends=f"{CORE_MODULE_ID}.{core_primitive}",
        description=description,
        inspector_schema={"type": "object", "additionalProperties": True},
        allowed_incoming_edges=["data_flow", "relationship", "evidence"],
        allowed_outgoing_edges=["data_flow", "relationship", "evidence"],
        runtime_handler=f"legacy_runtime.{legacy_type}",
        legacy_type=legacy_type,
        visual={"label": display_name},
    )

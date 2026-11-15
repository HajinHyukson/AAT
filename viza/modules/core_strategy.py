from __future__ import annotations

from viza.modules.models import NodeTypeDefinition, PaletteGroupDefinition, VizaModuleManifest


CORE_MODULE_ID = "viza.core.strategy"
CORE_MODULE_VERSION = "0.1.0"

CORE_PRIMITIVES = [
    "entity",
    "candidate_set",
    "attribute",
    "event",
    "evidence",
    "assumption",
    "transform",
    "gate",
    "score",
    "relationship",
    "scenario",
    "strategy_profile",
    "decision",
    "output",
    "audit",
]


def build_core_strategy_module() -> VizaModuleManifest:
    node_types = {
        f"{CORE_MODULE_ID}.{primitive}": NodeTypeDefinition(
            type_id=f"{CORE_MODULE_ID}.{primitive}",
            display_name=primitive.replace("_", " ").title(),
            category="core",
            extends="",
            description=f"Domain-neutral VIZA strategy primitive: {primitive}.",
            inspector_schema={"type": "object", "additionalProperties": True},
            allowed_incoming_edges=[],
            allowed_outgoing_edges=[],
            runtime_handler=None,
            visual={"shape": "primitive"},
        )
        for primitive in CORE_PRIMITIVES
    }
    return VizaModuleManifest(
        module_id=CORE_MODULE_ID,
        module_version=CORE_MODULE_VERSION,
        display_name="VIZA Core Strategy",
        domain="core",
        description="Domain-neutral primitives that domain modules extend.",
        node_types=node_types,
        palette_groups=[
            PaletteGroupDefinition(
                group_id="core_primitives",
                display_name="Core Primitives",
                node_types=list(node_types),
            )
        ],
    )

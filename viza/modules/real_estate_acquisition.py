from __future__ import annotations

import json
from pathlib import Path

from viza.config_paths import resolve_config_path, source_root
from viza.modules.core_strategy import CORE_MODULE_ID
from viza.modules.models import NodeTypeDefinition, VizaModuleManifest


REAL_ESTATE_MODULE_ID = "viza.real_estate.acquisition"
REAL_ESTATE_MODULE_VERSION = "0.1.0"
REPO_ROOT = source_root()
REAL_ESTATE_MODULE_MANIFEST_PATH = (
    REPO_ROOT / "config" / "viza_modules" / "viza.real_estate.acquisition.json"
)

REAL_ESTATE_NODE_TYPES = {
    "property_universe": ("Property Universe", "candidate_set", "Loads property candidates from local CSV."),
    "market_filter": ("Market Filter", "gate", "Filters properties by market."),
    "comparable_sales": ("Comparable Sales", "attribute", "Adds comparable-sales context."),
    "rent_roll": ("Rent Roll", "attribute", "Adds rent-roll context."),
    "noi_model": ("NOI Model", "transform", "Projects net operating income."),
    "cap_rate_filter": ("Cap Rate Filter", "gate", "Filters by capitalization rate."),
    "debt_terms": ("Debt Terms", "attribute", "Adds debt sizing assumptions."),
    "dscr_gate": ("DSCR Gate", "gate", "Filters by debt-service coverage ratio."),
    "renovation_budget": ("Renovation Budget", "attribute", "Adds renovation budget assumptions."),
    "exit_scenario": ("Exit Scenario", "transform", "Models exit capitalization assumptions."),
    "deal_score": ("Deal Score", "score", "Scores acquisition candidates."),
    "deal_pipeline": ("Deal Pipeline", "output", "Outputs a ranked property pipeline."),
    "investment_memo": ("Investment Memo", "output", "Outputs a concise investment memo."),
}


def build_real_estate_acquisition_module() -> VizaModuleManifest:
    manifest_path = resolve_config_path("viza_modules", "viza.real_estate.acquisition.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    node_types = {}
    runtime_handlers = {}
    for short_type, (display_name, primitive, description) in REAL_ESTATE_NODE_TYPES.items():
        type_id = f"{REAL_ESTATE_MODULE_ID}.{short_type}"
        runtime_handler = f"real_estate_runtime.{short_type}"
        node_types[type_id] = NodeTypeDefinition(
            type_id=type_id,
            display_name=display_name,
            category="real_estate",
            extends=f"{CORE_MODULE_ID}.{primitive}",
            description=description,
            inspector_schema={"type": "object", "additionalProperties": True},
            allowed_incoming_edges=["data_flow", "evidence"],
            allowed_outgoing_edges=["data_flow", "evidence"],
            runtime_handler=runtime_handler,
            visual={"label": display_name},
        ).model_dump(mode="json")
        runtime_handlers[type_id] = runtime_handler
    payload["node_types"] = node_types
    payload["runtime_handlers"] = runtime_handlers
    return VizaModuleManifest.model_validate(payload)

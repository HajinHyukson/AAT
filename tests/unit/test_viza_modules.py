from __future__ import annotations

from fastapi.testclient import TestClient

from viza.file_format import export_methodology_graph_to_viza, read_viza_manifest
from viza.modules import (
    FINANCE_MODULE_ID,
    create_unknown_node_placeholder,
    get_module_registry,
)
from viza.sample_data import load_sample_methodology_graph
from viza.service import app


client = TestClient(app)


def test_core_and_finance_modules_load() -> None:
    registry = get_module_registry()

    core = registry.get_module("viza.core.strategy")
    finance = registry.get_module(FINANCE_MODULE_ID)

    assert "viza.core.strategy.entity" in core.node_types
    assert "viza.finance.securities.universe" in finance.node_types
    assert finance.node_types["viza.finance.securities.score"].legacy_type == "score"
    assert finance.palette_groups[0].node_types


def test_legacy_node_types_map_to_finance_module_types() -> None:
    registry = get_module_registry()

    assert registry.legacy_to_module_type("universe") == "viza.finance.securities.universe"
    assert registry.module_to_legacy_type("viza.finance.securities.output_radar") == "output_radar"
    resolved = registry.resolve_node_type("attribute")

    assert resolved.status == "resolved"
    assert resolved.module_id == FINANCE_MODULE_ID
    assert resolved.legacy_type == "attribute"


def test_current_graph_requires_finance_module_and_export_records_requirement(tmp_path) -> None:
    graph = load_sample_methodology_graph()
    registry = get_module_registry()

    requirements = registry.required_modules_for_graph(graph)
    result, _manifest = export_methodology_graph_to_viza(graph, tmp_path / "graph.viza")
    written_manifest = read_viza_manifest(result.path)

    assert [requirement.module_id for requirement in requirements] == [FINANCE_MODULE_ID]
    assert [module.module_id for module in written_manifest.required_modules] == [FINANCE_MODULE_ID]


def test_unknown_module_creates_round_trippable_placeholder() -> None:
    registry = get_module_registry()
    resolved = registry.resolve_node_type("viza.real_estate.acquisition.noi_model")
    placeholder = create_unknown_node_placeholder(
        "viza.real_estate.acquisition",
        "noi_model",
        {"cap_rate": 0.055},
    )
    round_tripped = placeholder.model_validate(placeholder.model_dump(mode="json"))

    assert resolved.status == "missing_module"
    assert resolved.module_installed is False
    assert resolved.placeholder is not None
    assert round_tripped.raw_config == {"cap_rate": 0.055}
    assert round_tripped.executable is False


def test_module_registry_endpoints_return_serializable_palette_data() -> None:
    response = client.get("/viza/modules")
    assert response.status_code == 200
    modules = response.json()
    finance = next(module for module in modules if module["module_id"] == FINANCE_MODULE_ID)

    assert finance["palette_groups"][0]["display_name"] == "Finance Methodology"
    assert "viza.finance.securities.universe" in finance["node_types"]

    resolve_response = client.post(
        "/viza/modules/resolve-node-types",
        json={"type_ids": ["universe", "viza.unknown.module.node"]},
    )
    assert resolve_response.status_code == 200
    resolved = resolve_response.json()
    assert resolved[0]["status"] == "resolved"
    assert resolved[1]["status"] == "missing_module"


def test_module_compatibility_endpoint_reports_missing_modules() -> None:
    response = client.post(
        "/viza/modules/check-compatibility",
        json={
            "required_modules": [
                {"module_id": FINANCE_MODULE_ID, "version_range": ">=0.1.0", "required": True},
                {"module_id": "viza.missing.module", "version_range": "*", "required": True},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["status"] == "installed"
    assert payload[1]["status"] == "missing_required"

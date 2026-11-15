from __future__ import annotations

import zipfile

from viza.modules import REAL_ESTATE_MODULE_ID, get_module_registry
from viza.real_estate import (
    REAL_ESTATE_GRAPH_SCHEMA,
    export_real_estate_graph_to_viza,
    import_real_estate_graph_from_viza,
    load_property_universe,
    run_real_estate_acquisition_graph,
)


def _property_csv(tmp_path):
    path = tmp_path / "properties.csv"
    path.write_text(
        "\n".join(
            [
                "property_id,property_name,market,property_type,units,asking_price,noi,cap_rate,rent_growth_assumption,expense_growth_assumption,debt_rate,loan_to_value",
                "p-1,Oak Lofts,Austin,multifamily,120,18000000,1350000,0.075,0.04,0.025,0.055,0.65",
                "p-2,River Industrial,Dallas,industrial,1,12500000,820000,0.065,0.03,0.022,0.06,0.72",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _graph_payload(csv_path):
    return {
        "schema": REAL_ESTATE_GRAPH_SCHEMA,
        "methodology_id": "real-estate-smoke",
        "name": "Real Estate Acquisition Smoke",
        "domain": "real_estate.acquisition",
        "config": {
            "csv_path": str(csv_path),
            "min_dscr": 1.2,
            "max_loan_to_value": 0.75,
        },
        "nodes": [
            {
                "id": "property-universe",
                "type": "viza.real_estate.acquisition.property_universe",
                "config": {"csv_path": str(csv_path)},
            },
            {"id": "deal-score", "type": "viza.real_estate.acquisition.deal_score", "config": {}},
            {
                "id": "investment-memo",
                "type": "viza.real_estate.acquisition.investment_memo",
                "config": {},
            },
        ],
        "edges": [],
    }


def test_real_estate_module_loads_when_feature_flag_enabled(monkeypatch) -> None:
    monkeypatch.setenv("VIZA_ENABLE_NON_FINANCE_MODULES", "true")
    get_module_registry.cache_clear()

    module = get_module_registry().get_module(REAL_ESTATE_MODULE_ID)

    assert module.palette_groups[0].display_name == "Real Estate Acquisition"
    assert "viza.real_estate.acquisition.deal_score" in module.node_types

    get_module_registry.cache_clear()


def test_real_estate_module_is_missing_when_feature_flag_disabled(monkeypatch) -> None:
    monkeypatch.delenv("VIZA_ENABLE_NON_FINANCE_MODULES", raising=False)
    get_module_registry.cache_clear()

    resolved = get_module_registry().resolve_node_type(
        "viza.real_estate.acquisition.deal_score"
    )

    assert resolved.status == "missing_module"
    assert resolved.placeholder is not None
    assert resolved.placeholder["module_id"] == "viza.real_estate.acquisition"

    get_module_registry.cache_clear()


def test_local_csv_property_universe_loads(tmp_path) -> None:
    properties = load_property_universe(_property_csv(tmp_path))

    assert len(properties) == 2
    assert properties[0].property_name == "Oak Lofts"


def test_real_estate_deal_score_and_memo_run(tmp_path) -> None:
    result = run_real_estate_acquisition_graph(_graph_payload(_property_csv(tmp_path)))

    assert result.status == "completed"
    assert result.deal_pipeline[0]["deal_score"] >= result.deal_pipeline[1]["deal_score"]
    assert result.deal_pipeline[0]["dscr"] > 1
    assert "Oak Lofts" in result.investment_memo["markdown"]


def test_real_estate_viza_export_import_round_trip(tmp_path) -> None:
    target = tmp_path / "real-estate.viza"
    graph_payload = _graph_payload(_property_csv(tmp_path))

    result, manifest = export_real_estate_graph_to_viza(graph_payload, target)
    imported = import_real_estate_graph_from_viza(target)

    with zipfile.ZipFile(target) as archive:
        assert "graph/methodology.json" in archive.namelist()
    assert result.file_id == manifest["file_id"]
    assert manifest["required_modules"][1]["module_id"] == REAL_ESTATE_MODULE_ID
    assert imported["schema"] == REAL_ESTATE_GRAPH_SCHEMA
    assert imported["nodes"][0]["config"]["csv_path"] == graph_payload["config"]["csv_path"]


def test_missing_module_placeholder_preserves_raw_config(monkeypatch) -> None:
    monkeypatch.delenv("VIZA_ENABLE_NON_FINANCE_MODULES", raising=False)
    get_module_registry.cache_clear()
    raw_config = {"min_dscr": 1.35, "csv_path": "properties.csv"}

    placeholder = get_module_registry().resolve_node_type(
        "viza.real_estate.acquisition.dscr_gate"
    ).placeholder

    assert placeholder is not None
    placeholder["raw_config"] = raw_config
    assert placeholder["raw_config"] == raw_config

    get_module_registry.cache_clear()

from __future__ import annotations

from fastapi.testclient import TestClient

from viza.assets import (
    AssetResolveRequest,
    asset_id_for_ticker,
    duplicate_ticker_warnings,
    get_asset_store,
)
from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology
from viza.sample_data import load_sample_methodology_graph
from viza.service import app
from viza.universes import load_universe_definition


client = TestClient(app)


def test_seed_local_universe_creates_assets_and_provider_map(tmp_path) -> None:
    store = get_asset_store(tmp_path / "viza_projects.sqlite3")
    universe = load_universe_definition("pilot_sp500_static")

    assets = store.seed_local_universe(universe)
    first = assets[0]

    assert first.asset_id == asset_id_for_ticker(first.primary_symbol)
    assert first.provider_identifier_map["local_universe"] == first.primary_symbol
    assert store.identifiers_for_asset(first.asset_id)["ticker"] == first.primary_symbol


def test_resolve_ticker_to_asset_and_duplicate_warning(tmp_path) -> None:
    store = get_asset_store(tmp_path / "viza_projects.sqlite3")
    asset = store.seed_local_universe(load_universe_definition("pilot_sp500_static"))[0]

    result = store.resolve_asset(AssetResolveRequest(ticker=asset.primary_symbol))

    assert result.asset is not None
    assert result.asset.asset_id == asset.asset_id
    assert "missing_provider_identifiers" in result.warnings
    assert duplicate_ticker_warnings(["AAPL", "MSFT", "aapl"]) == ["duplicate_ticker:AAPL"]


def test_asset_endpoints_search_resolve_identifiers_and_reconcile(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))

    resolve_response = client.post("/viza/assets/resolve", json={"ticker": "AAPL"})
    assert resolve_response.status_code == 200
    asset_id = resolve_response.json()["asset"]["asset_id"]

    search_response = client.get("/viza/assets/search?q=AAPL")
    assert search_response.status_code == 200
    assert search_response.json()[0]["primary_symbol"] == "AAPL"

    identifiers_response = client.get(f"/viza/assets/{asset_id}/identifiers")
    assert identifiers_response.status_code == 200
    assert identifiers_response.json()["ticker"] == "AAPL"

    reconcile_response = client.post(
        "/viza/assets/reconcile",
        json={"provider_identifier_map": {"provider_a": "same", "provider_b": "same"}},
    )
    assert reconcile_response.status_code == 200
    assert reconcile_response.json()["conflicts"] == ["same"]


def test_runtime_rows_and_evidence_include_asset_and_entity_ids() -> None:
    graph = load_sample_methodology_graph()
    result = run_methodology(graph, load_attribute_registry())

    row = result.rows[0]
    company_evidence = result.evidence[f"company:{row.ticker}"]
    attribute_ref = next(ref for ref in row.evidence_refs if ref.startswith("attr:"))

    assert row.entity_id
    assert row.asset_id
    assert company_evidence["entity_id"] == row.entity_id
    assert company_evidence["asset_id"] == row.asset_id
    assert result.evidence[attribute_ref]["entity_id"] == row.entity_id
    assert result.evidence[attribute_ref]["asset_id"] == row.asset_id

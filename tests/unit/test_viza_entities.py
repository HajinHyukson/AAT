from __future__ import annotations

from fastapi.testclient import TestClient

from viza.entities import EntityResolveRequest, entity_id_for_ticker, get_entity_store
from viza.sample_data import load_sample_methodology_graph
from viza.service import app
from viza.universes import load_universe_definition


client = TestClient(app)


def test_seed_local_universe_creates_entities(tmp_path) -> None:
    store = get_entity_store(tmp_path / "viza_projects.sqlite3")
    universe = load_universe_definition("pilot_sp500_static")

    entities = store.seed_local_universe(universe)
    first = entities[0]

    assert first.entity_id == entity_id_for_ticker(first.identifiers["ticker"])
    assert first.domain == "finance.securities"
    assert first.metadata["missing_identifiers"] == ["figi", "cusip", "isin"]
    assert store.require_entity(first.entity_id).display_name == first.display_name


def test_resolve_ticker_to_entity_with_missing_identifier_warning(tmp_path) -> None:
    store = get_entity_store(tmp_path / "viza_projects.sqlite3")
    entity = store.seed_local_universe(load_universe_definition("pilot_sp500_static"))[0]

    result = store.resolve_entity(
        EntityResolveRequest(ticker=entity.identifiers["ticker"]),
    )

    assert result.entity is not None
    assert result.entity.entity_id == entity.entity_id
    assert "missing_provider_identifiers" in result.warnings


def test_entity_endpoints_search_resolve_and_relationships(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_sample_methodology_graph()
    ticker = graph.nodes[0].config.get("ticker_subset", ["AAPL"])[0]

    resolve_response = client.post("/viza/entities/resolve", json={"ticker": ticker})
    assert resolve_response.status_code == 200
    entity_id = resolve_response.json()["entity"]["entity_id"]

    search_response = client.get(f"/viza/entities/search?q={ticker}")
    assert search_response.status_code == 200
    assert search_response.json()

    entity_response = client.get(f"/viza/entities/{entity_id}")
    assert entity_response.status_code == 200

    relationships_response = client.get(f"/viza/entities/{entity_id}/relationships")
    assert relationships_response.status_code == 200
    assert relationships_response.json() == []

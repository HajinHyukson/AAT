from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from viza.assets import resolve_static_asset_identity
from viza.attribute_registry import load_attribute_registry
from viza.attribute_resolvers import resolve_attribute_values
from viza.execution import run_methodology
from viza.graph_schema import load_methodology_graph
from viza.observations import (
    OHLCVRow,
    ObservationIngestRequest,
    ObservationInput,
    calculate_rsi_14d,
    get_observation_store,
    observation_from_input,
    observation_for_export,
    observations_from_ohlcv,
)
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app
from viza.universes import load_universe_definition


client = TestClient(app)


def test_insert_observation_and_retrieve_as_of_cutoff(tmp_path) -> None:
    store = get_observation_store(tmp_path / "viza_projects.sqlite3")
    observed_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    available_at = observed_at + timedelta(hours=1)
    future_available_at = available_at + timedelta(days=2)
    entity_id, asset_id = resolve_static_asset_identity("AAPL")

    saved = store.ingest(
        ObservationIngestRequest(
            observations=[
                ObservationInput(
                    entity_id=entity_id,
                    asset_id=asset_id,
                    attribute_key="momentum",
                    value=0.42,
                    unit="score",
                    observed_at=observed_at,
                    available_at=available_at,
                    source_id="unit_test",
                    connector_id="local_csv",
                    data_version="unit_v1",
                    model_version="unit_model_v1",
                    confidence=0.91,
                ),
                ObservationInput(
                    entity_id=entity_id,
                    asset_id=asset_id,
                    attribute_key="momentum",
                    value=0.99,
                    unit="score",
                    observed_at=future_available_at,
                    available_at=future_available_at,
                    source_id="unit_test",
                    connector_id="local_csv",
                    data_version="unit_v2",
                    model_version="unit_model_v1",
                    confidence=0.91,
                ),
            ],
        ),
    )

    assert len(saved) == 2
    latest = store.get_latest_observation_as_of(
        entity_id,
        "momentum",
        available_at + timedelta(minutes=1),
    )
    assert latest is not None
    assert latest.value == 0.42
    assert latest.data_version == "unit_v1"

    lookahead = store.get_latest_observation_as_of(
        entity_id,
        "momentum",
        observed_at,
    )
    assert lookahead is None


def test_observation_endpoints_ingest_query_and_get(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    entity_id, asset_id = resolve_static_asset_identity("MSFT")
    observed_at = datetime(2026, 2, 1, tzinfo=timezone.utc)

    ingest_response = client.post(
        "/viza/observations/ingest",
        json={
            "observations": [
                {
                    "entity_id": entity_id,
                    "asset_id": asset_id,
                    "attribute_key": "latest_price",
                    "value": 411.25,
                    "unit": "price",
                    "observed_at": observed_at.isoformat(),
                    "available_at": observed_at.isoformat(),
                    "source_id": "unit_test",
                    "connector_id": "local_csv",
                    "data_version": "unit_price_v1",
                }
            ]
        },
    )

    assert ingest_response.status_code == 200
    observation_id = ingest_response.json()[0]["observation_id"]

    query_response = client.post(
        "/viza/observations/query",
        json={
            "entity_id": entity_id,
            "attribute_key": "latest_price",
            "cutoff": observed_at.isoformat(),
        },
    )
    assert query_response.status_code == 200
    assert query_response.json()["observations"][0]["observation_id"] == observation_id

    get_response = client.get(f"/viza/observations/{observation_id}")
    assert get_response.status_code == 200
    assert get_response.json()["value"] == 411.25


def test_compute_rsi_from_local_ohlcv_rows() -> None:
    rows = [
        OHLCVRow(
            timestamp=datetime(2026, 1, day, tzinfo=timezone.utc),
            close=100 + day + (day % 3),
            volume=1_000_000 + day * 1_000,
        )
        for day in range(1, 31)
    ]
    request = ObservationIngestRequest(
        entity_id="entity-us-equity-AAPL",
        asset_id="asset-us-equity-AAPL",
        ohlcv_rows=rows,
        source_record="aapl.csv",
    )

    observations = observations_from_ohlcv(request)
    values = {observation.attribute_key: observation.value for observation in observations}

    assert values["latest_price"] == 130
    assert values["rsi_14d"] == calculate_rsi_14d([row.close for row in rows])
    assert "momentum" in values
    assert "volume_spike" in values


def test_resolver_uses_prototype_without_source_and_observation_when_present(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    registry = load_attribute_registry()
    security = load_universe_definition("pilot_sp500_static").securities[0]
    entity_id, asset_id = resolve_static_asset_identity(security.ticker)

    fallback = resolve_attribute_values(security, ["momentum"], registry)["momentum"]
    assert fallback.is_prototype is True
    assert fallback.observation_id is None

    observed_at = datetime.now(timezone.utc) - timedelta(days=1)
    saved = get_observation_store().ingest(
        ObservationIngestRequest(
            observations=[
                ObservationInput(
                    entity_id=entity_id,
                    asset_id=asset_id,
                    attribute_key="momentum",
                    value=0.77,
                    unit="score",
                    observed_at=observed_at,
                    available_at=observed_at,
                    source_id="local_ohlcv_csv",
                    connector_id="local_csv",
                    data_version="local_ohlcv_test_v1",
                    model_version="technical_test_v1",
                    confidence=0.93,
                    rights_policy={"raw_snapshot_allowed": False},
                )
            ]
        )
    )

    resolved = resolve_attribute_values(security, ["momentum"], registry)["momentum"]
    assert resolved.value == 0.77
    assert resolved.is_prototype is False
    assert resolved.observation_id == saved[0].observation_id
    assert resolved.PIT_status == "point_in_time"


def test_runtime_evidence_includes_observation_metadata_and_checksum_is_stable(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    registry = load_attribute_registry()
    first = run_methodology(graph, registry)
    ticker = first.rows[0].ticker
    entity_id, asset_id = resolve_static_asset_identity(ticker)
    observed_at = datetime.now(timezone.utc) - timedelta(days=1)
    saved = get_observation_store().ingest(
        ObservationIngestRequest(
            observations=[
                ObservationInput(
                    entity_id=entity_id,
                    asset_id=asset_id,
                    attribute_key="momentum",
                    value=0.64,
                    unit="score",
                    observed_at=observed_at,
                    available_at=observed_at,
                    source_id="local_ohlcv_csv",
                    connector_id="local_csv",
                    data_version="local_ohlcv_test_v2",
                    model_version="technical_test_v1",
                    confidence=0.94,
                    rights_policy={"raw_snapshot_allowed": False},
                )
            ]
        )
    )

    second = run_methodology(graph, registry)
    third = run_methodology(graph, registry)
    evidence = second.evidence[f"attr:{ticker}:momentum"]

    assert evidence["observation_id"] == saved[0].observation_id
    assert evidence["available_at"] == saved[0].available_at.isoformat()
    assert evidence["rights_policy"]["raw_snapshot_allowed"] is False
    assert "local_ohlcv_test_v2" in second.manifest["data_versions"]
    assert second.result_checksum == third.result_checksum


def test_observation_export_redacts_restricted_source_data() -> None:
    observation = observation_from_input(
        ObservationInput(
            entity_id="entity-us-equity-AAPL",
            asset_id="asset-us-equity-AAPL",
            attribute_key="latest_price",
            value=123.45,
            unit="price",
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            available_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            rights_policy={"raw_snapshot_allowed": False},
        )
    )

    payload = observation_for_export(observation)

    assert payload["value"] == "[redacted]"
    assert payload["redaction_reason"] == "source_rights_restricted"

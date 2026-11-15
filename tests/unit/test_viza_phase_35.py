"""Phase-35 tests: HTTP API endpoints for the new Phase 26-33 surface."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from viza.commands import CommandMapping, SizingExpression
from viza.decisions import emit_and_persist_decisions
from viza.observations import ObservationInput, observation_from_input
from viza.service import app
from viza.strategy_profiles import (
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    StrategyProfileCreateRequest,
    VizaStrategyProfile,
    get_strategy_profile_store,
)


client = TestClient(app)


# ---- Taxonomy + conflicts endpoints --------------------------------------


def test_get_commands_taxonomy_returns_registered_commands() -> None:
    response = client.get("/viza/commands/taxonomy")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "viza.command_taxonomy.v1"
    iris = {entry["iri"] for entry in payload["commands"]}
    expected = {
        "viza:cmd/buy_to_open",
        "viza:cmd/sell_to_close",
        "viza:cmd/watch_closely",
        "viza:cmd/block_action",
    }
    assert expected.issubset(iris)


def test_get_commands_conflicts_returns_attack_edges() -> None:
    response = client.get("/viza/commands/conflicts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "viza.command_conflicts.v1"
    assert any(
        edge["left_command_iri"] == "viza:cmd/block_action"
        and edge["right_command_iri"] == "*"
        for edge in payload["conflicts"]
    )


# ---- /viza/radar/assemble -----------------------------------------------


def test_radar_assemble_with_ranking_rows_only() -> None:
    request = {
        "decisions": [],
        "ranking_rows": [
            {"ticker": "AAPL", "entity_id": "eq_aapl", "score": 0.83, "rank": 1},
            {"ticker": "MSFT", "entity_id": "eq_msft", "score": 0.78, "rank": 2},
        ],
        "config": {"mode": "ranking_only", "sources": ["ranking_results"]},
    }
    response = client.post("/viza/radar/assemble", json=request)
    assert response.status_code == 200
    view = response.json()
    assert view["mode"] == "ranking_only"
    assert view["item_counts_by_kind"]["ranking_result"] == 2
    assert view["item_counts_by_kind"].get("decision_command") is None


def test_radar_assemble_rejects_unknown_radar_mode() -> None:
    response = client.post(
        "/viza/radar/assemble",
        json={"decisions": [], "ranking_rows": [], "config": {"mode": "stream"}},
    )
    assert response.status_code == 422


# ---- /viza/strategy-profiles/{id}/dmn-export ----------------------------


def test_dmn_export_returns_xml_for_seeded_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "project.db"))

    create_response = client.post(
        "/viza/strategy-profiles",
        json={
            "display_name": "Phase-35 DMN export test",
            "domain": "finance.securities",
            "module_id": "viza.finance.securities",
            "decision_rules": [
                {
                    "rule_id": "rsi_buy",
                    "label": "RSI oversold",
                    "trigger": {
                        "observation_predicates": [
                            {
                                "attribute_key": "rsi_14d",
                                "operator": "lte",
                                "threshold": 30.0,
                            }
                        ]
                    },
                    "action_template": "Open small position.",
                    "command_mapping": {
                        "command_iri": "viza:cmd/buy_to_open",
                        "sizing": {
                            "method": "TARGET_WEIGHT",
                            "expression": "0.02",
                            "units": "weight",
                        },
                    },
                }
            ],
        },
    )
    assert create_response.status_code == 200, create_response.json()
    strategy_id = create_response.json()["strategy_profile_id"]

    export_response = client.get(
        f"/viza/strategy-profiles/{strategy_id}/dmn-export"
    )
    assert export_response.status_code == 200
    body = export_response.json()
    assert body["strategy_profile_id"] == strategy_id
    assert body["schema"] == "DMN/20211108"
    xml = body["xml"]
    assert xml.startswith("<?xml")
    assert "decision" in xml
    assert "BUY_TO_OPEN" in xml or "buy_to_open" in xml


def test_dmn_export_404s_for_unknown_profile() -> None:
    response = client.get("/viza/strategy-profiles/no-such-profile/dmn-export")
    assert response.status_code == 404


# ---- /viza/provenance/walk ----------------------------------------------


def test_provenance_walk_returns_observation_root(tmp_path, monkeypatch) -> None:
    """Wire end-to-end: emit_and_persist_decisions writes PROV edges, and
    GET /viza/provenance/walk?root_iri=<decision> walks back to the
    triggering observation."""
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "project.db"))
    import viza.project_store as project_store_mod

    original = project_store_mod.project_store_path
    project_store_mod.project_store_path = lambda: tmp_path / "project.db"
    try:
        cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
        profile = VizaStrategyProfile(
            strategy_profile_id="phase-35-walk",
            display_name="Walk test",
            domain="finance.securities",
            module_id="viza.finance.securities",
            decision_rules=[
                DecisionRule(
                    rule_id="rsi_buy",
                    label="RSI oversold",
                    trigger=DecisionTrigger(
                        observation_predicates=[
                            ObservationPredicate(
                                attribute_key="rsi_14d",
                                operator="lte",
                                threshold=30.0,
                            )
                        ]
                    ),
                    action_template="open position.",
                    command_mapping=CommandMapping(
                        command_iri="viza:cmd/buy_to_open",
                        sizing=SizingExpression(
                            method="TARGET_WEIGHT", expression="0.02"
                        ),
                    ),
                )
            ],
            created_at=cutoff,
            updated_at=cutoff,
        )
        observation = observation_from_input(
            ObservationInput(
                entity_id="eq_aapl",
                attribute_key="rsi_14d",
                value=27.0,
                observed_at=cutoff,
                available_at=cutoff,
                retrieved_at=cutoff,
            )
        )
        decisions, _ = emit_and_persist_decisions(
            profile=profile,
            observations=[observation],
            cutoff_timestamp=cutoff,
            run_id="run-phase-35",
            graph_hash="g",
            profile_version="v",
        )
        assert len(decisions) == 1
        decision = decisions[0]
        assert decision.provenance is not None

        response = client.get(
            "/viza/provenance/walk",
            params={"root_iri": decision.provenance.decision_entity_iri},
        )
        assert response.status_code == 200
        walk = response.json()
        assert walk["root_iri"] == decision.provenance.decision_entity_iri
        assert any(
            iri.startswith("viza:entity/observation/")
            for iri in walk["reachable_iris"]
        )
        assert "viza:activity/run/run-phase-35" in walk["reachable_iris"]
    finally:
        project_store_mod.project_store_path = original

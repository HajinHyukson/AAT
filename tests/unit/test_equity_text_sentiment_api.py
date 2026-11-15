"""Stage C smoke tests for the FastAPI router endpoints.

Exercises the endpoints via FastAPI's TestClient with the local engine token,
matching the existing equity wedge API tests' style.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from viza.equity.text.hashing import hash_section_text
from viza.equity.text.section_parser import (
    PARSER_VERSION,
    SEC_PUBLIC_TEXT_RIGHTS_POLICY,
)


ACCEPTED_AT = datetime(2024, 11, 2, 23, 8, 27, tzinfo=timezone.utc)
RETRIEVED_AT = datetime(2026, 5, 14, 14, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate the per-test SQLite store via VIZA_PROJECT_STORE_PATH.
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "project_store.sqlite"))
    monkeypatch.setenv("VIZA_ENGINE_TOKEN", "test-token")
    monkeypatch.setenv("VIZA_EQUITY_SEC_TEXT_ANALYSIS_ENABLED", "true")
    monkeypatch.setenv("VIZA_EQUITY_TEXT_SENTIMENT_RESOLVER_ENABLED", "true")
    monkeypatch.setenv("VIZA_EQUITY_FINBERT_ENABLED", "true")
    # Import after env is set so the FastAPI app picks up the token policy.
    from viza.service import app

    return TestClient(app)


def _section(text: str = "Competition is intense. Margins may compress.") -> dict:
    return {
        "filing_accession": "acc-api-1",
        "cik": "0000320193",
        "form_type": "10-K",
        "section_id": "risk_factors",
        "section_label": "Risk Factors",
        "section_text": text,
        "section_text_hash": hash_section_text(text),
        "parser_version": PARSER_VERSION,
        "filing_accepted_at": ACCEPTED_AT.isoformat(),
        "available_at": ACCEPTED_AT.isoformat(),
        "retrieved_at": RETRIEVED_AT.isoformat(),
        "lookahead_risk": "low",
        "rights_policy": SEC_PUBLIC_TEXT_RIGHTS_POLICY,
        "pit_policy": {"observed_at_basis": "filing_acceptance"},
        "warnings": [],
    }


def test_status_endpoint_reports_resolver_identity(client) -> None:
    response = client.get(
        "/viza/equity/text/sentiment/status",
        headers={"X-Viza-Engine-Token": "test-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["resolver_id"] == "viza.finance.text.sentiment"
    assert payload["resolver_namespace"] == "viza.finance.text"
    assert "local_finbert_mock" in payload["implementations"]


def test_resolve_endpoint_returns_redacted_preview(client) -> None:
    response = client.post(
        "/viza/equity/text/sentiment/resolve",
        headers={"X-Viza-Engine-Token": "test-token"},
        json={
            "target": {"cik": "0000320193", "ticker_alias": "AAPL"},
            "filing": {"accession": "acc-api-1"},
            "sections": ["risk_factors"],
            "package_mode": "output_only",
            "analysis_mode": "live_current",
            "mock_parsed_sections": [_section()],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["resolver_id"] == "viza.finance.text.sentiment"
    assert body["redacted_preview"]["package_mode"] == "output_only"
    assert "filing_reading_card" in body["redacted_preview"]
    # No raw chunk text leaks into output_only.
    redactions = body["redacted_preview"]["redactions"]
    assert any(r["field"] == "chunk_text" for r in redactions)


def test_marketplace_draft_strips_per_chunk_probabilities(client) -> None:
    response = client.post(
        "/viza/equity/text/sentiment/resolve",
        headers={"X-Viza-Engine-Token": "test-token"},
        json={
            "target": {"cik": "0000320193"},
            "filing": {"accession": "acc-api-1"},
            "sections": ["risk_factors"],
            "package_mode": "marketplace_draft",
            "analysis_mode": "live_current",
            "mock_parsed_sections": [_section()],
        },
    )
    assert response.status_code == 200, response.text
    redacted = response.json()["redacted_preview"]
    for summary in redacted["chunk_summaries"]:
        assert "positive_prob" not in summary
        assert "negative_prob" not in summary


def test_replay_endpoint_returns_stored_observations(client) -> None:
    initial = client.post(
        "/viza/equity/text/sentiment/resolve",
        headers={"X-Viza-Engine-Token": "test-token"},
        json={
            "target": {"cik": "0000320193"},
            "filing": {"accession": "acc-api-1"},
            "sections": ["risk_factors"],
            "mock_parsed_sections": [_section()],
        },
    )
    assert initial.status_code == 200, initial.text
    run_id = initial.json()["audit"]["run_id"]

    replay = client.post(
        f"/viza/equity/text/sentiment/runs/{run_id}/replay",
        headers={"X-Viza-Engine-Token": "test-token"},
    )
    assert replay.status_code == 200, replay.text
    body = replay.json()
    assert body["source"] == "stored_replay"


def test_resolve_endpoint_disabled_when_flags_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "p.sqlite"))
    monkeypatch.setenv("VIZA_ENGINE_TOKEN", "test-token")
    monkeypatch.delenv("VIZA_EQUITY_TEXT_SENTIMENT_RESOLVER_ENABLED", raising=False)
    monkeypatch.delenv("VIZA_EQUITY_SEC_TEXT_ANALYSIS_ENABLED", raising=False)
    monkeypatch.delenv("VIZA_EQUITY_FINBERT_ENABLED", raising=False)
    from viza.service import app

    disabled_client = TestClient(app)
    response = disabled_client.post(
        "/viza/equity/text/sentiment/resolve",
        headers={"X-Viza-Engine-Token": "test-token"},
        json={
            "target": {"cik": "0000320193"},
            "filing": {"accession": "acc-api-1"},
            "sections": ["risk_factors"],
            "mock_parsed_sections": [_section()],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"

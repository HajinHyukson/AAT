from __future__ import annotations

import json
from pathlib import Path


def test_entity_resolver_fixture_covers_required_historical_cases() -> None:
    payload = json.loads(Path("config/entity_resolver_cases.json").read_text(encoding="utf-8"))
    cases = payload["cases"]

    assert len([item for item in cases if item["kind"] == "m_and_a"]) >= 5
    assert any(item["before"] == "FB" and item["after"] == "META" for item in cases)
    assert any(item["before"] == "GOOG" and item["after"] == "GOOGL" for item in cases)

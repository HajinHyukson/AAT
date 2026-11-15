"""Tests for the SKOS-shaped concept registry introduced in Phase 26.

The migration goal is to lift hardcoded family alias dictionaries to data
without breaking existing call sites that pass bare strings. These tests pin
both behaviors: IRI lookup works, and legacy strings still resolve.
"""

from __future__ import annotations

import json

import pytest

from viza.concepts import (
    ConceptScheme,
    get_concept_scheme,
    load_concept_scheme,
    reset_concept_scheme_cache,
)
from viza.relationships import _expand_family_aliases


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_concept_scheme_cache()
    yield
    reset_concept_scheme_cache()


def test_default_concept_scheme_loads_and_validates() -> None:
    scheme = load_concept_scheme()
    assert isinstance(scheme, ConceptScheme)
    assert scheme.schema_name == "viza.concepts.v1"
    assert scheme.concept_scheme.startswith("http://")
    assert len(scheme.concepts) > 0


def test_resolve_accepts_iri_unchanged() -> None:
    scheme = get_concept_scheme()
    iri = "viza:family/relationship/insight"
    assert scheme.resolve(iri) == iri


def test_resolve_accepts_legacy_family_string() -> None:
    scheme = get_concept_scheme()
    assert (
        scheme.resolve("insight", domain="relationship")
        == "viza:family/relationship/insight"
    )
    assert scheme.resolve("event", domain="relationship") == "viza:family/relationship/event"


def test_resolve_or_none_returns_none_for_unknown() -> None:
    scheme = get_concept_scheme()
    assert scheme.resolve_or_none("not_a_real_family", domain="relationship") is None


def test_narrower_closure_walks_subtypes() -> None:
    scheme = get_concept_scheme()
    descendants = scheme.narrower_closure("viza:family/relationship/insight")
    assert "viza:family/relationship/insight_confirms_insight" in descendants
    assert "viza:family/relationship/insight_invalidates_insight" in descendants
    assert "viza:family/relationship/insight_to_event" in descendants


def test_broader_closure_walks_ancestors() -> None:
    scheme = get_concept_scheme()
    ancestors = scheme.broader_closure(
        "viza:family/relationship/insight_confirms_insight"
    )
    assert "viza:family/relationship/insight" in ancestors


def test_family_expansion_includes_alt_labels_and_descendants() -> None:
    scheme = get_concept_scheme()
    expanded = scheme.family_expansion("insight", domain="relationship")
    assert "insight" in expanded
    assert "insight_to_event" in expanded
    assert "insight_confirms_insight" in expanded
    assert "insight_invalidates_insight" in expanded


def test_expand_family_aliases_preserves_legacy_behavior() -> None:
    expanded = _expand_family_aliases(["insight"])
    assert "insight" in expanded
    assert "insight_to_event" in expanded
    assert "insight_invalidates_insight" in expanded


def test_expand_family_aliases_for_event_family() -> None:
    expanded = _expand_family_aliases(["event"])
    assert "event" in expanded
    assert "entity_to_event" in expanded
    assert "asset_to_event" in expanded


def test_expand_family_aliases_no_concepts_file_returns_identity(tmp_path, monkeypatch) -> None:
    """If the concept scheme cannot be loaded, the helper returns the input set
    rather than raising. Ensures the migration is back-compat-safe."""

    # Point the resolver at a directory that has no concepts file.
    monkeypatch.setenv("VIZA_CONFIG_DIR", str(tmp_path))
    reset_concept_scheme_cache()

    expanded = _expand_family_aliases(["event"])
    assert expanded == {"event"}


def test_command_taxonomy_loads_and_has_8_plus_2_commands() -> None:
    """Phase 27 prerequisite: the command registry config is shipped and
    parseable. Schema validation happens in test_viza_commands.py; this test
    just verifies the file is present and well-formed JSON."""
    from viza.config_paths import resolve_config_path

    payload = json.loads(resolve_config_path("viza_command_taxonomy.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "viza.command_taxonomy.v1"
    commands = payload["commands"]
    pref_labels = {entry["skos_pref_label"] for entry in commands}
    expected = {
        "BUY_TO_OPEN",
        "ADD_LONG",
        "HOLD",
        "TRIM_LONG",
        "SELL_TO_CLOSE",
        "WATCH_CLOSELY",
        "AVOID",
        "BLOCK_ACTION",
        "BLOCK_EXPORT",
    }
    missing = expected - pref_labels
    assert not missing, f"command registry missing MVP commands: {sorted(missing)}"


def test_command_conflicts_loads_with_block_action_default() -> None:
    from viza.config_paths import resolve_config_path

    payload = json.loads(resolve_config_path("viza_command_conflicts.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "viza.command_conflicts.v1"
    has_block_wildcard = any(
        edge["left_command_iri"] == "viza:cmd/block_action" and edge["right_command_iri"] == "*"
        for edge in payload["conflicts"]
    )
    assert has_block_wildcard, "BLOCK_ACTION must defeat all other commands by default"


def test_command_language_gate_lists_decision_command_card() -> None:
    """The desktop language-gate test reads this file; the MVP cards must be on
    the whitelist or the gate will reject the radar render."""
    from viza.config_paths import resolve_config_path

    payload = json.loads(
        resolve_config_path("viza_command_language_gate.json").read_text(encoding="utf-8")
    )
    whitelist = set(payload["whitelisted_component_display_names"])
    assert "DecisionCommandCard" in whitelist
    assert "BlockedCommandCard" in whitelist
    assert "WatchCommandCard" in whitelist

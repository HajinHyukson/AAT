from __future__ import annotations

from viza.compat import (
    feature_enabled,
    is_legacy_graph_schema,
    is_supported_graph_schema,
    normalize_schema_name,
)
from viza.graph_schema import VIZA_GRAPH_SCHEMA_VERSION


def test_viza_graph_v0_is_supported_and_legacy() -> None:
    assert is_legacy_graph_schema(VIZA_GRAPH_SCHEMA_VERSION)
    assert is_supported_graph_schema(VIZA_GRAPH_SCHEMA_VERSION)


def test_schema_names_are_normalized_for_legacy_imports() -> None:
    assert normalize_schema_name(" VIZA.Graph.V0 ") == VIZA_GRAPH_SCHEMA_VERSION
    assert normalize_schema_name("viza-methodology-graph-v0") == VIZA_GRAPH_SCHEMA_VERSION


def test_unknown_graph_schema_is_not_supported() -> None:
    assert not is_legacy_graph_schema("viza_graph_v99")
    assert not is_supported_graph_schema("viza_graph_v99")


def test_feature_flags_default_safely(monkeypatch) -> None:
    for key in [
        "VIZA_ENABLE_UNIVERSAL_CONTAINER",
        "VIZA_ENABLE_MODULE_REGISTRY",
        "VIZA_ENABLE_EXPERIMENTAL_GRAPH_V1",
        "VIZA_ENABLE_NON_FINANCE_MODULES",
        "VIZA_ENABLE_UNKNOWN_TEST_FLAG",
    ]:
        monkeypatch.delenv(key, raising=False)

    assert feature_enabled("VIZA_ENABLE_UNIVERSAL_CONTAINER")
    assert feature_enabled("module_registry")
    assert not feature_enabled("experimental_graph_v1")
    assert not feature_enabled("non_finance_modules")
    assert not feature_enabled("unknown_test_flag")
    assert feature_enabled("unknown_test_flag", default=True)


def test_feature_flags_read_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("VIZA_ENABLE_EXPERIMENTAL_GRAPH_V1", "yes")
    monkeypatch.setenv("VIZA_ENABLE_UNIVERSAL_CONTAINER", "off")
    monkeypatch.setenv("VIZA_ENABLE_NON_FINANCE_MODULES", "not-a-bool")

    assert feature_enabled("experimental_graph_v1")
    assert not feature_enabled("universal_container")
    assert not feature_enabled("non_finance_modules")
    assert feature_enabled("non_finance_modules", default=True) is False

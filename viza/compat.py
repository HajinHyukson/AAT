from __future__ import annotations

import os

from viza.graph_schema import VIZA_GRAPH_SCHEMA_VERSION


LEGACY_GRAPH_SCHEMAS = frozenset({VIZA_GRAPH_SCHEMA_VERSION})
SUPPORTED_GRAPH_SCHEMAS = frozenset({VIZA_GRAPH_SCHEMA_VERSION})

FEATURE_FLAG_DEFAULTS: dict[str, bool] = {
    "VIZA_ENABLE_UNIVERSAL_CONTAINER": True,
    "VIZA_ENABLE_MODULE_REGISTRY": True,
    "VIZA_ENABLE_EXPERIMENTAL_GRAPH_V1": False,
    "VIZA_ENABLE_NON_FINANCE_MODULES": False,
}

_SCHEMA_ALIASES = {
    "viza_graph_v0": VIZA_GRAPH_SCHEMA_VERSION,
    "viza_graph_0": VIZA_GRAPH_SCHEMA_VERSION,
    "viza_methodology_graph_v0": VIZA_GRAPH_SCHEMA_VERSION,
}
_TRUTHY = {"1", "true", "t", "yes", "y", "on", "enabled"}
_FALSY = {"0", "false", "f", "no", "n", "off", "disabled"}


def is_legacy_graph_schema(schema: str) -> bool:
    return normalize_schema_name(schema) in LEGACY_GRAPH_SCHEMAS


def is_supported_graph_schema(schema: str) -> bool:
    return normalize_schema_name(schema) in SUPPORTED_GRAPH_SCHEMAS


def normalize_schema_name(schema: str) -> str:
    normalized = str(schema or "").strip().lower()
    normalized = normalized.replace("-", "_").replace(".", "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return _SCHEMA_ALIASES.get(normalized, normalized)


def feature_enabled(name: str, default: bool = False) -> bool:
    flag_name = _normalize_feature_flag_name(name)
    if not flag_name:
        return default
    fallback = FEATURE_FLAG_DEFAULTS.get(flag_name, default)
    value = os.getenv(flag_name)
    if value is None:
        return fallback

    normalized_value = value.strip().lower()
    if normalized_value in _TRUTHY:
        return True
    if normalized_value in _FALSY:
        return False
    return fallback


def _normalize_feature_flag_name(name: str) -> str:
    normalized = str(name or "").strip().upper()
    normalized = "".join(character if character.isalnum() else "_" for character in normalized)
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    normalized = normalized.strip("_")
    if not normalized:
        return ""
    if normalized.startswith("VIZA_ENABLE_"):
        return normalized
    return f"VIZA_ENABLE_{normalized}"

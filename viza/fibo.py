"""FIBO mapping helpers.

Phase 30 of `docs/viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`.
The Phase 27 InvestmentCommandPayload carries nullable FIBO IRIs on its
CommandTarget. Phase 30 populates them: this module loads
`config/viza_fibo_mappings.json` and provides

* `fibo_instrument_class_for_asset_class(asset_class)` → IRI or None
* `fibo_iri_for_identifier_scheme(scheme)` → IRI or None
* `fibo_iri_for_event_type(event_type)` → IRI or None
* `asset_to_fibo_identity(asset)` → FiboIdentity (the bundle the asset
  resolver returns to `compile_decisions`)

The identity bundle is the contract `compile_decisions` consumes via its
`fibo_identity_resolver` callable. Callers either build their own resolver
from a custom security master or use the default
`default_fibo_identity_resolver()` that walks the local `AssetStore`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from viza.commands import CanonicalIdentifier
from viza.config_paths import resolve_config_path


FIBO_MAPPINGS_FILE_NAME = "viza_fibo_mappings.json"


class FiboMappings(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.fibo_mappings.v1", alias="schema")
    registry_version: str = "0.1.0"
    description: str | None = None
    asset_class_to_fibo_instrument_class: dict[str, str | None] = Field(default_factory=dict)
    identifier_scheme_to_fibo_iri: dict[str, str] = Field(default_factory=dict)
    event_type_to_fibo_iri: dict[str, str | None] = Field(default_factory=dict)
    fallback_legal_entity_class_iri: str | None = None


class FiboIdentity(BaseModel):
    """Resolved FIBO identity for an asset / instrument.

    The asset resolver returns one of these per asset_id; `compile_decisions`
    stamps the `legal_entity_iri` and `instrument_iri` onto the
    CommandTarget so commands ship with portable identifiers.
    """

    model_config = ConfigDict(extra="forbid")

    legal_entity_iri: str | None = None
    instrument_iri: str | None = None
    instrument_class_iri: str | None = None
    legal_entity_class_iri: str | None = None
    identifier_set: list[CanonicalIdentifier] = Field(default_factory=list)


def load_fibo_mappings(path: str | Path | None = None) -> FiboMappings:
    target = (
        Path(path)
        if path is not None
        else resolve_config_path(FIBO_MAPPINGS_FILE_NAME)
    )
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return FiboMappings.model_validate(payload)


@lru_cache(maxsize=1)
def get_fibo_mappings() -> FiboMappings:
    return load_fibo_mappings()


def reset_fibo_mappings_cache() -> None:
    get_fibo_mappings.cache_clear()


def fibo_instrument_class_for_asset_class(asset_class: str) -> str | None:
    mappings = get_fibo_mappings()
    return mappings.asset_class_to_fibo_instrument_class.get(asset_class)


def fibo_iri_for_identifier_scheme(scheme: str) -> str | None:
    mappings = get_fibo_mappings()
    return mappings.identifier_scheme_to_fibo_iri.get(scheme)


def fibo_iri_for_event_type(event_type: str) -> str | None:
    mappings = get_fibo_mappings()
    return mappings.event_type_to_fibo_iri.get(event_type)


def asset_to_fibo_identity(asset: Any) -> FiboIdentity:
    """Project a `VizaAsset` (or compatible mapping) into a FiboIdentity.

    Accepts duck-typed input — both a Pydantic `VizaAsset` instance and a
    dict-shaped equivalent — so this helper can be used in code paths where
    importing `viza.assets` would create an unwanted cycle.
    """
    mappings = get_fibo_mappings()

    def _attr(field: str, default: Any = None) -> Any:
        if isinstance(asset, dict):
            return asset.get(field, default)
        return getattr(asset, field, default)

    asset_class = _attr("asset_class")
    instrument_class_iri = mappings.asset_class_to_fibo_instrument_class.get(asset_class)
    legal_entity_iri = _attr("entity_id")
    instrument_iri = _attr("asset_id")

    identifier_set: list[CanonicalIdentifier] = []
    raw_identifiers = _attr("identifiers", {}) or {}
    if isinstance(raw_identifiers, dict):
        for scheme, value in raw_identifiers.items():
            if not isinstance(scheme, str) or not isinstance(value, (str, int)):
                continue
            scheme_iri = mappings.identifier_scheme_to_fibo_iri.get(scheme)
            identifier_set.append(
                CanonicalIdentifier(
                    scheme_iri=scheme_iri or f"viza:scheme/{scheme}",
                    value=str(value),
                )
            )

    return FiboIdentity(
        legal_entity_iri=(
            legal_entity_iri if isinstance(legal_entity_iri, str) else None
        ),
        instrument_iri=instrument_iri if isinstance(instrument_iri, str) else None,
        instrument_class_iri=instrument_class_iri,
        legal_entity_class_iri=mappings.fallback_legal_entity_class_iri,
        identifier_set=identifier_set,
    )


def default_fibo_identity_resolver() -> Callable[[str], FiboIdentity | None]:
    """Return a callable that maps `asset_id` to FiboIdentity by consulting
    the local AssetStore. The callable returns None when the asset is not
    in the store — the caller (compile_decisions) leaves the target's FIBO
    fields as None in that case, preserving back-compat."""
    from viza.assets import get_asset_store  # local import: cycle-safe

    def resolver(asset_id: str) -> FiboIdentity | None:
        if not asset_id:
            return None
        asset = get_asset_store().get_asset(asset_id)
        if asset is None:
            return None
        return asset_to_fibo_identity(asset)

    return resolver

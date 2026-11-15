from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.entities import EntityResolveRequest, entity_id_for_ticker, get_entity_store
from viza.project_store import project_store_path
from viza.universes import UniverseDefinition, load_universe_definition


class VizaAsset(BaseModel):
    """Canonical asset record for VIZA's local security master.

    Phase 30 adds nullable FIBO IRI fields so commands emitted from this
    asset can carry portable identifiers without forcing a rewrite of the
    pre-Phase-30 seed code. The fields default to `None`; callers that
    invoke ``apply_fibo_mappings(asset)`` (or seed new rows through the
    Phase-30-aware path) get them populated automatically.

    The two IRI fields keep the FIBO instrument/issuer split FIBO requires:
    ``fibo_instrument_iri`` identifies the security as an instrument
    (CommonStock, etc.); ``fibo_legal_entity_iri`` identifies the issuer.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.asset.v1", alias="schema")
    entity_id: str
    asset_id: str
    asset_class: str
    primary_symbol: str
    current_name: str
    exchange: str | None = None
    country: str = "US"
    currency: str = "USD"
    identifiers: dict[str, str] = Field(default_factory=dict)
    sector: str | None = None
    industry: str | None = None
    listing_status: str = "active"
    provider_identifier_map: dict[str, str] = Field(default_factory=dict)
    source_lineage: list[dict[str, Any]] = Field(default_factory=list)
    fibo_legal_entity_iri: str | None = None
    fibo_instrument_iri: str | None = None
    fibo_instrument_class_iri: str | None = None
    fibo_legal_entity_class_iri: str | None = None
    created_at: datetime
    updated_at: datetime


class AssetResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)


class AssetResolveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: dict[str, str]
    asset: VizaAsset | None = None
    warnings: list[str] = Field(default_factory=list)


class AssetReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_identifier_map: dict[str, str] = Field(default_factory=dict)


class AssetStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def seed_local_universe(
        self,
        universe: UniverseDefinition | None = None,
    ) -> list[VizaAsset]:
        definition = universe or load_universe_definition("pilot_sp500_static")
        entity_store = get_entity_store(self.path)
        entity_store.seed_local_universe(definition)
        timestamp = _utc_now()
        saved: list[VizaAsset] = []
        seen_tickers: set[str] = set()
        with self._connect() as connection:
            for security in definition.securities:
                ticker = security.ticker.upper()
                if ticker in seen_tickers:
                    continue
                seen_tickers.add(ticker)
                asset = VizaAsset(
                    entity_id=entity_id_for_ticker(ticker),
                    asset_id=asset_id_for_ticker(ticker),
                    asset_class="US_EQ",
                    primary_symbol=ticker,
                    current_name=security.name,
                    exchange=security.exchange or None,
                    identifiers={"ticker": ticker},
                    sector=security.sector or None,
                    industry=security.industry or None,
                    provider_identifier_map={"local_universe": ticker},
                    source_lineage=[
                        {
                            "source": definition.source,
                            "source_record_id": ticker,
                            "universe": definition.universe_name,
                            "version": definition.version,
                        }
                    ],
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                self.upsert_asset(asset, connection=connection)
                saved.append(asset)
        return saved

    def upsert_asset(
        self,
        asset: VizaAsset,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> VizaAsset:
        owns_connection = connection is None
        active_connection = connection or self._connect()
        try:
            active_connection.execute(
                """
                INSERT INTO finance_assets(
                    asset_id,
                    entity_id,
                    asset_class,
                    primary_symbol,
                    current_name,
                    exchange,
                    country,
                    currency,
                    identifiers_json,
                    sector,
                    industry,
                    listing_status,
                    provider_identifier_map_json,
                    source_lineage_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    entity_id = excluded.entity_id,
                    asset_class = excluded.asset_class,
                    primary_symbol = excluded.primary_symbol,
                    current_name = excluded.current_name,
                    exchange = excluded.exchange,
                    country = excluded.country,
                    currency = excluded.currency,
                    identifiers_json = excluded.identifiers_json,
                    sector = excluded.sector,
                    industry = excluded.industry,
                    listing_status = excluded.listing_status,
                    provider_identifier_map_json = excluded.provider_identifier_map_json,
                    source_lineage_json = excluded.source_lineage_json,
                    updated_at = excluded.updated_at
                """,
                (
                    asset.asset_id,
                    asset.entity_id,
                    asset.asset_class,
                    asset.primary_symbol,
                    asset.current_name,
                    asset.exchange,
                    asset.country,
                    asset.currency,
                    json.dumps(asset.identifiers, sort_keys=True),
                    asset.sector,
                    asset.industry,
                    asset.listing_status,
                    json.dumps(asset.provider_identifier_map, sort_keys=True),
                    json.dumps(asset.source_lineage, sort_keys=True),
                    asset.created_at.isoformat(),
                    asset.updated_at.isoformat(),
                ),
            )
            if owns_connection:
                active_connection.commit()
        finally:
            if owns_connection:
                active_connection.close()
        return asset

    def search_assets(self, query: str = "", limit: int = 25) -> list[VizaAsset]:
        pattern = f"%{query.strip().upper()}%"
        with self._connect() as connection:
            if query.strip():
                rows = connection.execute(
                    """
                    SELECT *
                    FROM finance_assets
                    WHERE primary_symbol LIKE ?
                       OR current_name LIKE ?
                       OR identifiers_json LIKE ?
                    ORDER BY primary_symbol
                    LIMIT ?
                    """,
                    (pattern, pattern, pattern, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM finance_assets ORDER BY primary_symbol LIMIT ?",
                    (limit,),
                ).fetchall()
        return [_asset_from_row(row) for row in rows]

    def resolve_asset(self, request: AssetResolveRequest) -> AssetResolveResult:
        ticker = (request.ticker or request.identifiers.get("ticker") or "").upper()
        query = {"ticker": ticker} if ticker else dict(request.identifiers)
        warnings: list[str] = []
        asset = self.get_asset(asset_id_for_ticker(ticker)) if ticker else None
        if asset is None:
            warnings.append("asset_not_found")
        elif not {"figi", "cusip", "isin"}.intersection(asset.identifiers):
            warnings.append("missing_provider_identifiers")
        return AssetResolveResult(query=query, asset=asset, warnings=warnings)

    def get_asset(self, asset_id: str) -> VizaAsset | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM finance_assets WHERE asset_id = ?",
                (asset_id,),
            ).fetchone()
        return _asset_from_row(row) if row is not None else None

    def require_asset(self, asset_id: str) -> VizaAsset:
        asset = self.get_asset(asset_id)
        if asset is None:
            raise KeyError(f"unknown VIZA asset: {asset_id}")
        return asset

    def identifiers_for_asset(self, asset_id: str) -> dict[str, str]:
        asset = self.require_asset(asset_id)
        return {
            **asset.identifiers,
            **{f"provider:{key}": value for key, value in asset.provider_identifier_map.items()},
        }

    def reconcile_provider_identifiers(
        self,
        request: AssetReconcileRequest,
    ) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}
        for provider, identifier in request.provider_identifier_map.items():
            values.setdefault(identifier, []).append(provider)
        conflicts = {
            identifier: providers
            for identifier, providers in values.items()
            if len(providers) > 1
        }
        return {"conflicts": sorted(conflicts)}

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(ASSET_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


ASSET_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS finance_assets (
  asset_id TEXT PRIMARY KEY,
  entity_id TEXT NOT NULL,
  asset_class TEXT NOT NULL,
  primary_symbol TEXT NOT NULL,
  current_name TEXT NOT NULL,
  exchange TEXT,
  country TEXT,
  currency TEXT,
  identifiers_json TEXT NOT NULL DEFAULT '{}',
  sector TEXT,
  industry TEXT,
  listing_status TEXT,
  provider_identifier_map_json TEXT NOT NULL DEFAULT '{}',
  source_lineage_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
);

CREATE INDEX IF NOT EXISTS idx_finance_assets_symbol
  ON finance_assets(primary_symbol);
"""


def get_asset_store(path: str | Path | None = None) -> AssetStore:
    return AssetStore(path)


def asset_id_for_ticker(ticker: str) -> str:
    return f"asset-us-equity-{ticker.strip().upper()}"


def resolve_static_asset_identity(ticker: str) -> tuple[str, str]:
    normalized = ticker.strip().upper()
    return entity_id_for_ticker(normalized), asset_id_for_ticker(normalized)


def duplicate_ticker_warnings(tickers: list[str]) -> list[str]:
    normalized = [ticker.strip().upper() for ticker in tickers if isinstance(ticker, str)]
    duplicates = sorted({ticker for ticker in normalized if normalized.count(ticker) > 1})
    return [f"duplicate_ticker:{ticker}" for ticker in duplicates]


def _asset_from_row(row: sqlite3.Row) -> VizaAsset:
    asset = VizaAsset(
        asset_id=row["asset_id"],
        entity_id=row["entity_id"],
        asset_class=row["asset_class"],
        primary_symbol=row["primary_symbol"],
        current_name=row["current_name"],
        exchange=row["exchange"],
        country=row["country"] or "US",
        currency=row["currency"] or "USD",
        identifiers=json.loads(row["identifiers_json"]),
        sector=row["sector"],
        industry=row["industry"],
        listing_status=row["listing_status"] or "active",
        provider_identifier_map=json.loads(row["provider_identifier_map_json"]),
        source_lineage=json.loads(row["source_lineage_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
    return apply_fibo_mappings(asset)


def apply_fibo_mappings(asset: VizaAsset) -> VizaAsset:
    """Populate the four FIBO IRI fields on a VizaAsset from the canonical
    mappings in `config/viza_fibo_mappings.json`. Pure function; returns a
    new instance via `model_copy` instead of mutating in place. Safe to call
    on assets that are already populated — fields that already have a value
    are preserved.

    Used by ``_asset_from_row`` and by the Phase-30 seed paths so a freshly
    seeded asset and a reloaded one carry the same FIBO identity.
    """
    from viza.fibo import (  # local import: avoid load-order cycle warmth
        get_fibo_mappings,
    )

    mappings = get_fibo_mappings()
    instrument_class = (
        asset.fibo_instrument_class_iri
        or mappings.asset_class_to_fibo_instrument_class.get(asset.asset_class)
    )
    legal_entity_class = (
        asset.fibo_legal_entity_class_iri
        or mappings.fallback_legal_entity_class_iri
    )
    instrument_iri = asset.fibo_instrument_iri or asset.asset_id
    legal_entity_iri = asset.fibo_legal_entity_iri or asset.entity_id
    return asset.model_copy(
        update={
            "fibo_instrument_iri": instrument_iri,
            "fibo_legal_entity_iri": legal_entity_iri,
            "fibo_instrument_class_iri": instrument_class,
            "fibo_legal_entity_class_iri": legal_entity_class,
        }
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

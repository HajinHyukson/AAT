from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.project_store import project_store_path
from viza.universes import UniverseDefinition, load_universe_definition


class VizaEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.entity.v1", alias="schema")
    entity_id: str
    entity_type: str
    display_name: str
    domain: str
    module_id: str | None = None
    aliases: list[str] = Field(default_factory=list)
    identifiers: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_lineage: list[dict[str, Any]] = Field(default_factory=list)
    rights_policy: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class EntityResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)


class EntityResolveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: dict[str, str]
    entity: VizaEntity | None = None
    warnings: list[str] = Field(default_factory=list)


class EntityRelationshipRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    family: str | None = None
    confidence: float | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class EntityStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def seed_local_universe(
        self,
        universe: UniverseDefinition | None = None,
    ) -> list[VizaEntity]:
        definition = universe or load_universe_definition("pilot_sp500_static")
        saved: list[VizaEntity] = []
        seen_tickers: set[str] = set()
        timestamp = _utc_now()
        with self._connect() as connection:
            for security in definition.securities:
                ticker = security.ticker.upper()
                if ticker in seen_tickers:
                    continue
                seen_tickers.add(ticker)
                entity = VizaEntity(
                    entity_id=entity_id_for_ticker(ticker),
                    entity_type="company",
                    display_name=security.name,
                    domain="finance.securities",
                    module_id="viza.finance.securities",
                    aliases=[ticker],
                    identifiers={"ticker": ticker},
                    metadata={
                        "sector": security.sector,
                        "industry": security.industry,
                        "exchange": security.exchange,
                        "missing_identifiers": ["figi", "cusip", "isin"],
                    },
                    source_lineage=[
                        {
                            "source": definition.source,
                            "source_record_id": ticker,
                            "universe": definition.universe_name,
                            "version": definition.version,
                        }
                    ],
                    rights_policy={"redistribution_allowed": True, "source": "local_universe"},
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                self.upsert_entity(entity, connection=connection)
                saved.append(entity)
        return saved

    def upsert_entity(
        self,
        entity: VizaEntity,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> VizaEntity:
        owns_connection = connection is None
        active_connection = connection or self._connect()
        try:
            active_connection.execute(
                """
                INSERT INTO entities(
                    entity_id,
                    entity_type,
                    display_name,
                    domain,
                    module_id,
                    aliases_json,
                    identifiers_json,
                    metadata_json,
                    source_lineage_json,
                    rights_policy_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    display_name = excluded.display_name,
                    domain = excluded.domain,
                    module_id = excluded.module_id,
                    aliases_json = excluded.aliases_json,
                    identifiers_json = excluded.identifiers_json,
                    metadata_json = excluded.metadata_json,
                    source_lineage_json = excluded.source_lineage_json,
                    rights_policy_json = excluded.rights_policy_json,
                    updated_at = excluded.updated_at
                """,
                (
                    entity.entity_id,
                    entity.entity_type,
                    entity.display_name,
                    entity.domain,
                    entity.module_id,
                    json.dumps(entity.aliases, sort_keys=True),
                    json.dumps(entity.identifiers, sort_keys=True),
                    json.dumps(entity.metadata, sort_keys=True),
                    json.dumps(entity.source_lineage, sort_keys=True),
                    json.dumps(entity.rights_policy, sort_keys=True),
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )
            if owns_connection:
                active_connection.commit()
        finally:
            if owns_connection:
                active_connection.close()
        return entity

    def search_entities(self, query: str = "", limit: int = 25) -> list[VizaEntity]:
        pattern = f"%{query.strip()}%"
        with self._connect() as connection:
            if query.strip():
                rows = connection.execute(
                    """
                    SELECT *
                    FROM entities
                    WHERE display_name LIKE ?
                       OR aliases_json LIKE ?
                       OR identifiers_json LIKE ?
                    ORDER BY display_name
                    LIMIT ?
                    """,
                    (pattern, pattern, pattern, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM entities ORDER BY display_name LIMIT ?",
                    (limit,),
                ).fetchall()
        return [_entity_from_row(row) for row in rows]

    def resolve_entity(self, request: EntityResolveRequest) -> EntityResolveResult:
        ticker = (request.ticker or request.identifiers.get("ticker") or "").upper()
        query = {"ticker": ticker} if ticker else dict(request.identifiers)
        warnings: list[str] = []
        entity = self.get_entity(entity_id_for_ticker(ticker)) if ticker else None
        if entity is None:
            warnings.append("entity_not_found")
        if entity is not None and entity.metadata.get("missing_identifiers"):
            warnings.append("missing_provider_identifiers")
        return EntityResolveResult(query=query, entity=entity, warnings=warnings)

    def get_entity(self, entity_id: str) -> VizaEntity | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM entities WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()
        return _entity_from_row(row) if row is not None else None

    def require_entity(self, entity_id: str) -> VizaEntity:
        entity = self.get_entity(entity_id)
        if entity is None:
            raise KeyError(f"unknown VIZA entity: {entity_id}")
        return entity

    def relationships_for_entity(self, entity_id: str) -> list[EntityRelationshipRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM entity_relationships
                WHERE source_entity_id = ? OR target_entity_id = ?
                ORDER BY updated_at DESC
                """,
                (entity_id, entity_id),
            ).fetchall()
        return [_relationship_from_row(row) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(ENTITY_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


ENTITY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  module_id TEXT,
  aliases_json TEXT NOT NULL DEFAULT '[]',
  identifiers_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  source_lineage_json TEXT NOT NULL DEFAULT '[]',
  rights_policy_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_relationships (
  relationship_id TEXT PRIMARY KEY,
  source_entity_id TEXT NOT NULL,
  target_entity_id TEXT NOT NULL,
  relationship_type TEXT NOT NULL,
  family TEXT,
  confidence REAL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entities_identifiers
  ON entities(entity_type, display_name);
"""


def get_entity_store(path: str | Path | None = None) -> EntityStore:
    return EntityStore(path)


def entity_id_for_ticker(ticker: str) -> str:
    return f"entity-us-equity-{ticker.strip().upper()}"


def _entity_from_row(row: sqlite3.Row) -> VizaEntity:
    return VizaEntity(
        entity_id=row["entity_id"],
        entity_type=row["entity_type"],
        display_name=row["display_name"],
        domain=row["domain"],
        module_id=row["module_id"],
        aliases=json.loads(row["aliases_json"]),
        identifiers=json.loads(row["identifiers_json"]),
        metadata=json.loads(row["metadata_json"]),
        source_lineage=json.loads(row["source_lineage_json"]),
        rights_policy=json.loads(row["rights_policy_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _relationship_from_row(row: sqlite3.Row) -> EntityRelationshipRecord:
    return EntityRelationshipRecord(
        relationship_id=row["relationship_id"],
        source_entity_id=row["source_entity_id"],
        target_entity_id=row["target_entity_id"],
        relationship_type=row["relationship_type"],
        family=row["family"],
        confidence=row["confidence"],
        evidence_refs=json.loads(row["evidence_refs_json"]),
        metadata=json.loads(row["metadata_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

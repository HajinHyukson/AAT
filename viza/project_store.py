from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from viza.credentials import CredentialRef, CredentialStatus
from viza.graph_schema import MethodologyGraph
from viza.runtime import hash_methodology_graph


PROJECT_STORE_ENV_VAR = "VIZA_PROJECT_STORE_PATH"
DEFAULT_PROJECT_ID = "local-sandbox"


class ProjectSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str
    description: str | None = None
    created_at: str
    updated_at: str
    methodology_count: int = 0


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="Local Sandbox", min_length=1)
    description: str | None = None


class MethodologyVersionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str
    project_id: str
    methodology_id: str
    name: str
    label: str | None = None
    message: str | None = None
    schema_version: str
    graph_hash: str
    parent_version_id: str | None = None
    created_at: str
    updated_at: str
    graph_created_at: str
    graph_updated_at: str
    node_count: int
    edge_count: int


class MethodologyVersionRecord(MethodologyVersionSummary):
    graph: MethodologyGraph


class SaveMethodologyVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: MethodologyGraph
    label: str | None = None
    message: str | None = None
    parent_version_id: str | None = None


class MethodologyVersionDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_version_id: str
    right_version_id: str
    left_graph_hash: str
    right_graph_hash: str
    added_nodes: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    changed_nodes: list[str] = Field(default_factory=list)
    added_edges: list[str] = Field(default_factory=list)
    removed_edges: list[str] = Field(default_factory=list)
    changed_edges: list[str] = Field(default_factory=list)
    metadata_changed: bool = False


class RunRecordSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str | None = None
    methodology_id: str
    version_id: str | None = None
    graph_hash: str
    status: str
    result_checksum: str
    created_at: str


class RunRecord(RunRecordSummary):
    manifest: dict[str, Any]
    result: dict[str, Any] | None = None


class SaveRadarOutputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: dict[str, Any]
    name: str | None = None
    version_id: str | None = None
    selected_columns: list[str] = Field(default_factory=list)
    displayed_tickers: list[str] = Field(default_factory=list)
    designer: dict[str, Any] = Field(default_factory=dict)


class SavedRadarOutputSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radar_id: str
    project_id: str | None = None
    methodology_id: str
    version_id: str | None = None
    run_id: str | None = None
    timestamp_cutoff: str | None = None
    result_checksum: str
    name: str | None = None
    selected_columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    evidence_ref_count: int = 0
    created_at: str


class SavedRadarOutputRecord(SavedRadarOutputSummary):
    output: dict[str, Any]


class CreateWatchlistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    tickers: list[str] = Field(default_factory=list)
    source_radar_id: str | None = None
    source_run_id: str | None = None


class UpdateWatchlistTickersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    add_tickers: list[str] = Field(default_factory=list)
    remove_tickers: list[str] = Field(default_factory=list)


class WatchlistRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watchlist_id: str
    project_id: str | None = None
    name: str
    tickers: list[str] = Field(default_factory=list)
    source_radar_id: str | None = None
    source_run_id: str | None = None
    created_at: str
    updated_at: str


class AlertDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_type: str = Field(min_length=1)
    attribute_key: str | None = None
    operator: str = "greater_than"
    threshold: float | None = None
    top_n: int | None = None
    relationship_type: str | None = None
    watchlist_id: str | None = None
    severity: str = "info"


class CreateAlertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    definition: AlertDefinition
    enabled: bool = True


class AlertRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: str
    project_id: str | None = None
    name: str
    definition: AlertDefinition
    enabled: bool = True
    created_at: str
    updated_at: str


class VizaFileImportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    import_id: str
    file_id: str
    project_id: str | None = None
    source_path: str | None = None
    imported_at: str
    manifest: dict[str, Any]
    container_checksum: str | None = None
    manifest_checksum: str | None = None
    status: str
    warnings: list[str] = Field(default_factory=list)
    quarantine_status: str = "none"


class VizaFileExportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: str
    file_id: str
    project_id: str | None = None
    target_path: str | None = None
    exported_at: str
    manifest: dict[str, Any]
    container_checksum: str | None = None
    manifest_checksum: str | None = None
    purpose: str | None = None
    visibility: str | None = None
    warnings: list[str] = Field(default_factory=list)


class VizaFileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    imports: list[VizaFileImportRecord] = Field(default_factory=list)
    exports: list[VizaFileExportRecord] = Field(default_factory=list)


class CreatorRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    creator_id: str | None = None
    display_name: str | None = None
    verification_status: str = "unverified"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreatorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    creator_id: str
    display_name: str | None = None
    verification_status: str
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectorConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    credential_refs: list[CredentialRef] = Field(default_factory=list)
    credential_status: list[CredentialStatus] = Field(default_factory=list)


class ConnectorConfigurationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    project_id: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    credential_refs: list[CredentialRef] = Field(default_factory=list)
    credential_status: list[CredentialStatus] = Field(default_factory=list)
    updated_at: str


class ProjectStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def list_projects(self) -> list[ProjectSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.project_id,
                    p.name,
                    p.description,
                    p.created_at,
                    p.updated_at,
                    COUNT(DISTINCT mv.methodology_id) AS methodology_count
                FROM projects p
                LEFT JOIN methodology_versions mv ON mv.project_id = p.project_id
                GROUP BY p.project_id
                ORDER BY p.updated_at DESC
                """
            ).fetchall()
        return [ProjectSummary.model_validate(dict(row)) for row in rows]

    def create_project(self, request: ProjectCreateRequest) -> ProjectSummary:
        timestamp = _utc_now()
        project_id = f"project-{uuid4()}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO projects(project_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, request.name, request.description, timestamp, timestamp),
            )
        return self.require_project(project_id)

    def ensure_default_project(self) -> ProjectSummary:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT project_id FROM projects WHERE project_id = ?",
                (DEFAULT_PROJECT_ID,),
            ).fetchone()
            if row is None:
                timestamp = _utc_now()
                connection.execute(
                    """
                    INSERT INTO projects(project_id, name, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        DEFAULT_PROJECT_ID,
                        "Local Sandbox",
                        "Default local VIZA project store.",
                        timestamp,
                        timestamp,
                    ),
                )
        return self.require_project(DEFAULT_PROJECT_ID)

    def require_project(self, project_id: str) -> ProjectSummary:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    p.project_id,
                    p.name,
                    p.description,
                    p.created_at,
                    p.updated_at,
                    COUNT(DISTINCT mv.methodology_id) AS methodology_count
                FROM projects p
                LEFT JOIN methodology_versions mv ON mv.project_id = p.project_id
                WHERE p.project_id = ?
                GROUP BY p.project_id
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA project: {project_id}")
        return ProjectSummary.model_validate(dict(row))

    def save_connector_configuration(
        self,
        connector_id: str,
        request: ConnectorConfigurationRequest,
    ) -> ConnectorConfigurationRecord:
        timestamp = _utc_now()
        settings = _redact_secret_settings(request.settings)
        credential_refs_json = [
            credential_ref.model_dump(mode="json") for credential_ref in request.credential_refs
        ]
        credential_status_json = [
            status.model_dump(mode="json") for status in request.credential_status
        ]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO connector_settings(
                    connector_id,
                    project_id,
                    metadata_json,
                    settings_json,
                    credential_refs_json,
                    credential_status_json,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(connector_id) DO UPDATE SET
                    project_id = excluded.project_id,
                    metadata_json = excluded.metadata_json,
                    settings_json = excluded.settings_json,
                    credential_refs_json = excluded.credential_refs_json,
                    credential_status_json = excluded.credential_status_json,
                    updated_at = excluded.updated_at
                """,
                (
                    connector_id,
                    request.project_id,
                    json.dumps({"settings": settings}, sort_keys=True),
                    json.dumps(settings, sort_keys=True),
                    json.dumps(credential_refs_json, sort_keys=True),
                    json.dumps(credential_status_json, sort_keys=True),
                    timestamp,
                ),
            )
        return self.require_connector_configuration(connector_id)

    def get_connector_configuration(
        self,
        connector_id: str,
    ) -> ConnectorConfigurationRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM connector_settings WHERE connector_id = ?",
                (connector_id,),
            ).fetchone()
        return _connector_configuration_from_row(row) if row is not None else None

    def require_connector_configuration(
        self,
        connector_id: str,
    ) -> ConnectorConfigurationRecord:
        record = self.get_connector_configuration(connector_id)
        if record is None:
            raise KeyError(f"unknown VIZA connector configuration: {connector_id}")
        return record

    def list_connector_configurations(self) -> list[ConnectorConfigurationRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM connector_settings ORDER BY connector_id"
            ).fetchall()
        return [_connector_configuration_from_row(row) for row in rows]

    def save_methodology_version(
        self,
        project_id: str,
        request: SaveMethodologyVersionRequest,
    ) -> MethodologyVersionRecord:
        self.require_project(project_id)
        graph = request.graph
        graph_hash = hash_methodology_graph(graph)
        timestamp = _utc_now()
        parent_version_id = request.parent_version_id
        if parent_version_id is None:
            parent = self.latest_methodology_version(graph.methodology_id, project_id=project_id)
            parent_version_id = parent.version_id if parent is not None else None

        version_id = f"version-{uuid4()}"
        graph_payload = graph.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO methodology_versions(
                    version_id,
                    project_id,
                    methodology_id,
                    name,
                    label,
                    message,
                    schema_version,
                    graph_hash,
                    parent_version_id,
                    graph_json,
                    created_at,
                    updated_at,
                    graph_created_at,
                    graph_updated_at,
                    node_count,
                    edge_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    project_id,
                    graph.methodology_id,
                    graph.name,
                    request.label,
                    request.message,
                    graph.schema_version,
                    graph_hash,
                    parent_version_id,
                    json.dumps(graph_payload, sort_keys=True),
                    timestamp,
                    timestamp,
                    graph.created_at.isoformat(),
                    graph.updated_at.isoformat(),
                    len(graph.nodes),
                    len(graph.edges),
                ),
            )
            connection.execute(
                "UPDATE projects SET updated_at = ? WHERE project_id = ?",
                (timestamp, project_id),
            )
        return self.require_methodology_version(graph.methodology_id, version_id)

    def list_project_versions(self, project_id: str) -> list[MethodologyVersionSummary]:
        self.require_project(project_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM methodology_versions
                WHERE project_id = ?
                ORDER BY created_at DESC
                """,
                (project_id,),
            ).fetchall()
        return [_version_summary_from_row(row) for row in rows]

    def list_methodology_versions(
        self,
        methodology_id: str,
        project_id: str | None = None,
    ) -> list[MethodologyVersionSummary]:
        params: tuple[str, ...]
        project_filter = ""
        if project_id:
            project_filter = "AND project_id = ?"
            params = (methodology_id, project_id)
        else:
            params = (methodology_id,)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM methodology_versions
                WHERE methodology_id = ?
                {project_filter}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
        return [_version_summary_from_row(row) for row in rows]

    def latest_methodology_version(
        self,
        methodology_id: str,
        project_id: str | None = None,
    ) -> MethodologyVersionSummary | None:
        versions = self.list_methodology_versions(methodology_id, project_id=project_id)
        return versions[0] if versions else None

    def require_methodology_version(
        self,
        methodology_id: str,
        version_id: str,
    ) -> MethodologyVersionRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM methodology_versions
                WHERE methodology_id = ? AND version_id = ?
                """,
                (methodology_id, version_id),
            ).fetchone()
        if row is None:
            raise KeyError(
                f"unknown VIZA methodology version: {methodology_id}/{version_id}"
            )
        return _version_record_from_row(row)

    def compare_versions(
        self,
        methodology_id: str,
        left_version_id: str,
        right_version_id: str,
    ) -> MethodologyVersionDiff:
        left = self.require_methodology_version(methodology_id, left_version_id)
        right = self.require_methodology_version(methodology_id, right_version_id)
        left_graph = left.graph.model_dump(mode="json")
        right_graph = right.graph.model_dump(mode="json")

        left_nodes = {node["id"]: node for node in left_graph["nodes"]}
        right_nodes = {node["id"]: node for node in right_graph["nodes"]}
        left_edges = {edge["id"]: edge for edge in left_graph["edges"]}
        right_edges = {edge["id"]: edge for edge in right_graph["edges"]}

        return MethodologyVersionDiff(
            left_version_id=left_version_id,
            right_version_id=right_version_id,
            left_graph_hash=left.graph_hash,
            right_graph_hash=right.graph_hash,
            added_nodes=sorted(set(right_nodes) - set(left_nodes)),
            removed_nodes=sorted(set(left_nodes) - set(right_nodes)),
            changed_nodes=sorted(
                node_id
                for node_id in set(left_nodes) & set(right_nodes)
                if left_nodes[node_id] != right_nodes[node_id]
            ),
            added_edges=sorted(set(right_edges) - set(left_edges)),
            removed_edges=sorted(set(left_edges) - set(right_edges)),
            changed_edges=sorted(
                edge_id
                for edge_id in set(left_edges) & set(right_edges)
                if left_edges[edge_id] != right_edges[edge_id]
            ),
            metadata_changed=left_graph.get("metadata", {}) != right_graph.get("metadata", {}),
        )

    def save_run_record(
        self,
        *,
        result_payload: dict[str, Any],
        project_id: str | None = None,
        version_id: str | None = None,
    ) -> RunRecord:
        if project_id is not None:
            self.require_project(project_id)
        manifest = result_payload.get("manifest")
        if not isinstance(manifest, dict):
            manifest = {}
        timestamp = _utc_now()
        run_id = _read_string(result_payload.get("run_id")) or f"run-{uuid4()}"
        result_checksum = _read_string(result_payload.get("result_checksum")) or _read_string(
            manifest.get("result_checksum")
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO run_records(
                    run_id,
                    project_id,
                    methodology_id,
                    version_id,
                    graph_hash,
                    status,
                    result_checksum,
                    manifest_json,
                    result_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    _read_string(result_payload.get("methodology_id")),
                    version_id,
                    _read_string(result_payload.get("graph_hash")),
                    _read_string(result_payload.get("status")),
                    result_checksum,
                    json.dumps(manifest, sort_keys=True),
                    json.dumps(result_payload, sort_keys=True),
                    timestamp,
                ),
            )
        return self.require_run_record(run_id)

    def list_run_records(
        self,
        *,
        project_id: str | None = None,
        methodology_id: str | None = None,
    ) -> list[RunRecordSummary]:
        where_clauses: list[str] = []
        params: list[str] = []
        if project_id is not None:
            where_clauses.append("project_id = ?")
            params.append(project_id)
        if methodology_id is not None:
            where_clauses.append("methodology_id = ?")
            params.append(methodology_id)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    run_id,
                    project_id,
                    methodology_id,
                    version_id,
                    graph_hash,
                    status,
                    result_checksum,
                    created_at
                FROM run_records
                {where_sql}
                ORDER BY created_at DESC
                """,
                tuple(params),
            ).fetchall()
        return [RunRecordSummary.model_validate(dict(row)) for row in rows]

    def require_run_record(self, run_id: str) -> RunRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM run_records
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA run record: {run_id}")
        return RunRecord(
            run_id=row["run_id"],
            project_id=row["project_id"],
            methodology_id=row["methodology_id"],
            version_id=row["version_id"],
            graph_hash=row["graph_hash"],
            status=row["status"],
            result_checksum=row["result_checksum"],
            created_at=row["created_at"],
            manifest=json.loads(row["manifest_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
        )

    def save_radar_output(
        self,
        project_id: str,
        request: SaveRadarOutputRequest,
    ) -> SavedRadarOutputRecord:
        self.require_project(project_id)
        result_payload = request.result
        manifest = result_payload.get("manifest")
        if not isinstance(manifest, dict):
            manifest = {}
        rows = _read_list(result_payload.get("rows"))
        selected_columns = request.selected_columns or _default_radar_columns(rows)
        displayed_tickers = request.displayed_tickers or [
            ticker
            for row in rows
            if isinstance((ticker := row.get("ticker") if isinstance(row, dict) else None), str)
        ]
        evidence_refs = _evidence_refs_for_rows(rows)
        radar_id = f"radar-{uuid4()}"
        timestamp = _utc_now()
        output_payload = {
            "radar_id": radar_id,
            "name": request.name,
            "project_id": project_id,
            "methodology_id": _read_string(result_payload.get("methodology_id")),
            "version_id": request.version_id or _read_optional_string(
                manifest.get("methodology_version_id")
            ),
            "run_id": _read_optional_string(result_payload.get("run_id")),
            "timestamp_cutoff": _read_optional_string(result_payload.get("timestamp_cutoff"))
            or _read_optional_string(manifest.get("timestamp_cutoff")),
            "result_checksum": _read_string(result_payload.get("result_checksum"))
            or _read_string(manifest.get("result_checksum")),
            "selected_columns": selected_columns,
            "displayed_tickers": displayed_tickers,
            "displayed_rows": [
                row for row in rows if row.get("ticker") in set(displayed_tickers)
            ],
            "evidence_refs": evidence_refs,
            "designer": request.designer,
            "created_at": timestamp,
        }

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO saved_radar_outputs(
                    radar_id,
                    project_id,
                    methodology_id,
                    version_id,
                    run_id,
                    result_checksum,
                    output_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    radar_id,
                    project_id,
                    output_payload["methodology_id"],
                    output_payload["version_id"],
                    output_payload["run_id"],
                    output_payload["result_checksum"],
                    json.dumps(output_payload, sort_keys=True),
                    timestamp,
                ),
            )
        return self.require_radar_output(radar_id)

    def list_radar_outputs(self, project_id: str | None = None) -> list[SavedRadarOutputSummary]:
        where_sql = "WHERE project_id = ?" if project_id is not None else ""
        params = (project_id,) if project_id is not None else ()
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM saved_radar_outputs
                {where_sql}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
        return [_radar_record_from_row(row) for row in rows]

    def require_radar_output(self, radar_id: str) -> SavedRadarOutputRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM saved_radar_outputs
                WHERE radar_id = ?
                """,
                (radar_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA radar output: {radar_id}")
        return _radar_record_from_row(row)

    def create_watchlist(
        self,
        project_id: str,
        request: CreateWatchlistRequest,
    ) -> WatchlistRecord:
        self.require_project(project_id)
        timestamp = _utc_now()
        watchlist_id = f"watchlist-{uuid4()}"
        tickers = _normalize_tickers(request.tickers)
        metadata = {
            "source_radar_id": request.source_radar_id,
            "source_run_id": request.source_run_id,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO watchlists(
                    watchlist_id,
                    project_id,
                    name,
                    tickers_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    watchlist_id,
                    project_id,
                    request.name,
                    json.dumps({"tickers": tickers, **metadata}, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
        return self.require_watchlist(watchlist_id)

    def update_watchlist_tickers(
        self,
        watchlist_id: str,
        request: UpdateWatchlistTickersRequest,
    ) -> WatchlistRecord:
        watchlist = self.require_watchlist(watchlist_id)
        tickers = set(watchlist.tickers)
        tickers.update(_normalize_tickers(request.add_tickers))
        tickers.difference_update(_normalize_tickers(request.remove_tickers))
        timestamp = _utc_now()
        payload = {
            "tickers": sorted(tickers),
            "source_radar_id": watchlist.source_radar_id,
            "source_run_id": watchlist.source_run_id,
        }
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE watchlists
                SET tickers_json = ?, updated_at = ?
                WHERE watchlist_id = ?
                """,
                (json.dumps(payload, sort_keys=True), timestamp, watchlist_id),
            )
        return self.require_watchlist(watchlist_id)

    def list_watchlists(self, project_id: str | None = None) -> list[WatchlistRecord]:
        where_sql = "WHERE project_id = ?" if project_id is not None else ""
        params = (project_id,) if project_id is not None else ()
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM watchlists
                {where_sql}
                ORDER BY updated_at DESC
                """,
                params,
            ).fetchall()
        return [_watchlist_from_row(row) for row in rows]

    def require_watchlist(self, watchlist_id: str) -> WatchlistRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM watchlists
                WHERE watchlist_id = ?
                """,
                (watchlist_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA watchlist: {watchlist_id}")
        return _watchlist_from_row(row)

    def create_alert(
        self,
        project_id: str,
        request: CreateAlertRequest,
    ) -> AlertRecord:
        self.require_project(project_id)
        timestamp = _utc_now()
        alert_id = f"alert-{uuid4()}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO alerts(
                    alert_id,
                    project_id,
                    name,
                    definition_json,
                    enabled,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    project_id,
                    request.name,
                    request.definition.model_dump_json(),
                    1 if request.enabled else 0,
                    timestamp,
                    timestamp,
                ),
            )
        return self.require_alert(alert_id)

    def list_alerts(self, project_id: str | None = None) -> list[AlertRecord]:
        where_sql = "WHERE project_id = ?" if project_id is not None else ""
        params = (project_id,) if project_id is not None else ()
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM alerts
                {where_sql}
                ORDER BY updated_at DESC
                """,
                params,
            ).fetchall()
        return [_alert_from_row(row) for row in rows]

    def require_alert(self, alert_id: str) -> AlertRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM alerts
                WHERE alert_id = ?
                """,
                (alert_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA alert: {alert_id}")
        return _alert_from_row(row)

    def save_viza_file_import(
        self,
        *,
        file_id: str,
        manifest: dict[str, Any],
        source_path: str | None = None,
        project_id: str | None = None,
        container_checksum: str | None = None,
        manifest_checksum: str | None = None,
        status: str = "imported",
        warnings: list[str] | None = None,
        quarantine_status: str = "none",
    ) -> VizaFileImportRecord:
        if project_id is not None:
            self.require_project(project_id)
        import_id = f"viza-import-{uuid4()}"
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO viza_file_imports(
                    import_id,
                    file_id,
                    project_id,
                    source_path,
                    imported_at,
                    manifest_json,
                    container_checksum,
                    manifest_checksum,
                    status,
                    warnings_json,
                    quarantine_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    file_id,
                    project_id,
                    source_path,
                    timestamp,
                    json.dumps(manifest, sort_keys=True),
                    container_checksum,
                    manifest_checksum,
                    status,
                    json.dumps(warnings or [], sort_keys=True),
                    quarantine_status,
                ),
            )
            if project_id is not None:
                connection.execute(
                    "UPDATE projects SET updated_at = ? WHERE project_id = ?",
                    (timestamp, project_id),
                )
        return self.require_viza_file_import(import_id)

    def save_viza_file_export(
        self,
        *,
        file_id: str,
        manifest: dict[str, Any],
        target_path: str | None = None,
        project_id: str | None = None,
        container_checksum: str | None = None,
        manifest_checksum: str | None = None,
        purpose: str | None = None,
        visibility: str | None = None,
        warnings: list[str] | None = None,
    ) -> VizaFileExportRecord:
        if project_id is not None:
            self.require_project(project_id)
        export_id = f"viza-export-{uuid4()}"
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO viza_file_exports(
                    export_id,
                    file_id,
                    project_id,
                    target_path,
                    exported_at,
                    manifest_json,
                    container_checksum,
                    manifest_checksum,
                    purpose,
                    visibility,
                    warnings_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    export_id,
                    file_id,
                    project_id,
                    target_path,
                    timestamp,
                    json.dumps(manifest, sort_keys=True),
                    container_checksum,
                    manifest_checksum,
                    purpose,
                    visibility,
                    json.dumps(warnings or [], sort_keys=True),
                ),
            )
            if project_id is not None:
                connection.execute(
                    "UPDATE projects SET updated_at = ? WHERE project_id = ?",
                    (timestamp, project_id),
                )
        return self.require_viza_file_export(export_id)

    def require_viza_file_import(self, import_id: str) -> VizaFileImportRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM viza_file_imports
                WHERE import_id = ?
                """,
                (import_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA file import: {import_id}")
        return _viza_file_import_from_row(row)

    def require_viza_file_export(self, export_id: str) -> VizaFileExportRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM viza_file_exports
                WHERE export_id = ?
                """,
                (export_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA file export: {export_id}")
        return _viza_file_export_from_row(row)

    def require_viza_file_record(self, file_id: str) -> VizaFileRecord:
        imports = self.list_viza_file_imports(file_id)
        exports = self.list_viza_file_exports(file_id)
        if not imports and not exports:
            raise KeyError(f"unknown VIZA file: {file_id}")
        return VizaFileRecord(file_id=file_id, imports=imports, exports=exports)

    def list_viza_file_records(self) -> list[VizaFileRecord]:
        records: dict[str, VizaFileRecord] = {}
        for item in self.list_viza_file_imports():
            record = records.setdefault(item.file_id, VizaFileRecord(file_id=item.file_id))
            record.imports.append(item)
        for item in self.list_viza_file_exports():
            record = records.setdefault(item.file_id, VizaFileRecord(file_id=item.file_id))
            record.exports.append(item)
        return sorted(records.values(), key=_viza_file_record_timestamp, reverse=True)

    def list_viza_file_imports(self, file_id: str | None = None) -> list[VizaFileImportRecord]:
        where = ""
        params: tuple[str, ...] = ()
        if file_id is not None:
            where = "WHERE file_id = ?"
            params = (file_id,)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM viza_file_imports
                {where}
                ORDER BY imported_at DESC
                """,
                params,
            ).fetchall()
        return [_viza_file_import_from_row(row) for row in rows]

    def list_viza_file_exports(self, file_id: str | None = None) -> list[VizaFileExportRecord]:
        where = ""
        params: tuple[str, ...] = ()
        if file_id is not None:
            where = "WHERE file_id = ?"
            params = (file_id,)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM viza_file_exports
                {where}
                ORDER BY exported_at DESC
                """,
                params,
            ).fetchall()
        return [_viza_file_export_from_row(row) for row in rows]

    def save_creator_record(self, request: CreatorRecordRequest) -> CreatorRecord:
        creator_id = request.creator_id or f"creator-{uuid4()}"
        timestamp = _utc_now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT created_at FROM creator_records WHERE creator_id = ?",
                (creator_id,),
            ).fetchone()
            created_at = existing["created_at"] if existing is not None else timestamp
            connection.execute(
                """
                INSERT INTO creator_records(
                    creator_id,
                    display_name,
                    verification_status,
                    created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(creator_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    verification_status = excluded.verification_status,
                    metadata_json = excluded.metadata_json
                """,
                (
                    creator_id,
                    request.display_name,
                    request.verification_status,
                    created_at,
                    json.dumps(request.metadata, sort_keys=True),
                ),
            )
        return self.require_creator_record(creator_id)

    def require_creator_record(self, creator_id: str) -> CreatorRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM creator_records
                WHERE creator_id = ?
                """,
                (creator_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA creator: {creator_id}")
        return _creator_record_from_row(row)

    def list_creator_records(self) -> list[CreatorRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM creator_records
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [_creator_record_from_row(row) for row in rows]

    def latest_viza_file_manifest(self, file_id: str) -> dict[str, Any]:
        record = self.require_viza_file_record(file_id)
        candidates: list[tuple[str, dict[str, Any]]] = []
        candidates.extend((item.imported_at, item.manifest) for item in record.imports)
        candidates.extend((item.exported_at, item.manifest) for item in record.exports)
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def quarantine_viza_file(self, file_id: str, reason: str) -> int:
        timestamp = _utc_now()
        updated = 0
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT import_id, warnings_json
                FROM viza_file_imports
                WHERE file_id = ?
                """,
                (file_id,),
            ).fetchall()
            for row in rows:
                warnings = _read_string_list(json.loads(row["warnings_json"]))
                warnings.append(f"quarantined: {reason}")
                connection.execute(
                    """
                    UPDATE viza_file_imports
                    SET quarantine_status = ?, warnings_json = ?
                    WHERE import_id = ?
                    """,
                    ("quarantined", json.dumps(warnings, sort_keys=True), row["import_id"]),
                )
                updated += 1
            if updated:
                connection.execute(
                    """
                    UPDATE projects
                    SET updated_at = ?
                    WHERE project_id IN (
                        SELECT project_id
                        FROM viza_file_imports
                        WHERE file_id = ? AND project_id IS NOT NULL
                    )
                    """,
                    (timestamp, file_id),
                )
        if updated == 0:
            self.require_viza_file_record(file_id)
        return updated

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS methodology_versions (
                    version_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    methodology_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    label TEXT,
                    message TEXT,
                    schema_version TEXT NOT NULL,
                    graph_hash TEXT NOT NULL,
                    parent_version_id TEXT,
                    graph_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    graph_created_at TEXT NOT NULL,
                    graph_updated_at TEXT NOT NULL,
                    node_count INTEGER NOT NULL,
                    edge_count INTEGER NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                );

                CREATE INDEX IF NOT EXISTS idx_methodology_versions_project
                    ON methodology_versions(project_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_methodology_versions_methodology
                    ON methodology_versions(methodology_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS run_records (
                    run_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    methodology_id TEXT NOT NULL,
                    version_id TEXT,
                    graph_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_checksum TEXT NOT NULL DEFAULT '',
                    manifest_json TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS saved_radar_outputs (
                    radar_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    methodology_id TEXT NOT NULL,
                    version_id TEXT,
                    run_id TEXT,
                    result_checksum TEXT,
                    output_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS connector_settings (
                    connector_id TEXT PRIMARY KEY,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS watchlists (
                    watchlist_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    name TEXT NOT NULL,
                    tickers_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    name TEXT NOT NULL,
                    definition_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS viza_file_imports (
                    import_id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    project_id TEXT,
                    source_path TEXT,
                    imported_at TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    container_checksum TEXT,
                    manifest_checksum TEXT,
                    status TEXT NOT NULL,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    quarantine_status TEXT NOT NULL DEFAULT 'none'
                );

                CREATE TABLE IF NOT EXISTS viza_file_exports (
                    export_id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    project_id TEXT,
                    target_path TEXT,
                    exported_at TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    container_checksum TEXT,
                    manifest_checksum TEXT,
                    purpose TEXT,
                    visibility TEXT,
                    warnings_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_viza_file_imports_file
                    ON viza_file_imports(file_id, imported_at DESC);

                CREATE INDEX IF NOT EXISTS idx_viza_file_exports_file
                    ON viza_file_exports(file_id, exported_at DESC);

                CREATE TABLE IF NOT EXISTS creator_records (
                    creator_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    verification_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

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

                CREATE TABLE IF NOT EXISTS observations (
                    observation_id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    asset_id TEXT,
                    attribute_key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    unit TEXT,
                    observed_at TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    connector_id TEXT NOT NULL,
                    source_record TEXT,
                    data_version TEXT,
                    model_version TEXT,
                    confidence REAL,
                    rights_policy_json TEXT NOT NULL DEFAULT '{}',
                    checksum TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    affected_entity_ids_json TEXT NOT NULL,
                    affected_asset_ids_json TEXT NOT NULL DEFAULT '[]',
                    related_entity_ids_json TEXT NOT NULL DEFAULT '[]',
                    observed_at TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    source_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_credibility REAL,
                    materiality REAL,
                    novelty REAL,
                    direction_hint TEXT,
                    time_horizon_hint TEXT,
                    risk_factors_json TEXT NOT NULL DEFAULT '[]',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    rights_policy_json TEXT NOT NULL DEFAULT '{}',
                    point_in_time_safe INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS insights (
                    insight_id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    asset_id TEXT,
                    related_entity_ids_json TEXT NOT NULL DEFAULT '[]',
                    related_asset_ids_json TEXT NOT NULL DEFAULT '[]',
                    insight_type TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    magnitude_json TEXT,
                    confidence REAL NOT NULL,
                    time_horizon_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    source_policy_json TEXT NOT NULL DEFAULT '{}',
                    observed_at TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    strategy_compatibility_json TEXT NOT NULL DEFAULT '[]',
                    risk_factors_json TEXT NOT NULL DEFAULT '[]',
                    invalidation_conditions_json TEXT NOT NULL DEFAULT '[]',
                    action_layer_json TEXT NOT NULL DEFAULT '{}',
                    derivation_trace_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS strategy_profiles (
                    strategy_profile_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    module_id TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS strategy_profile_versions (
                    version_id TEXT PRIMARY KEY,
                    strategy_profile_id TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    profile_hash TEXT NOT NULL,
                    parent_version_id TEXT,
                    label TEXT,
                    message TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS translations (
                    translation_id TEXT PRIMARY KEY,
                    insight_id TEXT NOT NULL,
                    strategy_profile_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    asset_id TEXT,
                    fit_score REAL NOT NULL,
                    relevance TEXT NOT NULL,
                    translated_summary TEXT NOT NULL,
                    strategy_fit_reasons_json TEXT NOT NULL DEFAULT '[]',
                    missing_confirmations_json TEXT NOT NULL DEFAULT '[]',
                    risk_factors_json TEXT NOT NULL DEFAULT '[]',
                    invalidation_conditions_json TEXT NOT NULL DEFAULT '[]',
                    suggested_research_action TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    generated_at TEXT NOT NULL,
                    not_investment_advice INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS validation_records (
                    validation_record_id TEXT PRIMARY KEY,
                    strategy_or_methodology_id TEXT NOT NULL,
                    strategy_profile_id TEXT,
                    run_id TEXT NOT NULL,
                    graph_hash TEXT NOT NULL,
                    result_checksum TEXT NOT NULL,
                    timestamp_cutoff TEXT,
                    generated_at TEXT NOT NULL,
                    domain TEXT,
                    module_id TEXT,
                    record_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runtime_jobs (
                    job_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    progress_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    result_ref TEXT,
                    warnings_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS runtime_job_events (
                    event_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runtime_cache_entries (
                    cache_checksum TEXT PRIMARY KEY,
                    cache_key_json TEXT NOT NULL,
                    result_ref TEXT,
                    result_checksum TEXT,
                    source_versions_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    last_hit_at TEXT,
                    hit_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS radar_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    radar_id TEXT,
                    methodology_id TEXT,
                    cadence TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    timezone TEXT NOT NULL DEFAULT 'local',
                    next_run_at TEXT,
                    definition_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entities_identifiers
                    ON entities(entity_type, display_name);

                CREATE INDEX IF NOT EXISTS idx_finance_assets_symbol
                    ON finance_assets(primary_symbol);

                CREATE INDEX IF NOT EXISTS idx_observations_lookup
                    ON observations(entity_id, attribute_key, available_at);

                CREATE INDEX IF NOT EXISTS idx_events_type_available
                    ON events(event_type, available_at);

                CREATE INDEX IF NOT EXISTS idx_insights_entity_available
                    ON insights(entity_id, insight_type, available_at);

                CREATE INDEX IF NOT EXISTS idx_runtime_job_events_job
                    ON runtime_job_events(job_id, sequence);

                CREATE INDEX IF NOT EXISTS idx_radar_schedules_project
                    ON radar_schedules(project_id, updated_at DESC);
                """
            )
            self._ensure_column(
                connection,
                "run_records",
                "result_checksum",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "connector_settings",
                "project_id",
                "TEXT",
            )
            self._ensure_column(
                connection,
                "connector_settings",
                "settings_json",
                "TEXT NOT NULL DEFAULT '{}'",
            )
            self._ensure_column(
                connection,
                "connector_settings",
                "credential_refs_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            self._ensure_column(
                connection,
                "connector_settings",
                "credential_status_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        if column_name not in {row["name"] for row in rows}:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            )


def get_project_store(path: str | Path | None = None) -> ProjectStore:
    return ProjectStore(path)


def project_store_path() -> Path:
    configured_path = os.getenv(PROJECT_STORE_ENV_VAR)
    if configured_path:
        return Path(configured_path)
    return Path.home() / ".viza" / "viza_projects.sqlite3"


def _connector_configuration_from_row(row: sqlite3.Row) -> ConnectorConfigurationRecord:
    settings = _load_json_object(row, "settings_json")
    credential_refs = [
        CredentialRef.model_validate(item)
        for item in _load_json_list(row, "credential_refs_json")
    ]
    credential_status = [
        CredentialStatus.model_validate(item)
        for item in _load_json_list(row, "credential_status_json")
    ]
    return ConnectorConfigurationRecord(
        connector_id=row["connector_id"],
        project_id=row["project_id"] if "project_id" in row.keys() else None,
        settings=settings,
        credential_refs=credential_refs,
        credential_status=credential_status,
        updated_at=row["updated_at"],
    )


def _load_json_object(row: sqlite3.Row, column_name: str) -> dict[str, Any]:
    if column_name not in row.keys():
        return {}
    value = row[column_name]
    if not value:
        return {}
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {}


def _load_json_list(row: sqlite3.Row, column_name: str) -> list[dict[str, Any]]:
    if column_name not in row.keys():
        return []
    value = row[column_name]
    if not value:
        return []
    loaded = json.loads(value)
    return loaded if isinstance(loaded, list) else []


def _redact_secret_settings(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***"
            if _looks_secret_key(key)
            else _redact_secret_settings(nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_secret_settings(item) for item in value]
    return value


def _looks_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ("secret", "token", "api_key", "apikey", "password"))


def _version_summary_from_row(row: sqlite3.Row) -> MethodologyVersionSummary:
    return MethodologyVersionSummary.model_validate(
        {
            key: row[key]
            for key in MethodologyVersionSummary.model_fields
        }
    )


def _version_record_from_row(row: sqlite3.Row) -> MethodologyVersionRecord:
    graph_payload = json.loads(row["graph_json"])
    return MethodologyVersionRecord(
        **_version_summary_from_row(row).model_dump(mode="json"),
        graph=MethodologyGraph.model_validate(graph_payload),
    )


def _radar_record_from_row(row: sqlite3.Row) -> SavedRadarOutputRecord:
    output = json.loads(row["output_json"])
    selected_columns = _read_string_list(output.get("selected_columns"))
    displayed_rows = _read_list(output.get("displayed_rows"))
    evidence_refs = _read_string_list(output.get("evidence_refs"))
    return SavedRadarOutputRecord(
        radar_id=row["radar_id"],
        project_id=row["project_id"],
        methodology_id=row["methodology_id"],
        version_id=row["version_id"],
        run_id=row["run_id"],
        timestamp_cutoff=_read_optional_string(output.get("timestamp_cutoff")),
        result_checksum=_read_string(row["result_checksum"]),
        name=_read_optional_string(output.get("name")),
        selected_columns=selected_columns,
        row_count=len(displayed_rows),
        evidence_ref_count=len(evidence_refs),
        created_at=row["created_at"],
        output=output,
    )


def _watchlist_from_row(row: sqlite3.Row) -> WatchlistRecord:
    payload = json.loads(row["tickers_json"])
    if isinstance(payload, list):
        payload = {"tickers": payload}
    return WatchlistRecord(
        watchlist_id=row["watchlist_id"],
        project_id=row["project_id"],
        name=row["name"],
        tickers=_normalize_tickers(_read_string_list(payload.get("tickers"))),
        source_radar_id=_read_optional_string(payload.get("source_radar_id")),
        source_run_id=_read_optional_string(payload.get("source_run_id")),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _alert_from_row(row: sqlite3.Row) -> AlertRecord:
    return AlertRecord(
        alert_id=row["alert_id"],
        project_id=row["project_id"],
        name=row["name"],
        definition=AlertDefinition.model_validate(json.loads(row["definition_json"])),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _viza_file_import_from_row(row: sqlite3.Row) -> VizaFileImportRecord:
    return VizaFileImportRecord(
        import_id=row["import_id"],
        file_id=row["file_id"],
        project_id=row["project_id"],
        source_path=row["source_path"],
        imported_at=row["imported_at"],
        manifest=json.loads(row["manifest_json"]),
        container_checksum=row["container_checksum"],
        manifest_checksum=row["manifest_checksum"],
        status=row["status"],
        warnings=_read_string_list(json.loads(row["warnings_json"])),
        quarantine_status=row["quarantine_status"],
    )


def _viza_file_export_from_row(row: sqlite3.Row) -> VizaFileExportRecord:
    return VizaFileExportRecord(
        export_id=row["export_id"],
        file_id=row["file_id"],
        project_id=row["project_id"],
        target_path=row["target_path"],
        exported_at=row["exported_at"],
        manifest=json.loads(row["manifest_json"]),
        container_checksum=row["container_checksum"],
        manifest_checksum=row["manifest_checksum"],
        purpose=row["purpose"],
        visibility=row["visibility"],
        warnings=_read_string_list(json.loads(row["warnings_json"])),
    )


def _creator_record_from_row(row: sqlite3.Row) -> CreatorRecord:
    return CreatorRecord(
        creator_id=row["creator_id"],
        display_name=row["display_name"],
        verification_status=row["verification_status"],
        created_at=row["created_at"],
        metadata=json.loads(row["metadata_json"]),
    )


def _viza_file_record_timestamp(record: VizaFileRecord) -> str:
    timestamps = [item.imported_at for item in record.imports]
    timestamps.extend(item.exported_at for item in record.exports)
    return max(timestamps) if timestamps else ""


def _default_radar_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns = ["ticker", "company_name", "score", "rank"]
    for row in rows[:1]:
        attributes = row.get("attributes") if isinstance(row, dict) else None
        if isinstance(attributes, dict):
            columns.extend(key for key in attributes if isinstance(key, str))
    return list(dict.fromkeys(columns))


def _evidence_refs_for_rows(rows: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for row in rows:
        refs.extend(_read_string_list(row.get("evidence_refs")))
    return list(dict.fromkeys(refs))


def _normalize_tickers(tickers: list[str]) -> list[str]:
    normalized = [
        ticker.strip().upper()
        for ticker in tickers
        if isinstance(ticker, str) and ticker.strip()
    ]
    return list(dict.fromkeys(normalized))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _read_optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _read_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _read_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]

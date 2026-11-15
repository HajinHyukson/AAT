from __future__ import annotations

import os
import platform
import sqlite3
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.attribute_registry import AttributeRegistry, load_attribute_registry
from viza.config_paths import required_config_file_status, resolve_config_dir
from viza.connectors import ConnectorDefinition, load_connector_catalog
from viza.file_format.models import VIZA_DOCUMENT_SCHEMA_VERSION
from viza.modules import get_module_registry
from viza.project_store import project_store_path


RUNTIME_DIAGNOSTICS_VERSION = "viza_runtime_phase_14_release_readiness_v0"

PROJECT_STORE_TABLES = [
    "projects",
    "methodology_versions",
    "run_records",
    "saved_radar_outputs",
    "connector_settings",
    "user_settings",
    "watchlists",
    "alerts",
    "viza_file_imports",
    "viza_file_exports",
    "creator_records",
    "entities",
    "finance_assets",
    "entity_relationships",
    "observations",
    "events",
    "insights",
    "strategy_profiles",
    "strategy_profile_versions",
    "translations",
    "validation_records",
    "runtime_jobs",
    "runtime_job_events",
    "runtime_cache_entries",
    "radar_schedules",
]


class DiagnosticCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class ProjectStoreDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    status: str
    directory_exists: bool
    directory_writable: bool
    database_exists: bool
    schema_tables: list[str] = Field(default_factory=list)
    missing_tables: list[str] = Field(default_factory=list)
    project_count: int = 0
    methodology_version_count: int = 0
    run_count: int = 0
    last_run_id: str | None = None
    last_run_status: str | None = None
    last_run_created_at: str | None = None
    error: str | None = None


class ConnectorRuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    display_name: str
    status: str
    source_type: str
    credential_required: bool
    credentials_configured: bool
    credential_mode: str
    query_allowed: bool
    cache_allowed: bool
    display_allowed: bool
    export_allowed: bool
    redistribution_allowed: bool
    license_policy: str
    cache_policy: str


class ConfigFileStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    resolved_path: str
    exists: bool


class RuntimeDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = "viza-local-engine"
    status: str
    engine_version: str
    diagnostics_version: str = RUNTIME_DIAGNOSTICS_VERSION
    python_version: str
    platform: str
    cwd: str
    package_root: str
    config_root: str
    config_files: list[ConfigFileStatus] = Field(default_factory=list)
    token_required: bool
    attribute_registry_schema_version: str
    attribute_registry_version: str
    attribute_count: int
    project_store: ProjectStoreDiagnostics
    connector_statuses: list[ConnectorRuntimeStatus] = Field(default_factory=list)
    file_format_version: str = VIZA_DOCUMENT_SCHEMA_VERSION
    installed_modules: list[dict[str, Any]] = Field(default_factory=list)
    credential_mode: str = "local"
    observation_store_health: dict[str, Any] = Field(default_factory=dict)
    viza_file_health: dict[str, Any] = Field(default_factory=dict)
    last_quarantine_event: dict[str, Any] = Field(default_factory=dict)
    source_backed_resolver_count: int = 0
    prototype_fallback_count: int = 0
    credential_ready_connector_count: int = 0
    observation_store_status: str = "unknown"
    last_resolver_warning_count: int = 0
    checks: list[DiagnosticCheck] = Field(default_factory=list)


def collect_runtime_diagnostics(engine_version: str = "unknown") -> RuntimeDiagnostics:
    registry, registry_error = _load_registry_safely()
    connectors, connector_error = _load_connectors_safely(registry)
    project_store = diagnose_project_store()
    config_files = [
        ConfigFileStatus.model_validate(item) for item in required_config_file_status()
    ]

    checks = [
        _project_store_check(project_store),
        _config_files_check(str(resolve_config_dir()), config_files),
        _attribute_registry_check(registry, registry_error),
        _connector_check(connectors, connector_error),
        _token_check(),
    ]
    status = _overall_status(checks)

    return RuntimeDiagnostics(
        status=status,
        engine_version=engine_version,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        cwd=os.getcwd(),
        package_root=str(Path(__file__).resolve().parents[1]),
        config_root=str(resolve_config_dir()),
        config_files=config_files,
        token_required=bool(os.getenv("VIZA_ENGINE_TOKEN")),
        attribute_registry_schema_version=registry.schema_version if registry else "unavailable",
        attribute_registry_version=(
            registry.registry_version or "unversioned" if registry else "unavailable"
        ),
        attribute_count=len(registry.attributes) if registry else 0,
        project_store=project_store,
        connector_statuses=[
            ConnectorRuntimeStatus(
                connector_id=connector.connector_id,
                display_name=connector.display_name,
                status=connector.status,
                source_type=connector.source_type,
                credential_required=any(
                    credential.required for credential in connector.credential_requirements
                ),
                credentials_configured=all(
                    not credential.required or credential.configured
                    for credential in connector.credential_requirements
                ),
                credential_mode=(
                    connector.credential_requirements[0].storage
                    if connector.credential_requirements
                    else "none"
                ),
                query_allowed=connector.entitlement.query_allowed,
                cache_allowed=connector.entitlement.local_cache_allowed,
                display_allowed=connector.entitlement.derived_value_allowed,
                export_allowed=connector.entitlement.export_allowed,
                redistribution_allowed=connector.entitlement.redistribution_allowed,
                license_policy=connector.license_policy,
                cache_policy=connector.cache_policy,
            )
            for connector in connectors
        ],
        file_format_version=VIZA_DOCUMENT_SCHEMA_VERSION,
        installed_modules=_installed_modules(),
        credential_mode=_credential_mode(connectors),
        observation_store_health=_observation_store_health(project_store),
        viza_file_health=_viza_file_health(project_store),
        last_quarantine_event=_last_quarantine_event(project_store),
        source_backed_resolver_count=_source_backed_resolver_count(project_store),
        prototype_fallback_count=_prototype_fallback_count(registry, project_store),
        credential_ready_connector_count=sum(
            1
            for connector in connectors
            if all(
                not credential.required or credential.configured
                for credential in connector.credential_requirements
            )
        ),
        observation_store_status=(
            "available" if "observations" not in project_store.missing_tables else "missing"
        ),
        last_resolver_warning_count=_last_resolver_warning_count(project_store),
        checks=checks,
    )


def diagnose_project_store(path: str | Path | None = None) -> ProjectStoreDiagnostics:
    active_path = Path(path) if path is not None else project_store_path()
    directory = active_path.parent
    directory_exists = directory.exists()
    directory_writable = _directory_writable(directory) if directory_exists else False
    database_exists = active_path.exists()

    if not database_exists:
        return ProjectStoreDiagnostics(
            path=str(active_path),
            status="not_initialized",
            directory_exists=directory_exists,
            directory_writable=directory_writable,
            database_exists=False,
            missing_tables=PROJECT_STORE_TABLES.copy(),
        )

    try:
        with sqlite3.connect(f"file:{active_path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            quick_check = connection.execute("PRAGMA quick_check").fetchone()
            quick_check_status = quick_check[0] if quick_check else "unknown"
            schema_tables = sorted(
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            )
            missing_tables = [
                table for table in PROJECT_STORE_TABLES if table not in set(schema_tables)
            ]
            project_count = _count_rows(connection, "projects", schema_tables)
            methodology_version_count = _count_rows(
                connection,
                "methodology_versions",
                schema_tables,
            )
            run_count = _count_rows(connection, "run_records", schema_tables)
            last_run = _last_run(connection, schema_tables)
    except sqlite3.Error as exc:
        return ProjectStoreDiagnostics(
            path=str(active_path),
            status="error",
            directory_exists=directory_exists,
            directory_writable=directory_writable,
            database_exists=True,
            error=str(exc),
        )

    if quick_check_status != "ok":
        status = "error"
        error = f"sqlite quick_check returned {quick_check_status}"
    elif missing_tables:
        status = "error"
        error = "project store schema is incomplete"
    elif not directory_writable:
        status = "warning"
        error = "project store directory is not writable"
    else:
        status = "ok"
        error = None

    return ProjectStoreDiagnostics(
        path=str(active_path),
        status=status,
        directory_exists=directory_exists,
        directory_writable=directory_writable,
        database_exists=True,
        schema_tables=schema_tables,
        missing_tables=missing_tables,
        project_count=project_count,
        methodology_version_count=methodology_version_count,
        run_count=run_count,
        last_run_id=last_run.get("run_id"),
        last_run_status=last_run.get("status"),
        last_run_created_at=last_run.get("created_at"),
        error=error,
    )


def _load_registry_safely() -> tuple[AttributeRegistry | None, str | None]:
    try:
        return load_attribute_registry(), None
    except Exception as exc:  # pragma: no cover - defensive release diagnostics.
        return None, str(exc)


def _load_connectors_safely(
    registry: AttributeRegistry | None,
) -> tuple[list[ConnectorDefinition], str | None]:
    try:
        return load_connector_catalog(registry) if registry else load_connector_catalog(), None
    except Exception as exc:  # pragma: no cover - defensive release diagnostics.
        return [], str(exc)


def _project_store_check(project_store: ProjectStoreDiagnostics) -> DiagnosticCheck:
    if project_store.status == "ok":
        return DiagnosticCheck(
            name="project_store",
            status="ok",
            message="Project store is readable and writable.",
            detail={"path": project_store.path},
        )
    if project_store.status == "not_initialized":
        return DiagnosticCheck(
            name="project_store",
            status="warning",
            message="Project store has not been created yet.",
            detail={"path": project_store.path},
        )
    return DiagnosticCheck(
        name="project_store",
        status=project_store.status,
        message=project_store.error or "Project store needs attention.",
        detail={"path": project_store.path, "missing_tables": project_store.missing_tables},
    )


def _config_files_check(
    config_root: str,
    config_files: list[ConfigFileStatus],
) -> DiagnosticCheck:
    missing = [item.path for item in config_files if not item.exists]
    if missing:
        return DiagnosticCheck(
            name="config_files",
            status="error",
            message=f"Missing VIZA config files: {', '.join(missing)}",
            detail={"config_root": config_root, "missing": missing},
        )
    return DiagnosticCheck(
        name="config_files",
        status="ok",
        message=f"{len(config_files)} VIZA config files are available.",
        detail={"config_root": config_root},
    )


def _attribute_registry_check(
    registry: AttributeRegistry | None,
    error: str | None,
) -> DiagnosticCheck:
    if registry is None:
        return DiagnosticCheck(
            name="attribute_registry",
            status="error",
            message=error or "Attribute registry could not be loaded.",
        )
    return DiagnosticCheck(
        name="attribute_registry",
        status="ok",
        message=f"{len(registry.attributes)} attributes loaded.",
        detail={"registry_version": registry.registry_version or "unversioned"},
    )


def _connector_check(
    connectors: list[ConnectorDefinition],
    error: str | None,
) -> DiagnosticCheck:
    if error:
        return DiagnosticCheck(
            name="connectors",
            status="error",
            message=error,
        )
    limited_count = sum(
        1
        for connector in connectors
        if connector.status in {"credential_required", "not_configured", "unavailable"}
    )
    status = "warning" if limited_count else "ok"
    return DiagnosticCheck(
        name="connectors",
        status=status,
        message=f"{len(connectors)} connectors loaded; {limited_count} need configuration.",
        detail={"limited_count": limited_count},
    )


def _token_check() -> DiagnosticCheck:
    token_required = bool(os.getenv("VIZA_ENGINE_TOKEN"))
    return DiagnosticCheck(
        name="local_service_token",
        status="ok" if token_required else "warning",
        message=(
            "Local engine token is required for API calls."
            if token_required
            else "Local engine token is not configured in this process."
        ),
    )


def _overall_status(checks: list[DiagnosticCheck]) -> str:
    statuses = {check.status for check in checks}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"


def _directory_writable(directory: Path) -> bool:
    try:
        probe = directory / ".viza_write_probe"
        with probe.open("w", encoding="utf-8") as handle:
            handle.write("ok")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _count_rows(
    connection: sqlite3.Connection,
    table_name: str,
    schema_tables: list[str],
) -> int:
    if table_name not in schema_tables:
        return 0
    row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return int(row["count"]) if row else 0


def _last_run(
    connection: sqlite3.Connection,
    schema_tables: list[str],
) -> dict[str, str | None]:
    if "run_records" not in schema_tables:
        return {}
    row = connection.execute(
        """
        SELECT run_id, status, created_at
        FROM run_records
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row["run_id"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _source_backed_resolver_count(project_store: ProjectStoreDiagnostics) -> int:
    if "observations" not in project_store.schema_tables:
        return 0
    try:
        with sqlite3.connect(project_store.path) as connection:
            row = connection.execute(
                "SELECT COUNT(DISTINCT attribute_key) FROM observations"
            ).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0


def _installed_modules() -> list[dict[str, Any]]:
    try:
        return [
            {
                "module_id": module.module_id,
                "module_version": module.module_version,
                "display_name": module.display_name,
                "domain": module.domain,
            }
            for module in get_module_registry().list_modules()
        ]
    except Exception:
        return []


def _credential_mode(connectors: list[ConnectorDefinition]) -> str:
    modes = {
        requirement.storage
        for connector in connectors
        for requirement in connector.credential_requirements
    }
    if not modes:
        return "no_credentials_required"
    if modes == {"environment"}:
        return "environment"
    if modes == {"local_secret_store"}:
        return "local_secret_store"
    return "mixed"


def _observation_store_health(project_store: ProjectStoreDiagnostics) -> dict[str, Any]:
    if "observations" not in project_store.schema_tables:
        return {"status": "missing", "observation_count": 0, "latest_available_at": None}
    try:
        with sqlite3.connect(project_store.path) as connection:
            row = connection.execute(
                "SELECT COUNT(*), MAX(available_at) FROM observations"
            ).fetchone()
        return {
            "status": "ok",
            "observation_count": int(row[0]) if row else 0,
            "latest_available_at": row[1] if row else None,
        }
    except sqlite3.Error as exc:
        return {"status": "error", "observation_count": 0, "error": str(exc)}


def _viza_file_health(project_store: ProjectStoreDiagnostics) -> dict[str, Any]:
    if (
        "viza_file_imports" not in project_store.schema_tables
        or "viza_file_exports" not in project_store.schema_tables
    ):
        return {"status": "missing", "import_count": 0, "export_count": 0}
    try:
        with sqlite3.connect(project_store.path) as connection:
            import_count = connection.execute("SELECT COUNT(*) FROM viza_file_imports").fetchone()
            export_count = connection.execute("SELECT COUNT(*) FROM viza_file_exports").fetchone()
            quarantined = connection.execute(
                """
                SELECT COUNT(*)
                FROM viza_file_imports
                WHERE quarantine_status = 'quarantined'
                """
            ).fetchone()
        return {
            "status": "ok",
            "document_schema_version": VIZA_DOCUMENT_SCHEMA_VERSION,
            "import_count": int(import_count[0]) if import_count else 0,
            "export_count": int(export_count[0]) if export_count else 0,
            "quarantined_import_count": int(quarantined[0]) if quarantined else 0,
        }
    except sqlite3.Error as exc:
        return {"status": "error", "import_count": 0, "export_count": 0, "error": str(exc)}


def _last_quarantine_event(project_store: ProjectStoreDiagnostics) -> dict[str, Any]:
    if "viza_file_imports" not in project_store.schema_tables:
        return {}
    try:
        with sqlite3.connect(project_store.path) as connection:
            row = connection.execute(
                """
                SELECT file_id, import_id, imported_at, warnings_json
                FROM viza_file_imports
                WHERE quarantine_status = 'quarantined'
                ORDER BY imported_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return {}
        return {
            "file_id": row[0],
            "import_id": row[1],
            "quarantined_at": row[2],
            "warnings": json_loads_list(row[3]),
        }
    except sqlite3.Error:
        return {}


def _prototype_fallback_count(
    registry: AttributeRegistry | None,
    project_store: ProjectStoreDiagnostics,
) -> int:
    if registry is None:
        return 0
    return max(0, len(registry.attributes) - _source_backed_resolver_count(project_store))


def _last_resolver_warning_count(project_store: ProjectStoreDiagnostics) -> int:
    if "run_records" not in project_store.schema_tables:
        return 0
    try:
        with sqlite3.connect(project_store.path) as connection:
            row = connection.execute(
                """
                SELECT result_json
                FROM run_records
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None or row[0] is None:
            return 0
        import json

        result = json.loads(row[0])
        warnings = result.get("warnings") if isinstance(result, dict) else []
        if not isinstance(warnings, list):
            return 0
        return sum(
            1
            for warning in warnings
            if isinstance(warning, dict)
            and "prototype" in str(warning.get("code", "")).lower()
        )
    except (sqlite3.Error, ValueError):
        return 0


def json_loads_list(value: Any) -> list[Any]:
    if not isinstance(value, str) or not value:
        return []
    import json

    loaded = json.loads(value)
    return loaded if isinstance(loaded, list) else []

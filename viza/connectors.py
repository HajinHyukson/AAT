from __future__ import annotations

import csv
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from viza.attribute_registry import AttributeDefinition, AttributeRegistry, load_attribute_registry
from viza.config_paths import display_config_path, resolve_config_path, source_root
from viza.credentials import CredentialStore
from viza.universes import default_universe_config_paths


REPO_ROOT = source_root()
LOCAL_CSV_ENV_VAR = "VIZA_LOCAL_CSV_PATH"


class EntitlementPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_label: str = "internal"
    query_allowed: bool = True
    local_cache_allowed: bool = True
    raw_snapshot_allowed: bool = True
    derived_value_allowed: bool = True
    export_allowed: bool = True
    redistribution_allowed: bool = False
    expires_at: datetime | None = None
    attribution_required: bool = False
    user_credential_required: bool = False
    organization_credential_required: bool = False
    limitations: list[str] = Field(default_factory=list)


class CredentialRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    display_name: str
    required: bool = False
    storage: str = "environment"
    env_var: str | None = None
    configured: bool = False
    secret_available: bool = False


class ConnectorDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    display_name: str
    source_type: str
    status: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    credential_requirements: list[CredentialRequirement] = Field(default_factory=list)
    license_policy: str = "internal_aat"
    cache_policy: str = "local_cache_allowed"
    entitlement: EntitlementPolicy = Field(default_factory=EntitlementPolicy)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ConnectorField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_key: str
    display_name: str
    unit: str = "unknown"
    source: str = ""
    license_policy: str = "internal_aat"
    cache_policy: str = "local_cache_allowed"
    entitlement: EntitlementPolicy = Field(default_factory=EntitlementPolicy)


class ConnectorHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    status: str
    message: str
    credential_required: bool = False
    credential_configured: bool = True
    credential_mode: str = "none"
    query_allowed: bool = True
    cache_allowed: bool = True
    display_allowed: bool = True
    export_allowed: bool = True
    redistribution_allowed: bool = False
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ConnectorPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EnvironmentCredentialStore:
    """Credential wrapper that reports availability without exposing secret values."""

    def __init__(self) -> None:
        self._store = CredentialStore()

    def has_secret(self, connector_id: str, key: str, env_var: str | None) -> bool:
        return self._store.has_secret(connector_id, key, env_var=env_var)

    def mode_for(self, connector_id: str, key: str, env_var: str | None) -> str:
        status = self._store.status_for_secret(connector_id, key, env_var=env_var)
        return status.credential_mode

    def describe_requirement(
        self,
        *args: str,
        required: bool,
        env_var: str | None,
    ) -> CredentialRequirement:
        if len(args) == 2:
            key, display_name = args
            connector_id = key
        elif len(args) == 3:
            connector_id, key, display_name = args
        else:
            raise TypeError("describe_requirement expects key/display_name or connector_id/key/display_name")
        configured = self.has_secret(connector_id, key, env_var)
        return CredentialRequirement(
            key=key,
            display_name=display_name,
            required=required,
            storage=self.mode_for(connector_id, key, env_var),
            env_var=env_var,
            configured=configured,
            secret_available=configured,
        )


class VizaConnector(ABC):
    connector_id: str

    @abstractmethod
    def definition(self) -> ConnectorDefinition:
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> ConnectorHealth:
        raise NotImplementedError

    @abstractmethod
    def list_fields(self, registry: AttributeRegistry | None = None) -> list[ConnectorField]:
        raise NotImplementedError

    @abstractmethod
    def preview(self, limit: int = 5) -> ConnectorPreview:
        raise NotImplementedError

    def read_window(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return []

    def read_latest(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {}

    def get_lineage(self, field_key: str) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "field_key": field_key,
        }

    def get_license_policy(self, field_key: str | None = None) -> str:
        return self.definition().license_policy

    def get_cache_policy(self, field_key: str | None = None) -> str:
        return self.definition().cache_policy

    def explain_missing(self, field_key: str, entity_id: str | None = None) -> str:
        subject = f" for {entity_id}" if entity_id else ""
        return f"{field_key}{subject} is unavailable from {self.connector_id}."


class LocalWorkspaceConnector(VizaConnector):
    connector_id = "local_viza_workspace"

    def definition(self) -> ConnectorDefinition:
        existing_paths = _existing_workspace_paths()
        return ConnectorDefinition(
            connector_id=self.connector_id,
            display_name="Local VIZA Workspace",
            source_type="local_config",
            status="available" if existing_paths else "unavailable",
            description="Local registry, universe config, and deterministic prototype resolver data.",
            capabilities=[
                "test_connection",
                "list_fields",
                "preview",
                "read_latest",
                "get_lineage",
                "explain_missing",
            ],
            license_policy="internal_aat",
            cache_policy="local_cache_allowed",
            entitlement=entitlement_from_policy("internal"),
            diagnostics={"config_paths": existing_paths},
        )

    def test_connection(self) -> ConnectorHealth:
        existing_paths = _existing_workspace_paths()
        status = "available" if existing_paths else "unavailable"
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=status,
            message=(
                "Local VIZA workspace files are readable."
                if existing_paths
                else "No local VIZA workspace files were found."
            ),
            diagnostics={"config_paths": existing_paths},
        )

    def list_fields(self, registry: AttributeRegistry | None = None) -> list[ConnectorField]:
        active_registry = registry if registry is not None else load_attribute_registry()
        return [
            ConnectorField(
                field_key=attribute.key,
                display_name=attribute.display_name,
                unit=attribute.unit,
                source=attribute.source,
                license_policy=attribute.license_policy,
                cache_policy=attribute.cache_policy,
                entitlement=entitlement_for_attribute(attribute),
            )
            for attribute in active_registry.attributes
        ]

    def preview(self, limit: int = 5) -> ConnectorPreview:
        rows = [
            {"kind": "config", "path": path}
            for path in _existing_workspace_paths()[: max(limit, 0)]
        ]
        return ConnectorPreview(connector_id=self.connector_id, rows=rows)


class LocalCsvConnector(VizaConnector):
    connector_id = "local_csv"

    def __init__(self, path: str | Path | None = None) -> None:
        configured_settings = _connector_settings(self.connector_id)
        raw_path = path or os.getenv(LOCAL_CSV_ENV_VAR) or configured_settings.get("path")
        self.path = Path(raw_path) if raw_path else None

    def definition(self) -> ConnectorDefinition:
        status = "available" if self.path is not None and self.path.exists() else "not_configured"
        return ConnectorDefinition(
            connector_id=self.connector_id,
            display_name="Local CSV",
            source_type="local_csv",
            status=status,
            description="User-selected local CSV files for entity-level attributes.",
            capabilities=[
                "test_connection",
                "list_fields",
                "preview",
                "read_latest",
                "get_lineage",
                "explain_missing",
            ],
            license_policy="user_supplied",
            cache_policy="user_local_file",
            entitlement=entitlement_from_policy("user_supplied_local_file"),
            diagnostics={
                "env_var": LOCAL_CSV_ENV_VAR,
                "path_configured": self.path is not None,
                "path_exists": bool(self.path is not None and self.path.exists()),
            },
        )

    def test_connection(self) -> ConnectorHealth:
        if self.path is None:
            return ConnectorHealth(
                connector_id=self.connector_id,
                status="not_configured",
                message=f"Set {LOCAL_CSV_ENV_VAR} to connect a local CSV source.",
            )
        if not self.path.exists():
            return ConnectorHealth(
                connector_id=self.connector_id,
                status="unavailable",
                message=f"CSV path does not exist: {self.path}",
            )
        if not self.path.is_file():
            return ConnectorHealth(
                connector_id=self.connector_id,
                status="unavailable",
                message=f"CSV path is not a file: {self.path}",
            )
        return ConnectorHealth(
            connector_id=self.connector_id,
            status="available",
            message="Local CSV is readable.",
            diagnostics={"path": str(self.path)},
        )

    def list_fields(self, registry: AttributeRegistry | None = None) -> list[ConnectorField]:
        if self.path is None:
            return []
        headers = _read_csv_headers(self.path)
        return [
            ConnectorField(
                field_key=header,
                display_name=header.replace("_", " ").title(),
                source=str(self.path),
                license_policy="user_supplied",
                cache_policy="user_local_file",
                entitlement=entitlement_from_policy("user_supplied_local_file"),
            )
            for header in headers
        ]

    def preview(self, limit: int = 5) -> ConnectorPreview:
        health = self.test_connection()
        if health.status != "available":
            return ConnectorPreview(
                connector_id=self.connector_id,
                warnings=[health.message],
            )

        rows: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader):
                if index >= limit:
                    break
                rows.append(dict(row))
        return ConnectorPreview(connector_id=self.connector_id, rows=rows)

    def read_latest(
        self,
        *,
        entity_id: str,
        field_keys: list[str],
        entity_column: str = "ticker",
    ) -> dict[str, Any]:
        health = self.test_connection()
        if health.status != "available":
            return {}

        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get(entity_column) == entity_id:
                    return {key: row.get(key) for key in field_keys}
        return {}

    def explain_missing(self, field_key: str, entity_id: str | None = None) -> str:
        health = self.test_connection()
        if health.status != "available":
            return health.message
        subject = f" for {entity_id}" if entity_id else ""
        return f"{field_key}{subject} was not present in the local CSV."


class SkeletonConnector(VizaConnector):
    def __init__(
        self,
        *,
        connector_id: str,
        display_name: str,
        source_type: str,
        description: str,
        env_var: str | None = None,
        public_without_credentials: bool = False,
        license_policy: str = "source_terms_required",
        cache_policy: str = "cache_policy_unset",
    ) -> None:
        self.connector_id = connector_id
        self.display_name = display_name
        self.source_type = source_type
        self.description = description
        self.env_var = env_var
        self.public_without_credentials = public_without_credentials
        self.license_policy = license_policy
        self.cache_policy = cache_policy

    def definition(self) -> ConnectorDefinition:
        credential_store = EnvironmentCredentialStore()
        credential_required = bool(self.env_var)
        credential = credential_store.describe_requirement(
            self.connector_id,
            f"{self.connector_id}_credential",
            f"{self.display_name} credential",
            required=credential_required,
            env_var=self.env_var,
        )
        status = self._status(credential)
        entitlement = entitlement_from_policy(
            "public_source"
            if self.public_without_credentials
            else "credential_required_no_export"
            if credential_required
            else "connector_not_configured"
        )
        return ConnectorDefinition(
            connector_id=self.connector_id,
            display_name=self.display_name,
            source_type=self.source_type,
            status=status,
            description=self.description,
            capabilities=[
                "test_connection",
                "list_fields",
                "get_lineage",
                "explain_missing",
            ],
            credential_requirements=[credential] if credential_required else [],
            license_policy=self.license_policy,
            cache_policy=self.cache_policy,
            entitlement=entitlement,
            diagnostics={"implemented": False, "env_var": self.env_var},
        )

    def test_connection(self) -> ConnectorHealth:
        definition = self.definition()
        credential_required = any(
            credential.required for credential in definition.credential_requirements
        )
        credential_configured = all(
            not credential.required or credential.configured
            for credential in definition.credential_requirements
        )
        credential_mode = (
            definition.credential_requirements[0].storage
            if definition.credential_requirements
            else "none"
        )
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=definition.status,
            message=(
                f"{self.display_name} connector is registered but not implemented yet."
                if definition.status != "available"
                else f"{self.display_name} credential is configured; data reads are not implemented yet."
            ),
            credential_required=credential_required,
            credential_configured=credential_configured,
            credential_mode=credential_mode,
            query_allowed=definition.entitlement.query_allowed,
            cache_allowed=definition.entitlement.local_cache_allowed,
            display_allowed=definition.entitlement.derived_value_allowed,
            export_allowed=definition.entitlement.export_allowed,
            redistribution_allowed=definition.entitlement.redistribution_allowed,
            diagnostics=definition.diagnostics,
        )

    def list_fields(self, registry: AttributeRegistry | None = None) -> list[ConnectorField]:
        return []

    def preview(self, limit: int = 5) -> ConnectorPreview:
        health = self.test_connection()
        return ConnectorPreview(connector_id=self.connector_id, warnings=[health.message])

    def _status(self, credential: CredentialRequirement) -> str:
        if self.public_without_credentials:
            return "registered"
        if credential.required and not credential.configured:
            return "credential_required"
        return "registered"


def load_connector_catalog(
    registry: AttributeRegistry | None = None,
) -> list[ConnectorDefinition]:
    active_registry = registry if registry is not None else load_attribute_registry()
    return [
        connector.definition()
        for connector in _connectors(active_registry).values()
    ]


def get_connector(connector_id: str) -> VizaConnector:
    connectors = _connectors()
    if connector_id not in connectors:
        raise KeyError(f"unknown VIZA connector: {connector_id}")
    return connectors[connector_id]


def test_connector_connection(connector_id: str) -> ConnectorHealth:
    return get_connector(connector_id).test_connection()


def list_connector_fields(
    connector_id: str,
    registry: AttributeRegistry | None = None,
) -> list[ConnectorField]:
    return get_connector(connector_id).list_fields(registry)


def preview_connector(connector_id: str, limit: int = 5) -> ConnectorPreview:
    return get_connector(connector_id).preview(limit=limit)


def connector_for_attribute(attribute: AttributeDefinition) -> ConnectorDefinition:
    connector_id = connector_id_for_attribute(attribute)
    return get_connector(connector_id).definition()


def connector_id_for_attribute(attribute: AttributeDefinition) -> str:
    source_type = attribute.source_type.lower()
    source = attribute.source.lower()
    if source_type == "local_csv":
        return "local_csv"
    if source_type in {"local_parquet", "parquet"}:
        return "local_parquet"
    if source_type in {"local_sqlite", "local_duckdb", "sqlite", "duckdb"}:
        return "local_sqlite_duckdb"
    if source_type in {"aat_postgres", "postgres"}:
        return "aat_postgres"
    if "fmp" in source or source_type == "fmp_paid_api":
        return "fmp"
    if "fred" in source:
        return "fred"
    if "edgar" in source or "sec" in source:
        return "sec_edgar"
    if "french" in source or "kenneth" in source:
        return "kenneth_french"
    return "local_viza_workspace"


def entitlement_for_attribute(attribute: AttributeDefinition) -> EntitlementPolicy:
    return entitlement_from_policy(attribute.entitlement_policy)


def entitlement_from_policy(policy_label: str) -> EntitlementPolicy:
    label = policy_label or "internal"
    normalized = label.lower()
    policy = EntitlementPolicy(policy_label=label)

    if "public" in normalized:
        policy.redistribution_allowed = True
        policy.attribution_required = True
    if "user_supplied" in normalized:
        policy.redistribution_allowed = False
    if "query_only" in normalized:
        policy.local_cache_allowed = False
        policy.raw_snapshot_allowed = False
        policy.export_allowed = False
        policy.limitations.append("Query-only source; raw snapshots and exports are restricted.")
    if "derived_only" in normalized:
        policy.raw_snapshot_allowed = False
        policy.limitations.append("Only derived values may be retained.")
    if "no_export" in normalized or "export_denied" in normalized:
        policy.export_allowed = False
        policy.limitations.append("Exports are not allowed by this source policy.")
    if "no_cache" in normalized or "cache_denied" in normalized:
        policy.local_cache_allowed = False
        policy.limitations.append("Local caching is not allowed by this source policy.")
    if "credential_required" in normalized or "api_key_required" in normalized:
        policy.user_credential_required = True
        policy.limitations.append("A user credential is required before querying this source.")
    if "organization_credential_required" in normalized:
        policy.organization_credential_required = True
        policy.limitations.append("An organization credential is required before querying this source.")
    if any(
        token in normalized
        for token in ["denied", "locked", "restricted", "unavailable", "license_required"]
    ):
        policy.query_allowed = False
        policy.local_cache_allowed = False
        policy.raw_snapshot_allowed = False
        policy.derived_value_allowed = False
        policy.export_allowed = False
        policy.limitations.append("The source is not currently queryable under this policy.")

    return policy


def build_connector_manifest(
    registry: AttributeRegistry,
    attribute_keys: list[str],
) -> dict[str, Any]:
    connectors_by_id: dict[str, dict[str, Any]] = {}
    for key in sorted(set(attribute_keys)):
        attribute = registry.get(key)
        if attribute is None:
            continue
        definition = connector_for_attribute(attribute)
        entry = connectors_by_id.setdefault(
            definition.connector_id,
            {
                "display_name": definition.display_name,
                "source_type": definition.source_type,
                "status": definition.status,
                "license_policy": definition.license_policy,
                "cache_policy": definition.cache_policy,
                "attribute_keys": [],
                "entitlement": definition.entitlement.model_dump(mode="json"),
            },
        )
        entry["attribute_keys"].append(key)
    return connectors_by_id


def redact_connector_settings(settings: dict[str, Any]) -> dict[str, Any]:
    secret_tokens = {"password", "secret", "token", "api_key", "apikey", "credential"}
    redacted: dict[str, Any] = {}
    for key, value in settings.items():
        normalized_key = key.lower().replace("-", "_")
        if any(token in normalized_key for token in secret_tokens):
            redacted[key] = "[redacted]"
        elif isinstance(value, dict):
            redacted[key] = redact_connector_settings(value)
        else:
            redacted[key] = value
    return redacted


def _connectors(registry: AttributeRegistry | None = None) -> dict[str, VizaConnector]:
    return {
        "local_viza_workspace": LocalWorkspaceConnector(),
        "local_csv": LocalCsvConnector(),
        "local_parquet": SkeletonConnector(
            connector_id="local_parquet",
            display_name="Local Parquet",
            source_type="local_parquet",
            description="Local parquet file connector skeleton.",
            license_policy="user_supplied",
            cache_policy="user_local_file",
        ),
        "local_sqlite_duckdb": SkeletonConnector(
            connector_id="local_sqlite_duckdb",
            display_name="Local SQLite/DuckDB",
            source_type="local_sqlite_duckdb",
            description="Local SQLite and DuckDB connector skeleton.",
            license_policy="user_supplied",
            cache_policy="user_local_database",
        ),
        "aat_postgres": SkeletonConnector(
            connector_id="aat_postgres",
            display_name="AAT Postgres",
            source_type="aat_postgres",
            description="Existing AAT database connector skeleton.",
            env_var="AAT_DATABASE_URL",
            license_policy="internal_aat",
            cache_policy="database_query",
        ),
        "kenneth_french": SkeletonConnector(
            connector_id="kenneth_french",
            display_name="Kenneth French Data Library",
            source_type="public_research",
            description="Public Kenneth French factor data connector skeleton.",
            public_without_credentials=True,
            license_policy="public_source_terms",
            cache_policy="public_cache_allowed",
        ),
        "sec_edgar": SkeletonConnector(
            connector_id="sec_edgar",
            display_name="SEC EDGAR",
            source_type="public_filings",
            description="Public SEC EDGAR filings connector skeleton.",
            public_without_credentials=True,
            license_policy="public_source_terms",
            cache_policy="public_cache_allowed",
        ),
        "fred": SkeletonConnector(
            connector_id="fred",
            display_name="FRED",
            source_type="public_macro",
            description="FRED public macro data connector skeleton.",
            public_without_credentials=True,
            license_policy="public_source_terms",
            cache_policy="public_cache_allowed",
        ),
        "fmp": SkeletonConnector(
            connector_id="fmp",
            display_name="Financial Modeling Prep",
            source_type="paid_api",
            description="FMP paid API connector skeleton.",
            env_var="FMP_API_KEY",
            license_policy="paid_api_terms",
            cache_policy="provider_terms_required",
        ),
    }


def _connector_settings(connector_id: str) -> dict[str, Any]:
    try:
        from viza.project_store import get_project_store

        record = get_project_store().get_connector_configuration(connector_id)
        return record.settings if record is not None else {}
    except Exception:
        return {}


def _existing_workspace_paths() -> list[str]:
    paths = [
        resolve_config_path("viza_attribute_registry.json"),
        *default_universe_config_paths(),
    ]
    return [
        display_config_path(path)
        for path in paths
        if path.exists()
    ]


def _read_csv_headers(path: Path) -> list[str]:
    if not path or not path.exists() or not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return [header for header in next(reader) if header]
        except StopIteration:
            return []

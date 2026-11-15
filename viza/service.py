from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from viza.audit import (
    ReproduceRunRequest,
    ReproduceRunResult,
    compare_manifests,
)
from viza.attribute_registry import AttributeRegistry, load_attribute_registry
from viza.batch import BatchExecutionRequest, BatchExecutionResult, execute_batch
from viza.connectors import (
    ConnectorDefinition,
    ConnectorField,
    ConnectorHealth,
    ConnectorPreview,
    list_connector_fields,
    load_connector_catalog,
    preview_connector,
    test_connector_connection,
)
from viza.credentials import CredentialRef, CredentialSetRequest, CredentialStatus, CredentialStore
from viza.diagnostics import RuntimeDiagnostics, collect_runtime_diagnostics
from viza.equity.preview import (
    EquityPreviewReplayRequest,
    EquityRuntimeWedgePreviewRequest,
    build_equity_runtime_wedge_preview,
    equity_runtime_wedge_status_payload,
    get_equity_preview_run_detail,
    list_equity_preview_runs,
    replay_equity_preview_run,
)
from viza.equity.package_export import (
    EquityPreviewPackageDraftRequest,
    export_equity_preview_package_draft,
)
from viza.equity.registry import EquityRegistryError
from viza.equity.text.service import (
    FinanceTextSentimentResolveRequest,
    finance_text_sentiment_status_payload,
    get_finance_text_sentiment_cache_payload,
    replay_finance_text_sentiment_endpoint,
    resolve_finance_text_sentiment_endpoint,
)
from viza.execution import MethodologyRunResult, run_methodology
from viza.exports import ExportRequest, ExportResult, export_payload
from viza.assets import (
    AssetReconcileRequest,
    AssetResolveRequest,
    AssetResolveResult,
    VizaAsset,
    get_asset_store,
)
from viza.entities import (
    EntityRelationshipRecord,
    EntityResolveRequest,
    EntityResolveResult,
    VizaEntity,
    get_entity_store,
)
from viza.events import (
    EventExtractRequest,
    EventQueryRequest,
    EventQueryResult,
    ManualEventRequest,
    VizaEvent,
    event_from_manual_request,
    extract_events_from_run_result,
    get_event_store,
    load_event_registry,
)
from viza.file_format import inspect_viza_container, read_viza_manifest
from viza.file_format.export import export_methodology_graph_to_viza
from viza.file_format.import_ import import_viza_methodology_graph
from viza.file_format.models import (
    VizaFileError,
    VizaFileExportRequest,
    VizaFileExportResponse,
    VizaFileImportRequest,
    VizaFileImportResponse,
    VizaFilePathRequest,
    VizaFileQuarantineRequest,
    VizaFileQuarantineResponse,
    VizaFileRecordResponse,
    VizaFileSectionsResponse,
    VizaFileManifest,
    VizaFileVisualization,
    VizaInspectionResult,
    SectionStatus,
    VizaValidationResult,
)
from viza.file_format.visualization import build_file_visualization
from viza.graph_schema import MethodologyGraph, VizaNodeType
from viza.insights import (
    InsightExtractRequest,
    InsightQueryRequest,
    InsightQueryResult,
    VizaInsight,
    extract_insights_from_run_result,
    get_insight_store,
    load_insight_registry,
)
from viza.insight_cards import InsightCardPayload, build_insight_cards_from_result
from viza.marketplace import source_rights_from_run_manifest
from viza.modules import (
    ModuleCompatibilityRequest,
    ModuleCompatibilityResult,
    ResolveNodeTypesRequest,
    ResolvedNodeType,
    VizaModuleManifest,
    get_module_registry,
)
from viza.observations import (
    ObservationIngestRequest,
    ObservationQueryRequest,
    ObservationQueryResult,
    VizaObservation,
    get_observation_store,
)
from viza.project_store import (
    AlertRecord,
    ConnectorConfigurationRecord,
    ConnectorConfigurationRequest,
    CreateAlertRequest,
    CreatorRecord,
    CreatorRecordRequest,
    CreateWatchlistRequest,
    MethodologyVersionDiff,
    MethodologyVersionRecord,
    MethodologyVersionSummary,
    ProjectCreateRequest,
    ProjectSummary,
    RunRecord,
    RunRecordSummary,
    SaveRadarOutputRequest,
    SaveMethodologyVersionRequest,
    SavedRadarOutputRecord,
    SavedRadarOutputSummary,
    UpdateWatchlistTickersRequest,
    WatchlistRecord,
    get_project_store,
)
from viza.relationships import (
    RelationshipQueryRequest,
    RelationshipQueryResult,
    query_relationships,
)
from viza.runtime_jobs import (
    RuntimeJobCreateRequest,
    RuntimeJobEvent,
    RuntimeJobRecord,
    RuntimeScheduleRecord,
    RuntimeScheduleRequest,
    get_runtime_job_store,
    start_runtime_job_background,
)
from viza.strategy_profiles import (
    StrategyProfileCloneRequest,
    StrategyProfileCreateRequest,
    StrategyProfileTemplateCatalog,
    StrategyProfileUpdateRequest,
    VizaStrategyProfile,
    get_strategy_profile_store,
    load_strategy_profile_templates,
)
from viza.translation import (
    TranslationBatchRequest,
    TranslationRequest,
    VizaTranslation,
    get_translation_store,
    translate_batch,
    translate_request,
)
from viza.universes import UniverseSummary, load_universe_summaries
from viza.validation_ledger import (
    ValidationCompareRequest,
    ValidationCompareResult,
    ValidationRecordRequest,
    ValidationReplayRequest,
    ValidationReplayResult,
    VizaValidationRecord,
    compare_validation_records,
    create_validation_record,
    get_validation_ledger_store,
    replay_validation_record,
)


app = FastAPI(title="VIZA Local Engine", version="0.2.0")


class RuntimeStatus(BaseModel):
    service: str = "viza-local-engine"
    mode: str = "local_prototype"
    database_required: bool = False
    data_sources: list[str] = Field(default_factory=list)
    connectors: list[str] = Field(default_factory=list)


class WatchlistRunRequest(BaseModel):
    graph: MethodologyGraph
    methodology_version_id: str | None = None


class ConnectorConfigureRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, str] = Field(default_factory=dict)
    project_id: str | None = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5175",
        "http://localhost:5175",
        "http://127.0.0.1:4174",
        "http://localhost:4174",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def validate_local_engine_token(request: Request) -> None:
    expected_token = os.getenv("VIZA_ENGINE_TOKEN")
    if not expected_token:
        return

    supplied_token = request.headers.get("x-viza-engine-token")
    if supplied_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid VIZA local engine token.")


@app.get("/health")
def health(_authorized: None = Depends(validate_local_engine_token)) -> dict[str, str]:
    return {"status": "ok", "service": "viza-local-engine"}


@app.get("/viza/runtime", response_model=RuntimeStatus)
def viza_runtime(_authorized: None = Depends(validate_local_engine_token)) -> RuntimeStatus:
    connectors = load_connector_catalog()
    return RuntimeStatus(
        data_sources=[
            "config/viza_attribute_registry.json",
            "config/mvp_universe.json",
            "config/pilot_sp500_universe.json",
            "phase_4_attribute_resolvers",
        ],
        connectors=[connector.connector_id for connector in connectors],
    )


@app.get("/viza/equity/runtime-wedge/status", response_model=dict[str, Any])
def viza_equity_runtime_wedge_status(
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    return equity_runtime_wedge_status_payload()


@app.post("/viza/equity/runtime-wedge/preview", response_model=dict[str, Any])
def viza_equity_runtime_wedge_preview(
    request: EquityRuntimeWedgePreviewRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    try:
        return build_equity_runtime_wedge_preview(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EquityRegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/viza/equity/runtime-wedge/runs", response_model=dict[str, Any])
def viza_equity_runtime_wedge_runs(
    limit: int = 25,
    offset: int = 0,
    target_entity_id: str | None = None,
    cik: str | None = None,
    ticker_alias: str | None = None,
    profile_id: str | None = None,
    status: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    try:
        return list_equity_preview_runs(
            limit=limit,
            offset=offset,
            target_entity_id=target_entity_id,
            cik=cik,
            ticker_alias=ticker_alias,
            profile_id=profile_id,
            status=status,
            created_after=created_after,
            created_before=created_before,
        ).model_dump(mode="json")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/viza/equity/runtime-wedge/runs/{run_id}", response_model=dict[str, Any])
def viza_equity_runtime_wedge_run_detail(
    run_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    try:
        return get_equity_preview_run_detail(run_id).model_dump(mode="json")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/equity/runtime-wedge/runs/{run_id}/replay", response_model=dict[str, Any])
def viza_equity_runtime_wedge_run_replay(
    run_id: str,
    request: EquityPreviewReplayRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    try:
        return replay_equity_preview_run(run_id, request).model_dump(mode="json")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/viza/equity/runtime-wedge/runs/{run_id}/package-draft", response_model=dict[str, Any])
def viza_equity_runtime_wedge_run_package_draft(
    run_id: str,
    request: EquityPreviewPackageDraftRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    try:
        return export_equity_preview_package_draft(run_id, request).model_dump(mode="json")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/viza/equity/text/sentiment/status", response_model=dict[str, Any])
def viza_equity_text_sentiment_status(
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    """Feature-flag status for the finance text sentiment resolver.

    Always responds; reveals only masked flag values. When flags are off, the
    resolve endpoint returns status='disabled' rather than 404.
    """
    return finance_text_sentiment_status_payload()


@app.post("/viza/equity/text/sentiment/resolve", response_model=dict[str, Any])
def viza_equity_text_sentiment_resolve(
    request: FinanceTextSentimentResolveRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    try:
        return resolve_finance_text_sentiment_endpoint(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/viza/equity/text/sentiment/cache/{cache_key}",
    response_model=dict[str, Any],
)
def viza_equity_text_sentiment_cache(
    cache_key: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    return get_finance_text_sentiment_cache_payload(cache_key)


@app.post(
    "/viza/equity/text/sentiment/runs/{run_id}/replay",
    response_model=dict[str, Any],
)
def viza_equity_text_sentiment_run_replay(
    run_id: str,
    cutoff_timestamp: str | None = None,
    package_mode: str = "output_only",
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, Any]:
    parsed_cutoff = None
    if cutoff_timestamp:
        try:
            parsed_cutoff = datetime.fromisoformat(cutoff_timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if package_mode not in {"white_box", "output_only", "marketplace_draft"}:
        raise HTTPException(status_code=422, detail=f"unknown package_mode={package_mode!r}")
    try:
        return replay_finance_text_sentiment_endpoint(
            run_id,
            cutoff_timestamp=parsed_cutoff,
            package_mode=package_mode,  # type: ignore[arg-type]
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/diagnostics", response_model=RuntimeDiagnostics)
def viza_diagnostics(
    _authorized: None = Depends(validate_local_engine_token),
) -> RuntimeDiagnostics:
    return collect_runtime_diagnostics(engine_version=app.version)


@app.get("/viza/attributes", response_model=AttributeRegistry)
def viza_attributes(_authorized: None = Depends(validate_local_engine_token)) -> AttributeRegistry:
    return load_attribute_registry()


@app.get("/viza/universes", response_model=list[UniverseSummary])
def viza_universes(_authorized: None = Depends(validate_local_engine_token)) -> list[UniverseSummary]:
    return load_universe_summaries()


@app.get("/viza/connectors", response_model=list[ConnectorDefinition])
def viza_connectors(
    _authorized: None = Depends(validate_local_engine_token),
) -> list[ConnectorDefinition]:
    return load_connector_catalog()


@app.get("/viza/connectors/{connector_id}/test", response_model=ConnectorHealth)
def viza_connector_test(
    connector_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> ConnectorHealth:
    try:
        return test_connector_connection(connector_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/connectors/{connector_id}/fields", response_model=list[ConnectorField])
def viza_connector_fields(
    connector_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[ConnectorField]:
    try:
        return list_connector_fields(connector_id, load_attribute_registry())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/connectors/{connector_id}/preview", response_model=ConnectorPreview)
def viza_connector_preview(
    connector_id: str,
    limit: int = 5,
    _authorized: None = Depends(validate_local_engine_token),
) -> ConnectorPreview:
    try:
        return preview_connector(connector_id, limit=max(0, min(limit, 50)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/connectors/{connector_id}/credentials", response_model=list[CredentialStatus])
def viza_connector_credentials(
    connector_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[CredentialStatus]:
    _require_connector_definition(connector_id)
    return _credential_statuses_for_connector(connector_id)


@app.post("/viza/connectors/{connector_id}/credentials", response_model=CredentialStatus)
def viza_connector_set_credential(
    connector_id: str,
    request: CredentialSetRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> CredentialStatus:
    definition = _require_connector_definition(connector_id)
    credential_store = CredentialStore()
    credential_ref = credential_store.set_secret(connector_id, request.key, request.value)
    status = credential_store.status_for_secret(
        connector_id,
        request.key,
        env_var=_credential_env_var(definition, request.key),
        required=_credential_required(definition, request.key),
    )
    _save_connector_configuration(
        connector_id,
        credential_refs=[credential_ref],
        credential_status=[status],
    )
    return status


@app.delete(
    "/viza/connectors/{connector_id}/credentials/{key}",
    response_model=list[CredentialStatus],
)
def viza_connector_delete_credential(
    connector_id: str,
    key: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[CredentialStatus]:
    _require_connector_definition(connector_id)
    CredentialStore().delete_secret(connector_id, key)
    existing = get_project_store().get_connector_configuration(connector_id)
    if existing is not None:
        _save_connector_configuration(
            connector_id,
            credential_refs=[
                credential_ref
                for credential_ref in existing.credential_refs
                if credential_ref.key != key
            ],
            credential_status=[
                status for status in _credential_statuses_for_connector(connector_id)
            ],
            settings=existing.settings,
            project_id=existing.project_id,
            replace_refs=True,
        )
    return _credential_statuses_for_connector(connector_id)


@app.post(
    "/viza/connectors/{connector_id}/configure",
    response_model=ConnectorConfigurationRecord,
)
def viza_connector_configure(
    connector_id: str,
    request: ConnectorConfigureRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> ConnectorConfigurationRecord:
    definition = _require_connector_definition(connector_id)
    credential_store = CredentialStore()
    credential_refs = [
        credential_store.set_secret(connector_id, key, value)
        for key, value in request.credentials.items()
    ]
    credential_status = [
        credential_store.status_for_secret(
            connector_id,
            key,
            env_var=_credential_env_var(definition, key),
            required=_credential_required(definition, key),
        )
        for key in request.credentials
    ]
    return _save_connector_configuration(
        connector_id,
        credential_refs=credential_refs,
        credential_status=credential_status,
        settings=request.settings,
        project_id=request.project_id,
    )


def _require_connector_definition(connector_id: str) -> ConnectorDefinition:
    connectors = {
        connector.connector_id: connector
        for connector in load_connector_catalog(load_attribute_registry())
    }
    if connector_id not in connectors:
        raise HTTPException(status_code=404, detail=f"unknown VIZA connector: {connector_id}")
    return connectors[connector_id]


def _credential_statuses_for_connector(connector_id: str) -> list[CredentialStatus]:
    definition = _require_connector_definition(connector_id)
    credential_store = CredentialStore()
    statuses_by_key = {
        status.key: status for status in credential_store.list_secret_status(connector_id)
    }
    for requirement in definition.credential_requirements:
        statuses_by_key[requirement.key] = credential_store.status_for_secret(
            connector_id,
            requirement.key,
            env_var=requirement.env_var,
            required=requirement.required,
        )
    return sorted(statuses_by_key.values(), key=lambda status: status.key)


def _save_connector_configuration(
    connector_id: str,
    *,
    credential_refs: list[CredentialRef],
    credential_status: list[CredentialStatus],
    settings: dict[str, Any] | None = None,
    project_id: str | None = None,
    replace_refs: bool = False,
) -> ConnectorConfigurationRecord:
    store = get_project_store()
    existing = store.get_connector_configuration(connector_id)
    existing_refs = [] if existing is None or replace_refs else existing.credential_refs
    refs_by_key = {credential_ref.key: credential_ref for credential_ref in existing_refs}
    refs_by_key.update({credential_ref.key: credential_ref for credential_ref in credential_refs})
    status_by_key = {
        status.key: status
        for status in (existing.credential_status if existing is not None else [])
    }
    status_by_key.update({status.key: status for status in credential_status})
    if credential_status:
        for status in _credential_statuses_for_connector(connector_id):
            status_by_key[status.key] = status
    return store.save_connector_configuration(
        connector_id,
        ConnectorConfigurationRequest(
            project_id=project_id if project_id is not None else existing.project_id if existing else None,
            settings=settings if settings is not None else existing.settings if existing else {},
            credential_refs=sorted(refs_by_key.values(), key=lambda ref: ref.key),
            credential_status=sorted(status_by_key.values(), key=lambda status: status.key),
        ),
    )


def _credential_env_var(definition: ConnectorDefinition, key: str) -> str | None:
    for requirement in definition.credential_requirements:
        if requirement.key == key:
            return requirement.env_var
    return None


def _credential_required(definition: ConnectorDefinition, key: str) -> bool:
    return any(
        requirement.key == key and requirement.required
        for requirement in definition.credential_requirements
    )


@app.get("/viza/modules", response_model=list[VizaModuleManifest])
def viza_modules(
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaModuleManifest]:
    return get_module_registry().list_modules()


@app.get("/viza/modules/{module_id}", response_model=VizaModuleManifest)
def viza_module(
    module_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaModuleManifest:
    try:
        return get_module_registry().get_module(module_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/modules/resolve-node-types", response_model=list[ResolvedNodeType])
def viza_resolve_module_node_types(
    request: ResolveNodeTypesRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[ResolvedNodeType]:
    registry = get_module_registry()
    return [registry.resolve_node_type(type_id) for type_id in request.type_ids]


@app.post("/viza/modules/check-compatibility", response_model=list[ModuleCompatibilityResult])
def viza_check_module_compatibility(
    request: ModuleCompatibilityRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[ModuleCompatibilityResult]:
    return get_module_registry().check_compatibility(request.required_modules)


@app.get("/viza/projects", response_model=list[ProjectSummary])
def viza_projects(
    _authorized: None = Depends(validate_local_engine_token),
) -> list[ProjectSummary]:
    store = get_project_store()
    store.ensure_default_project()
    return store.list_projects()


@app.post("/viza/projects", response_model=ProjectSummary)
def viza_create_project(
    request: ProjectCreateRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> ProjectSummary:
    return get_project_store().create_project(request)


@app.get("/viza/projects/default", response_model=ProjectSummary)
def viza_default_project(
    _authorized: None = Depends(validate_local_engine_token),
) -> ProjectSummary:
    return get_project_store().ensure_default_project()


@app.get("/viza/creators", response_model=list[CreatorRecord])
def viza_creators(
    _authorized: None = Depends(validate_local_engine_token),
) -> list[CreatorRecord]:
    return get_project_store().list_creator_records()


@app.post("/viza/creators", response_model=CreatorRecord)
def viza_save_creator(
    request: CreatorRecordRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> CreatorRecord:
    return get_project_store().save_creator_record(request)


@app.get("/viza/creators/{creator_id}", response_model=CreatorRecord)
def viza_creator(
    creator_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> CreatorRecord:
    try:
        return get_project_store().require_creator_record(creator_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/entities/search", response_model=list[VizaEntity])
def viza_entities_search(
    q: str = "",
    limit: int = 25,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaEntity]:
    store = get_entity_store()
    if not store.search_entities("", limit=1):
        store.seed_local_universe()
    return store.search_entities(q, limit=max(1, min(limit, 100)))


@app.post("/viza/entities/resolve", response_model=EntityResolveResult)
def viza_entities_resolve(
    request: EntityResolveRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> EntityResolveResult:
    store = get_entity_store()
    if request.ticker and store.get_entity(f"entity-us-equity-{request.ticker.upper()}") is None:
        store.seed_local_universe()
    return store.resolve_entity(request)


@app.get("/viza/entities/{entity_id}", response_model=VizaEntity)
def viza_entity(
    entity_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaEntity:
    try:
        return get_entity_store().require_entity(entity_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/entities/{entity_id}/relationships", response_model=list[EntityRelationshipRecord])
def viza_entity_relationships(
    entity_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[EntityRelationshipRecord]:
    return get_entity_store().relationships_for_entity(entity_id)


@app.get("/viza/assets/search", response_model=list[VizaAsset])
def viza_assets_search(
    q: str = "",
    limit: int = 25,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaAsset]:
    store = get_asset_store()
    if not store.search_assets("", limit=1):
        store.seed_local_universe()
    return store.search_assets(q, limit=max(1, min(limit, 100)))


@app.post("/viza/assets/resolve", response_model=AssetResolveResult)
def viza_assets_resolve(
    request: AssetResolveRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> AssetResolveResult:
    store = get_asset_store()
    if request.ticker and store.get_asset(f"asset-us-equity-{request.ticker.upper()}") is None:
        store.seed_local_universe()
    return store.resolve_asset(request)


@app.get("/viza/assets/{asset_id}", response_model=VizaAsset)
def viza_asset(
    asset_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaAsset:
    try:
        return get_asset_store().require_asset(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/assets/{asset_id}/identifiers", response_model=dict[str, str])
def viza_asset_identifiers(
    asset_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, str]:
    try:
        return get_asset_store().identifiers_for_asset(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/assets/reconcile", response_model=dict[str, list[str]])
def viza_assets_reconcile(
    request: AssetReconcileRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> dict[str, list[str]]:
    return get_asset_store().reconcile_provider_identifiers(request)


@app.post("/viza/observations/query", response_model=ObservationQueryResult)
def viza_observations_query(
    request: ObservationQueryRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> ObservationQueryResult:
    observations = get_observation_store().query_observations(request)
    return ObservationQueryResult(observations=observations)


@app.post("/viza/observations/ingest", response_model=list[VizaObservation])
def viza_observations_ingest(
    request: ObservationIngestRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaObservation]:
    try:
        return get_observation_store().ingest(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/viza/observations/{observation_id}", response_model=VizaObservation)
def viza_observation(
    observation_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaObservation:
    try:
        return get_observation_store().require_observation(observation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/events/extract", response_model=list[VizaEvent])
def viza_events_extract(
    request: EventExtractRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaEvent]:
    run_result_payload: dict[str, Any] | MethodologyRunResult | None = request.run_result
    if run_result_payload is None and request.graph is not None:
        run_result_payload = run_methodology(request.graph, load_attribute_registry())
    if run_result_payload is None:
        raise HTTPException(status_code=400, detail="event extraction requires graph or run_result")
    events = extract_events_from_run_result(
        run_result_payload,
        event_types=request.event_types,
        min_confidence=request.min_confidence,
        min_source_credibility=request.min_source_credibility,
        cutoff=request.cutoff,
    )
    if request.persist:
        store = get_event_store()
        events = [store.upsert_event(event) for event in events]
    return events


@app.post("/viza/events/query", response_model=EventQueryResult)
def viza_events_query(
    request: EventQueryRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> EventQueryResult:
    return EventQueryResult(events=get_event_store().query_events(request))


@app.post("/viza/events/manual", response_model=VizaEvent)
def viza_events_manual(
    request: ManualEventRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaEvent:
    registry = load_event_registry()
    if not registry.has_event_type(request.event_type):
        raise HTTPException(status_code=400, detail=f"unknown VIZA event type: {request.event_type}")
    return get_event_store().upsert_event(event_from_manual_request(request))


@app.get("/viza/events/{event_id}", response_model=VizaEvent)
def viza_event(
    event_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaEvent:
    try:
        return get_event_store().require_event(event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/insights/extract", response_model=list[VizaInsight])
def viza_insights_extract(
    request: InsightExtractRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaInsight]:
    run_result_payload: dict[str, Any] | MethodologyRunResult | None = request.run_result
    if run_result_payload is None and request.graph is not None:
        run_result_payload = run_methodology(request.graph, load_attribute_registry())
    if run_result_payload is None:
        raise HTTPException(status_code=400, detail="insight extraction requires graph or run_result")
    insights = extract_insights_from_run_result(
        run_result_payload,
        events=request.events or None,
        enabled_insight_types=request.enabled_insight_types,
        min_confidence=request.min_confidence,
        require_evidence_refs=request.require_evidence_refs,
        require_point_in_time_safe=request.require_point_in_time_safe,
        cutoff=request.cutoff,
        registry=load_insight_registry(),
    )
    if request.persist:
        store = get_insight_store()
        insights = [store.upsert_insight(insight) for insight in insights]
    return insights


@app.post("/viza/insights/query", response_model=InsightQueryResult)
def viza_insights_query(
    request: InsightQueryRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> InsightQueryResult:
    return InsightQueryResult(insights=get_insight_store().query_insights(request))


@app.get("/viza/insights/{insight_id}", response_model=VizaInsight)
def viza_insight(
    insight_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaInsight:
    try:
        return get_insight_store().require_insight(insight_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/strategy-profile-templates", response_model=StrategyProfileTemplateCatalog)
def viza_strategy_profile_templates(
    _authorized: None = Depends(validate_local_engine_token),
) -> StrategyProfileTemplateCatalog:
    return load_strategy_profile_templates()


@app.get("/viza/strategy-profiles", response_model=list[VizaStrategyProfile])
def viza_strategy_profiles(
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaStrategyProfile]:
    return get_strategy_profile_store().list_profiles()


@app.post("/viza/strategy-profiles", response_model=VizaStrategyProfile)
def viza_strategy_profile_create(
    request: StrategyProfileCreateRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaStrategyProfile:
    try:
        return get_strategy_profile_store().create_profile(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/viza/strategy-profiles/{profile_id}", response_model=VizaStrategyProfile)
def viza_strategy_profile_update(
    profile_id: str,
    request: StrategyProfileUpdateRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaStrategyProfile:
    try:
        return get_strategy_profile_store().update_profile(profile_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/strategy-profiles/{profile_id}/clone", response_model=VizaStrategyProfile)
def viza_strategy_profile_clone(
    profile_id: str,
    request: StrategyProfileCloneRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaStrategyProfile:
    try:
        return get_strategy_profile_store().clone_profile(profile_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/strategy-profiles/{profile_id}", response_model=VizaStrategyProfile)
def viza_strategy_profile(
    profile_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaStrategyProfile:
    try:
        return get_strategy_profile_store().require_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/translate", response_model=VizaTranslation)
def viza_translate(
    request: TranslationRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaTranslation:
    try:
        return translate_request(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/translate/batch", response_model=list[VizaTranslation])
def viza_translate_batch(
    request: TranslationBatchRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaTranslation]:
    try:
        return translate_batch(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/translations/{translation_id}", response_model=VizaTranslation)
def viza_translation(
    translation_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaTranslation:
    try:
        return get_translation_store().require_translation(translation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/validation/record", response_model=VizaValidationRecord)
def viza_validation_record_create(
    request: ValidationRecordRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaValidationRecord:
    try:
        return create_validation_record(request)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/viza/validation/{record_id}", response_model=VizaValidationRecord)
def viza_validation_record(
    record_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaValidationRecord:
    try:
        return get_validation_ledger_store().require_record(record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/validation/by-run/{run_id}", response_model=list[VizaValidationRecord])
def viza_validation_records_by_run(
    run_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaValidationRecord]:
    return get_validation_ledger_store().list_by_run(run_id)


@app.post("/viza/validation/compare", response_model=ValidationCompareResult)
def viza_validation_compare(
    request: ValidationCompareRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> ValidationCompareResult:
    try:
        return compare_validation_records(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/validation/replay", response_model=ValidationReplayResult)
def viza_validation_replay(
    request: ValidationReplayRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> ValidationReplayResult:
    try:
        return replay_validation_record(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/viza/projects/{project_id}/methodology-versions",
    response_model=list[MethodologyVersionSummary],
)
def viza_project_methodology_versions(
    project_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[MethodologyVersionSummary]:
    try:
        return get_project_store().list_project_versions(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/viza/projects/{project_id}/methodology-versions",
    response_model=MethodologyVersionRecord,
)
def viza_save_methodology_version(
    project_id: str,
    request: SaveMethodologyVersionRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> MethodologyVersionRecord:
    try:
        return get_project_store().save_methodology_version(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/viza/methodologies/{methodology_id}/versions",
    response_model=list[MethodologyVersionSummary],
)
def viza_methodology_versions(
    methodology_id: str,
    project_id: str | None = None,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[MethodologyVersionSummary]:
    return get_project_store().list_methodology_versions(
        methodology_id,
        project_id=project_id,
    )


@app.get(
    "/viza/methodologies/{methodology_id}/versions/compare",
    response_model=MethodologyVersionDiff,
)
def viza_compare_methodology_versions(
    methodology_id: str,
    left_version_id: str = Query(min_length=1),
    right_version_id: str = Query(min_length=1),
    _authorized: None = Depends(validate_local_engine_token),
) -> MethodologyVersionDiff:
    try:
        return get_project_store().compare_versions(
            methodology_id,
            left_version_id,
            right_version_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/viza/methodologies/{methodology_id}/versions/{version_id}",
    response_model=MethodologyVersionRecord,
)
def viza_methodology_version(
    methodology_id: str,
    version_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> MethodologyVersionRecord:
    try:
        return get_project_store().require_methodology_version(methodology_id, version_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/projects/{project_id}/runs", response_model=list[RunRecordSummary])
def viza_project_runs(
    project_id: str,
    methodology_id: str | None = None,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[RunRecordSummary]:
    try:
        get_project_store().require_project(project_id)
        return get_project_store().list_run_records(
            project_id=project_id,
            methodology_id=methodology_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/runs/{run_id}", response_model=RunRecord)
def viza_run_record(
    run_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> RunRecord:
    try:
        return get_project_store().require_run_record(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/runs/{run_id}/insight-cards", response_model=list[InsightCardPayload])
def viza_run_insight_cards(
    run_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[InsightCardPayload]:
    try:
        record = get_project_store().require_run_record(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if record.result is None:
        return []
    return build_insight_cards_from_result(record.result)


@app.get(
    "/viza/projects/{project_id}/radars",
    response_model=list[SavedRadarOutputSummary],
)
def viza_project_radars(
    project_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[SavedRadarOutputSummary]:
    try:
        store = get_project_store()
        store.require_project(project_id)
        return store.list_radar_outputs(project_id=project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/viza/projects/{project_id}/radars",
    response_model=SavedRadarOutputRecord,
)
def viza_save_radar_output(
    project_id: str,
    request: SaveRadarOutputRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> SavedRadarOutputRecord:
    try:
        return get_project_store().save_radar_output(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/radars/{radar_id}", response_model=SavedRadarOutputRecord)
def viza_radar_output(
    radar_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> SavedRadarOutputRecord:
    try:
        return get_project_store().require_radar_output(radar_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/viza/projects/{project_id}/watchlists",
    response_model=list[WatchlistRecord],
)
def viza_project_watchlists(
    project_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[WatchlistRecord]:
    try:
        store = get_project_store()
        store.require_project(project_id)
        return store.list_watchlists(project_id=project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/viza/projects/{project_id}/watchlists",
    response_model=WatchlistRecord,
)
def viza_create_watchlist(
    project_id: str,
    request: CreateWatchlistRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> WatchlistRecord:
    try:
        return get_project_store().create_watchlist(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/watchlists/{watchlist_id}/tickers", response_model=WatchlistRecord)
def viza_update_watchlist_tickers(
    watchlist_id: str,
    request: UpdateWatchlistTickersRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> WatchlistRecord:
    try:
        return get_project_store().update_watchlist_tickers(watchlist_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/watchlists/{watchlist_id}/execute", response_model=MethodologyRunResult)
def viza_execute_watchlist(
    watchlist_id: str,
    request: WatchlistRunRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> MethodologyRunResult:
    try:
        store = get_project_store()
        watchlist = store.require_watchlist(watchlist_id)
        graph = _graph_with_ticker_subset(request.graph, watchlist.tickers)
        result = run_methodology(graph, load_attribute_registry())
        if watchlist.project_id is not None:
            store.save_run_record(
                result_payload=result.model_dump(mode="json"),
                project_id=watchlist.project_id,
                version_id=request.methodology_version_id,
            )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/viza/projects/{project_id}/alerts",
    response_model=list[AlertRecord],
)
def viza_project_alerts(
    project_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[AlertRecord]:
    try:
        store = get_project_store()
        store.require_project(project_id)
        return store.list_alerts(project_id=project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/viza/projects/{project_id}/alerts",
    response_model=AlertRecord,
)
def viza_create_alert(
    project_id: str,
    request: CreateAlertRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> AlertRecord:
    try:
        return get_project_store().create_alert(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/execute", response_model=MethodologyRunResult)
def viza_execute(
    graph: MethodologyGraph,
    project_id: str | None = None,
    methodology_version_id: str | None = None,
    _authorized: None = Depends(validate_local_engine_token),
) -> MethodologyRunResult:
    registry = load_attribute_registry()
    result = run_methodology(graph, registry)
    if project_id is not None:
        try:
            get_project_store().save_run_record(
                result_payload=result.model_dump(mode="json"),
                project_id=project_id,
                version_id=methodology_version_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@app.post("/viza/jobs", response_model=RuntimeJobRecord)
def viza_create_runtime_job(
    request: RuntimeJobCreateRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> RuntimeJobRecord:
    try:
        if request.project_id is not None:
            get_project_store().require_project(request.project_id)
        job = get_runtime_job_store().create_job(request)
        if request.start_immediately:
            start_runtime_job_background(job.job_id)
        return job
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/jobs/{job_id}", response_model=RuntimeJobRecord)
def viza_runtime_job(
    job_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> RuntimeJobRecord:
    try:
        return get_runtime_job_store().require_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/projects/{project_id}/jobs", response_model=list[RuntimeJobRecord])
def viza_project_runtime_jobs(
    project_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[RuntimeJobRecord]:
    try:
        get_project_store().require_project(project_id)
        return get_runtime_job_store().list_jobs(project_id=project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/jobs/{job_id}/cancel", response_model=RuntimeJobRecord)
def viza_cancel_runtime_job(
    job_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> RuntimeJobRecord:
    try:
        return get_runtime_job_store().request_cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/jobs/{job_id}/events", response_model=list[RuntimeJobEvent])
def viza_runtime_job_events(
    job_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[RuntimeJobEvent]:
    try:
        return get_runtime_job_store().list_events(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/viza/projects/{project_id}/schedules",
    response_model=RuntimeScheduleRecord,
)
def viza_save_runtime_schedule(
    project_id: str,
    request: RuntimeScheduleRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> RuntimeScheduleRecord:
    try:
        project_store = get_project_store()
        project_store.require_project(project_id)
        if request.radar_id:
            project_store.require_radar_output(request.radar_id)
        return get_runtime_job_store().save_schedule(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/viza/projects/{project_id}/schedules",
    response_model=list[RuntimeScheduleRecord],
)
def viza_project_runtime_schedules(
    project_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> list[RuntimeScheduleRecord]:
    try:
        get_project_store().require_project(project_id)
        return get_runtime_job_store().list_schedules(project_id=project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/exports", response_model=ExportResult)
def viza_export(
    request: ExportRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> ExportResult:
    return export_payload(request)


@app.post("/viza/files/inspect", response_model=VizaInspectionResult)
def viza_file_inspect(
    request: VizaFilePathRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaInspectionResult:
    inspection = inspect_viza_container(request.resolved_path())
    if inspection.status == "invalid":
        raise HTTPException(status_code=400, detail=inspection.errors)
    return inspection


@app.post("/viza/files/validate", response_model=VizaValidationResult)
def viza_file_validate(
    request: VizaFilePathRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaValidationResult:
    inspection = inspect_viza_container(request.resolved_path())
    return VizaValidationResult(
        valid=inspection.status != "invalid" and not inspection.errors,
        inspection=inspection,
    )


@app.post("/viza/files/export", response_model=VizaFileExportResponse)
def viza_file_export(
    request: VizaFileExportRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaFileExportResponse:
    try:
        graph = request.graph
        if graph is None and request.methodology_version_id and request.project_id:
            for version in get_project_store().list_project_versions(request.project_id):
                if version.version_id == request.methodology_version_id:
                    graph = get_project_store().require_methodology_version(
                        version.methodology_id,
                        version.version_id,
                    ).graph
                    break
        if graph is None:
            raise ValueError("file export requires graph or methodology_version_id")
        validation_record = None
        source_rights = list(request.source_rights)
        wants_validation_record = request.include_validation_proof or (
            request.purpose == "marketplace_draft" and request.run_id is not None
        )
        if wants_validation_record:
            if request.run_id is None:
                raise ValueError("validation proof export requires run_id")
            records = get_validation_ledger_store().list_by_run(request.run_id)
            if records:
                validation_record = records[0]
            if request.purpose == "marketplace_draft":
                try:
                    run_record = get_project_store().require_run_record(request.run_id)
                    source_rights.extend(source_rights_from_run_manifest(run_record.manifest))
                except KeyError:
                    pass
        result, manifest = export_methodology_graph_to_viza(
            graph,
            request.target_path,
            display_name=request.display_name,
            purpose=request.purpose,
            visibility=request.visibility,
            include_validation_proof=request.include_validation_proof,
            validation_record=validation_record,
            include_signal_outputs=request.include_signal_outputs,
            include_sample_outputs=request.include_sample_outputs,
            redact_parameters=request.redact_parameters,
            lock_sections=request.lock_sections,
            creator_id=request.creator_id,
            creator_display_name=request.creator_display_name,
            source_rights=source_rights,
            not_investment_advice_acknowledged=request.not_investment_advice_acknowledged,
        )
        export_record = None
        if request.project_id is not None:
            export_record = get_project_store().save_viza_file_export(
                file_id=result.file_id,
                manifest=manifest,
                target_path=request.target_path,
                project_id=request.project_id,
                container_checksum=result.container_checksum,
                manifest_checksum=result.manifest_checksum,
                purpose=request.purpose,
                visibility=request.visibility.value,
                warnings=result.warnings,
            )
        return VizaFileExportResponse(
            result=result,
            manifest=manifest,
            export_record=(
                export_record.model_dump(mode="json") if export_record is not None else None
            ),
        )
    except (OSError, ValueError, VizaFileError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/viza/files/import", response_model=VizaFileImportResponse)
def viza_file_import(
    request: VizaFileImportRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaFileImportResponse:
    source_path = request.path
    try:
        if request.mode not in {
            "open_without_import",
            "import_to_project",
            "fork_as_new_methodology",
            "quarantine",
        }:
            raise ValueError(f"unsupported VIZA file import mode: {request.mode}")
        warnings: list[str] = []
        container_checksum = None
        manifest_checksum = None
        if not source_path.endswith(".viza.json"):
            inspection = inspect_viza_container(source_path)
            if inspection.status == "invalid":
                raise HTTPException(status_code=400, detail=inspection.errors)
            warnings.extend(inspection.warnings)
            container_checksum = inspection.container_checksum
            manifest_checksum = inspection.manifest_checksum
            manifest_model = read_viza_manifest(source_path)
            _enforce_viza_import_permissions(manifest_model, request.mode)
            graph = None
            graph_descriptor = manifest_model.sections.get("methodology_graph")
            if graph_descriptor and graph_descriptor.status == SectionStatus.INCLUDED:
                graph = import_viza_methodology_graph(source_path)[0]
            elif request.mode in {"import_to_project", "fork_as_new_methodology"}:
                raise ValueError("methodology graph is not readable for this package")
            manifest = manifest_model.model_dump(mode="json", by_alias=True)
        else:
            graph, manifest = import_viza_methodology_graph(source_path)
        store = get_project_store()
        project_id = request.project_id
        if request.mode in {"import_to_project", "fork_as_new_methodology"} and project_id is None:
            project_id = store.ensure_default_project().project_id
        if request.mode == "fork_as_new_methodology":
            if graph is None:
                raise ValueError("fork requires a readable methodology graph")
            graph = _fork_imported_graph(graph)
        version_record = None
        should_save_version = request.save_methodology_version or request.mode in {
            "import_to_project",
            "fork_as_new_methodology",
        }
        if should_save_version:
            if graph is None:
                raise ValueError("saving imported methodology requires a readable graph")
            if project_id is None:
                project_id = store.ensure_default_project().project_id
            version_record = store.save_methodology_version(
                project_id,
                SaveMethodologyVersionRequest(
                    graph=graph,
                    label=request.label,
                    message=request.message,
                ),
            )

        import_record = None
        status = "opened_without_import"
        if request.mode != "open_without_import":
            status = (
                "quarantined"
                if request.mode == "quarantine"
                else "imported_legacy_graph_json"
                if source_path.endswith(".viza.json")
                else request.mode
            )
            import_record = store.save_viza_file_import(
                file_id=manifest["file_id"],
                manifest=manifest,
                source_path=source_path,
                project_id=project_id,
                container_checksum=container_checksum,
                manifest_checksum=manifest_checksum,
                status=status,
                warnings=warnings,
                quarantine_status="quarantined" if request.mode == "quarantine" else "none",
            )
        return VizaFileImportResponse(
            status=import_record.status if import_record is not None else status,
            source_path=source_path,
            manifest=manifest,
            graph=graph,
            import_record=(
                import_record.model_dump(mode="json") if import_record is not None else None
            ),
            methodology_version=(
                version_record.model_dump(mode="json") if version_record is not None else None
            ),
            warnings=warnings,
        )
    except HTTPException:
        raise
    except (OSError, ValueError, VizaFileError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/viza/files/{file_id}/visualization", response_model=VizaFileVisualization)
def viza_file_visualization(
    file_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaFileVisualization:
    try:
        manifest = VizaFileManifest.model_validate(
            get_project_store().latest_viza_file_manifest(file_id)
        )
        return build_file_visualization(manifest)
    except (KeyError, VizaFileError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/files", response_model=list[VizaFileRecordResponse])
def viza_file_records(
    _authorized: None = Depends(validate_local_engine_token),
) -> list[VizaFileRecordResponse]:
    return [
        VizaFileRecordResponse(
            file_id=record.file_id,
            imports=[item.model_dump(mode="json") for item in record.imports],
            exports=[item.model_dump(mode="json") for item in record.exports],
        )
        for record in get_project_store().list_viza_file_records()
    ]


@app.get("/viza/files/{file_id}/sections", response_model=VizaFileSectionsResponse)
def viza_file_sections(
    file_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaFileSectionsResponse:
    try:
        from viza.file_format.models import VizaFileManifest

        manifest = VizaFileManifest.model_validate(
            get_project_store().latest_viza_file_manifest(file_id)
        )
        return VizaFileSectionsResponse(file_id=file_id, sections=manifest.sections)
    except (KeyError, VizaFileError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/viza/files/{file_id}", response_model=VizaFileRecordResponse)
def viza_file_record(
    file_id: str,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaFileRecordResponse:
    try:
        record = get_project_store().require_viza_file_record(file_id)
        return VizaFileRecordResponse(
            file_id=record.file_id,
            imports=[item.model_dump(mode="json") for item in record.imports],
            exports=[item.model_dump(mode="json") for item in record.exports],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/files/quarantine", response_model=VizaFileQuarantineResponse)
def viza_file_quarantine(
    request: VizaFileQuarantineRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> VizaFileQuarantineResponse:
    try:
        updated = get_project_store().quarantine_viza_file(request.file_id, request.reason)
        return VizaFileQuarantineResponse(
            file_id=request.file_id,
            quarantine_status="quarantined",
            records_updated=updated,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/batch/execute", response_model=BatchExecutionResult)
def viza_batch_execute(
    request: BatchExecutionRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> BatchExecutionResult:
    registry = load_attribute_registry()
    store = get_project_store() if request.project_id is not None else None
    try:
        if store is not None:
            store.require_project(request.project_id or "")
        return execute_batch(request, registry, store=store)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/viza/reproduce", response_model=ReproduceRunResult)
def viza_reproduce_run(
    request: ReproduceRunRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> ReproduceRunResult:
    registry = load_attribute_registry()
    result = run_methodology(request.graph, registry)
    checks = compare_manifests(request.baseline_manifest, result.manifest)
    matching = all(check.status == "match" for check in checks)
    if request.project_id is not None:
        try:
            get_project_store().save_run_record(
                result_payload=result.model_dump(mode="json"),
                project_id=request.project_id,
                version_id=request.methodology_version_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReproduceRunResult(
        status="matched" if matching else "mismatch",
        matching=matching,
        checks=checks,
        result=result.model_dump(mode="json"),
    )


@app.post("/viza/relationships/query", response_model=RelationshipQueryResult)
def viza_relationships_query(
    request: RelationshipQueryRequest,
    _authorized: None = Depends(validate_local_engine_token),
) -> RelationshipQueryResult:
    registry = load_attribute_registry()
    return query_relationships(request, registry)


def _graph_with_ticker_subset(
    graph: MethodologyGraph,
    tickers: list[str],
) -> MethodologyGraph:
    payload = graph.model_dump(mode="json")
    for node in payload.get("nodes", []):
        if not isinstance(node, dict) or node.get("type") != VizaNodeType.UNIVERSE.value:
            continue
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        node["config"] = {**config, "ticker_subset": tickers}
    return MethodologyGraph.model_validate(payload)


def _enforce_viza_import_permissions(manifest: VizaFileManifest, mode: str) -> None:
    permissions = manifest.permissions
    if mode == "open_without_import" and permissions.get("open_allowed", True) is False:
        raise ValueError("VIZA package does not allow opening")
    if mode == "fork_as_new_methodology" and permissions.get("fork_allowed", True) is False:
        raise ValueError("VIZA package does not allow forking")
    if mode == "import_to_project" and permissions.get("export_allowed", True) is False:
        graph_section = manifest.sections.get("methodology_graph")
        if graph_section is None or graph_section.status != SectionStatus.INCLUDED:
            raise ValueError("VIZA package does not expose an importable graph")


def _fork_imported_graph(graph: MethodologyGraph) -> MethodologyGraph:
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = graph.model_dump(mode="json")
    payload["methodology_id"] = f"methodology-{uuid4()}"
    payload["name"] = f"{graph.name} Fork"
    payload["created_at"] = timestamp
    payload["updated_at"] = timestamp
    return MethodologyGraph.model_validate(payload)


@app.get("/viza/runs/{run_id}/decisions", response_model=dict[str, Any])
def viza_run_decisions(run_id: str) -> dict[str, Any]:
    """Return persisted DecisionFrame rows for a run.

    Phase B (sandbox-only). Each row is a deterministic, PIT-filtered
    decision emitted by the user's own DecisionRule on the strategy profile.
    The endpoint is read-only; replay-with-cutoff lives at the POST below.
    """
    from viza.decisions import get_decision_store

    decisions = get_decision_store().list_decisions_by_run(run_id)
    return {
        "run_id": run_id,
        "decisions": [decision.model_dump(mode="json") for decision in decisions],
        "count": len(decisions),
        "mode": "sandbox_replay",
        "not_investment_advice": True,
    }


class DecisionsReplayRequest(BaseModel):
    cutoff_timestamp: datetime


@app.get("/viza/runtime/live-mode-status", response_model=dict[str, Any])
def viza_runtime_live_mode_status() -> dict[str, Any]:
    """Report whether live decision mode is enabled in this engine process,
    plus the current disclosure text and version. Read-only; safe to poll
    from the desktop shell to decide whether to surface the live-mode toggle.
    """
    from viza.decisions import (
        LIVE_MODE_DISCLOSURE_TEXT,
        LIVE_MODE_DISCLOSURE_VERSION,
        LIVE_MODE_ENV_VAR,
    )

    enabled = os.environ.get(LIVE_MODE_ENV_VAR, "").strip().lower() == "true"
    return {
        "enabled": enabled,
        "env_var": LIVE_MODE_ENV_VAR,
        "disclosure_version": LIVE_MODE_DISCLOSURE_VERSION,
        "disclosure_text": LIVE_MODE_DISCLOSURE_TEXT,
        "non_advice_boundary": True,
    }


class LiveModeOptInRecordRequest(BaseModel):
    accepted_disclosure_version: str
    accepted_by_user: str = "self"


@app.post(
    "/viza/profiles/{profile_id}/live-mode-opt-in",
    response_model=dict[str, Any],
)
def viza_profile_live_mode_opt_in(
    profile_id: str,
    request: LiveModeOptInRecordRequest,
) -> dict[str, Any]:
    """Record (or refresh) a live-mode opt-in on a strategy profile.

    Returns the updated profile. The disclosure version MUST match the
    current engine's ``LIVE_MODE_DISCLOSURE_VERSION``; mismatched versions
    raise 422 so the client cannot back-date its acceptance against stale
    text.
    """
    from viza.decisions import LIVE_MODE_DISCLOSURE_VERSION
    from viza.strategy_profiles import (
        LiveModeOptIn,
        StrategyProfileUpdateRequest,
        get_strategy_profile_store,
    )

    if request.accepted_disclosure_version != LIVE_MODE_DISCLOSURE_VERSION:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "live_mode_disclosure_version_mismatch",
                "accepted_disclosure_version": request.accepted_disclosure_version,
                "current_disclosure_version": LIVE_MODE_DISCLOSURE_VERSION,
            },
        )

    store = get_strategy_profile_store()
    opt_in = LiveModeOptIn(
        accepted_at=datetime.now(timezone.utc),
        accepted_disclosure_version=request.accepted_disclosure_version,
        accepted_by_user=request.accepted_by_user,
    )
    updated = store.update_profile(
        profile_id,
        StrategyProfileUpdateRequest(
            live_mode_opt_in=opt_in,
            label="live-mode opt-in recorded",
            message=(
                f"live-mode opt-in accepted at {opt_in.accepted_at.isoformat()} "
                f"by {opt_in.accepted_by_user!r} for disclosure "
                f"{opt_in.accepted_disclosure_version!r}"
            ),
        ),
    )
    return updated.model_dump(mode="json", by_alias=True)


class LiveDecisionsRequest(BaseModel):
    graph_hash: str
    profile_version: str
    observation_ids: list[str] = Field(default_factory=list)
    run_id: str | None = None
    cutoff_timestamp: datetime | None = None
    persist: bool = True


@app.post(
    "/viza/profiles/{profile_id}/decisions/live",
    response_model=dict[str, Any],
)
def viza_profile_decisions_live(
    profile_id: str,
    request: LiveDecisionsRequest,
) -> dict[str, Any]:
    """Compile live-mode decisions for a profile against observations loaded
    from the local observation store.

    All four live-mode guards run before any decision is emitted:
    ``VIZA_LIVE_MODE_ENABLED=true``, profile opt-in present, opt-in
    disclosure version current, every enabled rule carries ``effective_from``
    at-or-before the cutoff. Failures surface as HTTP 422 with a structured
    detail body so the desktop can route the user to remediation.
    """
    from viza.decisions import (
        LiveModeDisabledError,
        LiveModeOptInRequiredError,
        LiveModeOptInStaleError,
        LiveModeRuleEffectiveDateRequiredError,
        emit_and_persist_decisions,
    )
    from viza.observations import get_observation_store
    from viza.strategy_profiles import get_strategy_profile_store

    profile = get_strategy_profile_store().require_profile(profile_id)
    observation_store = get_observation_store()
    observations = [
        observation_store.require_observation(observation_id)
        for observation_id in request.observation_ids
    ]
    cutoff = request.cutoff_timestamp or datetime.now(timezone.utc)
    run_id = request.run_id or f"run-live-{uuid4()}"

    try:
        decisions, record = emit_and_persist_decisions(
            profile=profile,
            observations=observations,
            cutoff_timestamp=cutoff,
            run_id=run_id,
            graph_hash=request.graph_hash,
            profile_version=request.profile_version,
            persist=request.persist,
            mode="live",
        )
    except (
        LiveModeDisabledError,
        LiveModeOptInRequiredError,
        LiveModeOptInStaleError,
        LiveModeRuleEffectiveDateRequiredError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": type(exc).__name__, "message": str(exc)},
        ) from exc

    return {
        "run_id": run_id,
        "cutoff_timestamp": cutoff.isoformat(),
        "decisions": [decision.model_dump(mode="json") for decision in decisions],
        "count": len(decisions),
        "mode": "live",
        "validation_record_id": record.validation_record_id,
        "not_investment_advice": True,
    }


class DecisionsBacktestRequest(BaseModel):
    graph_hash: str
    profile_version: str
    observation_ids: list[str] = Field(default_factory=list)
    cutoffs: list[datetime] = Field(default_factory=list)
    run_id_prefix: str = "backtest"


@app.post(
    "/viza/profiles/{profile_id}/decisions/backtest",
    response_model=dict[str, Any],
)
def viza_profile_decisions_backtest(
    profile_id: str,
    request: DecisionsBacktestRequest,
) -> dict[str, Any]:
    """Run a sandbox-only backtest of a profile's DecisionRules across a
    series of cutoffs. Returns a summary report (by rule, by entity, plus
    the full decision list). Refuses live mode by construction — backtesting
    is inherently sandbox replay."""
    from viza.decisions_backtesting import (
        BacktestRequest,
        report_for_export,
        run_decisions_backtest,
    )
    from viza.observations import get_observation_store
    from viza.strategy_profiles import get_strategy_profile_store

    profile = get_strategy_profile_store().require_profile(profile_id)
    observation_store = get_observation_store()
    observations = [
        observation_store.require_observation(observation_id)
        for observation_id in request.observation_ids
    ]

    report = run_decisions_backtest(
        BacktestRequest(
            profile=profile,
            observations=observations,
            cutoffs=request.cutoffs,
            graph_hash=request.graph_hash,
            profile_version=request.profile_version,
            run_id_prefix=request.run_id_prefix,
        )
    )
    return report_for_export(report)


@app.post("/viza/runs/{run_id}/decisions/replay", response_model=dict[str, Any])
def viza_run_decisions_replay(
    run_id: str,
    request: DecisionsReplayRequest,
) -> dict[str, Any]:
    """Return persisted decisions whose triggering observations were all
    available at or before ``cutoff_timestamp``. Sandbox-only; the cutoff is
    a replay cutoff against stored decisions, not a live-mode trigger.

    A malformed ``pit_state`` row in the store surfaces as HTTP 422 (rather
    than silently disappearing from replay) so schema corruption is loud.
    """
    from viza.decisions import get_decision_store, replay_decisions_from_store

    try:
        decisions = replay_decisions_from_store(
            store=get_decision_store(),
            run_id=run_id,
            cutoff_timestamp=request.cutoff_timestamp,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "run_id": run_id,
        "cutoff_timestamp": request.cutoff_timestamp.isoformat(),
        "decisions": [decision.model_dump(mode="json") for decision in decisions],
        "count": len(decisions),
        "mode": "sandbox_replay",
        "not_investment_advice": True,
    }


# ---- Phase 35: HTTP API for the Phases 26-33 surface ---------------------


class RadarAssembleRequest(BaseModel):
    """Body for /viza/radar/assemble. Accepts a free-form set of decisions
    and ranking rows the caller has already produced (via /viza/runs/.../decisions
    or the methodology engine) plus an OutputRadarConfig payload."""

    model_config = {"extra": "forbid"}

    decisions: list[dict[str, Any]] = Field(default_factory=list)
    ranking_rows: list[dict[str, Any]] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


@app.get("/viza/commands/taxonomy", response_model=dict[str, Any])
def viza_commands_taxonomy() -> dict[str, Any]:
    """Return the command taxonomy registry. The desktop UI loads this on
    boot to populate the command-name labels in the radar; external tooling
    uses it to discover which command IRIs the engine recognizes."""
    from viza.commands import get_command_taxonomy

    taxonomy = get_command_taxonomy()
    return taxonomy.model_dump(mode="json", by_alias=True)


@app.get("/viza/commands/conflicts", response_model=dict[str, Any])
def viza_commands_conflicts() -> dict[str, Any]:
    """Return the command conflict registry (attack edges + unconditional
    defeats). Used by audit tools to inspect which commands attack which."""
    from viza.commands import get_command_conflicts

    return get_command_conflicts().model_dump(mode="json", by_alias=True)


@app.post("/viza/radar/assemble", response_model=dict[str, Any])
def viza_radar_assemble(request: RadarAssembleRequest) -> dict[str, Any]:
    """Assemble an OutputRadarView from decisions + ranking rows.

    The engine accepts decision payloads as JSON dicts (matching DecisionFrame)
    and ranking rows as RadarRow dicts; both shapes round-trip through their
    Pydantic models. The configuration mirrors `OutputRadarConfig`.
    """
    from viza.decisions import DecisionFrame
    from viza.execution import RadarRow
    from viza.radar import assemble_output_radar, parse_output_radar_config

    try:
        config = parse_output_radar_config(request.config)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid radar config: {exc}") from exc

    try:
        decisions = [DecisionFrame.model_validate(item) for item in request.decisions]
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid decision payload: {exc}") from exc

    try:
        ranking_rows = [RadarRow.model_validate(item) for item in request.ranking_rows]
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid ranking row: {exc}") from exc

    view = assemble_output_radar(
        config=config, ranking_rows=ranking_rows, decisions=decisions
    )
    return view.model_dump(mode="json", by_alias=True)


@app.get("/viza/provenance/walk", response_model=dict[str, Any])
def viza_provenance_walk(
    root_iri: str = Query(..., description="The IRI to walk outgoing PROV edges from"),
    max_hops: int = Query(16, ge=1, le=64),
) -> dict[str, Any]:
    """Walk the local PROV graph from `root_iri` over outgoing edges,
    returning the bounded set of edges and reachable IRIs. Used by the
    desktop 'where did this come from?' inspector."""
    from viza.provenance import query_provenance

    walk = query_provenance(root_iri, max_hops=max_hops)
    return walk.model_dump(mode="json", by_alias=True)


@app.get(
    "/viza/strategy-profiles/{strategy_profile_id}/dmn-export",
    response_model=dict[str, Any],
)
def viza_strategy_profile_dmn_export(strategy_profile_id: str) -> dict[str, Any]:
    """Export the strategy profile as DMN 1.5 XML.

    Returns a JSON envelope `{ "xml": "...", "schema": "DMN/20211108" }` so
    HTTP-aware tooling can transport the bytes; the XML is serialized as a
    string rather than a binary response.
    """
    from viza.dmn_export import export_strategy_profile_as_dmn
    from viza.strategy_profiles import get_strategy_profile_store

    try:
        profile = get_strategy_profile_store().require_profile(strategy_profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    xml = export_strategy_profile_as_dmn(profile)
    return {
        "strategy_profile_id": strategy_profile_id,
        "schema": "DMN/20211108",
        "xml": xml,
    }


def main() -> None:
    import uvicorn

    host = os.getenv("VIZA_ENGINE_HOST", "127.0.0.1")
    port = int(os.getenv("VIZA_ENGINE_PORT", "8765"))
    uvicorn.run("viza.service:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

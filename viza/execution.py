from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from pydantic import model_validator

from viza.audit import (
    connector_states_from_manifest,
    data_versions_from_evidence,
    entitlement_states_from_manifest,
    evidence_checksum,
    normalize_evidence_records,
    result_checksum,
    stable_checksum,
)
from viza.attribute_resolvers import AttributeValue, resolve_attribute_values
from viza.attribute_registry import AttributeRegistry
from viza.assets import resolve_static_asset_identity
from viza.connectors import (
    build_connector_manifest,
    connector_for_attribute,
    entitlement_for_attribute,
)
from viza.graph_schema import MethodologyGraph, VizaEdgeType, VizaNodeType
from viza.insights import VizaInsight, extract_insights_from_run_result
from viza.runtime import ExecutionPlan, compile_execution_plan, hash_methodology_graph
from viza.translation import VizaTranslation, default_strategy_profile, translate_insight
from viza.universes import UniverseDefinition, UniverseSecurity, load_universe_definition


class VizaExecutionStatus(StrEnum):
    COMPLETED = "completed"
    NOT_IMPLEMENTED = "not_implemented"
    FAILED = "failed"


class ExecutionWarning(BaseModel):
    code: str
    message: str
    node_id: str | None = None
    severity: str = "warning"


class RadarRow(BaseModel):
    ticker: str
    company_name: str | None = None
    entity_id: str | None = None
    asset_id: str | None = None
    score: float | None = None
    rank: int | None = None
    attributes: dict[str, float | str | bool | None] = Field(default_factory=dict)
    strategy_fit_score: float | None = None
    primary_insight_type: str | None = None
    translated_summary: str | None = None
    confidence: float | None = None
    horizon: dict[str, str] | None = None
    missing_confirmations: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    source_restrictions: list[str] = Field(default_factory=list)
    PIT_status: str | None = None
    warnings: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RelationshipEdge(BaseModel):
    relationship_id: str | None = None
    source: str
    target: str
    source_id: str | None = None
    source_type: str | None = None
    target_id: str | None = None
    target_type: str | None = None
    family: str | None = None
    relationship_type: str
    relationship_family: str = "unknown"
    weight: float | None = None
    direction: str = "outbound"
    confidence: float | None = None
    time_horizon: str | None = None
    observed_at: str | None = None
    available_at: str | None = None
    timestamp_available: str | None = None
    evidence_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    rights_policy: dict[str, Any] = Field(default_factory=dict)
    module_id: str | None = None
    source_lineage: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_universal_fields(self) -> "RelationshipEdge":
        if self.relationship_id is None:
            self.relationship_id = "rel-" + stable_checksum(
                {
                    "source": self.source,
                    "target": self.target,
                    "relationship_type": self.relationship_type,
                    "relationship_family": self.relationship_family,
                    "evidence_ref": self.evidence_ref,
                }
            )[:24]
        if self.source_id is None:
            self.source_id = self.source
        if self.target_id is None:
            self.target_id = self.target
        if self.source_type is None:
            self.source_type = _relationship_object_type(self.source)
        if self.target_type is None:
            self.target_type = _relationship_object_type(self.target)
        if self.family is None:
            self.family = _relationship_family(self.relationship_type, self.relationship_family)
        if self.available_at is None:
            self.available_at = self.timestamp_available
        if not self.evidence_refs and self.evidence_ref is not None:
            self.evidence_refs = [self.evidence_ref]
        return self


def _relationship_object_type(reference: str) -> str:
    if reference.startswith("insight:"):
        return "insight"
    if reference.startswith("event:"):
        return "event"
    if reference.startswith("asset:"):
        return "asset"
    if reference.startswith("company:") or reference.startswith("entity-"):
        return "entity"
    if reference.startswith("attr:") or reference.startswith("attribute:"):
        return "attribute"
    if reference.startswith("evidence:attr:"):
        return "attribute"
    if reference.startswith("strategy_profile:") or reference.startswith("strategy-profile:"):
        return "strategy_profile"
    if reference.startswith("output:"):
        return "output"
    if reference.startswith("sector:") or reference.startswith("industry:"):
        return "classification"
    return "object"


def _relationship_family(relationship_type: str, relationship_family: str) -> str:
    universal_families = {
        "entity_to_entity",
        "entity_to_attribute",
        "entity_to_event",
        "entity_to_insight",
        "insight_to_event",
        "insight_to_attribute",
        "insight_to_strategy_profile",
        "insight_confirms_insight",
        "insight_conflicts_with_insight",
        "insight_invalidates_insight",
        "asset_to_provider_identifier",
        "asset_to_corporate_action",
        "asset_to_supplier",
        "asset_to_customer",
        "asset_to_owner",
        "asset_to_peer",
        "asset_to_macro_series",
    }
    if relationship_type in universal_families:
        return relationship_type
    if relationship_type == "selected_attribute":
        return "entity_to_attribute"
    if relationship_type == "insight_to_evidence":
        return "insight_to_attribute"
    if relationship_type == "peer":
        return "asset_to_peer"
    if relationship_family == "classification":
        return "entity_to_entity"
    return relationship_family


class NodeExecutionResult(BaseModel):
    node_id: str
    node_type: str
    status: str
    output_ref: str | None = None
    warnings: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    started_at: str
    finished_at: str


class MethodologyRunResult(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    methodology_id: str
    graph_hash: str = ""
    status: VizaExecutionStatus
    timestamp_cutoff: str | None = None
    result_checksum: str = ""
    rows: list[RadarRow] = Field(default_factory=list)
    relationships: list[RelationshipEdge] = Field(default_factory=list)
    insights: list[VizaInsight] = Field(default_factory=list)
    insight_relationships: list[RelationshipEdge] = Field(default_factory=list)
    translations: list[VizaTranslation] = Field(default_factory=list)
    warnings: list[ExecutionWarning] = Field(default_factory=list)
    node_results: list[NodeExecutionResult] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)


BASE_OUTPUT_COLUMNS = {"ticker", "company_name", "score", "rank"}


def validate_executable_graph(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
) -> list[ExecutionWarning]:
    warnings: list[ExecutionWarning] = []

    if not graph.nodes_by_type(VizaNodeType.UNIVERSE):
        warnings.append(
            ExecutionWarning(
                code="missing_universe",
                message="Executable VIZA graphs require at least one universe node.",
                severity="error",
            )
        )

    if not graph.nodes_by_type(VizaNodeType.OUTPUT_RADAR):
        warnings.append(
            ExecutionWarning(
                code="missing_output_radar",
                message="Executable VIZA graphs require at least one output radar node.",
                severity="error",
            )
        )

    for node in graph.nodes_by_type(VizaNodeType.ATTRIBUTE):
        attribute_key = node.config.get("attribute_key")
        if not isinstance(attribute_key, str) or not attribute_key:
            warnings.append(
                ExecutionWarning(
                    code="missing_attribute_key",
                    message="Attribute nodes must include config.attribute_key.",
                    node_id=node.id,
                    severity="error",
                )
            )
            continue
        if registry.get(attribute_key) is None:
            warnings.append(
                ExecutionWarning(
                    code="unknown_attribute_key",
                    message=f"Attribute key is not registered: {attribute_key}",
                    node_id=node.id,
                    severity="error",
                )
            )

    warnings.extend(_validate_transform_compatibility(graph, registry))
    warnings.extend(_validate_score_registry_eligibility(graph, registry))
    warnings.extend(_validate_attribute_source_limitations(graph, registry))

    return warnings


def _validate_transform_compatibility(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
) -> list[ExecutionWarning]:
    warnings: list[ExecutionWarning] = []
    seen: set[tuple[str, str, str]] = set()

    for transform_node in graph.nodes_by_type(VizaNodeType.TRANSFORM):
        transform = _read_string(transform_node.config.get("transform"), "percentile_rank")
        upstream_node_ids = _ancestor_node_ids(graph, transform_node.id)
        for node in graph.nodes_by_type(VizaNodeType.ATTRIBUTE):
            if node.id not in upstream_node_ids:
                continue
            attribute_key = _read_string(node.config.get("attribute_key"))
            attribute = registry.get(attribute_key)
            if attribute is None:
                continue

            allowed_transforms = set(attribute.allowed_transforms)
            if transform in allowed_transforms:
                continue

            dedupe_key = (transform_node.id, attribute.key, transform)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            allowed_label = (
                ", ".join(sorted(allowed_transforms))
                if allowed_transforms
                else "no registered transforms"
            )
            warnings.append(
                ExecutionWarning(
                    code="incompatible_attribute_transform",
                    message=(
                        f"{attribute.display_name} does not list {transform} as an allowed "
                        f"transform; allowed transforms: {allowed_label}."
                    ),
                    node_id=transform_node.id,
                )
            )

    return warnings


def _validate_score_registry_eligibility(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
) -> list[ExecutionWarning]:
    score_keys, score_node_id = _score_input_attribute_keys(graph, active_node_ids=None)
    if score_node_id is None:
        return []

    score_node = next((node for node in graph.nodes if node.id == score_node_id), None)
    allow_evidence_only = _read_bool(
        score_node.config.get("allow_evidence_only") if score_node is not None else None
    )
    warnings: list[ExecutionWarning] = []

    for key in score_keys:
        attribute = registry.get(key)
        if attribute is None:
            continue
        if attribute.evidence_only and not allow_evidence_only:
            warnings.append(
                ExecutionWarning(
                    code="evidence_only_score_input",
                    message=(
                        f"{attribute.display_name} is marked evidence-only. Enable "
                        "allow_evidence_only on the Score node to acknowledge this scoring input."
                    ),
                    node_id=score_node_id,
                )
            )
            continue
        if attribute.production_scoring_allowed is False and not allow_evidence_only:
            warnings.append(
                ExecutionWarning(
                    code="score_input_not_production_allowed",
                    message=(
                        f"{attribute.display_name} is not marked as production-scoring allowed "
                        "in the attribute registry."
                    ),
                    node_id=score_node_id,
                )
            )

    return warnings


def _validate_attribute_source_limitations(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
) -> list[ExecutionWarning]:
    warnings: list[ExecutionWarning] = []

    for node in graph.nodes_by_type(VizaNodeType.ATTRIBUTE):
        attribute_key = _read_string(node.config.get("attribute_key"))
        attribute = registry.get(attribute_key)
        if attribute is None:
            continue

        if attribute.deprecation_status != "active":
            warnings.append(
                ExecutionWarning(
                    code="deprecated_attribute",
                    message=(
                        f"{attribute.display_name} is marked {attribute.deprecation_status} "
                        "in the attribute registry."
                    ),
                    node_id=node.id,
                )
            )

        entitlement = entitlement_for_attribute(attribute)
        connector = connector_for_attribute(attribute)
        if connector.status in {"credential_required", "not_configured", "unavailable"}:
            warnings.append(
                ExecutionWarning(
                    code="attribute_connector_not_configured",
                    message=(
                        f"{attribute.display_name} maps to connector {connector.display_name}, "
                        f"which is {connector.status}."
                    ),
                    node_id=node.id,
                )
            )
        if entitlement.user_credential_required or entitlement.organization_credential_required:
            warnings.append(
                ExecutionWarning(
                    code="attribute_credential_required",
                    message=(
                        f"{attribute.display_name} requires a credential before source data "
                        "can be queried."
                    ),
                    node_id=node.id,
                )
            )
        if not entitlement.query_allowed:
            warnings.append(
                ExecutionWarning(
                    code="attribute_query_not_allowed",
                    message=(
                        f"{attribute.display_name} is not currently queryable under "
                        f"{attribute.entitlement_policy}."
                    ),
                    node_id=node.id,
                )
            )
        if not entitlement.derived_value_allowed:
            warnings.append(
                ExecutionWarning(
                    code="attribute_derived_value_not_allowed",
                    message=(
                        f"{attribute.display_name} cannot produce derived VIZA values under "
                        f"{attribute.entitlement_policy}."
                    ),
                    node_id=node.id,
                )
            )
        if not entitlement.export_allowed:
            warnings.append(
                ExecutionWarning(
                    code="attribute_export_limited",
                    message=(
                        f"{attribute.display_name} has export restrictions under "
                        f"{attribute.entitlement_policy}."
                    ),
                    node_id=node.id,
                )
            )

    return warnings


def run_methodology_stub(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
) -> MethodologyRunResult:
    warnings = validate_executable_graph(graph, registry)
    status = (
        VizaExecutionStatus.FAILED
        if any(warning.severity == "error" for warning in warnings)
        else VizaExecutionStatus.NOT_IMPLEMENTED
    )
    if status != VizaExecutionStatus.FAILED:
        warnings.append(
            ExecutionWarning(
                code="execution_not_implemented",
                message="Phase 2 accepts VIZA graphs but does not run analytics yet.",
            )
        )

    return MethodologyRunResult(
        methodology_id=graph.methodology_id,
        graph_hash=hash_methodology_graph(graph),
        status=status,
        warnings=warnings,
        evidence={
            "graph": {
                "name": graph.name,
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "attribute_keys": graph.attribute_keys(),
            }
        },
    )


def run_methodology(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
) -> MethodologyRunResult:
    run_id = str(uuid4())
    run_started_at = datetime.now(timezone.utc).isoformat()
    warnings = validate_executable_graph(graph, registry)
    plan = compile_execution_plan(graph)
    warnings.extend(
        ExecutionWarning(
            code=warning.code,
            message=warning.message,
            node_id=warning.node_id,
            severity=warning.severity,
        )
        for warning in plan.warnings
    )
    if any(warning.severity == "error" for warning in warnings):
        return _failed_result(graph, warnings, plan=plan)

    active_node_ids = set(plan.ordered_node_ids)
    try:
        universe, securities, universe_warnings = _resolve_universe(graph, active_node_ids)
    except ValueError as exc:
        warnings.append(
            ExecutionWarning(
                code="universe_resolution_failed",
                message=str(exc),
                severity="error",
            )
        )
        return _failed_result(graph, warnings, plan=plan)

    warnings.extend(universe_warnings)
    requested_keys = _requested_attribute_keys(graph, registry, active_node_ids)
    score_keys = _score_attribute_keys(graph, requested_keys, active_node_ids, warnings)
    materialized_keys = sorted(
        set(requested_keys) | set(score_keys) | set(_output_columns(graph, active_node_ids))
    )
    materialized_keys = [key for key in materialized_keys if registry.get(key) is not None]

    if not score_keys:
        warnings.append(
            ExecutionWarning(
                code="no_scoreable_attributes",
                message="Add Attribute nodes or score weights before running the methodology.",
                severity="error",
            )
        )
        return _failed_result(graph, warnings, plan=plan)

    resolved_attributes = {
        security.ticker: resolve_attribute_values(
            security=security,
            attribute_keys=materialized_keys,
            registry=registry,
        )
        for security in securities
    }

    if any(
        value.is_prototype
        for ticker_values in resolved_attributes.values()
        for value in ticker_values.values()
    ):
        warnings.append(
            ExecutionWarning(
                code="prototype_attribute_values",
                message=(
                    "Phase 4 uses local data where available and explicitly labeled "
                    "deterministic prototype fallbacks for unresolved research attributes."
                ),
            )
        )

    raw_attributes = {
        ticker: {key: value.value for key, value in ticker_values.items()}
        for ticker, ticker_values in resolved_attributes.items()
    }
    scoring_attributes = _build_scoring_attributes(
        raw_attributes=raw_attributes,
        score_keys=score_keys,
        graph=graph,
        active_node_ids=active_node_ids,
        warnings=warnings,
    )
    filtered_securities = _apply_filters(
        securities=securities,
        raw_attributes=raw_attributes,
        graph=graph,
        active_node_ids=active_node_ids,
        warnings=warnings,
    )
    scored_rows = _score_securities(
        securities=filtered_securities,
        raw_attributes=raw_attributes,
        scoring_attributes=scoring_attributes,
        score_keys=score_keys,
        graph=graph,
        active_node_ids=active_node_ids,
        warnings=warnings,
    )
    rows = _build_radar_rows(
        scored_rows=scored_rows,
        raw_attributes=raw_attributes,
        scoring_attributes=scoring_attributes,
        score_keys=score_keys,
        graph=graph,
        active_node_ids=active_node_ids,
    )

    if not rows:
        warnings.append(
            ExecutionWarning(
                code="no_rows_after_execution",
                message="The methodology ran but produced no radar rows.",
            )
        )

    relationships = _build_relationships(
        rows=rows,
        securities={security.ticker: security for security in securities},
        raw_attributes=raw_attributes,
        resolved_attributes=resolved_attributes,
        scoring_attributes=scoring_attributes,
        score_keys=score_keys,
        graph=graph,
        active_node_ids=active_node_ids,
    )
    node_results = _build_node_results(plan, warnings)
    evidence = normalize_evidence_records(
        _build_evidence(
            graph=graph,
            universe=universe,
            rows=rows,
            raw_attributes=raw_attributes,
            resolved_attributes=resolved_attributes,
            score_keys=score_keys,
            materialized_keys=materialized_keys,
        )
    )
    insight_source_payload = {
        "rows": [row.model_dump(mode="json") for row in rows],
        "relationships": [edge.model_dump(mode="json") for edge in relationships],
        "warnings": [warning.model_dump(mode="json") for warning in warnings],
        "evidence": evidence,
    }
    insights = extract_insights_from_run_result(
        insight_source_payload,
        min_confidence=0.45,
    )
    insight_relationships = _build_insight_relationships(insights)
    translations = [translate_insight(insight, default_strategy_profile()) for insight in insights]
    _apply_translations_to_rows(rows, translations, insights)
    checksum = result_checksum(
        rows=rows,
        relationships=[*relationships, *insight_relationships],
        warnings=warnings,
        evidence=evidence,
    )
    run_finished_at = datetime.now(timezone.utc).isoformat()
    manifest = _build_manifest(
        graph=graph,
        registry=registry,
        plan=plan,
        universe=universe,
        warnings=warnings,
        run_id=run_id,
        run_started_at=run_started_at,
        run_finished_at=run_finished_at,
        node_results=node_results,
        evidence=evidence,
        result_checksum_value=checksum,
    )

    return MethodologyRunResult(
        run_id=run_id,
        methodology_id=graph.methodology_id,
        graph_hash=plan.graph_hash,
        status=VizaExecutionStatus.COMPLETED,
        timestamp_cutoff=_timestamp_cutoff(graph),
        result_checksum=checksum,
        rows=rows,
        relationships=relationships,
        insights=insights,
        insight_relationships=insight_relationships,
        translations=translations,
        warnings=warnings,
        node_results=node_results,
        evidence=evidence,
        manifest=manifest,
    )


def _failed_result(
    graph: MethodologyGraph,
    warnings: list[ExecutionWarning],
    plan: ExecutionPlan | None = None,
) -> MethodologyRunResult:
    run_id = str(uuid4())
    run_started_at = datetime.now(timezone.utc).isoformat()
    run_finished_at = datetime.now(timezone.utc).isoformat()
    graph_hash = plan.graph_hash if plan is not None else hash_methodology_graph(graph)
    node_results = _build_node_results(plan, warnings) if plan is not None else []
    evidence = normalize_evidence_records(
        {
            "graph": {
                "name": graph.name,
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "attribute_keys": graph.attribute_keys(),
            }
        }
    )
    checksum = result_checksum(
        rows=[],
        relationships=[],
        warnings=warnings,
        evidence=evidence,
    )
    return MethodologyRunResult(
        run_id=run_id,
        methodology_id=graph.methodology_id,
        graph_hash=graph_hash,
        status=VizaExecutionStatus.FAILED,
        timestamp_cutoff=_timestamp_cutoff(graph),
        result_checksum=checksum,
        warnings=warnings,
        node_results=node_results,
        manifest=_build_manifest(
            graph=graph,
            registry=None,
            plan=plan,
            universe=None,
            warnings=warnings,
            run_id=run_id,
            run_started_at=run_started_at,
            run_finished_at=run_finished_at,
            node_results=node_results,
            evidence=evidence,
            result_checksum_value=checksum,
        ),
        evidence=evidence,
    )


def _resolve_universe(
    graph: MethodologyGraph,
    active_node_ids: set[str] | None = None,
) -> tuple[UniverseDefinition, list[UniverseSecurity], list[ExecutionWarning]]:
    warnings: list[ExecutionWarning] = []
    universe_node = _active_nodes_by_type(graph, VizaNodeType.UNIVERSE, active_node_ids)[0]
    universe_name = _read_string(universe_node.config.get("universe_name"))
    universe_version = _read_string(universe_node.config.get("universe_version"))
    universe = load_universe_definition(
        universe_name=universe_name or None,
        version=universe_version or None,
    )

    securities = universe.securities
    ticker_subset = _read_string_list(universe_node.config.get("ticker_subset"))
    if ticker_subset:
        requested_tickers = {ticker.upper() for ticker in ticker_subset}
        available_by_ticker = {security.ticker.upper(): security for security in securities}
        securities = [
            available_by_ticker[ticker]
            for ticker in requested_tickers
            if ticker in available_by_ticker
        ]
        missing_tickers = sorted(requested_tickers - set(available_by_ticker))
        if missing_tickers:
            warnings.append(
                ExecutionWarning(
                    code="unknown_ticker_subset_members",
                    message=f"Ticker subset members were not in the universe: {missing_tickers}",
                    node_id=universe_node.id,
                )
            )

    if not securities:
        raise ValueError("selected universe resolved to zero securities")

    return universe, securities, warnings


def _active_nodes_by_type(
    graph: MethodologyGraph,
    node_type: VizaNodeType,
    active_node_ids: set[str] | None,
) -> list:
    nodes = graph.nodes_by_type(node_type)
    if active_node_ids is None:
        return nodes
    return [node for node in nodes if node.id in active_node_ids]


def _data_flow_reverse_edges(graph: MethodologyGraph) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {}
    for edge in graph.edges:
        if edge.type != VizaEdgeType.DATA_FLOW:
            continue
        reverse.setdefault(edge.target, set()).add(edge.source)
    return reverse


def _ancestor_node_ids(graph: MethodologyGraph, node_id: str) -> set[str]:
    reverse = _data_flow_reverse_edges(graph)
    seen = {node_id}
    stack = [node_id]
    while stack:
        current = stack.pop()
        for upstream in reverse.get(current, set()):
            if upstream not in seen:
                seen.add(upstream)
                stack.append(upstream)
    return seen


def _score_input_attribute_keys(
    graph: MethodologyGraph,
    active_node_ids: set[str] | None,
) -> tuple[list[str], str | None]:
    score_nodes = _active_nodes_by_type(graph, VizaNodeType.SCORE, active_node_ids)
    if not score_nodes:
        return [], None

    score_node = score_nodes[0]
    ancestor_ids = _ancestor_node_ids(graph, score_node.id)
    if active_node_ids is not None:
        ancestor_ids &= active_node_ids

    keys: list[str] = []
    for node in graph.nodes:
        if node.id not in ancestor_ids or node.type != VizaNodeType.ATTRIBUTE:
            continue
        attribute_key = node.config.get("attribute_key")
        if isinstance(attribute_key, str) and attribute_key and attribute_key not in keys:
            keys.append(attribute_key)
    return keys, score_node.id


def _score_transform_nodes(
    graph: MethodologyGraph,
    active_node_ids: set[str] | None,
):
    score_nodes = _active_nodes_by_type(graph, VizaNodeType.SCORE, active_node_ids)
    if not score_nodes:
        return _active_nodes_by_type(graph, VizaNodeType.TRANSFORM, active_node_ids)

    ancestor_ids = _ancestor_node_ids(graph, score_nodes[0].id)
    if active_node_ids is not None:
        ancestor_ids &= active_node_ids
    return [
        node
        for node in graph.nodes_by_type(VizaNodeType.TRANSFORM)
        if node.id in ancestor_ids
    ]


def _requested_attribute_keys(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
    active_node_ids: set[str] | None = None,
) -> list[str]:
    keys: list[str] = []
    for node in graph.nodes_by_type(VizaNodeType.ATTRIBUTE):
        if active_node_ids is not None and node.id not in active_node_ids:
            continue
        attribute_key = node.config.get("attribute_key")
        if not isinstance(attribute_key, str):
            continue
        key = attribute_key
        if registry.get(key) is not None and key not in keys:
            keys.append(key)

    for column in _output_columns(graph, active_node_ids):
        if registry.get(column) is not None and column not in keys:
            keys.append(column)

    return keys


def _score_attribute_keys(
    graph: MethodologyGraph,
    requested_keys: list[str],
    active_node_ids: set[str] | None = None,
    warnings: list[ExecutionWarning] | None = None,
) -> list[str]:
    score_nodes = _active_nodes_by_type(graph, VizaNodeType.SCORE, active_node_ids)
    upstream_score_keys, score_node_id = _score_input_attribute_keys(graph, active_node_ids)
    allowed_score_keys = upstream_score_keys or [
        key
        for key in requested_keys
        if key not in {"sector", "industry", "run_status"}
    ]
    score_weights = _read_number_record(
        score_nodes[0].config.get("weights") if score_nodes else None
    )
    ignored_weight_keys = [
        key for key in score_weights if key not in allowed_score_keys
    ]
    if ignored_weight_keys and warnings is not None:
        warnings.append(
            ExecutionWarning(
                code="ignored_score_weight",
                message=(
                    "Score weights were ignored because their attributes are not "
                    f"upstream of the Score node: {', '.join(sorted(ignored_weight_keys))}"
                ),
                node_id=score_node_id,
            )
        )

    keys = [key for key in score_weights if key in allowed_score_keys]
    if keys:
        return keys
    if score_weights:
        return []
    return allowed_score_keys


def _output_columns(
    graph: MethodologyGraph,
    active_node_ids: set[str] | None = None,
) -> list[str]:
    output_nodes = _active_nodes_by_type(graph, VizaNodeType.OUTPUT_RADAR, active_node_ids)
    if not output_nodes:
        return []
    return _read_string_list(output_nodes[0].config.get("columns"))


def _build_scoring_attributes(
    raw_attributes: dict[str, dict[str, float | str | bool | None]],
    score_keys: list[str],
    graph: MethodologyGraph,
    active_node_ids: set[str] | None,
    warnings: list[ExecutionWarning],
) -> dict[str, dict[str, float | None]]:
    transform_nodes = _score_transform_nodes(graph, active_node_ids)
    if not transform_nodes:
        warnings.append(
            ExecutionWarning(
                code="implicit_score_normalization",
                message=(
                    "No Transform node was connected, so numeric score inputs were "
                    "converted to percentile ranks."
                ),
            )
        )
        return _percentile_rank_attributes(raw_attributes, score_keys, "higher_is_better")

    transform_node = transform_nodes[0]
    transform = _read_string(transform_node.config.get("transform"), "percentile_rank")
    direction = _read_string(transform_node.config.get("direction"), "higher_is_better")

    if transform == "percentile_rank":
        return _percentile_rank_attributes(raw_attributes, score_keys, direction)
    if transform == "z_score":
        return _z_score_attributes(raw_attributes, score_keys, direction)
    if transform == "absolute_value":
        absolute_values = {
            ticker: {
                key: abs(value) if isinstance(value, int | float) else None
                for key, value in attributes.items()
            }
            for ticker, attributes in raw_attributes.items()
        }
        return _percentile_rank_attributes(absolute_values, score_keys, direction)

    warnings.append(
        ExecutionWarning(
            code="unsupported_transform",
            message=f"Unsupported transform {transform}; percentile ranks were used.",
            node_id=transform_node.id,
        )
    )
    return _percentile_rank_attributes(raw_attributes, score_keys, direction)


def _percentile_rank_attributes(
    raw_attributes: dict[str, dict[str, float | str | bool | None]],
    score_keys: list[str],
    direction: str,
) -> dict[str, dict[str, float | None]]:
    output = {ticker: {} for ticker in raw_attributes}
    for key in score_keys:
        numeric_values = [
            (ticker, float(value))
            for ticker, attributes in raw_attributes.items()
            if isinstance((value := attributes.get(key)), int | float)
        ]
        sorted_values = sorted(numeric_values, key=lambda item: item[1])
        denominator = max(len(sorted_values) - 1, 1)
        ranks = {
            ticker: index / denominator
            for index, (ticker, _value) in enumerate(sorted_values)
        }
        for ticker in output:
            percentile = ranks.get(ticker)
            if percentile is None:
                output[ticker][key] = None
            elif direction == "lower_is_better":
                output[ticker][key] = round(1 - percentile, 6)
            else:
                output[ticker][key] = round(percentile, 6)
    return output


def _z_score_attributes(
    raw_attributes: dict[str, dict[str, float | str | bool | None]],
    score_keys: list[str],
    direction: str,
) -> dict[str, dict[str, float | None]]:
    output = {ticker: {} for ticker in raw_attributes}
    for key in score_keys:
        values = [
            float(value)
            for attributes in raw_attributes.values()
            if isinstance((value := attributes.get(key)), int | float)
        ]
        if not values:
            for ticker in output:
                output[ticker][key] = None
            continue
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / max(len(values) - 1, 1)
        stddev = math.sqrt(variance) or 1.0
        for ticker, attributes in raw_attributes.items():
            value = attributes.get(key)
            if not isinstance(value, int | float):
                output[ticker][key] = None
                continue
            z_score = (float(value) - mean) / stddev
            output[ticker][key] = round(-z_score if direction == "lower_is_better" else z_score, 6)
    return output


def _apply_filters(
    securities: list[UniverseSecurity],
    raw_attributes: dict[str, dict[str, float | str | bool | None]],
    graph: MethodologyGraph,
    active_node_ids: set[str] | None,
    warnings: list[ExecutionWarning],
) -> list[UniverseSecurity]:
    filtered = securities
    for filter_node in _active_nodes_by_type(graph, VizaNodeType.FILTER, active_node_ids):
        attribute_key = _read_string(filter_node.config.get("attribute_key"))
        operator = _read_string(filter_node.config.get("operator"), "is_available")
        before_count = len(filtered)
        filtered = [
            security
            for security in filtered
            if _passes_filter(
                value=raw_attributes[security.ticker].get(attribute_key),
                ticker=security.ticker,
                operator=operator,
                config=filter_node.config,
            )
        ]
        if not filtered:
            warnings.append(
                ExecutionWarning(
                    code="filter_removed_all_rows",
                    message=f"Filter {filter_node.id} removed all {before_count} candidate rows.",
                    node_id=filter_node.id,
                )
            )
            break
    return filtered


def _passes_filter(
    value: float | str | bool | None,
    ticker: str,
    operator: str,
    config: dict[str, Any],
) -> bool:
    if operator == "is_available":
        return value is not None and value != ""
    if operator == "ticker_in":
        allowed_tickers = {item.upper() for item in _read_string_list(config.get("value"))}
        return ticker.upper() in allowed_tickers
    if operator in {"equals", "sector_equals", "industry_equals"}:
        return str(value or "").lower() == _read_string(config.get("value")).lower()
    if operator == "greater_than":
        return _read_float(value) > _read_float(config.get("value"))
    if operator == "less_than":
        return _read_float(value) < _read_float(config.get("value"))
    if operator == "between":
        low, high = _filter_bounds(config)
        numeric_value = _read_float(value)
        return low <= numeric_value <= high
    return True


def _score_securities(
    securities: list[UniverseSecurity],
    raw_attributes: dict[str, dict[str, float | str | bool | None]],
    scoring_attributes: dict[str, dict[str, float | None]],
    score_keys: list[str],
    graph: MethodologyGraph,
    active_node_ids: set[str] | None,
    warnings: list[ExecutionWarning],
) -> list[tuple[UniverseSecurity, float, list[str]]]:
    score_nodes = _active_nodes_by_type(graph, VizaNodeType.SCORE, active_node_ids)
    score_node = score_nodes[0] if score_nodes else None
    score_method = _read_string(
        score_node.config.get("method") if score_node else None,
        "weighted_sum",
    )
    missing_policy = _read_string(
        score_node.config.get("missing_data") if score_node else None,
        "renormalize_available_weights",
    )
    weights = _read_number_record(score_node.config.get("weights") if score_node else None)
    weights = {key: value for key, value in weights.items() if key in score_keys and value > 0}
    if not weights:
        equal_weight = 1 / len(score_keys)
        weights = {key: equal_weight for key in score_keys}

    scored: list[tuple[UniverseSecurity, float, list[str]]] = []
    for security in securities:
        ticker = security.ticker
        row_warnings: list[str] = []
        available_terms: list[tuple[float, float]] = []
        missing_keys: list[str] = []
        for key, weight in weights.items():
            value = scoring_attributes.get(ticker, {}).get(key)
            if value is None:
                missing_keys.append(key)
                continue
            available_terms.append((value, weight))

        if missing_keys and missing_policy == "require_all_inputs":
            continue
        if missing_keys:
            row_warnings.append(f"missing score inputs: {', '.join(missing_keys)}")

        if not available_terms:
            continue

        if score_method == "average_rank":
            score = sum(value for value, _weight in available_terms) / len(available_terms)
        elif missing_policy == "penalize_missing":
            declared_weight = sum(weights.values()) or 1.0
            score = sum(value * weight for value, weight in available_terms) / declared_weight
        else:
            available_weight = sum(weight for _value, weight in available_terms) or 1.0
            score = sum(value * weight for value, weight in available_terms) / available_weight

        scored.append((security, round(score, 6), row_warnings))

    if not scored:
        warnings.append(
            ExecutionWarning(
                code="no_scoreable_rows",
                message="No securities had enough numeric score inputs to produce a radar row.",
            )
        )

    return scored


def _build_radar_rows(
    scored_rows: list[tuple[UniverseSecurity, float, list[str]]],
    raw_attributes: dict[str, dict[str, float | str | bool | None]],
    scoring_attributes: dict[str, dict[str, float | None]],
    score_keys: list[str],
    graph: MethodologyGraph,
    active_node_ids: set[str] | None,
) -> list[RadarRow]:
    output_nodes = _active_nodes_by_type(graph, VizaNodeType.OUTPUT_RADAR, active_node_ids)
    output_config = output_nodes[0].config if output_nodes else {}
    top_n = max(1, int(_read_float(output_config.get("top_n"), 25)))
    sort_direction = _read_string(output_config.get("sort"), "descending")
    reverse = sort_direction != "ascending"
    columns = _output_columns(graph, active_node_ids) or ["ticker", "company_name", "score"]
    requested_columns = [column for column in columns if column not in BASE_OUTPUT_COLUMNS]

    sorted_rows = sorted(scored_rows, key=lambda item: item[1], reverse=reverse)[:top_n]
    rows: list[RadarRow] = []
    for rank, (security, score, row_warnings) in enumerate(sorted_rows, start=1):
        entity_id, asset_id = resolve_static_asset_identity(security.ticker)
        attributes: dict[str, float | str | bool | None] = {}
        all_attribute_columns = list(dict.fromkeys(requested_columns + score_keys))
        for key in all_attribute_columns:
            if key.endswith("_score"):
                source_key = key.removesuffix("_score")
                attributes[key] = scoring_attributes.get(security.ticker, {}).get(source_key)
            else:
                attributes[key] = raw_attributes.get(security.ticker, {}).get(key)

        rows.append(
            RadarRow(
                ticker=security.ticker,
                company_name=security.name,
                entity_id=entity_id,
                asset_id=asset_id,
                score=score,
                rank=rank,
                attributes=attributes,
                warnings=row_warnings,
                evidence_refs=[
                    f"company:{security.ticker}",
                    *[f"attr:{security.ticker}:{key}" for key in all_attribute_columns],
                ],
            )
        )
    return rows


def _requested_columns_for_rows(
    graph: MethodologyGraph,
    active_node_ids: set[str] | None,
) -> list[str]:
    active_attribute_keys = [
        node.config.get("attribute_key")
        for node in _active_nodes_by_type(graph, VizaNodeType.ATTRIBUTE, active_node_ids)
        if isinstance(node.config.get("attribute_key"), str)
    ]
    return list(dict.fromkeys(active_attribute_keys + _output_columns(graph, active_node_ids)))


def _build_relationships(
    rows: list[RadarRow],
    securities: dict[str, UniverseSecurity],
    raw_attributes: dict[str, dict[str, float | str | bool | None]],
    resolved_attributes: dict[str, dict[str, AttributeValue]],
    scoring_attributes: dict[str, dict[str, float | None]],
    score_keys: list[str],
    graph: MethodologyGraph,
    active_node_ids: set[str] | None,
) -> list[RelationshipEdge]:
    relationship_types = _relationship_types(graph, active_node_ids)
    relationships: list[RelationshipEdge] = []
    for row in rows:
        security = securities[row.ticker]
        if "company_to_selected_attributes" in relationship_types:
            for key in score_keys:
                relationships.append(
                    RelationshipEdge(
                        source=f"company:{row.ticker}",
                        target=f"attribute:{key}",
                        relationship_type="selected_attribute",
                        relationship_family="attribute",
                        weight=scoring_attributes.get(row.ticker, {}).get(key),
                        confidence=_attribute_confidence(resolved_attributes, row.ticker, key),
                        evidence_ref=f"attr:{row.ticker}:{key}",
                        source_lineage=_attribute_lineage(resolved_attributes, row.ticker, key),
                    )
                )

        if "company_to_sector" in relationship_types and security.sector:
            relationships.append(
                RelationshipEdge(
                    source=f"company:{row.ticker}",
                    target=f"sector:{security.sector}",
                    relationship_type="sector",
                    relationship_family="classification",
                    weight=1.0,
                    confidence=_attribute_confidence(resolved_attributes, row.ticker, "sector"),
                    evidence_ref=f"attr:{row.ticker}:sector",
                    source_lineage=_attribute_lineage(resolved_attributes, row.ticker, "sector"),
                )
            )

        if "company_to_industry" in relationship_types and security.industry:
            relationships.append(
                RelationshipEdge(
                    source=f"company:{row.ticker}",
                    target=f"industry:{security.industry}",
                    relationship_type="industry",
                    relationship_family="classification",
                    weight=1.0,
                    confidence=_attribute_confidence(resolved_attributes, row.ticker, "industry"),
                    evidence_ref=f"attr:{row.ticker}:industry",
                    source_lineage=_attribute_lineage(resolved_attributes, row.ticker, "industry"),
                )
            )

        if "company_to_peers" in relationship_types:
            peer_count = max(len(security.peers[:5]), 1)
            for peer in security.peers[:5]:
                relationships.append(
                    RelationshipEdge(
                        source=f"company:{row.ticker}",
                        target=f"company:{peer}",
                        relationship_type="peer",
                        relationship_family="peer",
                        weight=round(1 / peer_count, 6),
                        confidence=0.55,
                        evidence_ref=f"company:{row.ticker}",
                        source_lineage={
                            "source": "local_universe",
                            "source_record_id": f"universe_security:{row.ticker}",
                        },
                        diagnostics={"peer_count": len(security.peers)},
                    )
                )

        if "company_to_recent_event_evidence" in relationship_types:
            event_materiality = _read_float(
                raw_attributes.get(row.ticker, {}).get("event_materiality")
            )
            if event_materiality >= 0.65:
                relationships.append(
                    RelationshipEdge(
                        source=f"company:{row.ticker}",
                        target=f"event:{row.ticker}:materiality",
                        relationship_type="recent_event_evidence",
                        relationship_family="event",
                        weight=event_materiality,
                        confidence=_attribute_confidence(
                            resolved_attributes,
                            row.ticker,
                            "event_materiality",
                        ),
                        evidence_ref=f"attr:{row.ticker}:event_materiality",
                        source_lineage=_attribute_lineage(
                            resolved_attributes,
                            row.ticker,
                            "event_materiality",
                        ),
                        diagnostics={"threshold": 0.65},
                    )
                )

    return relationships


def _build_insight_relationships(insights: list[VizaInsight]) -> list[RelationshipEdge]:
    relationships: list[RelationshipEdge] = []
    for insight in insights:
        insight_ref = f"insight:{insight.insight_id}"
        relationships.append(
            RelationshipEdge(
                source=insight.entity_id,
                target=insight_ref,
                relationship_type="entity_to_insight",
                relationship_family="insight",
                weight=insight.confidence,
                confidence=insight.confidence,
                timestamp_available=insight.available_at.isoformat(),
                evidence_ref=insight.evidence_refs[0] if insight.evidence_refs else None,
                source_lineage={
                    "insight_type": insight.insight_type,
                    "direction": insight.direction,
                },
            )
        )
        for evidence_ref in insight.evidence_refs:
            relationships.append(
                RelationshipEdge(
                    source=insight_ref,
                    target=f"evidence:{evidence_ref}",
                    relationship_type="insight_to_evidence",
                    relationship_family="insight",
                    weight=1.0,
                    confidence=insight.confidence,
                    timestamp_available=insight.available_at.isoformat(),
                    evidence_ref=evidence_ref,
                    source_lineage={"insight_type": insight.insight_type},
                )
            )
    return relationships


def _apply_translations_to_rows(
    rows: list[RadarRow],
    translations: list[VizaTranslation],
    insights: list[VizaInsight],
) -> None:
    best_by_entity: dict[str, VizaTranslation] = {}
    insight_types = {insight.insight_id: insight.insight_type for insight in insights}
    for translation in translations:
        current = best_by_entity.get(translation.entity_id)
        if current is None or translation.fit_score > current.fit_score:
            best_by_entity[translation.entity_id] = translation
    for row in rows:
        if row.entity_id is None:
            continue
        translation = best_by_entity.get(row.entity_id)
        if translation is None:
            continue
        row.strategy_fit_score = translation.fit_score
        row.primary_insight_type = insight_types.get(translation.insight_id)
        row.translated_summary = translation.translated_summary
        row.confidence = translation.fit_score
        row.horizon = {"label": translation.relevance}
        row.missing_confirmations = translation.missing_confirmations
        row.invalidation_conditions = translation.invalidation_conditions
        row.risk_flags = translation.risk_factors
        row.evidence_count = len(translation.evidence_refs)
        row.source_restrictions = [
            "not_investment_advice"
            if translation.not_investment_advice
            else "advice_flag_missing"
        ]
        row.PIT_status = "point_in_time"


def _relationship_types(
    graph: MethodologyGraph,
    active_node_ids: set[str] | None = None,
) -> set[str]:
    relationship_nodes = _active_nodes_by_type(graph, VizaNodeType.RELATIONSHIP, active_node_ids)
    if not relationship_nodes:
        return {"company_to_selected_attributes", "company_to_sector", "company_to_peers"}
    return set(_read_string_list(relationship_nodes[0].config.get("relationships")))


def _attribute_confidence(
    resolved_attributes: dict[str, dict[str, AttributeValue]],
    ticker: str,
    key: str,
) -> float | None:
    value = resolved_attributes.get(ticker, {}).get(key)
    return value.confidence if value else None


def _attribute_lineage(
    resolved_attributes: dict[str, dict[str, AttributeValue]],
    ticker: str,
    key: str,
) -> dict[str, Any]:
    value = resolved_attributes.get(ticker, {}).get(key)
    if value is None:
        return {}
    return {
        "source": value.source,
        "connector_id": value.connector_id,
        "source_record_id": value.source_record_id,
        "data_version": value.data_version,
        "model_version": value.model_version,
        "license_policy": value.license_policy,
        "entitlement_policy": value.entitlement_policy,
        "is_prototype": value.is_prototype,
        "observation_id": value.observation_id,
        "observed_at": value.observed_at,
        "available_at": value.available_at,
        "retrieved_at": value.retrieved_at,
        "PIT_status": value.PIT_status,
    }


def _build_evidence(
    graph: MethodologyGraph,
    universe: UniverseDefinition,
    rows: list[RadarRow],
    raw_attributes: dict[str, dict[str, float | str | bool | None]],
    resolved_attributes: dict[str, dict[str, AttributeValue]],
    score_keys: list[str],
    materialized_keys: list[str],
) -> dict[str, Any]:
    universe_timestamp_available = (
        universe.timestamp_available.isoformat()
        if universe.timestamp_available
        else None
    )
    evidence: dict[str, Any] = {
        "graph": {
            "evidence_ref": "graph",
            "source": "methodology_graph",
            "source_record_id": graph.methodology_id,
            "name": graph.name,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "attribute_keys": graph.attribute_keys(),
            "score_keys": score_keys,
        },
        f"universe:{universe.key}": {
            "evidence_ref": f"universe:{universe.key}",
            "universe_name": universe.universe_name,
            "version": universe.version,
            "source": universe.source,
            "source_record_id": universe.key,
            "timestamp_available": universe_timestamp_available,
            "asset_count": len(universe.securities),
            "config_path": universe.config_path,
        },
    }
    for row in rows:
        evidence[f"company:{row.ticker}"] = {
            "evidence_ref": f"company:{row.ticker}",
            "ticker": row.ticker,
            "company_name": row.company_name,
            "entity_id": row.entity_id,
            "asset_id": row.asset_id,
            "rank": row.rank,
            "score": row.score,
            "source": "radar_output",
            "source_record_id": row.asset_id or f"company:{row.ticker}",
            "source_identifier": row.ticker,
            "resolved_identifier_type": "ticker",
            "value": {
                "ticker": row.ticker,
                "entity_id": row.entity_id,
                "asset_id": row.asset_id,
                "rank": row.rank,
                "score": row.score,
            },
        }
        for key in materialized_keys:
            resolved_value = resolved_attributes.get(row.ticker, {}).get(key)
            evidence[f"attr:{row.ticker}:{key}"] = {
                "evidence_ref": f"attr:{row.ticker}:{key}",
                "attribute_key": key,
                "entity_id": row.entity_id,
                "asset_id": row.asset_id,
                "value": raw_attributes.get(row.ticker, {}).get(key),
                "unit": resolved_value.unit if resolved_value else None,
                "source": resolved_value.source if resolved_value else "unknown",
                "connector_id": resolved_value.connector_id if resolved_value else None,
                "source_record_id": resolved_value.source_record_id if resolved_value else None,
                "source_identifier": row.ticker,
                "resolved_identifier_type": "ticker",
                "source_timestamp": (
                    resolved_value.event_time
                    if resolved_value and resolved_value.event_time
                    else universe_timestamp_available
                ),
                "timestamp_available": (
                    resolved_value.timestamp_available
                    if resolved_value and resolved_value.timestamp_available
                    else universe_timestamp_available
                ),
                "data_version": resolved_value.data_version if resolved_value else None,
                "model_version": resolved_value.model_version if resolved_value else None,
                "observation_id": resolved_value.observation_id if resolved_value else None,
                "observed_at": resolved_value.observed_at if resolved_value else None,
                "available_at": resolved_value.available_at if resolved_value else None,
                "retrieved_at": resolved_value.retrieved_at if resolved_value else None,
                "rights_policy": resolved_value.rights_policy if resolved_value else {},
                "PIT_status": resolved_value.PIT_status if resolved_value else None,
                "contribution_stage": resolved_value.contribution_stage if resolved_value else None,
                "license_policy": resolved_value.license_policy if resolved_value else None,
                "cache_policy": resolved_value.cache_policy if resolved_value else None,
                "entitlement_policy": resolved_value.entitlement_policy if resolved_value else None,
                "calculation": {
                    "attribute_key": key,
                    "score_input": key in score_keys,
                },
                "limitations": resolved_value.limitations if resolved_value else [],
                "entitlement": (
                    resolved_value.entitlement.model_dump(mode="json")
                    if resolved_value
                    else None
                ),
                "confidence": resolved_value.confidence if resolved_value else None,
                "missing_reason": resolved_value.missing_reason if resolved_value else None,
                "is_prototype": resolved_value.is_prototype if resolved_value else True,
                "diagnostics": resolved_value.diagnostics if resolved_value else {},
            }
    return evidence


def _build_node_results(
    plan: ExecutionPlan,
    warnings: list[ExecutionWarning],
) -> list[NodeExecutionResult]:
    timestamp = datetime.now(timezone.utc).isoformat()
    warnings_by_node: dict[str, list[ExecutionWarning]] = {}
    for warning in warnings:
        if warning.node_id:
            warnings_by_node.setdefault(warning.node_id, []).append(warning)

    node_results: list[NodeExecutionResult] = []
    for step in plan.steps:
        node_warnings = warnings_by_node.get(step.node_id, [])
        has_error = any(warning.severity == "error" for warning in node_warnings)
        has_warning = bool(node_warnings)
        status = "failed" if has_error else "completed_with_warnings" if has_warning else "completed"
        node_results.append(
            NodeExecutionResult(
                node_id=step.node_id,
                node_type=step.node_type.value,
                status=status,
                output_ref=f"node:{step.node_id}",
                warnings=[warning.code for warning in node_warnings],
                diagnostics={
                    "upstream_node_ids": step.upstream_node_ids,
                    "downstream_node_ids": step.downstream_node_ids,
                },
                started_at=timestamp,
                finished_at=timestamp,
            )
        )
    return node_results


def _build_manifest(
    graph: MethodologyGraph,
    registry: AttributeRegistry | None,
    plan: ExecutionPlan | None,
    universe: UniverseDefinition | None,
    warnings: list[ExecutionWarning],
    run_id: str,
    run_started_at: str,
    run_finished_at: str,
    node_results: list[NodeExecutionResult],
    evidence: dict[str, Any],
    result_checksum_value: str,
) -> dict[str, Any]:
    graph_hash = plan.graph_hash if plan is not None else hash_methodology_graph(graph)
    manifest_attribute_keys = (
        _manifest_attribute_keys(graph, registry) if registry is not None else []
    )
    data_version_summary = data_versions_from_evidence(evidence)
    manifest: dict[str, Any] = {
        "runtime_version": "viza_runtime_phase_10_audit_v0",
        "run_id": run_id,
        "methodology_id": graph.methodology_id,
        "methodology_version_id": _methodology_version_id(graph),
        "graph_schema_version": graph.schema_version,
        "graph_hash": graph_hash,
        "attribute_registry_schema_version": (
            registry.schema_version if registry is not None else None
        ),
        "registry_version": registry.registry_version if registry is not None else None,
        "timestamp_cutoff": _timestamp_cutoff(graph),
        "run_started_at": run_started_at,
        "run_finished_at": run_finished_at,
        "universe": (
            {
                "universe_name": universe.universe_name,
                "version": universe.version,
                "source": universe.source,
            }
            if universe is not None
            else None
        ),
        "connectors": (
            build_connector_manifest(registry, manifest_attribute_keys)
            if registry is not None
            else {}
        ),
        "attribute_keys": manifest_attribute_keys,
        "data_versions": data_version_summary["data_versions"],
        "model_versions": data_version_summary["model_versions"],
        "ordered_node_ids": plan.ordered_node_ids if plan is not None else [],
        "node_execution_statuses": {
            node.node_id: node.status
            for node in node_results
        },
        "warning_codes": [warning.code for warning in warnings],
        "warnings": [warning.model_dump(mode="json") for warning in warnings],
        "evidence_count": len(evidence),
        "evidence_checksum": evidence_checksum(evidence),
        "result_checksum": result_checksum_value,
    }
    manifest["connector_states"] = connector_states_from_manifest(manifest)
    manifest["entitlement_states"] = entitlement_states_from_manifest(manifest)
    return manifest


def _manifest_attribute_keys(
    graph: MethodologyGraph,
    registry: AttributeRegistry,
) -> list[str]:
    keys = list(graph.attribute_keys())
    keys.extend(_output_columns(graph))
    return sorted({key for key in keys if registry.get(key) is not None})


def _methodology_version_id(graph: MethodologyGraph) -> str | None:
    metadata = graph.metadata or {}
    for key in ["methodology_version_id", "version_id"]:
        value = metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _timestamp_cutoff(graph: MethodologyGraph) -> str | None:
    universe_nodes = graph.nodes_by_type(VizaNodeType.UNIVERSE)
    for node in universe_nodes:
        for key in ["timestamp_cutoff", "as_of"]:
            value = node.config.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _read_string(value: Any, fallback: str = "") -> str:
    return value if isinstance(value, str) else fallback


def _read_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _read_float(value: Any, fallback: float = 0.0) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return fallback
        return parsed if math.isfinite(parsed) else fallback
    return fallback


def _read_bool(value: Any, fallback: bool = False) -> bool:
    return value if isinstance(value, bool) else fallback


def _read_number_record(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        key: float(raw_value)
        for key, raw_value in value.items()
        if isinstance(key, str) and isinstance(raw_value, int | float)
    }


def _filter_bounds(config: dict[str, Any]) -> tuple[float, float]:
    if "min_value" in config or "max_value" in config:
        return _read_float(config.get("min_value"), -math.inf), _read_float(
            config.get("max_value"),
            math.inf,
        )
    values = [_read_float(item) for item in _read_string_list(config.get("value"))]
    if len(values) >= 2:
        return min(values[0], values[1]), max(values[0], values[1])
    return -math.inf, math.inf

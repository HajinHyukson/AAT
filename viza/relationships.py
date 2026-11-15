from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from viza.attribute_registry import AttributeRegistry
from viza.audit import stable_checksum
from viza.execution import ExecutionWarning, MethodologyRunResult, RelationshipEdge, run_methodology
from viza.graph_schema import MethodologyGraph


class RelationshipQueryRequest(BaseModel):
    graph: MethodologyGraph | None = None
    run_result: MethodologyRunResult | None = None
    entity_ref: str | None = None
    entity_id: str | None = None
    asset_id: str | None = None
    insight_id: str | None = None
    event_id: str | None = None
    family: str | None = None
    source_type: str | None = None
    target_type: str | None = None
    min_confidence: float | None = Field(default=None, ge=0, le=1)
    time_horizon: str | None = None
    PIT_only: bool = False
    relationship_type: str | None = None
    relationship_families: list[str] = Field(default_factory=list)
    min_strength: float | None = None
    max_edges: int = Field(default=50, ge=1, le=500)

    @model_validator(mode="after")
    def require_graph_or_run_result(self) -> "RelationshipQueryRequest":
        if self.graph is None and self.run_result is None:
            raise ValueError("relationship query requires graph or run_result")
        return self


class RelationshipQueryResult(BaseModel):
    run_id: str
    methodology_id: str
    entity_ref: str | None = None
    relationships: list[RelationshipEdge] = Field(default_factory=list)
    warnings: list[ExecutionWarning] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)


def query_relationships(
    request: RelationshipQueryRequest,
    registry: AttributeRegistry,
) -> RelationshipQueryResult:
    run_result = request.run_result
    if run_result is None:
        if request.graph is None:
            raise ValueError("relationship query requires graph or run_result")
        run_result = run_methodology(request.graph, registry)
    relationships = [
        *run_result.relationships,
        *getattr(run_result, "insight_relationships", []),
        *_event_relationship_edges(run_result),
        *_insight_reaction_edges(run_result),
        *_insight_strategy_profile_edges(run_result),
    ]

    entity_ref = request.entity_ref or request.entity_id
    if entity_ref:
        relationships = [
            edge
            for edge in relationships
            if edge.source == entity_ref
            or edge.target == entity_ref
            or edge.source_id == entity_ref
            or edge.target_id == entity_ref
        ]

    if request.asset_id:
        relationships = [
            edge
            for edge in relationships
            if edge.source == request.asset_id
            or edge.target == request.asset_id
            or edge.source_id == request.asset_id
            or edge.target_id == request.asset_id
        ]

    if request.insight_id:
        insight_ref = _insight_ref(request.insight_id)
        relationships = [
            edge
            for edge in relationships
            if edge.source in {request.insight_id, insight_ref}
            or edge.target in {request.insight_id, insight_ref}
            or edge.source_id in {request.insight_id, insight_ref}
            or edge.target_id in {request.insight_id, insight_ref}
        ]

    if request.event_id:
        event_ref = _event_ref(request.event_id)
        relationships = [
            edge
            for edge in relationships
            if edge.source in {request.event_id, event_ref}
            or edge.target in {request.event_id, event_ref}
            or edge.source_id in {request.event_id, event_ref}
            or edge.target_id in {request.event_id, event_ref}
        ]

    requested_family_list = [*request.relationship_families]
    if request.family:
        requested_family_list.append(request.family)
    if requested_family_list:
        requested_families = _expand_family_aliases(requested_family_list)
        relationships = [
            edge
            for edge in relationships
            if edge.relationship_family in requested_families or edge.family in requested_families
        ]

    if request.source_type:
        relationships = [edge for edge in relationships if edge.source_type == request.source_type]

    if request.target_type:
        relationships = [edge for edge in relationships if edge.target_type == request.target_type]

    if request.relationship_type:
        relationships = [
            edge for edge in relationships if edge.relationship_type == request.relationship_type
        ]

    if request.time_horizon:
        relationships = [
            edge for edge in relationships if edge.time_horizon in {request.time_horizon, None}
        ]

    if request.PIT_only:
        relationships = [edge for edge in relationships if edge.available_at or edge.timestamp_available]

    if request.min_confidence is not None:
        relationships = [
            edge
            for edge in relationships
            if edge.confidence is None or edge.confidence >= request.min_confidence
        ]

    if request.min_strength is not None:
        relationships = [
            edge
            for edge in relationships
            if edge.weight is None or abs(edge.weight) >= request.min_strength
        ]

    relationships = relationships[: request.max_edges]

    return RelationshipQueryResult(
        run_id=run_result.run_id,
        methodology_id=run_result.methodology_id,
        entity_ref=entity_ref,
        relationships=relationships,
        warnings=run_result.warnings,
        evidence=run_result.evidence,
    )


def _event_relationship_edges(run_result: MethodologyRunResult) -> list[RelationshipEdge]:
    try:
        from viza.events import extract_events_from_run_result

        events = extract_events_from_run_result(
            run_result,
            min_confidence=0.4,
        )
    except Exception:
        return []

    edges: list[RelationshipEdge] = []
    insights = list(getattr(run_result, "insights", []))
    for event in events:
        evidence_ref = event.evidence_refs[0] if event.evidence_refs else None
        for entity_id in event.affected_entity_ids:
            edges.append(
                RelationshipEdge(
                    source=entity_id,
                    target=f"event:{event.event_id}",
                    relationship_type="entity_to_event",
                    relationship_family="event",
                    family="entity_to_event",
                    weight=event.materiality,
                    confidence=event.confidence,
                    observed_at=event.observed_at.isoformat(),
                    available_at=event.available_at.isoformat(),
                    timestamp_available=event.available_at.isoformat(),
                    evidence_ref=evidence_ref,
                    evidence_refs=event.evidence_refs,
                    rights_policy=event.rights_policy,
                    source_lineage=event.source,
                    diagnostics={"event_type": event.event_type},
                )
            )
        for asset_id in event.affected_asset_ids:
            edges.append(
                RelationshipEdge(
                    source=asset_id,
                    target=f"event:{event.event_id}",
                    relationship_type="asset_to_event",
                    relationship_family="event",
                    family="asset_to_event",
                    weight=event.materiality,
                    confidence=event.confidence,
                    observed_at=event.observed_at.isoformat(),
                    available_at=event.available_at.isoformat(),
                    timestamp_available=event.available_at.isoformat(),
                    evidence_ref=evidence_ref,
                    evidence_refs=event.evidence_refs,
                    rights_policy=event.rights_policy,
                    source_lineage=event.source,
                    diagnostics={"event_type": event.event_type},
                )
            )
        for insight in insights:
            if not _event_matches_insight(event, insight):
                continue
            edges.append(
                RelationshipEdge(
                    source=_insight_ref(insight.insight_id),
                    target=f"event:{event.event_id}",
                    relationship_type="derived_from",
                    relationship_family="insight_event",
                    family="insight_to_event",
                    weight=min(event.materiality, insight.confidence),
                    confidence=min(event.confidence, insight.confidence),
                    observed_at=event.observed_at.isoformat(),
                    available_at=event.available_at.isoformat(),
                    timestamp_available=event.available_at.isoformat(),
                    evidence_ref=evidence_ref,
                    evidence_refs=list(dict.fromkeys([*event.evidence_refs, *insight.evidence_refs])),
                    rights_policy=event.rights_policy or insight.source_policy,
                    source_lineage={"event_type": event.event_type, "insight_type": insight.insight_type},
                    diagnostics={"family": "insight_to_event"},
                )
            )
    return edges


def _insight_reaction_edges(run_result: MethodologyRunResult) -> list[RelationshipEdge]:
    insights = list(getattr(run_result, "insights", []))
    if len(insights) < 2:
        return []

    reaction_rules = [
        ("acquisition_rumor", "unusual_volume", "confirms", "insight_confirms_insight"),
        ("insider_purchase", "momentum_breakout", "confirms", "insight_confirms_insight"),
        ("regulatory_action", "acquisition_rumor", "invalidates", "insight_invalidates_insight"),
        ("earnings_miss", "bullish_social_sentiment", "conflicts", "insight_conflicts_with_insight"),
        ("macro_liquidity_shock", "small_cap_breakout_signal", "conflicts", "insight_conflicts_with_insight"),
    ]
    edges: list[RelationshipEdge] = []
    for left in insights:
        for right in insights:
            if left.insight_id == right.insight_id or left.entity_id != right.entity_id:
                continue
            left_tokens = _insight_tokens(left)
            right_tokens = _insight_tokens(right)
            for trigger, target, relationship_type, family in reaction_rules:
                if trigger not in left_tokens or target not in right_tokens:
                    continue
                evidence_refs = list(dict.fromkeys([*left.evidence_refs, *right.evidence_refs]))
                edges.append(
                    RelationshipEdge(
                        source=_insight_ref(left.insight_id),
                        target=_insight_ref(right.insight_id),
                        relationship_type=relationship_type,
                        relationship_family="insight_reaction",
                        family=family,
                        weight=min(left.confidence, right.confidence),
                        confidence=min(left.confidence, right.confidence),
                        time_horizon=_shared_time_horizon(left.time_horizon, right.time_horizon),
                        observed_at=min(left.observed_at, right.observed_at).isoformat(),
                        available_at=max(left.available_at, right.available_at).isoformat(),
                        timestamp_available=max(left.available_at, right.available_at).isoformat(),
                        evidence_ref=evidence_refs[0] if evidence_refs else None,
                        evidence_refs=evidence_refs,
                        rights_policy=_merge_rights(left.source_policy, right.source_policy),
                        source_lineage={
                            "left_insight_type": left.insight_type,
                            "right_insight_type": right.insight_type,
                            "rule": f"{trigger}_{relationship_type}_{target}",
                        },
                        diagnostics={"reaction_rule": True},
                    )
                )
    return _dedupe_edges(edges)


def _insight_strategy_profile_edges(run_result: MethodologyRunResult) -> list[RelationshipEdge]:
    insights_by_id = {
        insight.insight_id: insight for insight in list(getattr(run_result, "insights", []))
    }
    translations = list(getattr(run_result, "translations", []))
    edges: list[RelationshipEdge] = []
    for translation in translations:
        insight = insights_by_id.get(translation.insight_id)
        if insight is None:
            continue
        edges.append(
            RelationshipEdge(
                source=_insight_ref(translation.insight_id),
                target=f"strategy_profile:{translation.strategy_profile_id}",
                relationship_type="depends_on",
                relationship_family="strategy_profile",
                family="insight_to_strategy_profile",
                weight=translation.fit_score,
                confidence=translation.fit_score,
                available_at=translation.generated_at.isoformat(),
                timestamp_available=translation.generated_at.isoformat(),
                evidence_ref=translation.evidence_refs[0] if translation.evidence_refs else None,
                evidence_refs=translation.evidence_refs,
                rights_policy=insight.source_policy,
                source_lineage={"translation_id": translation.translation_id},
                diagnostics={"relevance": translation.relevance},
            )
        )
    return edges


def _event_matches_insight(event, insight) -> bool:
    event_ref = f"event:{event.event_id}"
    event_type = insight.derivation_trace.get("event_type")
    if isinstance(event_type, str) and event_type != event.event_type:
        return False
    if event_ref in insight.evidence_refs:
        return True
    if set(event.evidence_refs).intersection(insight.evidence_refs):
        return True
    if insight.entity_id in event.affected_entity_ids:
        return True
    return insight.asset_id is not None and insight.asset_id in event.affected_asset_ids


def _insight_tokens(insight) -> set[str]:
    tokens = {insight.insight_type}
    event_type = insight.derivation_trace.get("event_type")
    if isinstance(event_type, str):
        tokens.add(event_type)
    tokens.update(str(item) for item in insight.risk_factors)
    tokens.update(str(item) for item in insight.invalidation_conditions)
    return tokens


def _shared_time_horizon(left: dict[str, str], right: dict[str, str]) -> str | None:
    left_max = left.get("max")
    right_max = right.get("max")
    if left_max and right_max and left_max == right_max:
        return left_max
    return left_max or right_max


def _merge_rights(left: dict, right: dict) -> dict:
    return {
        "left": left,
        "right": right,
    }


def _dedupe_edges(edges: list[RelationshipEdge]) -> list[RelationshipEdge]:
    deduped: dict[str, RelationshipEdge] = {}
    for edge in edges:
        deduped[edge.relationship_id or stable_checksum(edge.model_dump(mode="json"))] = edge
    return list(deduped.values())


def _expand_family_aliases(families: list[str]) -> set[str]:
    """Expand user-supplied family filters into the full set of matching family
    labels.

    Phase 26 migration: the legacy hardcoded dict has been lifted to
    `config/viza_concepts.json` so a new relationship family can be added
    without a code change. The concept scheme is loaded once per process and
    consulted via `ConceptScheme.family_expansion`, which walks
    `skos:narrower` transitively. The legacy bare strings (`"event"`,
    `"insight"`, `"attribute"`, `"strategy_profile"`) remain accepted because
    each concept declares them as `skos:alt_labels`.

    Falls back to a non-expanding identity when the concept scheme is
    unavailable (e.g. a stripped-down test rig); existing tests pass the bare
    strings, which still match `edge.relationship_family` directly.
    """
    expanded = set(families)
    try:
        scheme = _concept_scheme_for_relationships()
    except Exception:
        return expanded
    for family in families:
        expanded.update(scheme.family_expansion(family, domain="relationship"))
    return expanded


def _concept_scheme_for_relationships():
    from viza.concepts import get_concept_scheme

    return get_concept_scheme()


def _insight_ref(insight_id: str) -> str:
    return insight_id if insight_id.startswith("insight:") else f"insight:{insight_id}"


def _event_ref(event_id: str) -> str:
    return event_id if event_id.startswith("event:") else f"event:{event_id}"

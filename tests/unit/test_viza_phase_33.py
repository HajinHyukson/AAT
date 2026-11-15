"""Phase-33 tests: typed PROV graph + automatic edge writes from
emit_and_persist_decisions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from viza.commands import CommandMapping, SizingExpression
from viza.decisions import emit_and_persist_decisions
from viza.observations import ObservationInput, VizaObservation, observation_from_input
from viza.provenance import (
    ProvenanceEdge,
    ProvenanceStore,
    query_provenance,
    record_decision_provenance,
    record_run_bundle,
)
from viza.strategy_profiles import (
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    VizaStrategyProfile,
)


def _store(tmp_path: Path) -> ProvenanceStore:
    return ProvenanceStore(tmp_path / "prov.db")


def _observation(
    *,
    entity_id: str = "eq_aapl",
    attribute_key: str = "rsi_14d",
    value: float = 27.0,
    moment: datetime,
) -> VizaObservation:
    item = ObservationInput(
        entity_id=entity_id,
        attribute_key=attribute_key,
        value=value,
        observed_at=moment,
        available_at=moment,
        retrieved_at=moment,
    )
    return observation_from_input(item)


def _profile() -> VizaStrategyProfile:
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rule = DecisionRule(
        rule_id="rsi_buy",
        label="RSI oversold",
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(attribute_key="rsi_14d", operator="lte", threshold=30.0)
            ]
        ),
        action_template="open small position.",
        command_mapping=CommandMapping(
            command_iri="viza:cmd/buy_to_open",
            sizing=SizingExpression(method="TARGET_WEIGHT", expression="0.02"),
        ),
    )
    return VizaStrategyProfile(
        strategy_profile_id="phase-33-test",
        display_name="Phase 33 test",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        created_at=now,
        updated_at=now,
    )


# ---- Store mechanics -----------------------------------------------------


def test_provenance_store_writes_and_reads_back_edges(tmp_path: Path) -> None:
    store = _store(tmp_path)
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    edge = ProvenanceEdge(
        edge_id="edge-1",
        subject_iri="viza:entity/decision/dec-1",
        predicate="wasGeneratedBy",
        object_iri="viza:activity/run/run-1",
        generated_at_time=moment,
        run_id="run-1",
    )
    written = store.write_edges([edge])
    assert written == 1
    edges = store.edges_for_run("run-1")
    assert len(edges) == 1
    assert edges[0].predicate == "wasGeneratedBy"


def test_provenance_store_walk_from_collects_outgoing_edges(tmp_path: Path) -> None:
    store = _store(tmp_path)
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    store.write_edges(
        [
            ProvenanceEdge(
                edge_id="e1",
                subject_iri="viza:entity/decision/dec-1",
                predicate="wasGeneratedBy",
                object_iri="viza:activity/run/run-1",
                generated_at_time=moment,
                run_id="run-1",
            ),
            ProvenanceEdge(
                edge_id="e2",
                subject_iri="viza:activity/run/run-1",
                predicate="used",
                object_iri="viza:entity/observation/obs-1",
                generated_at_time=moment,
                run_id="run-1",
            ),
            ProvenanceEdge(
                edge_id="e3",
                subject_iri="viza:entity/decision/dec-2",
                predicate="wasGeneratedBy",
                object_iri="viza:activity/run/run-2",
                generated_at_time=moment,
                run_id="run-2",
            ),
        ]
    )

    walk = store.walk_from("viza:entity/decision/dec-1")
    iris = set(walk.reachable_iris)
    assert "viza:activity/run/run-1" in iris
    assert "viza:entity/observation/obs-1" in iris
    # Should not cross into the unrelated run-2 lineage.
    assert "viza:entity/decision/dec-2" not in iris


# ---- record_decision_provenance + record_run_bundle ---------------------


def test_record_decision_provenance_emits_canonical_edge_set(tmp_path: Path) -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    profile = _profile()
    observations = [_observation(moment=cutoff)]

    project_db = tmp_path / "project.db"
    import viza.project_store as project_store_mod

    original_env = project_store_mod.project_store_path
    project_store_mod.project_store_path = lambda: project_db
    try:
        decisions, _ = emit_and_persist_decisions(
            profile=profile,
            observations=observations,
            cutoff_timestamp=cutoff,
            run_id="run-phase-33",
            graph_hash="g",
            profile_version="v",
        )
        assert len(decisions) == 1
        # The PROV store now lives at the same project DB.
        from viza.provenance import get_provenance_store

        store = get_provenance_store()
        edges = store.edges_for_run("run-phase-33")
        predicates = sorted({edge.predicate for edge in edges})
        assert "wasGeneratedBy" in predicates
        assert "wasAttributedTo" in predicates
        assert "used" in predicates
        assert "wasDerivedFrom" in predicates
        assert "hadMember" in predicates
    finally:
        project_store_mod.project_store_path = original_env


def test_query_provenance_walks_back_to_observation_root(tmp_path: Path) -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    profile = _profile()
    observations = [_observation(moment=cutoff)]

    project_db = tmp_path / "project.db"
    import viza.project_store as project_store_mod

    original_env = project_store_mod.project_store_path
    project_store_mod.project_store_path = lambda: project_db
    try:
        decisions, _ = emit_and_persist_decisions(
            profile=profile,
            observations=observations,
            cutoff_timestamp=cutoff,
            run_id="run-phase-33",
            graph_hash="g",
            profile_version="v",
        )
        decision = decisions[0]
        assert decision.provenance is not None
        walk = query_provenance(decision.provenance.decision_entity_iri)
        iris = set(walk.reachable_iris)
        assert "viza:activity/run/run-phase-33" in iris
        # The observation IRI for the single triggering observation is present.
        assert any(iri.startswith("viza:entity/observation/") for iri in iris)
        # Agent attribution edge is in the walk.
        agent_iris = [
            edge.object_iri for edge in walk.edges if edge.predicate == "wasAttributedTo"
        ]
        assert any("strategy_profile" in iri for iri in agent_iris)
    finally:
        project_store_mod.project_store_path = original_env


def test_run_bundle_carries_hadmember_edges_for_each_decision(tmp_path: Path) -> None:
    """`record_run_bundle` emits a `viza:bundle/run/<run_id>` entity with a
    `hadMember` edge per decision IRI. Future marketplace exports use this
    bundle as the anchor when packaging the run's full lineage."""
    store = _store(tmp_path)
    started = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    ended = datetime(2026, 5, 21, 12, 0, 1, tzinfo=timezone.utc)
    written = record_run_bundle(
        run_id="run-X",
        activity_iri="viza:activity/run/run-X",
        decision_iris=["viza:entity/decision/d-1", "viza:entity/decision/d-2"],
        started_at_time=started,
        ended_at_time=ended,
        agent_iri="viza:agent/strategy_profile/test",
        store=store,
    )
    assert written >= 3  # 1 wasInformedBy + 1 wasAttributedTo + 2 hadMember
    bundle_walk = store.walk_from("viza:bundle/run/run-X")
    member_iris = [
        edge.object_iri
        for edge in bundle_walk.edges
        if edge.predicate == "hadMember"
    ]
    assert sorted(member_iris) == [
        "viza:entity/decision/d-1",
        "viza:entity/decision/d-2",
    ]


# ---- Rights-aware edges --------------------------------------------------


def test_edge_carries_rights_ref_when_observation_blocks_export(tmp_path: Path) -> None:
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    profile = _profile()
    item = ObservationInput(
        entity_id="eq_aapl",
        attribute_key="rsi_14d",
        value=27.0,
        observed_at=cutoff,
        available_at=cutoff,
        retrieved_at=cutoff,
        rights_policy={"export_allowed": False, "raw_snapshot_allowed": False},
    )
    blocked_obs = observation_from_input(item)

    project_db = tmp_path / "project.db"
    import viza.project_store as project_store_mod

    original = project_store_mod.project_store_path
    project_store_mod.project_store_path = lambda: project_db
    try:
        decisions, _ = emit_and_persist_decisions(
            profile=profile,
            observations=[blocked_obs],
            cutoff_timestamp=cutoff,
            run_id="run-blocked",
            graph_hash="g",
            profile_version="v",
        )
        # Rights-blocked observations promote the rule's emit to BLOCK_EXPORT
        # — Phase 27 behavior. Verify the PROV edge picks up the rights_policy_ref.
        from viza.provenance import get_provenance_store

        store = get_provenance_store()
        edges = store.edges_for_run("run-blocked")
        wgb_edges = [e for e in edges if e.predicate == "wasGeneratedBy"]
        assert wgb_edges, "should have at least one wasGeneratedBy edge"
        assert any(edge.rights_policy_ref == "export_blocked" for edge in wgb_edges)
    finally:
        project_store_mod.project_store_path = original


# ---- Idempotency --------------------------------------------------------


def test_record_decision_provenance_is_idempotent(tmp_path: Path) -> None:
    """Edges are content-addressed by (subject, predicate, object,
    generated_at_time), so re-running the same record_decision_provenance
    call must not double-count."""
    store = _store(tmp_path)
    cutoff = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)

    # Build a minimal decision-like duck-typed object so we don't have to
    # emit_and_persist again. The provenance module accepts any object with
    # the right attributes.
    class _FakeProvenance:
        decision_entity_iri = "viza:entity/decision/d-1"
        was_generated_by_run_iri = "viza:activity/run/run-1"
        was_attributed_to_agent_iri = "viza:agent/strategy_profile/test"
        used_observation_iris = ["viza:entity/observation/obs-1"]

    class _FakeAudit:
        run_id = "run-1"

    class _FakeDecision:
        provenance = _FakeProvenance()
        audit = _FakeAudit()
        source_rights_state = {}

    fake = _FakeDecision()
    first = record_decision_provenance(
        decisions=[fake], store=store, generated_at=cutoff
    )
    second = record_decision_provenance(
        decisions=[fake], store=store, generated_at=cutoff
    )
    assert first == second
    edges = store.edges_for_run("run-1")
    # Same edges, no duplicates.
    edge_ids = [edge.edge_id for edge in edges]
    assert len(edge_ids) == len(set(edge_ids))

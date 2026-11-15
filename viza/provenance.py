"""W3C-PROV graph store for VIZA — Phase 33.

The compliance plan (`docs/viza_end_product/VIZA_KR_COMPLIANCE_REPORT.md` §3,
`VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md` §3 Phase 33) calls for
lineage to become a queryable graph rather than a per-output dict. Phase 27
already shipped a `DecisionProvenance` block carrying PROV-shaped fields
(`decision_entity_iri`, `was_generated_by_run_iri`, `used_observation_iris`).
Phase 33 lifts those fields into a typed edge table so:

* Lineage is queryable independent of which entity owns it.
* New entity kinds (events, insights, validation records) can join the graph
  without growing per-entity schema.
* Marketplace dispute resolution has a single source of truth: "show me the
  chain that produced this signal" is one graph walk.

Vocabulary
----------

Subject/predicate/object are IRIs and a small set of PROV predicates:

* ``prov:wasGeneratedBy``  Entity → Activity
* ``prov:used``            Activity → Entity
* ``prov:wasDerivedFrom``  Entity → Entity
* ``prov:wasAttributedTo`` Entity → Agent
* ``prov:wasInformedBy``   Activity → Activity (via shared entity)
* ``prov:hadMember``       Bundle → Entity (used for run-bundle membership)

The store is content-agnostic — edges can describe any entity. The
``record_decision_provenance`` helper translates a `DecisionFrame` into the
canonical edge set; `record_run_provenance` does the same for a
`MethodologyRunResult`-style summary.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from viza.project_store import project_store_path


ProvPredicate = Literal[
    "wasGeneratedBy",
    "used",
    "wasDerivedFrom",
    "wasAttributedTo",
    "wasInformedBy",
    "hadMember",
]


class ProvenanceEdge(BaseModel):
    """A single typed lineage edge.

    `subject_iri` and `object_iri` are stable, content-addressed IRIs
    (``viza:entity/decision/decision-…``, ``viza:activity/run/run-…``, etc.).
    `generated_at_time` records the wall-clock time the edge was written,
    not when the underlying entity came into being.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.provenance_edge.v1", alias="schema")
    edge_id: str
    subject_iri: str
    predicate: ProvPredicate
    object_iri: str
    generated_at_time: datetime
    rights_policy_ref: str | None = None
    run_id: str | None = None  # Index hint; lets us list edges per run.


class ProvenanceStore:
    """SQLite-backed PROV edge store."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def write_edges(self, edges: Iterable[ProvenanceEdge]) -> int:
        rows = [
            (
                edge.edge_id,
                edge.subject_iri,
                edge.predicate,
                edge.object_iri,
                edge.generated_at_time.isoformat(),
                edge.rights_policy_ref,
                edge.run_id,
            )
            for edge in edges
        ]
        if not rows:
            return 0
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO provenance_edges(
                    edge_id, subject_iri, predicate, object_iri,
                    generated_at_time, rights_policy_ref, run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(edge_id) DO UPDATE SET
                    subject_iri = excluded.subject_iri,
                    predicate = excluded.predicate,
                    object_iri = excluded.object_iri,
                    generated_at_time = excluded.generated_at_time,
                    rights_policy_ref = excluded.rights_policy_ref,
                    run_id = excluded.run_id
                """,
                rows,
            )
        return len(rows)

    def edges_for_run(self, run_id: str) -> list[ProvenanceEdge]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM provenance_edges WHERE run_id = ? "
                "ORDER BY generated_at_time ASC, edge_id ASC",
                (run_id,),
            ).fetchall()
        return [_edge_from_row(row) for row in rows]

    def edges_with_subject(self, subject_iri: str) -> list[ProvenanceEdge]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM provenance_edges WHERE subject_iri = ? "
                "ORDER BY generated_at_time ASC, edge_id ASC",
                (subject_iri,),
            ).fetchall()
        return [_edge_from_row(row) for row in rows]

    def edges_with_object(self, object_iri: str) -> list[ProvenanceEdge]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM provenance_edges WHERE object_iri = ? "
                "ORDER BY generated_at_time ASC, edge_id ASC",
                (object_iri,),
            ).fetchall()
        return [_edge_from_row(row) for row in rows]

    def walk_from(
        self,
        root_iri: str,
        *,
        max_hops: int = 16,
    ) -> "ProvenanceWalk":
        """Breadth-first walk from `root_iri` over outgoing edges.

        Outgoing = the root is the SUBJECT of the edge. For an Entity, that
        traces back to the activities and entities it depends on (because
        Entity ``wasGeneratedBy`` Activity, Activity ``used`` Entity).
        ``max_hops`` caps the BFS depth so cycles cannot infinite-loop.
        """
        visited: set[str] = set()
        edges: list[ProvenanceEdge] = []
        frontier: list[tuple[str, int]] = [(root_iri, 0)]
        while frontier:
            iri, depth = frontier.pop(0)
            if iri in visited or depth > max_hops:
                continue
            visited.add(iri)
            outgoing = self.edges_with_subject(iri)
            for edge in outgoing:
                edges.append(edge)
                if edge.object_iri not in visited:
                    frontier.append((edge.object_iri, depth + 1))
        return ProvenanceWalk(root_iri=root_iri, edges=edges, reachable_iris=sorted(visited))

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(PROVENANCE_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


PROVENANCE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS provenance_edges (
  edge_id TEXT PRIMARY KEY,
  subject_iri TEXT NOT NULL,
  predicate TEXT NOT NULL,
  object_iri TEXT NOT NULL,
  generated_at_time TEXT NOT NULL,
  rights_policy_ref TEXT,
  run_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_provenance_subject
  ON provenance_edges(subject_iri);
CREATE INDEX IF NOT EXISTS idx_provenance_object
  ON provenance_edges(object_iri);
CREATE INDEX IF NOT EXISTS idx_provenance_run
  ON provenance_edges(run_id);
"""


class ProvenanceWalk(BaseModel):
    """Bounded walk over the PROV graph from a root IRI."""

    model_config = ConfigDict(extra="forbid")

    root_iri: str
    edges: list[ProvenanceEdge] = Field(default_factory=list)
    reachable_iris: list[str] = Field(default_factory=list)


def get_provenance_store(path: str | Path | None = None) -> ProvenanceStore:
    return ProvenanceStore(path)


# ---- Decision → edge translation ----------------------------------------


def record_decision_provenance(
    *,
    decisions: list[Any],
    store: ProvenanceStore | None = None,
    generated_at: datetime | None = None,
) -> int:
    """Write the canonical PROV edges for a list of DecisionFrames.

    For each decision with a `provenance` block, emit:

    * (decision Entity) ``prov:wasGeneratedBy`` (run Activity)
    * (decision Entity) ``prov:wasAttributedTo`` (agent)
    * (run Activity) ``prov:used`` (each observation Entity)

    Returns the number of edges written. Idempotent: edges are
    content-addressed by (subject, predicate, object, generated_at).
    """
    active = store or get_provenance_store()
    moment = generated_at or datetime.now(timezone.utc)
    edges: list[ProvenanceEdge] = []
    for decision in decisions:
        provenance = getattr(decision, "provenance", None)
        if provenance is None:
            continue
        # decision wasGeneratedBy run
        edges.append(
            _edge(
                subject=provenance.decision_entity_iri,
                predicate="wasGeneratedBy",
                object_iri=provenance.was_generated_by_run_iri,
                moment=moment,
                run_id=decision.audit.run_id,
                rights_policy_ref=_rights_ref(decision),
            )
        )
        # decision wasAttributedTo agent
        edges.append(
            _edge(
                subject=provenance.decision_entity_iri,
                predicate="wasAttributedTo",
                object_iri=provenance.was_attributed_to_agent_iri,
                moment=moment,
                run_id=decision.audit.run_id,
            )
        )
        # run used each triggering observation
        for obs_iri in provenance.used_observation_iris:
            edges.append(
                _edge(
                    subject=provenance.was_generated_by_run_iri,
                    predicate="used",
                    object_iri=obs_iri,
                    moment=moment,
                    run_id=decision.audit.run_id,
                )
            )
        # decision wasDerivedFrom each observation entity
        for obs_iri in provenance.used_observation_iris:
            edges.append(
                _edge(
                    subject=provenance.decision_entity_iri,
                    predicate="wasDerivedFrom",
                    object_iri=obs_iri,
                    moment=moment,
                    run_id=decision.audit.run_id,
                )
            )
    return active.write_edges(edges)


def record_run_bundle(
    *,
    run_id: str,
    activity_iri: str,
    decision_iris: Iterable[str],
    started_at_time: datetime,
    ended_at_time: datetime,
    agent_iri: str | None = None,
    store: ProvenanceStore | None = None,
) -> int:
    """Promote a MethodologyRunResult to a first-class `prov:Activity` row
    with explicit start/end times and per-decision `hadMember` edges from
    the bundle entity to each decision."""
    active = store or get_provenance_store()
    bundle_iri = f"viza:bundle/run/{run_id}"
    edges: list[ProvenanceEdge] = [
        _edge(
            subject=activity_iri,
            predicate="wasInformedBy",
            object_iri=bundle_iri,
            moment=started_at_time,
            run_id=run_id,
        )
    ]
    if agent_iri:
        edges.append(
            _edge(
                subject=activity_iri,
                predicate="wasAttributedTo",
                object_iri=agent_iri,
                moment=started_at_time,
                run_id=run_id,
            )
        )
    for decision_iri in decision_iris:
        edges.append(
            _edge(
                subject=bundle_iri,
                predicate="hadMember",
                object_iri=decision_iri,
                moment=ended_at_time,
                run_id=run_id,
            )
        )
    return active.write_edges(edges)


def query_provenance(
    root_iri: str,
    *,
    store: ProvenanceStore | None = None,
    max_hops: int = 16,
) -> ProvenanceWalk:
    """High-level query: walk forward from `root_iri` over outgoing edges,
    bounded by `max_hops`. Used by the desktop "Where did this come from?"
    inspector and by future marketplace dispute resolution."""
    active = store or get_provenance_store()
    return active.walk_from(root_iri, max_hops=max_hops)


# ---- Internals ----------------------------------------------------------


def _edge(
    *,
    subject: str,
    predicate: ProvPredicate,
    object_iri: str,
    moment: datetime,
    run_id: str | None = None,
    rights_policy_ref: str | None = None,
) -> ProvenanceEdge:
    edge_id = _edge_id(
        subject=subject,
        predicate=predicate,
        object_iri=object_iri,
        moment=moment,
    )
    return ProvenanceEdge(
        edge_id=edge_id,
        subject_iri=subject,
        predicate=predicate,
        object_iri=object_iri,
        generated_at_time=moment,
        rights_policy_ref=rights_policy_ref,
        run_id=run_id,
    )


def _edge_id(
    *, subject: str, predicate: str, object_iri: str, moment: datetime
) -> str:
    import hashlib

    payload = {
        "subject": subject,
        "predicate": predicate,
        "object": object_iri,
        "generated_at_time": moment.isoformat(),
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"prov-{digest[:24]}"


def _rights_ref(decision: Any) -> str | None:
    state = getattr(decision, "source_rights_state", None)
    if not isinstance(state, dict):
        return None
    if state.get("export_allowed") is False:
        return "export_blocked"
    if state.get("raw_snapshot_allowed") is False:
        return "raw_snapshot_blocked"
    return None


def _edge_from_row(row: sqlite3.Row) -> ProvenanceEdge:
    return ProvenanceEdge(
        edge_id=row["edge_id"],
        subject_iri=row["subject_iri"],
        predicate=row["predicate"],
        object_iri=row["object_iri"],
        generated_at_time=datetime.fromisoformat(row["generated_at_time"]),
        rights_policy_ref=row["rights_policy_ref"],
        run_id=row["run_id"],
    )

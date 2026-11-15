"""VIZA decision frames, executor, and store.

See docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md. The module covers Phases A
through C.2 of that plan:

- ``DecisionFrame`` — the typed payload emitted by output_radar when a user's
  ``DecisionRule`` fires against PIT-filtered observations.
- ``compile_decisions`` — deterministic executor for both ``sandbox_replay``
  and ``live`` modes. Live mode is gated by ``_enforce_live_mode_preconditions``.
- ``DecisionStore`` — SQLite-backed persistence; CHECK constraint accepts
  ``sandbox_replay`` and ``live`` and rejects any other value at the DB layer.
- ``replay_decisions_from_store`` — pin-5 (B) replay path; filters by cutoff
  so a replay never returns decisions whose triggering observations were not
  yet available at the requested cutoff.

The simulator-frame structural points are enforced here:

1. User authors the rule — the executor never synthesizes a rule.
2. Output language is the user's ``action_template`` quoted verbatim.
3. Sandbox-replay is the default mode; live mode requires
   ``VIZA_LIVE_MODE_ENABLED=true`` AND a per-profile opt-in matching the
   current ``LIVE_MODE_DISCLOSURE_VERSION`` AND every enabled rule
   declaring ``effective_from <= cutoff_timestamp``. The SQLite CHECK
   rejects any mode outside ``(sandbox_replay, live)``.
5. No portfolio integration — executor operates on observations only.
6. No execution — this module emits frames, nothing else.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from viza.fibo import FiboIdentity

from pydantic import BaseModel, ConfigDict, Field

from datetime import timedelta

from viza.audit import evidence_checksum as compute_evidence_checksum, stable_checksum
from viza.commands import (
    CommandMapping,
    CommandTarget,
    InvestmentCommandPayload,
    SizingExpression,
    build_command_from_concept,
    get_command_conflicts,
    get_command_taxonomy,
)
from viza.feel_lite import FeelLiteError, evaluate as feel_evaluate
from viza.observations import VizaObservation
from viza.project_store import project_store_path
from viza.strategy_profiles import (
    CooldownPolicy,
    DecisionRule,
    LiveModeOptIn,
    ObservationPredicate,
    VizaStrategyProfile,
)

# NOTE: viza.validation_ledger imports are deferred to function scope to avoid
# a circular import (viza.validation_ledger → viza.file_format → viza.marketplace
# → viza.validation_ledger). The validation ledger types are only used by
# Phase B helpers below, so the cycle is broken cleanly by lazy import.


DecisionMode = Literal["sandbox_replay", "live"]

LIVE_MODE_ENV_VAR = "VIZA_LIVE_MODE_ENABLED"
LIVE_MODE_DISCLOSURE_VERSION = "v1"

LIVE_MODE_DISCLOSURE_TEXT = (
    "You are activating live mode for this strategy profile. In live mode, "
    "VIZA computes decisions against the latest observations the engine has "
    "in the local project store at the moment the run is started, rather than "
    "against a stored historical cutoff.\n\n"
    "This is not investment advice. The decisions emitted are deterministic "
    "firings of the rules YOU authored in this strategy profile. VIZA does not "
    "produce its own investment guidance. The action templates in your rules "
    "are quoted verbatim.\n\n"
    "By activating live mode, you confirm:\n"
    "- You authored the rules in this profile, or you are reviewing community "
    "shapes and accept them as your own.\n"
    "- You understand that VIZA neither places orders nor connects to brokerages.\n"
    "- You will exercise your own judgment before taking any step based on the "
    "rule firings displayed.\n\n"
    "This consent is recorded with a timestamp and a version identifier. If "
    "the disclosure text is updated, you will be asked to re-confirm."
)


class LiveModeDisabledError(RuntimeError):
    """Raised when live mode is requested but VIZA_LIVE_MODE_ENABLED is not set."""


class LiveModeOptInRequiredError(RuntimeError):
    """Raised when live mode is requested for a profile with no opt-in record."""


class LiveModeOptInStaleError(RuntimeError):
    """Raised when the profile's opt-in disclosure version does not match the
    current ``LIVE_MODE_DISCLOSURE_VERSION``. The user must re-confirm."""

    def __init__(self, *, accepted_version: str, current_version: str) -> None:
        super().__init__(
            f"live-mode opt-in stale: profile accepted {accepted_version!r}, "
            f"current disclosure version is {current_version!r}; re-opt-in required"
        )
        self.accepted_version = accepted_version
        self.current_version = current_version


class LiveModeRuleEffectiveDateRequiredError(RuntimeError):
    """Raised when an enabled DecisionRule lacks ``effective_from`` under live
    mode. The pin-5 (C) gate that is lenient in sandbox replay is strict in
    live mode — every rule must declare when it became effective."""

    def __init__(self, *, rule_id: str) -> None:
        super().__init__(
            f"live mode requires DecisionRule.effective_from on every enabled "
            f"rule; rule {rule_id!r} has effective_from=None"
        )
        self.rule_id = rule_id


class DecisionAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    graph_hash: str
    profile_version: str
    run_id: str
    evidence_checksum: str


class DecisionProvenance(BaseModel):
    """W3C-PROV-shaped provenance for a single decision.

    Phase 27 of `docs/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md` §2.3.
    The four checksum fields from `DecisionAudit` survive as content-address
    identifiers for the underlying `prov:Entity` instances (the graph, the
    profile, the evidence bundle, the result). Phase 33 lifts these into a
    typed PROV edge table; Phase 27 only requires the field layout so the
    DecisionFrame's persisted shape is forward-compatible.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    decision_entity_iri: str
    was_generated_by_run_iri: str
    was_attributed_to_agent_iri: str
    used_observation_iris: list[str] = Field(default_factory=list)
    used_event_iris: list[str] = Field(default_factory=list)
    used_insight_iris: list[str] = Field(default_factory=list)
    was_derived_from_iris: list[str] = Field(default_factory=list)
    graph_hash: str
    profile_version: str
    evidence_checksum: str
    result_checksum: str | None = None


class PriorEmission(BaseModel):
    """A previously-emitted decision used for cooldown bookkeeping.

    Phase C. Callers of ``compile_decisions`` pass a list of these to enforce
    per-rule cooldown and dead-band suppression across runs. The values are
    plain identifiers and floats so this is store-agnostic.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    entity_id: str
    cutoff_timestamp: datetime
    trigger_values: dict[str, float] = Field(default_factory=dict)


class DecisionFrame(BaseModel):
    """A single decision emitted by an output_radar node under sandbox replay.

    ``action_template`` is the user's own rule wording, quoted verbatim. The
    runtime never substitutes or augments it. ``not_investment_advice`` is a
    structural marker; the simulator frame is defended by the seven structural
    points, not by this flag alone.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.decision.v1", alias="schema")
    decision_id: str
    strategy_profile_id: str
    rule_id: str
    entity_id: str
    asset_id: str | None = None
    action_template: str
    rule_text: str
    trigger_observation_ids: list[str] = Field(default_factory=list)
    pit_state: dict[str, Any] = Field(default_factory=dict)
    source_rights_state: dict[str, Any] = Field(default_factory=dict)
    cutoff_timestamp: datetime
    mode: DecisionMode = "sandbox_replay"
    emitted_at: datetime
    audit: DecisionAudit
    not_investment_advice: bool = True
    # Phase 27 additions. `command` is optional so legacy rules without a
    # command_mapping continue to emit DecisionFrames with command=None;
    # `provenance` is optional so persisted pre-Phase-27 rows decode without
    # requiring a backfill of PROV identifiers.
    command: InvestmentCommandPayload | None = None
    provenance: DecisionProvenance | None = None
    argumentation_status: Literal["accepted", "rejected", "undecided"] = "undecided"
    argumentation_reason: str | None = None


def compile_decisions(
    *,
    profile: VizaStrategyProfile,
    observations: list[VizaObservation],
    cutoff_timestamp: datetime,
    run_id: str,
    graph_hash: str,
    profile_version: str,
    mode: str = "sandbox_replay",
    emitted_at: datetime | None = None,
    prior_emissions: list[PriorEmission] | None = None,
    transaction_time_cutoff: datetime | None = None,
    fibo_identity_resolver: "Callable[[str], FiboIdentity | None] | None" = None,
    events: list[Any] | None = None,
) -> list[DecisionFrame]:
    """Compile a strategy profile's DecisionRule list against PIT-filtered
    observations and return the resulting DecisionFrame list.

    Deterministic: same inputs ⇒ identical output (decision IDs, evidence
    checksums, ordering).

    Phase 28 bitemporal semantics
    -----------------------------
    ``cutoff_timestamp`` is the *valid-time* cutoff — the PIT discipline
    timestamp the existing engine has always used (filters by
    ``available_at``). ``transaction_time_cutoff`` is the *transaction-time*
    AS-OF point — the snapshot of what the system *believed* at that moment.

    * When ``transaction_time_cutoff`` is ``None`` (the default), the executor
      uses the system's *current belief*: only observations whose
      ``transaction_time_end`` is ``None`` are considered. This matches the
      pre-Phase-28 behavior on data sets that have no corrections (every row
      has ``transaction_time_end = None``).
    * When ``transaction_time_cutoff`` is set, the executor reconstructs the
      observation set the system held at that transaction time. This is what
      ``replay_decisions_from_store`` uses to prove that a past run can be
      reproduced even after corrections.

    Live mode raises ``NotImplementedError``. Phase A enforces the boundary at
    both the type level (``DecisionMode`` literal) and the runtime level (this
    function), and the DB layer (CHECK constraint on the decisions table).
    """
    if mode not in ("sandbox_replay", "live"):
        raise ValueError(
            f"unknown output_radar mode={mode!r}; "
            "supported: ('sandbox_replay', 'live')"
        )
    if mode == "live":
        _enforce_live_mode_preconditions(profile=profile, cutoff_timestamp=cutoff_timestamp)

    emit_time = emitted_at or _utc_now()

    pit_observations = [
        obs for obs in observations if obs.available_at <= cutoff_timestamp
    ]
    pit_observations = _filter_by_transaction_time(
        pit_observations, transaction_time_cutoff
    )

    obs_by_id: dict[str, VizaObservation] = {
        obs.observation_id: obs for obs in pit_observations
    }
    latest_by_key: dict[tuple[str, str], VizaObservation] = {}
    for obs in pit_observations:
        key = (obs.entity_id, obs.attribute_key)
        existing = latest_by_key.get(key)
        if existing is None or obs.available_at > existing.available_at:
            latest_by_key[key] = obs

    entity_ids = sorted({obs.entity_id for obs in pit_observations})

    decisions: list[DecisionFrame] = []
    for rule in profile.decision_rules:
        if not rule.enabled:
            continue
        if rule.effective_from is not None and rule.effective_from > cutoff_timestamp:
            # Pin-5 (C) analog: a rule that did not yet exist as of the
            # replay cutoff cannot have fired. Sandbox replay must not
            # fabricate decisions retroactively.
            continue
        for entity_id in entity_ids:
            triggered_ids = _evaluate_rule_for_entity(
                rule=rule,
                entity_id=entity_id,
                latest_by_key=latest_by_key,
                events=events,
                cutoff_timestamp=cutoff_timestamp,
            )
            if triggered_ids is None:
                continue
            if _cooldown_suppresses(
                rule=rule,
                entity_id=entity_id,
                cutoff_timestamp=cutoff_timestamp,
                prior_emissions=prior_emissions or [],
                latest_by_key=latest_by_key,
            ):
                continue
            decision_id = _decision_id(
                rule_id=rule.rule_id,
                entity_id=entity_id,
                cutoff_timestamp=cutoff_timestamp,
                run_id=run_id,
            )
            evidence_checksum = _evidence_checksum(triggered_ids, obs_by_id)
            asset_id = _asset_id_for_entity(latest_by_key, entity_id)
            pit_state = _pit_state(triggered_ids, obs_by_id, cutoff_timestamp)
            source_rights_state = _source_rights_state(triggered_ids, obs_by_id)
            command = _build_command_for_rule(
                rule=rule,
                entity_id=entity_id,
                asset_id=asset_id,
                latest_by_key=latest_by_key,
                triggered_ids=triggered_ids,
                obs_by_id=obs_by_id,
                source_rights_state=source_rights_state,
                pit_state=pit_state,
                fibo_identity_resolver=fibo_identity_resolver,
            )
            provenance = _build_provenance(
                decision_id=decision_id,
                run_id=run_id,
                profile=profile,
                triggered_ids=triggered_ids,
                graph_hash=graph_hash,
                profile_version=profile_version,
                evidence_checksum=evidence_checksum,
            )
            decisions.append(
                DecisionFrame(
                    decision_id=decision_id,
                    strategy_profile_id=profile.strategy_profile_id,
                    rule_id=rule.rule_id,
                    entity_id=entity_id,
                    asset_id=asset_id,
                    action_template=rule.action_template,
                    rule_text=f"{rule.rule_id}: {rule.label}",
                    trigger_observation_ids=sorted(triggered_ids),
                    pit_state=pit_state,
                    source_rights_state=source_rights_state,
                    cutoff_timestamp=cutoff_timestamp,
                    mode="sandbox_replay",
                    emitted_at=emit_time,
                    audit=DecisionAudit(
                        graph_hash=graph_hash,
                        profile_version=profile_version,
                        run_id=run_id,
                        evidence_checksum=evidence_checksum,
                    ),
                    command=command,
                    provenance=provenance,
                )
            )

    from viza.argumentation import apply_argumentation  # local: cycle-safe

    decisions = apply_argumentation(decisions, events=events)
    decisions.sort(key=lambda d: (d.entity_id, d.rule_id, d.decision_id))
    # Stamp emitted decisions with the requested mode (sandbox_replay or live)
    # rather than the executor's default literal. The mode is the caller's
    # contract; the DecisionFrame must reflect it.
    if mode == "live":
        decisions = [
            decision.model_copy(update={"mode": "live"}) for decision in decisions
        ]
    return decisions


def _enforce_live_mode_preconditions(
    *,
    profile: VizaStrategyProfile,
    cutoff_timestamp: datetime,
) -> None:
    """Defense-in-depth guard for live mode.

    Phase C.2 invariants enforced here:

    1. ``VIZA_LIVE_MODE_ENABLED=true`` must be set in the process environment.
       Deployments default-off; tests and live operators opt in explicitly.
    2. The strategy profile carries a non-null ``live_mode_opt_in`` whose
       ``accepted_disclosure_version`` matches the current
       ``LIVE_MODE_DISCLOSURE_VERSION``. Stale opt-ins re-prompt the user.
    3. Every enabled ``DecisionRule`` declares an ``effective_from`` ≤ cutoff.
       Sandbox replay tolerates ``effective_from=None`` for synthetic
       fixtures; live mode does not.
    """
    if os.environ.get(LIVE_MODE_ENV_VAR, "").strip().lower() != "true":
        raise LiveModeDisabledError(
            f"live mode requires {LIVE_MODE_ENV_VAR}=true in the process "
            "environment (currently unset or off)"
        )

    opt_in: LiveModeOptIn | None = profile.live_mode_opt_in
    if opt_in is None:
        raise LiveModeOptInRequiredError(
            f"strategy profile {profile.strategy_profile_id!r} has no live-mode "
            "opt-in record; the user must accept the disclosure first"
        )
    if opt_in.accepted_disclosure_version != LIVE_MODE_DISCLOSURE_VERSION:
        raise LiveModeOptInStaleError(
            accepted_version=opt_in.accepted_disclosure_version,
            current_version=LIVE_MODE_DISCLOSURE_VERSION,
        )

    for rule in profile.decision_rules:
        if not rule.enabled:
            continue
        if rule.effective_from is None:
            raise LiveModeRuleEffectiveDateRequiredError(rule_id=rule.rule_id)
        if rule.effective_from > cutoff_timestamp:
            raise LiveModeRuleEffectiveDateRequiredError(rule_id=rule.rule_id)


def replay_decisions_from_store(
    *,
    store: DecisionStore,
    run_id: str,
    cutoff_timestamp: datetime,
) -> list[DecisionFrame]:
    """Pin-5 (B) replay: return only decisions whose max triggering observation
    available_at is at or before ``cutoff_timestamp``. Decisions emitted at a
    later cutoff (or with any post-cutoff observation in their pit_state) are
    filtered out."""
    decisions = store.list_decisions_by_run(run_id)
    filtered: list[DecisionFrame] = []
    for decision in decisions:
        max_obs_avail = decision.pit_state.get("max_observation_available_at")
        if not isinstance(max_obs_avail, str) or not max_obs_avail:
            raise ValueError(
                f"decision {decision.decision_id!r} has malformed "
                f"pit_state.max_observation_available_at={max_obs_avail!r}; "
                "the executor always writes a valid ISO timestamp, so a missing "
                "or non-string value indicates schema corruption or a writer "
                "that bypassed compile_decisions"
            )
        max_obs_dt = datetime.fromisoformat(max_obs_avail)
        if max_obs_dt > cutoff_timestamp:
            continue
        if decision.cutoff_timestamp > cutoff_timestamp:
            continue
        filtered.append(decision)
    return filtered


class DecisionStore:
    """SQLite-backed persistence for DecisionFrame rows.

    The schema CHECK constraint accepts only ``sandbox_replay`` and ``live``
    as valid ``mode`` values, so a typo or future code path that produced
    any other mode would be rejected at the DB layer regardless of the
    Pydantic literal type.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    _DECISION_INSERT_COLUMNS = (
        "decision_id",
        "strategy_profile_id",
        "rule_id",
        "entity_id",
        "asset_id",
        "action_template",
        "rule_text",
        "trigger_observation_ids_json",
        "pit_state_json",
        "source_rights_state_json",
        "cutoff_timestamp",
        "mode",
        "emitted_at",
        "graph_hash",
        "profile_version",
        "run_id",
        "evidence_checksum",
        "not_investment_advice",
        "command_json",
        "provenance_json",
        "argumentation_status",
        "argumentation_reason",
        "command_iri",
    )

    def upsert_decision(self, decision: DecisionFrame) -> DecisionFrame:
        columns = self._DECISION_INSERT_COLUMNS
        placeholders = ", ".join(["?"] * len(columns))
        update_set = ",\n                    ".join(
            f"{column} = excluded.{column}"
            for column in columns
            if column != "decision_id"
        )
        sql = (
            f"INSERT INTO decisions({', '.join(columns)})\n"
            f"VALUES ({placeholders})\n"
            f"ON CONFLICT(decision_id) DO UPDATE SET\n                    {update_set}"
        )
        with self._connect() as connection:
            connection.execute(sql, _decision_row_values(decision))
        return self.require_decision(decision.decision_id)

    def get_decision(self, decision_id: str) -> DecisionFrame | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM decisions WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
        return _decision_from_row(row) if row is not None else None

    def require_decision(self, decision_id: str) -> DecisionFrame:
        decision = self.get_decision(decision_id)
        if decision is None:
            raise KeyError(f"unknown VIZA decision: {decision_id}")
        return decision

    def list_decisions_by_run(self, run_id: str) -> list[DecisionFrame]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM decisions
                WHERE run_id = ?
                ORDER BY entity_id ASC, rule_id ASC, decision_id ASC
                """,
                (run_id,),
            ).fetchall()
        return [_decision_from_row(row) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(DECISION_TABLE_SQL)
            _migrate_pre_c2_check_if_needed(connection)
            _migrate_phase_27_command_columns(connection)
            connection.executescript(DECISION_INDEX_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


_PRE_C2_CHECK_FRAGMENT = "CHECK (mode = 'sandbox_replay')"
_C2_CHECK_FRAGMENT = "CHECK (mode IN ('sandbox_replay', 'live'))"


def _migrate_pre_c2_check_if_needed(connection: sqlite3.Connection) -> None:
    """Migrate a pre-C.2 decisions table to the widened CHECK constraint.

    Phase C.2 widens the SQLite CHECK from ``mode = 'sandbox_replay'`` to
    ``mode IN ('sandbox_replay', 'live')``. ``CREATE TABLE IF NOT EXISTS``
    skips recreation when the table already exists, so a database created
    under Phase C.1 retains the old (overly narrow) CHECK and would reject
    ``mode='live'`` inserts. This helper detects that case and migrates
    via the standard SQLite temp-table copy pattern. Idempotent — re-running
    against an already-migrated table is a no-op.
    """
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='decisions'"
    ).fetchone()
    if row is None:
        return
    existing_sql = row[0] if not isinstance(row, sqlite3.Row) else row["sql"]
    if not isinstance(existing_sql, str):
        return
    if _C2_CHECK_FRAGMENT in existing_sql:
        return
    if _PRE_C2_CHECK_FRAGMENT not in existing_sql:
        return

    # Migrate: build new table, copy rows, swap, re-create indexes.
    connection.executescript(
        """
        BEGIN;
        CREATE TABLE decisions_c2_migration (
          decision_id TEXT PRIMARY KEY,
          strategy_profile_id TEXT NOT NULL,
          rule_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          asset_id TEXT,
          action_template TEXT NOT NULL,
          rule_text TEXT NOT NULL,
          trigger_observation_ids_json TEXT NOT NULL DEFAULT '[]',
          pit_state_json TEXT NOT NULL DEFAULT '{}',
          source_rights_state_json TEXT NOT NULL DEFAULT '{}',
          cutoff_timestamp TEXT NOT NULL,
          mode TEXT NOT NULL DEFAULT 'sandbox_replay',
          emitted_at TEXT NOT NULL,
          graph_hash TEXT NOT NULL,
          profile_version TEXT NOT NULL,
          run_id TEXT NOT NULL,
          evidence_checksum TEXT NOT NULL,
          not_investment_advice INTEGER NOT NULL DEFAULT 1,
          CHECK (mode IN ('sandbox_replay', 'live'))
        );
        INSERT INTO decisions_c2_migration SELECT * FROM decisions;
        DROP TABLE decisions;
        ALTER TABLE decisions_c2_migration RENAME TO decisions;
        CREATE INDEX IF NOT EXISTS idx_decisions_run
          ON decisions(run_id, cutoff_timestamp);
        CREATE INDEX IF NOT EXISTS idx_decisions_entity
          ON decisions(entity_id, emitted_at);
        COMMIT;
        """
    )


DECISION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS decisions (
  decision_id TEXT PRIMARY KEY,
  strategy_profile_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  asset_id TEXT,
  action_template TEXT NOT NULL,
  rule_text TEXT NOT NULL,
  trigger_observation_ids_json TEXT NOT NULL DEFAULT '[]',
  pit_state_json TEXT NOT NULL DEFAULT '{}',
  source_rights_state_json TEXT NOT NULL DEFAULT '{}',
  cutoff_timestamp TEXT NOT NULL,
  mode TEXT NOT NULL DEFAULT 'sandbox_replay',
  emitted_at TEXT NOT NULL,
  graph_hash TEXT NOT NULL,
  profile_version TEXT NOT NULL,
  run_id TEXT NOT NULL,
  evidence_checksum TEXT NOT NULL,
  not_investment_advice INTEGER NOT NULL DEFAULT 1,
  command_json TEXT,
  provenance_json TEXT,
  argumentation_status TEXT NOT NULL DEFAULT 'undecided',
  argumentation_reason TEXT,
  command_iri TEXT,
  CHECK (mode IN ('sandbox_replay', 'live'))
);
"""

# Indexes are created AFTER the Phase-27 column migration so that pre-Phase-27
# tables (which lack `command_iri`) do not trigger a "no such column" error
# from the index DDL before the migration has a chance to run.
DECISION_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_decisions_run
  ON decisions(run_id, cutoff_timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_entity
  ON decisions(entity_id, emitted_at);
CREATE INDEX IF NOT EXISTS idx_decisions_command_iri
  ON decisions(command_iri);
"""


_PHASE_27_NEW_COLUMNS = (
    ("command_json", "TEXT"),
    ("provenance_json", "TEXT"),
    ("argumentation_status", "TEXT NOT NULL DEFAULT 'undecided'"),
    ("argumentation_reason", "TEXT"),
    ("command_iri", "TEXT"),
)


def _migrate_phase_27_command_columns(connection: sqlite3.Connection) -> None:
    """Add Phase-27 command columns to a pre-Phase-27 decisions table.

    Idempotent. Re-running against an already-migrated table is a no-op
    because each ALTER TABLE is gated on a PRAGMA table_info() probe.
    """
    existing = {
        row[1]
        for row in connection.execute("PRAGMA table_info(decisions)").fetchall()
    }
    if not existing:
        # Table did not exist before CREATE TABLE IF NOT EXISTS ran above; in
        # that case the freshly-created table already has all columns and we
        # do not need to alter anything.
        return
    for column_name, column_definition in _PHASE_27_NEW_COLUMNS:
        if column_name in existing:
            continue
        connection.execute(
            f"ALTER TABLE decisions ADD COLUMN {column_name} {column_definition}"
        )
    indexes = {
        row[1]
        for row in connection.execute(
            "SELECT * FROM sqlite_master WHERE type='index' AND tbl_name='decisions'"
        ).fetchall()
    }
    if "idx_decisions_command_iri" not in indexes:
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_decisions_command_iri "
            "ON decisions(command_iri)"
        )


def get_decision_store(path: str | Path | None = None) -> DecisionStore:
    return DecisionStore(path)


# ---- Validation ledger integration (Phase B) ------------------------------


def validation_record_for_decisions(
    *,
    profile: VizaStrategyProfile,
    decisions: list[DecisionFrame],
    triggering_observations: list[VizaObservation],
    cutoff_timestamp: datetime,
    run_id: str,
    graph_hash: str,
    profile_version: str,
    methodology_id: str = "viza.output_radar.decisions",
    domain: str = "finance",
    module_id: str = "viza.finance.securities",
    generated_at: datetime | None = None,
) -> "VizaValidationRecord":
    """Build a VizaValidationRecord pinning a decision run to its inputs.

    The record's ``outputs`` carries one entry per decision; ``evidence_checksum``
    derives from the triggering observations; ``result_checksum`` derives from
    the canonical decision payload list.
    """
    from viza.validation_ledger import VizaValidationRecord  # local import: cycle break

    evidence_payload = {
        obs.observation_id: {
            "value": obs.value,
            "available_at": obs.available_at.isoformat(),
            "checksum": obs.checksum,
            "timestamp_available": obs.available_at.isoformat(),
        }
        for obs in triggering_observations
    }
    evidence_cs = compute_evidence_checksum(evidence_payload) if evidence_payload else stable_checksum({})

    result_payload = [decision.model_dump(mode="json") for decision in decisions]
    result_cs = stable_checksum(result_payload)

    pit_summary = {
        "status": "passed" if triggering_observations else "not_applicable",
        "checked_count": len(triggering_observations),
        "passed_count": len(triggering_observations),
        "violation_count": 0,
        "invalid_timestamp_count": 0,
        "not_applicable_count": 0,
        "cutoff_timestamp": cutoff_timestamp.isoformat(),
    }

    outputs = [
        {
            "decision_id": decision.decision_id,
            "rule_id": decision.rule_id,
            "entity_id": decision.entity_id,
            "asset_id": decision.asset_id,
            "cutoff_timestamp": decision.cutoff_timestamp.isoformat(),
            "mode": decision.mode,
            "evidence_checksum": decision.audit.evidence_checksum,
            "max_observation_available_at": decision.pit_state.get(
                "max_observation_available_at"
            ),
            "command_iri": (
                decision.command.command_iri if decision.command is not None else None
            ),
            "argumentation_status": decision.argumentation_status,
        }
        for decision in decisions
    ]

    generated = generated_at or _utc_now()
    record_payload: dict[str, Any] = {
        "strategy_or_methodology_id": methodology_id,
        "strategy_profile_id": profile.strategy_profile_id,
        "run_id": run_id,
        "graph_hash": graph_hash,
        "result_checksum": result_cs,
        "timestamp_cutoff": cutoff_timestamp.isoformat(),
        "generated_at": generated.isoformat(),
        "domain": domain,
        "module_id": module_id,
        "entity_universe": {
            "row_count": len(decisions),
            "entity_ids": sorted({decision.entity_id for decision in decisions}),
            "asset_ids": sorted(
                {decision.asset_id for decision in decisions if decision.asset_id}
            ),
            "tickers": [],
        },
        "outputs": outputs,
        "evidence_checksum": evidence_cs,
        "data_versions": [],
        "model_versions": [],
        "connector_states": [],
        "PIT_summary": pit_summary,
        "performance_observation": {
            "status": "pending",
            "evaluation_window": "sandbox_replay",
        },
        "in_sample_out_of_sample_label": "sandbox_replay",
        "warnings": [],
        "source_rights": [],
    }
    record_payload["validation_record_id"] = (
        "validation-" + stable_checksum(record_payload)[:24]
    )
    return VizaValidationRecord.model_validate(record_payload)


def emit_and_persist_decisions(
    *,
    profile: VizaStrategyProfile,
    observations: list[VizaObservation],
    cutoff_timestamp: datetime,
    run_id: str,
    graph_hash: str,
    profile_version: str,
    decision_store: DecisionStore | None = None,
    validation_store_path: str | Path | None = None,
    persist: bool = True,
    emitted_at: datetime | None = None,
    prior_emissions: list[PriorEmission] | None = None,
    mode: str = "sandbox_replay",
) -> tuple[list[DecisionFrame], "VizaValidationRecord"]:
    """Compile decisions, persist DecisionFrames and the validation record.

    The validation record is always built (even when no decisions fired) so
    that replay can prove the run was deterministic on its inputs. When
    ``persist=False``, returns the compiled artifacts without writing.

    ``prior_emissions`` is forwarded to ``compile_decisions`` so Phase C
    cooldown/dead-band enforcement applies through this entry point too.
    ``mode`` is forwarded so live mode (Phase C.2) runs through the same
    entry point as sandbox replay; live-mode preconditions raise from
    inside ``compile_decisions`` before any DecisionFrame is emitted, so
    no live failure produces a half-persisted state here.
    """
    from viza.validation_ledger import get_validation_ledger_store  # local import

    decisions = compile_decisions(
        profile=profile,
        observations=observations,
        cutoff_timestamp=cutoff_timestamp,
        run_id=run_id,
        graph_hash=graph_hash,
        profile_version=profile_version,
        emitted_at=emitted_at,
        prior_emissions=prior_emissions,
        mode=mode,
    )

    triggered_ids: set[str] = set()
    for decision in decisions:
        triggered_ids.update(decision.trigger_observation_ids)
    triggering_observations = [
        obs for obs in observations if obs.observation_id in triggered_ids
    ]

    validation_record = validation_record_for_decisions(
        profile=profile,
        decisions=decisions,
        triggering_observations=triggering_observations,
        cutoff_timestamp=cutoff_timestamp,
        run_id=run_id,
        graph_hash=graph_hash,
        profile_version=profile_version,
        generated_at=emitted_at,
    )

    if persist:
        store = decision_store or DecisionStore()
        for decision in decisions:
            store.upsert_decision(decision)
        get_validation_ledger_store(validation_store_path).save_record(validation_record)
        # Phase 33: write the typed PROV edges for this run alongside the
        # DecisionStore upserts so the lineage graph stays in lockstep with
        # the persisted decisions. Failures here are intentionally surfaced
        # — partial persistence (decisions saved, edges missing) would
        # silently break replay/audit and Phase 35 marketplace dispute
        # resolution.
        from viza.provenance import (  # local: avoid load-order cycle
            get_provenance_store,
            record_decision_provenance,
            record_run_bundle,
        )

        prov_store = get_provenance_store()
        record_decision_provenance(
            decisions=decisions,
            store=prov_store,
            generated_at=emitted_at,
        )
        decision_iris = [
            d.provenance.decision_entity_iri
            for d in decisions
            if d.provenance is not None
        ]
        if decision_iris:
            record_run_bundle(
                run_id=run_id,
                activity_iri=f"viza:activity/run/{run_id}",
                decision_iris=decision_iris,
                started_at_time=cutoff_timestamp,
                ended_at_time=emitted_at or _utc_now(),
                agent_iri=f"viza:agent/strategy_profile/{profile.strategy_profile_id}",
                store=prov_store,
            )

    return decisions, validation_record


def _cooldown_suppresses(
    *,
    rule: DecisionRule,
    entity_id: str,
    cutoff_timestamp: datetime,
    prior_emissions: list[PriorEmission],
    latest_by_key: dict[tuple[str, str], VizaObservation],
) -> bool:
    policy: CooldownPolicy = rule.cooldown_policy
    if (
        policy.max_fires_per_entity_per_window is None
        and policy.dead_band_threshold is None
    ):
        return False

    matching = [
        emission
        for emission in prior_emissions
        if emission.rule_id == rule.rule_id and emission.entity_id == entity_id
    ]
    if not matching:
        return False

    # Window-scoped candidates are used by the cap; dead-band uses all prior
    # emissions at-or-before this cutoff because it tracks "did the trigger
    # value move enough since the last fire," which is window-independent.
    candidates_at_or_before_cutoff = [
        emission for emission in matching if emission.cutoff_timestamp <= cutoff_timestamp
    ]
    if policy.window_seconds is not None:
        window_start = cutoff_timestamp - timedelta(seconds=policy.window_seconds)
        in_window = [
            emission
            for emission in candidates_at_or_before_cutoff
            if emission.cutoff_timestamp > window_start
        ]
    else:
        in_window = candidates_at_or_before_cutoff

    if policy.max_fires_per_entity_per_window is not None and len(in_window) >= policy.max_fires_per_entity_per_window:
        return True

    if policy.dead_band_threshold is not None and candidates_at_or_before_cutoff:
        most_recent = max(
            candidates_at_or_before_cutoff,
            key=lambda emission: emission.cutoff_timestamp,
        )
        for predicate in rule.trigger.observation_predicates:
            observation = latest_by_key.get((entity_id, predicate.attribute_key))
            if observation is None:
                continue
            prior_value = most_recent.trigger_values.get(predicate.attribute_key)
            if prior_value is None:
                continue
            try:
                current_value = float(observation.value)
            except (TypeError, ValueError):
                continue
            if abs(current_value - float(prior_value)) < policy.dead_band_threshold:
                return True

    return False


def _evaluate_rule_for_entity(
    *,
    rule: DecisionRule,
    entity_id: str,
    latest_by_key: dict[tuple[str, str], VizaObservation],
    events: list[Any] | None = None,
    cutoff_timestamp: datetime | None = None,
) -> list[str] | None:
    """Evaluate the rule's trigger against the entity's latest observations.

    Phase 29: when the rule's trigger carries a `feel_expression`, it is
    evaluated against the entity's full observation context and overrides
    `observation_predicates`. The structured predicates still run as a
    parallel keys-required check so cooldown / dead-band bookkeeping retains
    its attribute_key handle and so a FEEL trigger that omits required
    evidence keys does not falsely fire.

    Phase 32: when the trigger carries an `event_pattern`, the pattern is
    evaluated against the entity's events (filtered by the cutoff). The
    pattern can stand alone OR combine with observation predicates / FEEL
    expressions — when more than one trigger form is present, ALL must
    succeed.

    Returns the list of triggering observation IDs, or `None` if the rule
    does not fire for this entity.
    """
    # Event-pattern leg (Phase 32). Runs first; if absent, the leg passes.
    if rule.trigger.has_event_pattern():
        if not events:
            return None
        from viza.event_patterns import evaluate_pattern  # local: cycle-safe

        entity_events = [
            event
            for event in events
            if entity_id in getattr(event, "affected_entity_ids", [])
        ]
        if not entity_events:
            return None
        pattern_match = evaluate_pattern(
            rule.trigger.event_pattern,
            entity_events,
            cutoff_timestamp=cutoff_timestamp,
        )
        if pattern_match is None:
            return None

    # FEEL-expression leg (Phase 29).
    if rule.trigger.has_feel_expression():
        return _evaluate_feel_trigger(
            rule=rule, entity_id=entity_id, latest_by_key=latest_by_key
        )

    triggered: list[str] = []
    for predicate in rule.trigger.observation_predicates:
        obs = latest_by_key.get((entity_id, predicate.attribute_key))
        if obs is None:
            return None
        if not _predicate_satisfied(predicate, obs.value):
            return None
        triggered.append(obs.observation_id)
    if not triggered and not rule.trigger.has_event_pattern():
        return None
    if not triggered and rule.trigger.has_event_pattern():
        # An event-pattern-only rule still needs some triggering observation
        # to satisfy the existing evidence-checksum / cooldown machinery;
        # bind a synthetic placeholder by reusing any observation for the
        # entity. This keeps Phase-32 event-only rules deterministic even
        # when no structured predicates are declared.
        any_observation = next(
            (
                obs
                for (obs_entity, _attribute), obs in latest_by_key.items()
                if obs_entity == entity_id
            ),
            None,
        )
        if any_observation is None:
            return None
        triggered.append(any_observation.observation_id)
    return triggered


def _evaluate_feel_trigger(
    *,
    rule: DecisionRule,
    entity_id: str,
    latest_by_key: dict[tuple[str, str], VizaObservation],
) -> list[str] | None:
    """Evaluate a FEEL-Lite boolean expression against the entity's context.

    The context bound for evaluation is the same shape `_sizing_context`
    builds for command sizing: each attribute is bound by its bare key
    (`rsi_14d`) plus a dotted `technical.<key>` / `portfolio.<key>` alias
    where the key shape implies a domain. The expression must evaluate to a
    boolean; numeric or other types raise.
    """
    context = _sizing_context(entity_id=entity_id, latest_by_key=latest_by_key)
    expression = rule.trigger.feel_expression or ""
    try:
        result = feel_evaluate(expression, context)
    except FeelLiteError:
        # An unbound identifier or syntax error is treated as the trigger
        # not firing — the engine should not crash a whole run because one
        # rule references an attribute that hasn't been ingested yet.
        return None
    if not isinstance(result, bool):
        raise ValueError(
            f"rule {rule.rule_id!r} FEEL trigger returned non-boolean: {result!r}"
        )
    if not result:
        return None
    # Triggering observation set: every attribute key the rule references AND
    # that is bound for this entity. Structured predicates (if any) take
    # priority because they already declare their required keys.
    triggered_ids: list[str] = []
    seen: set[str] = set()
    for predicate in rule.trigger.observation_predicates:
        obs = latest_by_key.get((entity_id, predicate.attribute_key))
        if obs is not None and obs.observation_id not in seen:
            triggered_ids.append(obs.observation_id)
            seen.add(obs.observation_id)
    for attribute_key in rule.trigger.referenced_attribute_keys():
        obs = latest_by_key.get((entity_id, attribute_key))
        if obs is not None and obs.observation_id not in seen:
            triggered_ids.append(obs.observation_id)
            seen.add(obs.observation_id)
    if not triggered_ids:
        # A trigger that evaluated true but bound no observations is
        # suspicious — treat as not-fired so downstream provenance has a
        # non-empty evidence set to point at.
        return None
    return triggered_ids


def _predicate_satisfied(predicate: ObservationPredicate, value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    if predicate.operator == "lte":
        return numeric <= float(predicate.threshold)  # type: ignore[arg-type]
    if predicate.operator == "gte":
        return numeric >= float(predicate.threshold)  # type: ignore[arg-type]
    if predicate.operator == "lt":
        return numeric < float(predicate.threshold)  # type: ignore[arg-type]
    if predicate.operator == "gt":
        return numeric > float(predicate.threshold)  # type: ignore[arg-type]
    if predicate.operator == "eq":
        return numeric == float(predicate.threshold)  # type: ignore[arg-type]
    if predicate.operator == "between":
        return (
            float(predicate.range_min) <= numeric <= float(predicate.range_max)  # type: ignore[arg-type]
        )
    raise ValueError(f"unknown predicate operator: {predicate.operator}")


def _decision_id(
    *,
    rule_id: str,
    entity_id: str,
    cutoff_timestamp: datetime,
    run_id: str,
) -> str:
    payload = {
        "rule_id": rule_id,
        "entity_id": entity_id,
        "cutoff": cutoff_timestamp.isoformat(),
        "run_id": run_id,
    }
    return f"decision-{_hash_payload(payload)[:24]}"


def _evidence_checksum(
    triggered_ids: list[str],
    obs_by_id: dict[str, VizaObservation],
) -> str:
    payload = sorted(
        (obs_id, obs_by_id[obs_id].checksum) for obs_id in triggered_ids
    )
    return stable_checksum(payload)


def _pit_state(
    triggered_ids: list[str],
    obs_by_id: dict[str, VizaObservation],
    cutoff_timestamp: datetime,
) -> dict[str, Any]:
    available_ats = [obs_by_id[oid].available_at for oid in triggered_ids]
    return {
        "cutoff_timestamp": cutoff_timestamp.isoformat(),
        "max_observation_available_at": (
            max(available_ats).isoformat() if available_ats else None
        ),
        "observation_count": len(triggered_ids),
        "lookahead_risk": "low",
    }


def _source_rights_state(
    triggered_ids: list[str],
    obs_by_id: dict[str, VizaObservation],
) -> dict[str, Any]:
    rights_policies = [obs_by_id[oid].rights_policy for oid in triggered_ids]
    export_allowed = all(
        policy.get("export_allowed") is not False for policy in rights_policies
    )
    raw_snapshot_allowed = all(
        policy.get("raw_snapshot_allowed") is not False for policy in rights_policies
    )
    return {
        "export_allowed": export_allowed,
        "raw_snapshot_allowed": raw_snapshot_allowed,
        "policies": rights_policies,
    }


def _asset_id_for_entity(
    latest_by_key: dict[tuple[str, str], VizaObservation],
    entity_id: str,
) -> str | None:
    for (obs_entity, _attribute), obs in latest_by_key.items():
        if obs_entity == entity_id and obs.asset_id:
            return obs.asset_id
    return None


def _filter_by_transaction_time(
    observations: list[VizaObservation],
    transaction_time_cutoff: datetime | None,
) -> list[VizaObservation]:
    """Apply the Phase-28 transaction-time AS-OF predicate.

    Two modes:

    * ``transaction_time_cutoff is None`` (default): keep only rows whose
      ``transaction_time_end`` is ``None`` (current belief). Rows on
      Phase-28-migrated tables that have never been corrected satisfy this
      trivially, so existing tests stay green.
    * ``transaction_time_cutoff`` set: keep rows whose
      ``transaction_time_start <= ttx`` AND
      ``(transaction_time_end IS NULL OR transaction_time_end > ttx)``.

    Rows that lack a ``transaction_time_start`` (synthetic fixtures created
    outside the ingest pipeline) are kept as-is so unit tests that build
    `VizaObservation` directly without bitemporal stamps still fire rules.
    """
    if transaction_time_cutoff is None:
        return [
            obs for obs in observations if obs.transaction_time_end is None
        ]
    kept: list[VizaObservation] = []
    for obs in observations:
        if obs.transaction_time_start is None:
            kept.append(obs)
            continue
        if obs.transaction_time_start > transaction_time_cutoff:
            continue
        if (
            obs.transaction_time_end is not None
            and obs.transaction_time_end <= transaction_time_cutoff
        ):
            continue
        kept.append(obs)
    return kept


def _build_command_for_rule(
    *,
    rule: DecisionRule,
    entity_id: str,
    asset_id: str | None,
    latest_by_key: dict[tuple[str, str], VizaObservation],
    triggered_ids: list[str],
    obs_by_id: dict[str, VizaObservation],
    source_rights_state: dict[str, Any],
    pit_state: dict[str, Any],
    fibo_identity_resolver: Callable[[str], "FiboIdentity | None"] | None = None,
) -> InvestmentCommandPayload | None:
    """Build the structured command payload for a firing rule, when the rule
    declares a `command_mapping`. Phase 27.

    Pre-emission gates:
    * If `source_rights_state.export_allowed` is False, the command is
      replaced by a `BLOCK_EXPORT` system veto with the original target
      preserved for audit.
    * Sizing expressions are evaluated via FEEL-Lite against the
      observation-context built from `latest_by_key`. A FEEL-Lite failure
      causes the command to be replaced by `BLOCK_ACTION` with a defeater
      record explaining the failure.

    A rule without `command_mapping` returns `None`, preserving the
    pre-Phase-27 DecisionFrame shape exactly.
    """
    mapping = rule.command_mapping
    if mapping is None:
        return None

    taxonomy = get_command_taxonomy()
    target_concept = taxonomy.get(mapping.command_iri)
    if target_concept is None:
        return _block_action_command(
            entity_id=entity_id,
            asset_id=asset_id,
            rationale=f"unknown command_iri={mapping.command_iri!r}",
            defeater_kind="evidence_absent",
        )

    target = CommandTarget(
        entity_id=entity_id,
        instrument_id=asset_id,
        ticker_alias=_ticker_alias_for_entity(latest_by_key, entity_id),
    )
    if fibo_identity_resolver is not None and asset_id:
        identity = fibo_identity_resolver(asset_id)
        if identity is not None:
            target = target.model_copy(
                update={
                    "fibo_legal_entity_iri": identity.legal_entity_iri,
                    "fibo_instrument_iri": identity.instrument_iri,
                    "identifier_set": list(identity.identifier_set),
                }
            )

    if source_rights_state.get("export_allowed") is False:
        block_export = taxonomy.get("viza:cmd/block_export")
        if block_export is None:  # registry mis-seeded
            return _block_action_command(
                entity_id=entity_id,
                asset_id=asset_id,
                rationale="BLOCK_EXPORT concept missing from registry",
                defeater_kind="rights_blocked",
            )
        return build_command_from_concept(
            concept=block_export,
            target=target,
            sizing=None,
            resolved_sizing_value=None,
            command_confidence=1.0,
            defeaters=[],
        )

    sizing = mapping.sizing
    resolved_value: float | None = None
    if sizing is not None:
        context = _sizing_context(entity_id=entity_id, latest_by_key=latest_by_key)
        try:
            evaluated = feel_evaluate(sizing.expression, context)
        except FeelLiteError as exc:
            return _block_action_command(
                entity_id=entity_id,
                asset_id=asset_id,
                rationale=f"sizing evaluation failed: {exc}",
                defeater_kind="evidence_absent",
            )
        if isinstance(evaluated, bool) or not isinstance(evaluated, (int, float)):
            return _block_action_command(
                entity_id=entity_id,
                asset_id=asset_id,
                rationale=(
                    f"sizing expression returned non-numeric value: {evaluated!r}"
                ),
                defeater_kind="evidence_absent",
            )
        resolved_value = float(evaluated)

    return build_command_from_concept(
        concept=target_concept,
        target=target,
        sizing=sizing,
        resolved_sizing_value=resolved_value,
        command_confidence=_command_confidence_from_pit(pit_state, source_rights_state),
        defeaters=[],
    )


def _block_action_command(
    *,
    entity_id: str,
    asset_id: str | None,
    rationale: str,
    defeater_kind: str,
) -> InvestmentCommandPayload:
    from viza.commands import Defeater  # local import: avoid top-level cycle warmth

    taxonomy = get_command_taxonomy()
    concept = taxonomy.require("viza:cmd/block_action")
    target = CommandTarget(entity_id=entity_id, instrument_id=asset_id)
    return build_command_from_concept(
        concept=concept,
        target=target,
        sizing=None,
        resolved_sizing_value=None,
        command_confidence=1.0,
        defeaters=[
            Defeater(defeater_kind=defeater_kind, rationale=rationale)  # type: ignore[arg-type]
        ],
    )


def _sizing_context(
    *,
    entity_id: str,
    latest_by_key: dict[tuple[str, str], VizaObservation],
) -> dict[str, Any]:
    """Build the FEEL-Lite context for sizing evaluation.

    Attributes are bound by their bare key (e.g. `rsi_14d`) and by a dotted
    `technical.rsi_14d` alias when the key shape is recognized as technical.
    Portfolio-state observations bind under `portfolio.<key>` when the
    attribute key matches the pattern `portfolio.position.weight.<security>`
    (Phase 27 supports this minimally; richer portfolio models follow in
    Phase 28).
    """
    context: dict[str, Any] = {}
    technical: dict[str, Any] = {}
    portfolio: dict[str, Any] = {}
    for (obs_entity, attribute_key), obs in latest_by_key.items():
        if obs_entity != entity_id:
            continue
        value: Any
        try:
            value = float(obs.value) if isinstance(obs.value, (int, float)) else obs.value
        except (TypeError, ValueError):
            value = obs.value
        context[attribute_key] = value
        if attribute_key.startswith("portfolio."):
            _nested_set(portfolio, attribute_key[len("portfolio.") :], value)
        else:
            technical[attribute_key] = value
    if technical:
        context.setdefault("technical", technical)
    if portfolio:
        context.setdefault("portfolio", portfolio)
    return context


def _nested_set(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cursor = target
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})  # type: ignore[assignment]
    cursor[parts[-1]] = value


def _ticker_alias_for_entity(
    latest_by_key: dict[tuple[str, str], VizaObservation],
    entity_id: str,
) -> str | None:
    """Best-effort: use the asset_id as ticker alias when present."""
    for (obs_entity, _attribute), obs in latest_by_key.items():
        if obs_entity == entity_id and obs.asset_id:
            return obs.asset_id
    return None


def _command_confidence_from_pit(
    pit_state: dict[str, Any], source_rights_state: dict[str, Any]
) -> float:
    """Heuristic command confidence: 1.0 when PIT-safe and export-allowed,
    discounted otherwise. Phase 31's ASPIC+ resolver will refine this with
    source_credibility once observations carry it uniformly."""
    confidence = 1.0
    if pit_state.get("lookahead_risk") not in (None, "low"):
        confidence -= 0.3
    if source_rights_state.get("export_allowed") is False:
        confidence -= 0.2
    if source_rights_state.get("raw_snapshot_allowed") is False:
        confidence -= 0.1
    return max(0.0, min(1.0, confidence))


def _build_provenance(
    *,
    decision_id: str,
    run_id: str,
    profile: VizaStrategyProfile,
    triggered_ids: list[str],
    graph_hash: str,
    profile_version: str,
    evidence_checksum: str,
) -> DecisionProvenance:
    return DecisionProvenance(
        decision_entity_iri=f"viza:entity/decision/{decision_id}",
        was_generated_by_run_iri=f"viza:activity/run/{run_id}",
        was_attributed_to_agent_iri=(
            f"viza:agent/strategy_profile/{profile.strategy_profile_id}"
        ),
        used_observation_iris=[
            f"viza:entity/observation/{obs_id}" for obs_id in sorted(triggered_ids)
        ],
        graph_hash=graph_hash,
        profile_version=profile_version,
        evidence_checksum=evidence_checksum,
    )


def _decision_row_values(decision: DecisionFrame) -> tuple[Any, ...]:
    return (
        decision.decision_id,
        decision.strategy_profile_id,
        decision.rule_id,
        decision.entity_id,
        decision.asset_id,
        decision.action_template,
        decision.rule_text,
        json.dumps(decision.trigger_observation_ids, sort_keys=True),
        json.dumps(decision.pit_state, sort_keys=True, default=str),
        json.dumps(decision.source_rights_state, sort_keys=True, default=str),
        decision.cutoff_timestamp.isoformat(),
        decision.mode,
        decision.emitted_at.isoformat(),
        decision.audit.graph_hash,
        decision.audit.profile_version,
        decision.audit.run_id,
        decision.audit.evidence_checksum,
        1 if decision.not_investment_advice else 0,
        (
            json.dumps(decision.command.model_dump(mode="json"), sort_keys=True)
            if decision.command is not None
            else None
        ),
        (
            json.dumps(decision.provenance.model_dump(mode="json"), sort_keys=True)
            if decision.provenance is not None
            else None
        ),
        decision.argumentation_status,
        decision.argumentation_reason,
        decision.command.command_iri if decision.command is not None else None,
    )


def _decision_from_row(row: sqlite3.Row) -> DecisionFrame:
    command_payload = row["command_json"] if "command_json" in row.keys() else None
    provenance_payload = (
        row["provenance_json"] if "provenance_json" in row.keys() else None
    )
    argumentation_status = (
        row["argumentation_status"]
        if "argumentation_status" in row.keys() and row["argumentation_status"]
        else "undecided"
    )
    argumentation_reason = (
        row["argumentation_reason"]
        if "argumentation_reason" in row.keys()
        else None
    )

    command = (
        InvestmentCommandPayload.model_validate(json.loads(command_payload))
        if command_payload
        else None
    )
    provenance = (
        DecisionProvenance.model_validate(json.loads(provenance_payload))
        if provenance_payload
        else None
    )

    return DecisionFrame(
        decision_id=row["decision_id"],
        strategy_profile_id=row["strategy_profile_id"],
        rule_id=row["rule_id"],
        entity_id=row["entity_id"],
        asset_id=row["asset_id"],
        action_template=row["action_template"],
        rule_text=row["rule_text"],
        trigger_observation_ids=json.loads(row["trigger_observation_ids_json"]),
        pit_state=json.loads(row["pit_state_json"]),
        source_rights_state=json.loads(row["source_rights_state_json"]),
        cutoff_timestamp=datetime.fromisoformat(row["cutoff_timestamp"]),
        mode=row["mode"],
        emitted_at=datetime.fromisoformat(row["emitted_at"]),
        audit=DecisionAudit(
            graph_hash=row["graph_hash"],
            profile_version=row["profile_version"],
            run_id=row["run_id"],
            evidence_checksum=row["evidence_checksum"],
        ),
        not_investment_advice=bool(row["not_investment_advice"]),
        command=command,
        provenance=provenance,
        argumentation_status=argumentation_status,
        argumentation_reason=argumentation_reason,
    )


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

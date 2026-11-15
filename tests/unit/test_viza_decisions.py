"""Unit tests for the VIZA decision executor and store.

See docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md for scope. Covers Phases A
through C.2:

- DecisionRule / ObservationPredicate / CooldownPolicy schema validation
- compile_decisions firing semantics (predicate satisfied / not satisfied)
- PIT enforcement (observations past cutoff are dropped)
- Determinism (identical inputs ⇒ identical output)
- Cooldown / dead-band suppression (Phase C.1)
- Package-redaction modes (Phase C.1)
- Live-mode enforcement: env flag, opt-in presence, opt-in disclosure
  version match, per-rule effective_from gate (Phase C.2)
- DecisionStore roundtrip + CHECK constraint rejects modes outside the
  ``(sandbox_replay, live)`` set
- Template pilot rules (equity + real-estate) load and fire deterministically
- output_radar_mode helper behavior (default, unknown, sandbox_replay, live)
- LIVE_MODE_DISCLOSURE_TEXT non-advice language sweep
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from viza.decisions import (
    DecisionFrame,
    DecisionStore,
    PriorEmission,
    compile_decisions,
    emit_and_persist_decisions,
    replay_decisions_from_store,
    validation_record_for_decisions,
)
from viza.decisions_redaction import (
    PackageRedactionBlocked,
    redact_decisions_for_package,
)
from viza.observations import ObservationQueryRequest, get_observation_store
from viza.strategy_profiles import (
    StrategyProfileCreateRequest,
    get_strategy_profile_store,
    strategy_profile_hash,
)
from viza.validation_ledger import get_validation_ledger_store
from viza.graph_schema import (
    GraphPosition,
    MethodologyNode,
    VizaNodeType,
    output_radar_mode,
)
from viza.observations import ObservationInput, VizaObservation, observation_from_input
from viza.strategy_profiles import (
    CooldownPolicy,
    DecisionRule,
    DecisionTrigger,
    ObservationPredicate,
    VizaStrategyProfile,
    load_strategy_profile_templates,
)  # noqa: E402 (kept above; second import block continues below)


def _make_observation(
    *,
    entity_id: str,
    attribute_key: str,
    value: float,
    available_at: datetime,
    asset_id: str | None = None,
    rights_policy: dict | None = None,
) -> VizaObservation:
    item = ObservationInput(
        entity_id=entity_id,
        asset_id=asset_id,
        attribute_key=attribute_key,
        value=value,
        observed_at=available_at,
        available_at=available_at,
        retrieved_at=available_at + timedelta(hours=1),
        source_id="test_source",
        connector_id="test_connector",
        rights_policy=rights_policy
        or {"export_allowed": True, "raw_snapshot_allowed": True},
    )
    return observation_from_input(item)


def _rsi_rule(enabled: bool = True) -> DecisionRule:
    return DecisionRule(
        rule_id="rsi-deep-oversold-v1",
        label="Deep oversold (RSI 14d ≤ 30)",
        enabled=enabled,
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(
                    attribute_key="rsi_14d",
                    operator="lte",
                    threshold=30.0,
                )
            ]
        ),
        action_template="Flag for analyst review: RSI deep-oversold reading.",
    )


def _make_profile(rules: list[DecisionRule]) -> VizaStrategyProfile:
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    return VizaStrategyProfile(
        strategy_profile_id="test-profile",
        display_name="Test Profile",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=rules,
        created_at=now,
        updated_at=now,
    )


# ---- Schema validation ------------------------------------------------------


def test_predicate_requires_threshold_for_lte() -> None:
    with pytest.raises(ValidationError):
        ObservationPredicate(attribute_key="rsi_14d", operator="lte")


def test_predicate_between_requires_range() -> None:
    with pytest.raises(ValidationError):
        ObservationPredicate(attribute_key="rsi_14d", operator="between")


def test_predicate_between_rejects_inverted_range() -> None:
    with pytest.raises(ValidationError):
        ObservationPredicate(
            attribute_key="rsi_14d",
            operator="between",
            range_min=50.0,
            range_max=30.0,
        )


# ---- Executor firing semantics ---------------------------------------------


def test_compile_decisions_fires_below_threshold() -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-1",
        graph_hash="hash-1",
        profile_version="ver-1",
    )
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.rule_id == "rsi-deep-oversold-v1"
    assert decision.entity_id == "AAPL"
    assert decision.action_template == "Flag for analyst review: RSI deep-oversold reading."
    assert decision.mode == "sandbox_replay"
    assert decision.not_investment_advice is True
    assert decision.pit_state["lookahead_risk"] == "low"
    assert decision.audit.graph_hash == "hash-1"
    assert decision.trigger_observation_ids == [obs.observation_id]


def test_compile_decisions_does_not_fire_above_threshold() -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=45.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-1",
        graph_hash="hash-1",
        profile_version="ver-1",
    )
    assert decisions == []


def test_compile_decisions_disabled_rule_does_not_fire() -> None:
    profile = _make_profile([_rsi_rule(enabled=False)])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-1",
        graph_hash="hash-1",
        profile_version="ver-1",
    )
    assert decisions == []


def test_compile_decisions_missing_required_observation_does_not_fire() -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="momentum",
        value=-0.05,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-1",
        graph_hash="hash-1",
        profile_version="ver-1",
    )
    assert decisions == []


# ---- PIT enforcement (rehearsal of the lookahead audit gate) ---------------


def test_compile_decisions_drops_post_cutoff_observations() -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=20.0,
        available_at=cutoff + timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-1",
        graph_hash="hash-1",
        profile_version="ver-1",
    )
    assert decisions == []


# ---- Determinism -----------------------------------------------------------


def test_compile_decisions_is_deterministic() -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    fixed_emit = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    first = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-1",
        graph_hash="hash-1",
        profile_version="ver-1",
        emitted_at=fixed_emit,
    )
    second = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-1",
        graph_hash="hash-1",
        profile_version="ver-1",
        emitted_at=fixed_emit,
    )
    assert [d.model_dump(mode="json") for d in first] == [
        d.model_dump(mode="json") for d in second
    ]


# ---- Phase C.2 boundary: live mode requires env flag + opt-in --------------


def test_compile_decisions_blocks_live_mode_without_env_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default-off live mode: without VIZA_LIVE_MODE_ENABLED=true the executor
    refuses to run even when the profile carries an opt-in."""
    from viza.decisions import LIVE_MODE_ENV_VAR, LiveModeDisabledError

    monkeypatch.delenv(LIVE_MODE_ENV_VAR, raising=False)
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    with pytest.raises(LiveModeDisabledError):
        compile_decisions(
            profile=profile,
            observations=[],
            cutoff_timestamp=cutoff,
            run_id="run-1",
            graph_hash="hash-1",
            profile_version="ver-1",
            mode="live",
        )


def test_compile_decisions_raises_value_error_on_unknown_mode() -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="unknown output_radar mode"):
        compile_decisions(
            profile=profile,
            observations=[],
            cutoff_timestamp=cutoff,
            run_id="run-1",
            graph_hash="hash-1",
            profile_version="ver-1",
            mode="paper_trade",
        )


# ---- Persistence -----------------------------------------------------------


def test_decision_store_roundtrip(tmp_path: Path) -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-store-1",
        graph_hash="hash-1",
        profile_version="ver-1",
    )
    store = DecisionStore(tmp_path / "viza_decisions.sqlite3")
    for decision in decisions:
        store.upsert_decision(decision)
    fetched = store.list_decisions_by_run("run-store-1")
    assert len(fetched) == 1
    assert fetched[0].decision_id == decisions[0].decision_id
    assert fetched[0].action_template == decisions[0].action_template
    assert fetched[0].audit.graph_hash == "hash-1"
    assert fetched[0].audit.evidence_checksum == decisions[0].audit.evidence_checksum


def test_decision_store_check_blocks_unknown_mode(tmp_path: Path) -> None:
    """SQLite CHECK constraint rejects any mode outside the supported set
    (``sandbox_replay`` and ``live`` as of Phase C.2). A typo or future
    code path that produced an unknown mode is rejected at the DB layer."""
    store = DecisionStore(tmp_path / "viza_decisions.sqlite3")
    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO decisions(
                    decision_id, strategy_profile_id, rule_id, entity_id, asset_id,
                    action_template, rule_text, trigger_observation_ids_json,
                    pit_state_json, source_rights_state_json,
                    cutoff_timestamp, mode, emitted_at,
                    graph_hash, profile_version, run_id, evidence_checksum,
                    not_investment_advice
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', '{}', '{}', ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    "decision-test",
                    "profile-1",
                    "rule-1",
                    "AAPL",
                    None,
                    "test action",
                    "rule-1: test",
                    "2026-05-20T00:00:00+00:00",
                    "paper_trade",  # ← unsupported mode rejected by CHECK
                    "2026-05-20T00:00:00+00:00",
                    "h",
                    "v",
                    "r",
                    "c",
                ),
            )


def test_replay_decisions_filters_past_cutoff(tmp_path: Path) -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-replay-1",
        graph_hash="hash-1",
        profile_version="ver-1",
    )
    store = DecisionStore(tmp_path / "viza_decisions.sqlite3")
    for decision in decisions:
        store.upsert_decision(decision)

    pre_cutoff = obs.available_at - timedelta(seconds=1)
    pre_replay = replay_decisions_from_store(
        store=store,
        run_id="run-replay-1",
        cutoff_timestamp=pre_cutoff,
    )
    assert pre_replay == []

    full_replay = replay_decisions_from_store(
        store=store,
        run_id="run-replay-1",
        cutoff_timestamp=cutoff,
    )
    assert len(full_replay) == 1
    assert full_replay[0].decision_id == decisions[0].decision_id


# ---- Template integration --------------------------------------------------


def test_template_pilot_rule_loads_through_catalog() -> None:
    catalog = load_strategy_profile_templates()
    template = catalog.templates[0]
    assert len(template.decision_rules) == 1
    rule = template.decision_rules[0]
    assert rule.rule_id == "rsi-deep-oversold-v1"
    predicate = rule.trigger.observation_predicates[0]
    assert predicate.attribute_key == "rsi_14d"
    assert predicate.operator == "lte"
    assert predicate.threshold == 30.0
    assert "Flag for analyst review" in rule.action_template


# ---- output_radar_mode helper ----------------------------------------------


def _radar_node(config: dict | None = None) -> MethodologyNode:
    return MethodologyNode(
        id="radar-1",
        type=VizaNodeType.OUTPUT_RADAR,
        position=GraphPosition(x=0.0, y=0.0),
        config=config or {},
    )


def test_output_radar_mode_defaults_to_sandbox_replay() -> None:
    assert output_radar_mode(_radar_node()) == "sandbox_replay"


def test_output_radar_mode_accepts_explicit_sandbox_replay() -> None:
    assert output_radar_mode(_radar_node({"mode": "sandbox_replay"})) == "sandbox_replay"


def test_output_radar_mode_raises_on_unknown_mode() -> None:
    with pytest.raises(ValueError):
        output_radar_mode(_radar_node({"mode": "paper_trade"}))


def test_output_radar_mode_accepts_live() -> None:
    """Phase C.2: ``live`` is a supported mode at the graph-schema layer.
    Runtime activation is still gated by ``VIZA_LIVE_MODE_ENABLED`` plus a
    per-profile opt-in enforced by ``compile_decisions``."""
    assert output_radar_mode(_radar_node({"mode": "live"})) == "live"


def test_pre_c2_decisions_table_migrates_on_store_init(tmp_path: Path) -> None:
    """A SQLite DB created under the Phase C.1 schema (narrow CHECK
    rejecting 'live') is automatically migrated when a Phase C.2 DecisionStore
    opens it. Existing rows are preserved; the new CHECK accepts 'live'."""
    db_path = tmp_path / "pre_c2_decisions.sqlite3"
    # Hand-roll the pre-C.2 schema so we can verify the migration path.
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE decisions (
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
              CHECK (mode = 'sandbox_replay')
            );
            INSERT INTO decisions(
              decision_id, strategy_profile_id, rule_id, entity_id, asset_id,
              action_template, rule_text, trigger_observation_ids_json,
              pit_state_json, source_rights_state_json,
              cutoff_timestamp, mode, emitted_at,
              graph_hash, profile_version, run_id, evidence_checksum,
              not_investment_advice
            ) VALUES (
              'pre-c2-decision', 'profile-pre', 'rule-pre', 'AAPL', NULL,
              'pre-migration action', 'rule-pre: pre',
              '["obs-1"]', '{}', '{}',
              '2026-05-20T00:00:00+00:00', 'sandbox_replay',
              '2026-05-20T00:00:00+00:00',
              'h-pre', 'v-pre', 'run-pre', 'cs-pre', 1
            );
            """
        )

    # Opening a C.2 DecisionStore must migrate the schema.
    store = DecisionStore(db_path)

    # Pre-existing row preserved.
    surviving = store.list_decisions_by_run("run-pre")
    assert len(surviving) == 1
    assert surviving[0].decision_id == "pre-c2-decision"
    assert surviving[0].mode == "sandbox_replay"

    # New CHECK accepts mode='live'.
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            """
            INSERT INTO decisions(
              decision_id, strategy_profile_id, rule_id, entity_id, asset_id,
              action_template, rule_text, trigger_observation_ids_json,
              pit_state_json, source_rights_state_json,
              cutoff_timestamp, mode, emitted_at,
              graph_hash, profile_version, run_id, evidence_checksum,
              not_investment_advice
            ) VALUES (
              'post-c2-decision', 'profile-post', 'rule-post', 'AAPL', NULL,
              'post-migration action', 'rule-post: post',
              '["obs-2"]', '{}', '{}',
              '2026-05-20T00:00:00+00:00', 'live',
              '2026-05-20T00:00:00+00:00',
              'h-post', 'v-post', 'run-post', 'cs-post', 1
            )
            """
        )

    # And the post-migration table still rejects unsupported modes.
    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO decisions(
                  decision_id, strategy_profile_id, rule_id, entity_id, asset_id,
                  action_template, rule_text, trigger_observation_ids_json,
                  pit_state_json, source_rights_state_json,
                  cutoff_timestamp, mode, emitted_at,
                  graph_hash, profile_version, run_id, evidence_checksum,
                  not_investment_advice
                ) VALUES (
                  'rejected', 'profile-x', 'rule-x', 'AAPL', NULL,
                  'x', 'x', '[]', '{}', '{}',
                  '2026-05-20T00:00:00+00:00', 'paper_trade',
                  '2026-05-20T00:00:00+00:00',
                  'h', 'v', 'r', 'c', 1
                )
                """
            )


def test_post_c2_store_init_is_idempotent_on_already_migrated_db(
    tmp_path: Path,
) -> None:
    """Re-initialising a DecisionStore against an already-C.2 DB is a no-op:
    no migration runs, no rows are touched."""
    db_path = tmp_path / "already_c2_decisions.sqlite3"
    DecisionStore(db_path)  # first init creates fresh C.2 schema
    # Re-open: must not error, must not drop rows.
    second = DecisionStore(db_path)
    assert second.list_decisions_by_run("nonexistent") == []


def test_live_mode_disclosure_text_uses_no_directive_language() -> None:
    """The user-facing disclosure paragraph is the load-bearing non-advice
    surface in live mode. Sweep it for the same forbidden patterns the
    desktop test enforces, plus broader conjugations of recommend/trade."""
    import re

    from viza.decisions import LIVE_MODE_DISCLOSURE_TEXT

    forbidden_patterns = [
        re.compile(r"\bBuy\b"),
        re.compile(r"\bSell\b"),
        re.compile(r"\bAct\s+now\b", re.IGNORECASE),
        re.compile(r"\bTrade\w*\b"),
        re.compile(r"\bRecommend\w*\b", re.IGNORECASE),
        re.compile(r"\btoday\b", re.IGNORECASE),
        re.compile(r"\bcurrent\s+(price|reading|market)", re.IGNORECASE),
    ]
    for pattern in forbidden_patterns:
        match = pattern.search(LIVE_MODE_DISCLOSURE_TEXT)
        assert match is None, (
            f"LIVE_MODE_DISCLOSURE_TEXT contains directive language matching "
            f"{pattern.pattern!r}: {match.group(0)!r}"
        )
    # And it MUST contain the non-advice anchor.
    assert "not investment advice" in LIVE_MODE_DISCLOSURE_TEXT


def test_output_radar_mode_rejects_non_radar_node() -> None:
    node = MethodologyNode(
        id="not-a-radar",
        type=VizaNodeType.SCORE,
        position=GraphPosition(x=0.0, y=0.0),
    )
    with pytest.raises(ValueError):
        output_radar_mode(node)


# ---- Phase B: validation ledger integration -------------------------------


def test_validation_record_for_decisions_pins_inputs() -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-vr",
        graph_hash="hash-vr",
        profile_version="ver-vr",
    )
    record = validation_record_for_decisions(
        profile=profile,
        decisions=decisions,
        triggering_observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-vr",
        graph_hash="hash-vr",
        profile_version="ver-vr",
    )

    assert record.run_id == "run-vr"
    assert record.graph_hash == "hash-vr"
    assert record.timestamp_cutoff == cutoff
    assert record.strategy_profile_id == profile.strategy_profile_id
    assert record.result_checksum
    assert record.evidence_checksum
    assert len(record.outputs) == 1
    output = record.outputs[0]
    assert output["decision_id"] == decisions[0].decision_id
    assert output["rule_id"] == decisions[0].rule_id
    assert output["mode"] == "sandbox_replay"
    assert record.PIT_summary["status"] == "passed"
    assert record.in_sample_out_of_sample_label == "sandbox_replay"
    assert record.performance_observation["status"] == "pending"


def test_emit_and_persist_decisions_round_trips_ledger(tmp_path: Path) -> None:
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    store_path = tmp_path / "viza_phase_b.sqlite3"
    decisions, record = emit_and_persist_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-emit-1",
        graph_hash="hash-emit-1",
        profile_version="ver-emit-1",
        decision_store=DecisionStore(store_path),
        validation_store_path=store_path,
    )
    assert len(decisions) == 1
    assert record.run_id == "run-emit-1"

    ledger = get_validation_ledger_store(store_path)
    persisted_records = ledger.list_by_run("run-emit-1")
    assert len(persisted_records) == 1
    assert persisted_records[0].validation_record_id == record.validation_record_id
    assert persisted_records[0].outputs[0]["decision_id"] == decisions[0].decision_id


def test_emit_and_persist_decisions_records_empty_run(tmp_path: Path) -> None:
    """A run that produces no decisions still emits a validation record so the
    inputs are pinned (the audit trail says 'we ran this and nothing fired')."""
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=55.0,  # above threshold; rule does not fire
        available_at=cutoff - timedelta(hours=1),
    )
    store_path = tmp_path / "viza_phase_b_empty.sqlite3"
    decisions, record = emit_and_persist_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-empty-1",
        graph_hash="hash-empty-1",
        profile_version="ver-empty-1",
        decision_store=DecisionStore(store_path),
        validation_store_path=store_path,
    )
    assert decisions == []
    assert record.run_id == "run-empty-1"
    assert record.outputs == []
    assert record.PIT_summary["status"] == "not_applicable"


# ---- Phase B: end-to-end replay-from-store ---------------------------------


def test_replay_from_persisted_stores_is_bit_identical(tmp_path: Path) -> None:
    """End-to-end: persist observations to ObservationStore, profile to
    StrategyProfileStore, emit decisions + validation record. Then reload
    observations + profile from their stores and re-run compile_decisions
    with the same run_id / cutoff / graph_hash / profile_version. The output
    must be bit-identical to the persisted decisions.
    """
    store_path = tmp_path / "viza_replay.sqlite3"
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    fixed_emit = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)

    # 1. Persist observation
    observation_store = get_observation_store(store_path)
    observation = observation_store.upsert_observation(
        _make_observation(
            entity_id="AAPL",
            attribute_key="rsi_14d",
            value=25.0,
            available_at=cutoff - timedelta(hours=1),
        )
    )

    # 2. Persist profile (via the strategy profile store)
    profile_store = get_strategy_profile_store(store_path)
    profile = profile_store.create_profile(
        StrategyProfileCreateRequest(
            strategy_profile_id="replay-test-profile",
            display_name="Replay Test Profile",
            decision_rules=[_rsi_rule()],
            label="initial",
        )
    )
    profile_version = strategy_profile_hash(profile)

    # 3. First run: compile + persist decisions + validation record
    first_decisions, first_record = emit_and_persist_decisions(
        profile=profile,
        observations=[observation],
        cutoff_timestamp=cutoff,
        run_id="run-replay-end-to-end",
        graph_hash="hash-replay-1",
        profile_version=profile_version,
        decision_store=DecisionStore(store_path),
        validation_store_path=store_path,
        emitted_at=fixed_emit,
    )
    assert len(first_decisions) == 1

    # 4. Reload observations and profile from their stores
    reloaded_observations = observation_store.query_observations(
        ObservationQueryRequest(
            entity_id="AAPL",
            attribute_key="rsi_14d",
            cutoff=cutoff,
            limit=50,
        )
    )
    assert len(reloaded_observations) == 1
    assert reloaded_observations[0].observation_id == observation.observation_id

    reloaded_profile = profile_store.require_profile("replay-test-profile")
    assert strategy_profile_hash(reloaded_profile) == profile_version

    # 5. Re-run compile_decisions against reloaded inputs
    replay_decisions = compile_decisions(
        profile=reloaded_profile,
        observations=reloaded_observations,
        cutoff_timestamp=cutoff,
        run_id="run-replay-end-to-end",
        graph_hash="hash-replay-1",
        profile_version=profile_version,
        emitted_at=fixed_emit,
    )

    # 6. Bit-identical assertion
    assert [d.model_dump(mode="json") for d in replay_decisions] == [
        d.model_dump(mode="json") for d in first_decisions
    ]

    # 7. Validation record round-trips
    ledger = get_validation_ledger_store(store_path)
    persisted_record = ledger.require_record(first_record.validation_record_id)
    assert persisted_record.result_checksum == first_record.result_checksum
    assert persisted_record.evidence_checksum == first_record.evidence_checksum


# ---- Phase C: cooldown / dead-band ----------------------------------------


def test_cooldown_policy_requires_window_when_cap_set() -> None:
    with pytest.raises(ValidationError):
        CooldownPolicy(max_fires_per_entity_per_window=1)


def test_cooldown_policy_rejects_negative_dead_band() -> None:
    with pytest.raises(ValidationError):
        CooldownPolicy(dead_band_threshold=-0.1)


def _rsi_rule_with_cooldown(policy: CooldownPolicy) -> DecisionRule:
    return DecisionRule(
        rule_id="rsi-deep-oversold-cooldown",
        label="Deep oversold with cooldown",
        enabled=True,
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(
                    attribute_key="rsi_14d",
                    operator="lte",
                    threshold=30.0,
                )
            ]
        ),
        action_template="Flag for analyst review: RSI deep-oversold.",
        cooldown_policy=policy,
    )


def test_cooldown_suppresses_when_cap_reached_in_window() -> None:
    cooldown = CooldownPolicy(
        max_fires_per_entity_per_window=1,
        window_seconds=30 * 24 * 3600,
    )
    profile = _make_profile([_rsi_rule_with_cooldown(cooldown)])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    prior = [
        PriorEmission(
            rule_id="rsi-deep-oversold-cooldown",
            entity_id="AAPL",
            cutoff_timestamp=cutoff - timedelta(days=10),
            trigger_values={"rsi_14d": 28.0},
        ),
    ]
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-cooldown-1",
        graph_hash="h",
        profile_version="v",
        prior_emissions=prior,
    )
    assert decisions == []


def test_cooldown_does_not_suppress_when_prior_outside_window() -> None:
    cooldown = CooldownPolicy(
        max_fires_per_entity_per_window=1,
        window_seconds=7 * 24 * 3600,  # 7-day window
    )
    profile = _make_profile([_rsi_rule_with_cooldown(cooldown)])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    prior = [
        PriorEmission(
            rule_id="rsi-deep-oversold-cooldown",
            entity_id="AAPL",
            cutoff_timestamp=cutoff - timedelta(days=30),  # outside window
            trigger_values={"rsi_14d": 28.0},
        ),
    ]
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-cooldown-2",
        graph_hash="h",
        profile_version="v",
        prior_emissions=prior,
    )
    assert len(decisions) == 1


def test_dead_band_suppresses_when_delta_below_threshold() -> None:
    cooldown = CooldownPolicy(dead_band_threshold=5.0)
    profile = _make_profile([_rsi_rule_with_cooldown(cooldown)])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    prior = [
        PriorEmission(
            rule_id="rsi-deep-oversold-cooldown",
            entity_id="AAPL",
            cutoff_timestamp=cutoff - timedelta(days=3),
            trigger_values={"rsi_14d": 28.0},
        ),
    ]
    # Current value 26.0 is only 2.0 away from prior 28.0; threshold 5.0 → suppress.
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=26.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-deadband-1",
        graph_hash="h",
        profile_version="v",
        prior_emissions=prior,
    )
    assert decisions == []


def test_dead_band_fires_when_delta_exceeds_threshold() -> None:
    cooldown = CooldownPolicy(dead_band_threshold=5.0)
    profile = _make_profile([_rsi_rule_with_cooldown(cooldown)])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    prior = [
        PriorEmission(
            rule_id="rsi-deep-oversold-cooldown",
            entity_id="AAPL",
            cutoff_timestamp=cutoff - timedelta(days=3),
            trigger_values={"rsi_14d": 28.0},
        ),
    ]
    # Current 20.0 is 8.0 away from prior 28.0; threshold 5.0 → fires.
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=20.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-deadband-2",
        graph_hash="h",
        profile_version="v",
        prior_emissions=prior,
    )
    assert len(decisions) == 1


def test_compile_decisions_backward_compat_without_prior_emissions() -> None:
    """The Phase C cooldown wiring must not change Phase A/B behavior when
    callers omit prior_emissions (or pass an empty list)."""
    profile = _make_profile([_rsi_rule()])
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-backcompat",
        graph_hash="h",
        profile_version="v",
    )
    assert len(decisions) == 1


# ---- Phase C: package-redaction -------------------------------------------


def _decision_fixture() -> DecisionFrame:
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    profile = _make_profile([_rsi_rule()])
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-redaction",
        graph_hash="hash-redaction",
        profile_version="ver-redaction",
    )
    assert len(decisions) == 1
    return decisions[0]


def test_redact_white_box_returns_full_payload() -> None:
    decision = _decision_fixture()
    package = redact_decisions_for_package([decision], mode="white_box")
    assert package["package_mode"] == "white_box"
    assert package["decision_count"] == 1
    assert package["decisions"][0]["rule_text"] == decision.rule_text
    assert package["decisions"][0]["action_template"] == decision.action_template
    assert package["decisions"][0]["trigger_observation_ids"] == sorted(
        decision.trigger_observation_ids
    )


def test_redact_output_only_redacts_rule_text_and_triggers() -> None:
    decision = _decision_fixture()
    package = redact_decisions_for_package([decision], mode="output_only")
    assert package["package_mode"] == "output_only"
    payload = package["decisions"][0]
    assert payload["rule_text"] == "[redacted]"
    assert payload["trigger_observation_ids"] == []
    assert payload["trigger_observation_count"] == len(decision.trigger_observation_ids)
    # action_template is intentionally retained — output_only ships the action,
    # just not the rule identity that produced it.
    assert payload["action_template"] == decision.action_template
    assert payload["entity_id"] == decision.entity_id
    redacted_fields = {entry["field"] for entry in package["redactions"]}
    assert "rule_text" in redacted_fields
    assert "trigger_observation_ids" in redacted_fields


def test_redact_marketplace_draft_strips_per_decision_content() -> None:
    decision = _decision_fixture()
    package = redact_decisions_for_package([decision], mode="marketplace_draft")
    assert package["package_mode"] == "marketplace_draft"
    assert package["decisions"] == []
    assert package["decision_count"] == 1
    assert package["entity_count"] == 1
    assert package["rule_count"] == 1
    assert package["audit"]["runs"] == [decision.audit.run_id]
    redacted_fields = {entry["field"] for entry in package["redactions"]}
    assert "per_decision_payload" in redacted_fields
    assert "rule_text" in redacted_fields
    assert "action_template" in redacted_fields
    assert "trigger_observation_ids" in redacted_fields
    assert "entity_ids" in redacted_fields


def test_redact_blocks_when_export_not_allowed() -> None:
    """Any decision with source_rights_state.export_allowed=False blocks the
    entire export, regardless of requested mode."""
    decision = _decision_fixture()
    blocked = decision.model_copy(
        update={
            "source_rights_state": {
                **decision.source_rights_state,
                "export_allowed": False,
            }
        }
    )
    for mode in ("white_box", "output_only", "marketplace_draft"):
        with pytest.raises(PackageRedactionBlocked) as exc_info:
            redact_decisions_for_package([blocked], mode=mode)
        assert exc_info.value.mode == mode
        assert "export_allowed=False" in str(exc_info.value)


# ---- Phase C: second module (real-estate) ---------------------------------


def test_real_estate_template_loads_and_carries_decision_rule() -> None:
    catalog = load_strategy_profile_templates()
    real_estate = next(
        (t for t in catalog.templates if t.domain == "real_estate.acquisition"),
        None,
    )
    assert real_estate is not None, "real-estate template missing from catalog"
    assert real_estate.module_id == "viza.real_estate_acquisition"
    assert len(real_estate.decision_rules) == 1
    rule = real_estate.decision_rules[0]
    assert rule.rule_id == "cap-rate-low-vacancy-band-v1"
    assert len(rule.trigger.observation_predicates) == 2
    attribute_keys = {p.attribute_key for p in rule.trigger.observation_predicates}
    assert attribute_keys == {"cap_rate_bps", "vacancy_rate"}
    assert rule.cooldown_policy.max_fires_per_entity_per_window == 1
    assert rule.cooldown_policy.window_seconds == 2592000


def test_real_estate_decision_fires_against_fixture_observations() -> None:
    """The DecisionFrame contract is module-agnostic: the real-estate rule
    fires deterministically against cap_rate / vacancy observations, using
    the same compile_decisions executor used by the equity domain."""
    catalog = load_strategy_profile_templates()
    real_estate_template = next(
        t for t in catalog.templates if t.domain == "real_estate.acquisition"
    )
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    profile = VizaStrategyProfile(
        strategy_profile_id="real-estate-test",
        display_name=real_estate_template.display_name,
        domain=real_estate_template.domain,
        module_id=real_estate_template.module_id,
        entity_types=real_estate_template.entity_types,
        decision_rules=real_estate_template.decision_rules,
        created_at=now,
        updated_at=now,
    )
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    cap_rate_obs = _make_observation(
        entity_id="PROP-001",
        attribute_key="cap_rate_bps",
        value=750.0,  # >= 700 threshold
        available_at=cutoff - timedelta(hours=1),
    )
    vacancy_obs = _make_observation(
        entity_id="PROP-001",
        attribute_key="vacancy_rate",
        value=0.05,  # <= 0.08 threshold
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[cap_rate_obs, vacancy_obs],
        cutoff_timestamp=cutoff,
        run_id="run-real-estate-1",
        graph_hash="hash-re-1",
        profile_version="ver-re-1",
    )
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.rule_id == "cap-rate-low-vacancy-band-v1"
    assert decision.entity_id == "PROP-001"
    assert "cap rate" in decision.action_template.lower()
    assert decision.strategy_profile_id == "real-estate-test"
    assert set(decision.trigger_observation_ids) == {
        cap_rate_obs.observation_id,
        vacancy_obs.observation_id,
    }


def _live_mode_profile(rule: DecisionRule) -> VizaStrategyProfile:
    """A profile with the current live-mode opt-in pre-recorded."""
    from viza.decisions import LIVE_MODE_DISCLOSURE_VERSION
    from viza.strategy_profiles import LiveModeOptIn

    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    return VizaStrategyProfile(
        strategy_profile_id="live-test-profile",
        display_name="Live Mode Test",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[rule],
        live_mode_opt_in=LiveModeOptIn(
            accepted_at=now - timedelta(days=1),
            accepted_disclosure_version=LIVE_MODE_DISCLOSURE_VERSION,
            accepted_by_user="self",
        ),
        created_at=now,
        updated_at=now,
    )


def _live_eligible_rule() -> DecisionRule:
    """An rsi rule with effective_from set (live mode requires this)."""
    return DecisionRule(
        rule_id="rsi-deep-oversold-live",
        label="Deep oversold (RSI ≤ 30) — live",
        enabled=True,
        trigger=DecisionTrigger(
            observation_predicates=[
                ObservationPredicate(
                    attribute_key="rsi_14d",
                    operator="lte",
                    threshold=30.0,
                )
            ]
        ),
        action_template="Flag for analyst review: RSI deep-oversold.",
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_live_mode_blocks_when_profile_has_no_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from viza.decisions import LIVE_MODE_ENV_VAR, LiveModeOptInRequiredError

    monkeypatch.setenv(LIVE_MODE_ENV_VAR, "true")
    profile = _make_profile([_live_eligible_rule()])  # no live_mode_opt_in
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    with pytest.raises(LiveModeOptInRequiredError):
        compile_decisions(
            profile=profile,
            observations=[],
            cutoff_timestamp=cutoff,
            run_id="run-live-1",
            graph_hash="h",
            profile_version="v",
            mode="live",
        )


def test_live_mode_blocks_when_opt_in_is_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from viza.decisions import LIVE_MODE_ENV_VAR, LiveModeOptInStaleError
    from viza.strategy_profiles import LiveModeOptIn

    monkeypatch.setenv(LIVE_MODE_ENV_VAR, "true")
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    profile = VizaStrategyProfile(
        strategy_profile_id="stale-opt-in",
        display_name="Stale Opt-In",
        domain="finance.securities",
        module_id="viza.finance.securities",
        decision_rules=[_live_eligible_rule()],
        live_mode_opt_in=LiveModeOptIn(
            accepted_at=now - timedelta(days=180),
            accepted_disclosure_version="v0",  # stale
            accepted_by_user="self",
        ),
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(LiveModeOptInStaleError) as exc_info:
        compile_decisions(
            profile=profile,
            observations=[],
            cutoff_timestamp=now,
            run_id="run-stale-1",
            graph_hash="h",
            profile_version="v",
            mode="live",
        )
    assert exc_info.value.accepted_version == "v0"


def test_live_mode_requires_rule_effective_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from viza.decisions import LIVE_MODE_ENV_VAR, LiveModeRuleEffectiveDateRequiredError

    monkeypatch.setenv(LIVE_MODE_ENV_VAR, "true")
    # Rule has no effective_from; profile has valid opt-in.
    rule_without_effective_from = _rsi_rule()  # effective_from=None
    profile = _live_mode_profile(rule_without_effective_from)
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    with pytest.raises(LiveModeRuleEffectiveDateRequiredError) as exc_info:
        compile_decisions(
            profile=profile,
            observations=[],
            cutoff_timestamp=cutoff,
            run_id="run-live-eff",
            graph_hash="h",
            profile_version="v",
            mode="live",
        )
    assert exc_info.value.rule_id == "rsi-deep-oversold-v1"


def test_live_mode_emits_decisions_when_all_guards_satisfied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from viza.decisions import LIVE_MODE_ENV_VAR

    monkeypatch.setenv(LIVE_MODE_ENV_VAR, "true")
    profile = _live_mode_profile(_live_eligible_rule())
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-live-success",
        graph_hash="h",
        profile_version="v",
        mode="live",
    )
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.mode == "live"
    assert decision.rule_id == "rsi-deep-oversold-live"
    assert decision.action_template == "Flag for analyst review: RSI deep-oversold."
    assert decision.not_investment_advice is True


def test_live_mode_decisions_persist_through_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SQLite CHECK accepts mode='live'; round-trip preserves the mode."""
    from viza.decisions import LIVE_MODE_ENV_VAR

    monkeypatch.setenv(LIVE_MODE_ENV_VAR, "true")
    profile = _live_mode_profile(_live_eligible_rule())
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    obs = _make_observation(
        entity_id="AAPL",
        attribute_key="rsi_14d",
        value=25.0,
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[obs],
        cutoff_timestamp=cutoff,
        run_id="run-live-store",
        graph_hash="h",
        profile_version="v",
        mode="live",
    )
    store = DecisionStore(tmp_path / "live_store.sqlite3")
    for decision in decisions:
        store.upsert_decision(decision)
    persisted = store.list_decisions_by_run("run-live-store")
    assert len(persisted) == 1
    assert persisted[0].mode == "live"
    assert persisted[0].action_template == decisions[0].action_template


def test_live_mode_rule_effective_after_cutoff_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rule whose effective_from is later than the cutoff cannot fire under
    live mode — the strict pin-5 (C) gate runs as a precondition, raising
    LiveModeRuleEffectiveDateRequiredError before any per-entity evaluation."""
    from viza.decisions import LIVE_MODE_ENV_VAR, LiveModeRuleEffectiveDateRequiredError

    monkeypatch.setenv(LIVE_MODE_ENV_VAR, "true")
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    future_rule = _live_eligible_rule().model_copy(
        update={"effective_from": cutoff + timedelta(days=1)},
    )
    profile = _live_mode_profile(future_rule)
    with pytest.raises(LiveModeRuleEffectiveDateRequiredError):
        compile_decisions(
            profile=profile,
            observations=[],
            cutoff_timestamp=cutoff,
            run_id="run-live-future",
            graph_hash="h",
            profile_version="v",
            mode="live",
        )


def test_real_estate_decision_does_not_fire_when_vacancy_too_high() -> None:
    """When vacancy exceeds the threshold, the rule does not fire even if
    cap_rate is within band — multiple-predicate AND semantics."""
    catalog = load_strategy_profile_templates()
    real_estate_template = next(
        t for t in catalog.templates if t.domain == "real_estate.acquisition"
    )
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    profile = VizaStrategyProfile(
        strategy_profile_id="real-estate-test-2",
        display_name=real_estate_template.display_name,
        domain=real_estate_template.domain,
        module_id=real_estate_template.module_id,
        entity_types=real_estate_template.entity_types,
        decision_rules=real_estate_template.decision_rules,
        created_at=now,
        updated_at=now,
    )
    cutoff = datetime(2026, 5, 20, tzinfo=timezone.utc)
    cap_rate_obs = _make_observation(
        entity_id="PROP-002",
        attribute_key="cap_rate_bps",
        value=900.0,
        available_at=cutoff - timedelta(hours=1),
    )
    vacancy_obs = _make_observation(
        entity_id="PROP-002",
        attribute_key="vacancy_rate",
        value=0.15,  # exceeds 0.08 threshold
        available_at=cutoff - timedelta(hours=1),
    )
    decisions = compile_decisions(
        profile=profile,
        observations=[cap_rate_obs, vacancy_obs],
        cutoff_timestamp=cutoff,
        run_id="run-real-estate-3",
        graph_hash="hash-re-3",
        profile_version="ver-re-3",
    )
    assert decisions == []

"""Phase-28 unit tests: bitemporal observation columns, AS-OF queries, and
the correction flow that closes a prior row's transaction_time_end and
inserts a new row instead of overwriting in place.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from viza.observations import (
    ObservationInput,
    ObservationStore,
    VizaObservation,
    observation_from_input,
)


def _store(tmp_path: Path) -> ObservationStore:
    return ObservationStore(tmp_path / "obs.db")


def _observation(
    *,
    entity_id: str = "eq_aapl",
    attribute_key: str = "rsi_14d",
    value: float = 27.0,
    moment: datetime,
    valid_time_start: datetime | None = None,
) -> VizaObservation:
    item = ObservationInput(
        entity_id=entity_id,
        attribute_key=attribute_key,
        value=value,
        observed_at=moment,
        available_at=moment,
        retrieved_at=moment,
    )
    obs = observation_from_input(item)
    if valid_time_start is not None:
        obs = obs.model_copy(update={"valid_time_start": valid_time_start})
    return obs


# ---- Defaults / model validator -----------------------------------------


def test_observation_defaults_bitemporal_columns_from_legacy_timestamps() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    obs = _observation(moment=moment)
    assert obs.valid_time_start == moment
    assert obs.valid_time_end is None
    assert obs.transaction_time_start == moment
    assert obs.transaction_time_end is None


def test_observation_validator_rejects_inverted_intervals() -> None:
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        VizaObservation(
            observation_id="x",
            entity_id="e",
            attribute_key="rsi_14d",
            value=27.0,
            observed_at=moment,
            available_at=moment,
            retrieved_at=moment,
            source_id="s",
            connector_id="c",
            checksum="sum",
            valid_time_start=moment + timedelta(days=1),
            valid_time_end=moment,
        )


# ---- Persistence round-trip ---------------------------------------------


def test_persist_and_reload_preserves_bitemporal_fields(tmp_path: Path) -> None:
    store = _store(tmp_path)
    moment = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    obs = _observation(moment=moment)
    store.upsert_observation(obs)
    reloaded = store.require_observation(obs.observation_id)
    assert reloaded.valid_time_start == moment
    assert reloaded.transaction_time_start == moment
    assert reloaded.valid_time_end is None
    assert reloaded.transaction_time_end is None


# ---- Migration ----------------------------------------------------------


def test_migration_backfills_bitemporal_columns_on_pre_phase_28_table(
    tmp_path: Path,
) -> None:
    """A database that pre-dates Phase 28 has the old observations schema
    with no bitemporal columns. The migration must (a) add the columns and
    (b) backfill them from observed_at / retrieved_at so AS-OF queries
    return existing rows."""
    db_path = tmp_path / "legacy.db"
    import sqlite3

    legacy_sql = """
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
    )
    """
    connection = sqlite3.connect(db_path)
    connection.executescript(legacy_sql)
    moment = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    connection.execute(
        """
        INSERT INTO observations(
            observation_id, entity_id, asset_id, attribute_key, value_json, unit,
            observed_at, available_at, retrieved_at,
            source_id, connector_id, source_record, data_version, model_version,
            confidence, rights_policy_json, checksum
        ) VALUES (
            'legacy-row', 'eq_aapl', NULL, 'rsi_14d', '27.0', NULL,
            ?, ?, ?,
            's', 'c', NULL, NULL, NULL, NULL, '{}', 'sum'
        )
        """,
        (moment.isoformat(), moment.isoformat(), moment.isoformat()),
    )
    connection.commit()
    connection.close()

    # Open via the store — the migration should now run on top of the legacy table.
    store = ObservationStore(db_path)
    legacy = store.require_observation("legacy-row")
    assert legacy.valid_time_start == moment
    assert legacy.transaction_time_start == moment


# ---- AS-OF transaction time --------------------------------------------


def test_as_of_transaction_time_returns_only_belief_at_that_moment(
    tmp_path: Path,
) -> None:
    """Two corrections of the same fact across three transaction times.
    An AS-OF query at each of t0, t1, t2 returns the single row the system
    believed at that moment."""
    store = _store(tmp_path)
    t0 = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)

    initial = _observation(value=27.0, moment=t0)
    store.upsert_observation(initial)

    first_correction = _observation(
        value=28.5, moment=t1, valid_time_start=t0
    )
    store.correct_observation(
        prior_observation_id=initial.observation_id,
        new_observation=first_correction,
        correction_time=t1,
    )

    second_correction = _observation(
        value=29.1, moment=t2, valid_time_start=t0
    )
    # Must chain off the current-belief row, which after the first correction
    # is the row we wrote at t1.
    current = store.get_as_of_transaction_time(transaction_time=t1, entity_id="eq_aapl")
    assert len(current) == 1
    store.correct_observation(
        prior_observation_id=current[0].observation_id,
        new_observation=second_correction,
        correction_time=t2,
    )

    as_of_t0 = store.get_as_of_transaction_time(transaction_time=t0, entity_id="eq_aapl")
    as_of_t1_plus = store.get_as_of_transaction_time(
        transaction_time=t1 + timedelta(microseconds=1), entity_id="eq_aapl"
    )
    as_of_t2_plus = store.get_as_of_transaction_time(
        transaction_time=t2 + timedelta(microseconds=1), entity_id="eq_aapl"
    )

    assert [row.value for row in as_of_t0] == [27.0]
    assert [row.value for row in as_of_t1_plus] == [28.5]
    assert [row.value for row in as_of_t2_plus] == [29.1]


def test_correction_refuses_to_chain_off_superseded_row(tmp_path: Path) -> None:
    store = _store(tmp_path)
    t0 = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)

    initial = _observation(value=27.0, moment=t0)
    store.upsert_observation(initial)
    corrected = _observation(value=28.5, moment=t1, valid_time_start=t0)
    store.correct_observation(
        prior_observation_id=initial.observation_id,
        new_observation=corrected,
        correction_time=t1,
    )

    second = _observation(value=29.1, moment=t2, valid_time_start=t0)
    with pytest.raises(ValueError):
        store.correct_observation(
            prior_observation_id=initial.observation_id,
            new_observation=second,
            correction_time=t2,
        )


# ---- AS-OF valid time --------------------------------------------------


def test_as_of_valid_time_respects_current_belief_filter(tmp_path: Path) -> None:
    """A row whose valid_time interval contained the queried valid_time but
    which has been superseded by a correction (different value, same
    valid_time_start) must NOT be returned. AS-OF valid time is always the
    *current belief* about the past."""
    store = _store(tmp_path)
    valid_moment = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
    tx0 = datetime(2026, 5, 19, 13, 0, tzinfo=timezone.utc)
    tx1 = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)

    initial = _observation(value=27.0, moment=tx0, valid_time_start=valid_moment)
    store.upsert_observation(initial)
    corrected = _observation(value=28.5, moment=tx1, valid_time_start=valid_moment)
    store.correct_observation(
        prior_observation_id=initial.observation_id,
        new_observation=corrected,
        correction_time=tx1,
    )

    as_of_valid = store.get_as_of_valid_time(
        valid_time=valid_moment + timedelta(seconds=1),
        entity_id="eq_aapl",
    )
    assert len(as_of_valid) == 1
    assert as_of_valid[0].value == 28.5

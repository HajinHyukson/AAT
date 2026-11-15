from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import pstdev
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.project_store import project_store_path


TECHNICAL_OBSERVATION_KEYS = {
    "latest_price",
    "rsi_14d",
    "momentum",
    "moving_average_trend",
    "volume_spike",
    "realized_volatility",
    "short_term_reversal",
    "sector_relative_strength",
    "unexplained_residual_bps",
}


class VizaObservation(BaseModel):
    """A single observation of an attribute value for an entity.

    Phase 28 (`docs/viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`)
    adds explicit bitemporal columns (Snodgrass / SQL:2011) so the store can
    distinguish *valid time* (when a fact is true in the world) from
    *transaction time* (when the system believed it). The three legacy
    timestamps are RETAINED because they carry source-specific semantics that
    bitemporal columns alone do not capture:

    * ``observed_at`` — when the source generated the data point.
    * ``available_at`` — earliest moment the engine could have queried the
      source for it (the financial PIT discipline timestamp).
    * ``retrieved_at`` — when this process actually fetched it.

    Bitemporal columns:

    * ``valid_time_start`` — when the fact began being true. Defaults to
      ``observed_at`` when omitted.
    * ``valid_time_end`` — when the fact stops being true. ``None`` means
      "still true" and is the common case for point-in-time price/RSI/etc.
    * ``transaction_time_start`` — when the system started believing this
      row. Defaults to ``retrieved_at`` when omitted.
    * ``transaction_time_end`` — when this belief was superseded by a
      correction. ``None`` means "current belief."

    A correction (``ObservationStore.correct_observation``) closes the prior
    row's ``transaction_time_end`` and inserts a new row with a fresh
    ``transaction_time_start``. The pair preserves history without
    overwriting; AS-OF queries reconstruct what the system believed at any
    past transaction time.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.observation.v1", alias="schema")
    observation_id: str
    entity_id: str
    asset_id: str | None = None
    attribute_key: str
    value: Any
    unit: str | None = None
    observed_at: datetime
    available_at: datetime
    retrieved_at: datetime
    source_id: str
    connector_id: str
    source_record: str | None = None
    data_version: str | None = None
    model_version: str | None = None
    confidence: float | None = None
    rights_policy: dict[str, Any] = Field(default_factory=dict)
    checksum: str
    # Phase 28 bitemporal columns. Defaults populated by the model validator
    # below so legacy callers that omit them keep working.
    valid_time_start: datetime | None = None
    valid_time_end: datetime | None = None
    transaction_time_start: datetime | None = None
    transaction_time_end: datetime | None = None

    @model_validator(mode="after")
    def populate_bitemporal_defaults(self) -> "VizaObservation":
        if self.valid_time_start is None:
            self.valid_time_start = self.observed_at
        if self.transaction_time_start is None:
            self.transaction_time_start = self.retrieved_at
        if (
            self.valid_time_end is not None
            and self.valid_time_end < self.valid_time_start
        ):
            raise ValueError(
                "valid_time_end cannot be earlier than valid_time_start"
            )
        if (
            self.transaction_time_end is not None
            and self.transaction_time_end < self.transaction_time_start
        ):
            raise ValueError(
                "transaction_time_end cannot be earlier than transaction_time_start"
            )
        return self


class ObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    asset_id: str | None = None
    attribute_key: str
    value: Any
    unit: str | None = None
    observed_at: datetime
    available_at: datetime
    retrieved_at: datetime | None = None
    source_id: str = "manual"
    connector_id: str = "local_viza_workspace"
    source_record: str | None = None
    data_version: str | None = None
    model_version: str | None = None
    confidence: float | None = None
    rights_policy: dict[str, Any] = Field(default_factory=dict)


class OHLCVRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: float | None = None
    available_at: datetime | None = None


class ObservationIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[ObservationInput] = Field(default_factory=list)
    entity_id: str | None = None
    asset_id: str | None = None
    ohlcv_rows: list[OHLCVRow] = Field(default_factory=list)
    source_id: str = "local_ohlcv_csv"
    connector_id: str = "local_csv"
    source_record: str | None = None
    data_version: str = "local_ohlcv_v0"
    model_version: str = "viza_technical_observation_v0"
    rights_policy: dict[str, Any] = Field(default_factory=lambda: _default_local_csv_rights())


class ObservationQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str | None = None
    asset_id: str | None = None
    attribute_key: str | None = None
    cutoff: datetime | None = None
    limit: int = 50


class ObservationQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[VizaObservation] = Field(default_factory=list)


class ObservationStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    _INSERT_COLUMNS = (
        "observation_id",
        "entity_id",
        "asset_id",
        "attribute_key",
        "value_json",
        "unit",
        "observed_at",
        "available_at",
        "retrieved_at",
        "source_id",
        "connector_id",
        "source_record",
        "data_version",
        "model_version",
        "confidence",
        "rights_policy_json",
        "checksum",
        "valid_time_start",
        "valid_time_end",
        "transaction_time_start",
        "transaction_time_end",
    )

    def upsert_observation(self, observation: VizaObservation) -> VizaObservation:
        """Insert or idempotently re-upsert an observation by content-addressed
        ``observation_id``. Bitemporal corrections use the explicit
        ``correct_observation`` flow below; ``upsert_observation`` is the
        no-correction path used by the ingest pipeline.
        """
        columns = self._INSERT_COLUMNS
        placeholders = ", ".join(["?"] * len(columns))
        update_set = ",\n                    ".join(
            f"{column} = excluded.{column}"
            for column in columns
            if column != "observation_id"
        )
        sql = (
            f"INSERT INTO observations({', '.join(columns)})\n"
            f"VALUES ({placeholders})\n"
            f"ON CONFLICT(observation_id) DO UPDATE SET\n                    {update_set}"
        )
        with self._connect() as connection:
            connection.execute(sql, _observation_row_values(observation))
        return self.require_observation(observation.observation_id)

    def correct_observation(
        self,
        *,
        prior_observation_id: str,
        new_observation: VizaObservation,
        correction_time: datetime | None = None,
    ) -> tuple[VizaObservation, VizaObservation]:
        """Apply a bitemporal correction.

        Closes the prior row's ``transaction_time_end`` to ``correction_time``
        (default: ``now()``) and inserts ``new_observation`` with
        ``transaction_time_start = correction_time``. The new observation's
        ``valid_time_start`` is preserved from the caller; the new observation
        is rebuilt to clear any caller-supplied ``transaction_time_start`` and
        force it to align with the correction boundary so a later AS-OF query
        returns a clean interval.

        Returns ``(prior_after_close, new_after_insert)``.

        Raises ``KeyError`` if ``prior_observation_id`` is not in the store.
        Raises ``ValueError`` if the prior row is already superseded
        (``transaction_time_end IS NOT NULL``) — the caller should chain off
        the most recent uncorrected row, not a historical one.
        """
        prior = self.require_observation(prior_observation_id)
        if prior.transaction_time_end is not None:
            raise ValueError(
                f"observation {prior_observation_id!r} is already superseded "
                f"(transaction_time_end={prior.transaction_time_end.isoformat()}); "
                "chain corrections off the current-belief row, not a closed one"
            )
        moment = correction_time or _utc_now_datetime()
        if moment < prior.transaction_time_start:
            raise ValueError(
                "correction_time cannot precede the prior row's transaction_time_start"
            )
        rebuilt_new = new_observation.model_copy(
            update={
                "transaction_time_start": moment,
                "transaction_time_end": None,
                "valid_time_start": (
                    new_observation.valid_time_start or prior.valid_time_start
                ),
            }
        )
        with self._connect() as connection:
            connection.execute(
                "UPDATE observations SET transaction_time_end = ? "
                "WHERE observation_id = ? AND transaction_time_end IS NULL",
                (moment.isoformat(), prior_observation_id),
            )
        self.upsert_observation(rebuilt_new)
        return (
            self.require_observation(prior_observation_id),
            self.require_observation(rebuilt_new.observation_id),
        )

    def get_as_of_transaction_time(
        self,
        *,
        transaction_time: datetime,
        entity_id: str | None = None,
        attribute_key: str | None = None,
    ) -> list[VizaObservation]:
        """Return the rows the system believed at the given transaction time.

        Implements the classic bitemporal AS-OF transaction query:

            transaction_time_start <= :ttx
              AND (transaction_time_end IS NULL OR transaction_time_end > :ttx)
        """
        clauses = [
            "transaction_time_start <= ?",
            "(transaction_time_end IS NULL OR transaction_time_end > ?)",
        ]
        params: list[Any] = [transaction_time.isoformat(), transaction_time.isoformat()]
        if entity_id is not None:
            clauses.append("entity_id = ?")
            params.append(entity_id)
        if attribute_key is not None:
            clauses.append("attribute_key = ?")
            params.append(attribute_key)
        sql = (
            "SELECT * FROM observations "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY entity_id ASC, attribute_key ASC, valid_time_start ASC"
        )
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_observation_from_row(row) for row in rows]

    def get_as_of_valid_time(
        self,
        *,
        valid_time: datetime,
        entity_id: str | None = None,
        attribute_key: str | None = None,
    ) -> list[VizaObservation]:
        """Return facts currently believed to have been true at the given
        valid time. Combines the valid-time AS-OF predicate with the
        current-belief filter so corrections do not surface superseded rows.

            valid_time_start <= :vt
              AND (valid_time_end IS NULL OR valid_time_end > :vt)
              AND transaction_time_end IS NULL
        """
        clauses = [
            "valid_time_start <= ?",
            "(valid_time_end IS NULL OR valid_time_end > ?)",
            "transaction_time_end IS NULL",
        ]
        params: list[Any] = [valid_time.isoformat(), valid_time.isoformat()]
        if entity_id is not None:
            clauses.append("entity_id = ?")
            params.append(entity_id)
        if attribute_key is not None:
            clauses.append("attribute_key = ?")
            params.append(attribute_key)
        sql = (
            "SELECT * FROM observations "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY entity_id ASC, attribute_key ASC, valid_time_start ASC"
        )
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_observation_from_row(row) for row in rows]

    def ingest(self, request: ObservationIngestRequest) -> list[VizaObservation]:
        observations = [observation_from_input(item) for item in request.observations]
        if request.ohlcv_rows:
            if not request.entity_id:
                raise ValueError("entity_id is required when ingesting OHLCV rows")
            observations.extend(observations_from_ohlcv(request))
        return [self.upsert_observation(observation) for observation in observations]

    def query_observations(self, request: ObservationQueryRequest) -> list[VizaObservation]:
        clauses: list[str] = []
        params: list[Any] = []
        if request.entity_id:
            clauses.append("entity_id = ?")
            params.append(request.entity_id)
        if request.asset_id:
            clauses.append("asset_id = ?")
            params.append(request.asset_id)
        if request.attribute_key:
            clauses.append("attribute_key = ?")
            params.append(request.attribute_key)
        if request.cutoff:
            clauses.append("available_at <= ?")
            params.append(request.cutoff.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(request.limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM observations
                {where}
                ORDER BY available_at DESC, observed_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_observation_from_row(row) for row in rows]

    def get_latest_observation_as_of(
        self,
        entity_id: str,
        attribute_key: str,
        cutoff: datetime,
    ) -> VizaObservation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM observations
                WHERE entity_id = ?
                  AND attribute_key = ?
                  AND available_at <= ?
                ORDER BY available_at DESC, observed_at DESC
                LIMIT 1
                """,
                (entity_id, attribute_key, cutoff.isoformat()),
            ).fetchone()
        return _observation_from_row(row) if row is not None else None

    def get_observation(self, observation_id: str) -> VizaObservation | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM observations WHERE observation_id = ?",
                (observation_id,),
            ).fetchone()
        return _observation_from_row(row) if row is not None else None

    def require_observation(self, observation_id: str) -> VizaObservation:
        observation = self.get_observation(observation_id)
        if observation is None:
            raise KeyError(f"unknown VIZA observation: {observation_id}")
        return observation

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(OBSERVATION_TABLE_SQL)
            _migrate_phase_28_bitemporal_columns(connection)
            connection.executescript(OBSERVATION_INDEX_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


OBSERVATION_TABLE_SQL = """
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
  checksum TEXT NOT NULL,
  valid_time_start TEXT,
  valid_time_end TEXT,
  transaction_time_start TEXT,
  transaction_time_end TEXT
);
"""


# Indexes are created AFTER the Phase-28 column migration so that pre-Phase-28
# tables (which lack the bitemporal columns) do not trigger "no such column"
# errors before the migration has had a chance to ALTER TABLE them in.
OBSERVATION_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_observations_lookup
  ON observations(entity_id, attribute_key, available_at);
CREATE INDEX IF NOT EXISTS idx_observations_transaction_time
  ON observations(transaction_time_start, transaction_time_end);
CREATE INDEX IF NOT EXISTS idx_observations_valid_time
  ON observations(entity_id, attribute_key, valid_time_start);
"""


_PHASE_28_NEW_COLUMNS = (
    ("valid_time_start", "TEXT"),
    ("valid_time_end", "TEXT"),
    ("transaction_time_start", "TEXT"),
    ("transaction_time_end", "TEXT"),
)


def _migrate_phase_28_bitemporal_columns(connection: sqlite3.Connection) -> None:
    """Add Phase-28 bitemporal columns to a pre-Phase-28 observations table
    and backfill the start columns from ``observed_at`` / ``retrieved_at``.

    Idempotent. Re-running against an already-migrated table is a no-op
    because each ALTER TABLE is gated on a PRAGMA table_info() probe and the
    backfill UPDATE only touches NULL rows.

    Note on the NULL constraint: SQLite does not support ALTER TABLE … ADD
    COLUMN ... NOT NULL DEFAULT ... well across all versions, so the columns
    are nullable at the storage level. Application-level invariant: every
    row written through ``ObservationStore.upsert_observation`` carries
    non-NULL ``valid_time_start`` and ``transaction_time_start`` because the
    Pydantic ``VizaObservation`` validator populates them from
    ``observed_at`` / ``retrieved_at`` defaults.
    """
    existing = {
        row[1]
        for row in connection.execute("PRAGMA table_info(observations)").fetchall()
    }
    if not existing:
        # Fresh table created by OBSERVATION_TABLE_SQL above already has the
        # columns; nothing to migrate.
        return
    for column_name, column_definition in _PHASE_28_NEW_COLUMNS:
        if column_name in existing:
            continue
        connection.execute(
            f"ALTER TABLE observations ADD COLUMN {column_name} {column_definition}"
        )
    # Backfill: existing rows get valid_time_start = observed_at and
    # transaction_time_start = retrieved_at. _end columns remain NULL so
    # they're treated as the current belief and still-true facts.
    connection.execute(
        "UPDATE observations SET valid_time_start = observed_at "
        "WHERE valid_time_start IS NULL"
    )
    connection.execute(
        "UPDATE observations SET transaction_time_start = retrieved_at "
        "WHERE transaction_time_start IS NULL"
    )


def get_observation_store(path: str | Path | None = None) -> ObservationStore:
    return ObservationStore(path)


def ohlcv_rows_from_csv(path: str | Path) -> list[OHLCVRow]:
    rows: list[OHLCVRow] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp_value = row.get("timestamp") or row.get("date") or row.get("observed_at")
            close_value = row.get("close") or row.get("adj_close")
            if close_value is None:
                raise ValueError("OHLCV CSV row is missing close")
            rows.append(
                OHLCVRow(
                    timestamp=_parse_datetime(timestamp_value),
                    open=_optional_float(row.get("open")),
                    high=_optional_float(row.get("high")),
                    low=_optional_float(row.get("low")),
                    close=_read_float(close_value),
                    volume=_optional_float(row.get("volume")),
                    available_at=(
                        _parse_datetime(row.get("available_at")) if row.get("available_at") else None
                    ),
                )
            )
    return rows


def observation_from_input(item: ObservationInput) -> VizaObservation:
    retrieved_at = item.retrieved_at or _utc_now_datetime()
    payload = {
        "entity_id": item.entity_id,
        "asset_id": item.asset_id,
        "attribute_key": item.attribute_key,
        "value": item.value,
        "observed_at": item.observed_at.isoformat(),
        "available_at": item.available_at.isoformat(),
        "source_id": item.source_id,
        "connector_id": item.connector_id,
        "source_record": item.source_record,
    }
    checksum = _checksum(payload)
    return VizaObservation(
        observation_id=f"obs-{checksum[:24]}",
        entity_id=item.entity_id,
        asset_id=item.asset_id,
        attribute_key=item.attribute_key,
        value=item.value,
        unit=item.unit,
        observed_at=item.observed_at,
        available_at=item.available_at,
        retrieved_at=retrieved_at,
        source_id=item.source_id,
        connector_id=item.connector_id,
        source_record=item.source_record,
        data_version=item.data_version,
        model_version=item.model_version,
        confidence=item.confidence,
        rights_policy=item.rights_policy,
        checksum=checksum,
    )


def observations_from_ohlcv(request: ObservationIngestRequest) -> list[VizaObservation]:
    rows = sorted(request.ohlcv_rows, key=lambda row: row.timestamp)
    values = technical_values_from_ohlcv(rows)
    if not values:
        return []
    observed_at = rows[-1].timestamp
    available_at = rows[-1].available_at or observed_at
    retrieved_at = _utc_now_datetime()
    observations: list[VizaObservation] = []
    for attribute_key, value in values.items():
        item = ObservationInput(
            entity_id=request.entity_id or "",
            asset_id=request.asset_id,
            attribute_key=attribute_key,
            value=value,
            unit=_technical_unit(attribute_key),
            observed_at=observed_at,
            available_at=available_at,
            retrieved_at=retrieved_at,
            source_id=request.source_id,
            connector_id=request.connector_id,
            source_record=request.source_record,
            data_version=request.data_version,
            model_version=request.model_version,
            confidence=0.92,
            rights_policy=request.rights_policy,
        )
        observations.append(observation_from_input(item))
    return observations


def technical_values_from_ohlcv(rows: list[OHLCVRow]) -> dict[str, float]:
    closes = [row.close for row in rows if math.isfinite(row.close)]
    volumes = [row.volume for row in rows if row.volume is not None and math.isfinite(row.volume)]
    if not closes:
        return {}

    values: dict[str, float] = {"latest_price": round(closes[-1], 6)}
    rsi = calculate_rsi_14d(closes)
    if rsi is not None:
        values["rsi_14d"] = rsi
    if len(closes) >= 21:
        values["momentum"] = round((closes[-1] / closes[-21]) - 1, 6)
    if len(closes) >= 50:
        short_ma = sum(closes[-20:]) / 20
        long_ma = sum(closes[-50:]) / 50
        values["moving_average_trend"] = round((short_ma / long_ma) - 1, 6)
    if len(closes) >= 2:
        returns = [(closes[index] / closes[index - 1]) - 1 for index in range(1, len(closes))]
        values["short_term_reversal"] = round(-returns[-1], 6)
        if len(returns) >= 20:
            values["realized_volatility"] = round(pstdev(returns[-20:]) * math.sqrt(252), 6)
    if len(volumes) >= 21:
        average_volume = sum(volumes[-21:-1]) / 20
        if average_volume:
            values["volume_spike"] = round(volumes[-1] / average_volume, 6)
    return values


def calculate_rsi_14d(closes: list[float]) -> float | None:
    if len(closes) < 15:
        return None
    deltas = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    window = deltas[-14:]
    gains = [max(delta, 0.0) for delta in window]
    losses = [abs(min(delta, 0.0)) for delta in window]
    average_gain = sum(gains) / 14
    average_loss = sum(losses) / 14
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return round(100 - (100 / (1 + relative_strength)), 6)


def observation_for_export(observation: VizaObservation) -> dict[str, Any]:
    payload = observation.model_dump(mode="json", by_alias=True)
    rights = observation.rights_policy
    if rights.get("raw_snapshot_allowed") is False or rights.get("export_allowed") is False:
        payload["value"] = "[redacted]"
        payload["redaction_reason"] = "source_rights_restricted"
    return payload


def _observation_row_values(observation: VizaObservation) -> tuple[Any, ...]:
    return (
        observation.observation_id,
        observation.entity_id,
        observation.asset_id,
        observation.attribute_key,
        json.dumps(observation.value, sort_keys=True),
        observation.unit,
        observation.observed_at.isoformat(),
        observation.available_at.isoformat(),
        observation.retrieved_at.isoformat(),
        observation.source_id,
        observation.connector_id,
        observation.source_record,
        observation.data_version,
        observation.model_version,
        observation.confidence,
        json.dumps(observation.rights_policy, sort_keys=True),
        observation.checksum,
        observation.valid_time_start.isoformat() if observation.valid_time_start else None,
        observation.valid_time_end.isoformat() if observation.valid_time_end else None,
        (
            observation.transaction_time_start.isoformat()
            if observation.transaction_time_start
            else None
        ),
        (
            observation.transaction_time_end.isoformat()
            if observation.transaction_time_end
            else None
        ),
    )


def _observation_from_row(row: sqlite3.Row) -> VizaObservation:
    column_names = row.keys()

    def _maybe_dt(name: str) -> datetime | None:
        if name not in column_names:
            return None
        value = row[name]
        if not value:
            return None
        return datetime.fromisoformat(value)

    return VizaObservation(
        observation_id=row["observation_id"],
        entity_id=row["entity_id"],
        asset_id=row["asset_id"],
        attribute_key=row["attribute_key"],
        value=json.loads(row["value_json"]),
        unit=row["unit"],
        observed_at=datetime.fromisoformat(row["observed_at"]),
        available_at=datetime.fromisoformat(row["available_at"]),
        retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
        source_id=row["source_id"],
        connector_id=row["connector_id"],
        source_record=row["source_record"],
        data_version=row["data_version"],
        model_version=row["model_version"],
        confidence=row["confidence"],
        rights_policy=json.loads(row["rights_policy_json"]),
        checksum=row["checksum"],
        valid_time_start=_maybe_dt("valid_time_start"),
        valid_time_end=_maybe_dt("valid_time_end"),
        transaction_time_start=_maybe_dt("transaction_time_start"),
        transaction_time_end=_maybe_dt("transaction_time_end"),
    )


def _checksum(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _technical_unit(attribute_key: str) -> str:
    if attribute_key == "latest_price":
        return "price"
    if attribute_key == "rsi_14d":
        return "score_0_100"
    return "score"


def _utc_now_datetime() -> datetime:
    return datetime.now(timezone.utc)


def _default_local_csv_rights() -> dict[str, Any]:
    return {
        "raw_snapshot_allowed": False,
        "connector_id": "local_csv",
        "source_id": "local_ohlcv_csv",
        "license_policy": "user_provided",
        "cache_policy": "local_project_store",
        "display_policy": "derived_values_allowed",
        "export_policy": "derived_values_allowed",
        "derived_value_policy": "allowed",
        "redistribution_policy": "restricted",
        "attribution_required": False,
        "retention_policy": "local_project_store",
    }


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("OHLCV CSV row is missing timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_float(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value:
        return float(value)
    raise ValueError("expected numeric OHLCV value")


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return _read_float(value)

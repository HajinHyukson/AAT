"""Pin-6 cache_key / run_id observation store.

Two distinct lookup paths against a SQLite table that is additive to the
existing local project store. The base ``viza.observations`` store remains
unchanged; this module owns its own table because the cache_key,
section/chunk identity, and model-governance columns are not part of the
generic ``viza.observation.v1`` schema.

  CACHE HIT  ->  source="cache"          keyed by cache_key
  REPLAY     ->  source="stored_replay"  keyed by run_id

A single observation row carries BOTH columns; cache_key is nullable to
support replay-only imports (e.g. observations restored from a .viza file
that were never indexed by the local resolver).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from viza.equity.text.types import (
    DeltaRecord,
    RunSnapshot,
    SectionAggregate,
    SentimentObservation,
)
from viza.project_store import project_store_path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sec_text_sentiment_observations (
  observation_id            TEXT PRIMARY KEY,
  cache_key                 TEXT,
  run_id                    TEXT NOT NULL,
  entity_id                 TEXT NOT NULL,
  cik                       TEXT NOT NULL,
  ticker_alias              TEXT,
  filing_accession          TEXT NOT NULL,
  section_id                TEXT NOT NULL,
  chunk_id                  TEXT NOT NULL,
  input_text_hash           TEXT NOT NULL,
  section_text_hash         TEXT NOT NULL,
  parser_version            TEXT NOT NULL,
  chunking_policy_hash      TEXT NOT NULL,
  model_id                  TEXT NOT NULL,
  model_version             TEXT NOT NULL,
  model_hash                TEXT NOT NULL,
  tokenizer_hash            TEXT NOT NULL,
  inference_config_hash     TEXT NOT NULL,
  positive_prob             REAL NOT NULL,
  neutral_prob              REAL NOT NULL,
  negative_prob             REAL NOT NULL,
  label                     TEXT NOT NULL,
  confidence                REAL NOT NULL,
  confidence_label          TEXT NOT NULL,
  requires_human_review     INTEGER NOT NULL DEFAULT 0,
  matched_human_review_terms_json TEXT NOT NULL DEFAULT '[]',
  human_review_term_set_version TEXT NOT NULL,
  observed_at               TEXT NOT NULL,
  available_at              TEXT NOT NULL,
  retrieved_at              TEXT NOT NULL,
  inference_at              TEXT NOT NULL,
  source_id                 TEXT NOT NULL,
  source_ref                TEXT NOT NULL,
  lookahead_risk            TEXT NOT NULL DEFAULT 'low',
  rights_policy_json        TEXT NOT NULL DEFAULT '{}',
  payload_json              TEXT NOT NULL
);

-- cache_key is per (filing, section, model) and is intentionally NOT unique:
-- a single cache_key maps to N chunk observations (one per chunk produced by
-- the deterministic chunker). chunk_id is unique within the cache_key bucket.
CREATE INDEX IF NOT EXISTS idx_sec_text_sentiment_cache_key
  ON sec_text_sentiment_observations(cache_key)
  WHERE cache_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_sec_text_sentiment_cache_chunk
  ON sec_text_sentiment_observations(cache_key, chunk_id)
  WHERE cache_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sec_text_sentiment_run_id
  ON sec_text_sentiment_observations(run_id);

CREATE INDEX IF NOT EXISTS idx_sec_text_sentiment_lookup
  ON sec_text_sentiment_observations(entity_id, filing_accession, section_id);

CREATE TABLE IF NOT EXISTS sec_text_sentiment_runs (
  run_id                    TEXT PRIMARY KEY,
  resolver_id               TEXT NOT NULL,
  resolver_version          TEXT NOT NULL,
  analysis_mode             TEXT NOT NULL,
  model_policy              TEXT NOT NULL,
  cache_policy              TEXT NOT NULL,
  parser_version            TEXT NOT NULL,
  chunking_policy_hash      TEXT NOT NULL,
  inference_config_hash     TEXT NOT NULL,
  cutoff_timestamp          TEXT,
  created_at                TEXT NOT NULL,
  status                    TEXT NOT NULL,
  proof_checksum            TEXT NOT NULL,
  snapshot_json             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sec_text_sentiment_section_aggregates (
  section_sentiment_id      TEXT PRIMARY KEY,
  run_id                    TEXT NOT NULL,
  entity_id                 TEXT NOT NULL,
  filing_accession          TEXT NOT NULL,
  section_id                TEXT NOT NULL,
  payload_json              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sec_text_sentiment_aggregates_run
  ON sec_text_sentiment_section_aggregates(run_id);

CREATE TABLE IF NOT EXISTS sec_text_sentiment_deltas (
  delta_id                  TEXT PRIMARY KEY,
  run_id                    TEXT NOT NULL,
  entity_id                 TEXT NOT NULL,
  current_filing_accession  TEXT NOT NULL,
  prior_filing_accession    TEXT NOT NULL,
  section_id                TEXT NOT NULL,
  payload_json              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sec_text_sentiment_deltas_run
  ON sec_text_sentiment_deltas(run_id);
"""


class SentimentObservationStore:
    """SQLite store for sentiment observations, runs, aggregates, and deltas.

    All persisted columns are derived from the Pydantic types in
    ``viza.equity.text.types``; ``payload_json`` carries a round-trip-safe
    serialization of each record so additive fields don't require schema
    migrations.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    # ---- Persistence ----------------------------------------------------

    def upsert_observation(self, observation: SentimentObservation) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sec_text_sentiment_observations(
                    observation_id, cache_key, run_id, entity_id, cik,
                    ticker_alias, filing_accession, section_id, chunk_id,
                    input_text_hash, section_text_hash, parser_version,
                    chunking_policy_hash, model_id, model_version, model_hash,
                    tokenizer_hash, inference_config_hash,
                    positive_prob, neutral_prob, negative_prob, label,
                    confidence, confidence_label,
                    requires_human_review, matched_human_review_terms_json,
                    human_review_term_set_version,
                    observed_at, available_at, retrieved_at, inference_at,
                    source_id, source_ref, lookahead_risk, rights_policy_json,
                    payload_json
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?
                )
                ON CONFLICT(observation_id) DO NOTHING
                """,
                (
                    observation.observation_id,
                    observation.cache_key,
                    observation.run_id,
                    observation.entity_id,
                    observation.cik,
                    observation.ticker_alias,
                    observation.filing_accession,
                    observation.section_id,
                    observation.chunk_id,
                    observation.input_text_hash,
                    observation.section_text_hash,
                    observation.parser_version,
                    observation.chunking_policy_hash,
                    observation.model_id,
                    observation.model_version,
                    observation.model_hash,
                    observation.tokenizer_hash,
                    observation.inference_config_hash,
                    observation.positive_prob,
                    observation.neutral_prob,
                    observation.negative_prob,
                    observation.label,
                    observation.confidence,
                    observation.confidence_label,
                    1 if observation.requires_human_review else 0,
                    json.dumps(observation.matched_human_review_terms),
                    observation.human_review_term_set_version,
                    observation.observed_at.isoformat(),
                    observation.available_at.isoformat(),
                    observation.retrieved_at.isoformat(),
                    observation.inference_at.isoformat(),
                    observation.source_id,
                    observation.source_ref,
                    observation.lookahead_risk,
                    json.dumps(observation.rights_policy),
                    observation.model_dump_json(),
                ),
            )

    def upsert_run(self, snapshot: RunSnapshot) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sec_text_sentiment_runs(
                    run_id, resolver_id, resolver_version, analysis_mode,
                    model_policy, cache_policy, parser_version,
                    chunking_policy_hash, inference_config_hash,
                    cutoff_timestamp, created_at, status, proof_checksum,
                    snapshot_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    proof_checksum = excluded.proof_checksum,
                    snapshot_json = excluded.snapshot_json
                """,
                (
                    snapshot.run_id,
                    snapshot.resolver_id,
                    snapshot.resolver_version,
                    snapshot.analysis_mode,
                    snapshot.model_policy,
                    snapshot.cache_policy,
                    snapshot.parser_version,
                    snapshot.chunking_policy_hash,
                    snapshot.inference_config_hash,
                    snapshot.cutoff_timestamp.isoformat() if snapshot.cutoff_timestamp else None,
                    snapshot.created_at.isoformat(),
                    snapshot.status,
                    snapshot.proof_checksum,
                    snapshot.model_dump_json(),
                ),
            )

    def upsert_section_aggregate(self, aggregate: SectionAggregate) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sec_text_sentiment_section_aggregates(
                    section_sentiment_id, run_id, entity_id, filing_accession,
                    section_id, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(section_sentiment_id) DO NOTHING
                """,
                (
                    aggregate.section_sentiment_id,
                    aggregate.run_id,
                    aggregate.entity_id,
                    aggregate.filing_accession,
                    aggregate.section_id,
                    aggregate.model_dump_json(),
                ),
            )

    def upsert_delta(self, delta: DeltaRecord, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sec_text_sentiment_deltas(
                    delta_id, run_id, entity_id, current_filing_accession,
                    prior_filing_accession, section_id, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(delta_id) DO NOTHING
                """,
                (
                    delta.delta_id,
                    run_id,
                    delta.entity_id,
                    delta.current_filing_accession,
                    delta.prior_filing_accession,
                    delta.section_id,
                    delta.model_dump_json(),
                ),
            )

    # ---- Lookup paths ---------------------------------------------------

    def lookup_by_cache_key(self, cache_key: str) -> list[SentimentObservation]:
        """Pin-6 cache hit lookup.

        Returns the full chunk set for the (filing, section, model) tuple
        keyed by ``cache_key``. Empty list means cache miss; non-empty means
        cache hit (the deterministic chunker guarantees the chunk set is
        complete for a given cache_key).
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM sec_text_sentiment_observations "
                "WHERE cache_key = ? ORDER BY chunk_id",
                (cache_key,),
            ).fetchall()
        return [
            SentimentObservation.model_validate_json(row["payload_json"])
            for row in rows
        ]

    def list_observations_for_run(
        self,
        run_id: str,
        *,
        cutoff: datetime | None = None,
    ) -> list[SentimentObservation]:
        """Pin-6 replay lookup. Returns all observations recorded under run_id.

        If ``cutoff`` is provided, the replay PIT correctness assertion (pin 5
        clause B) is enforced here: only observations with
        ``available_at <= cutoff`` are returned, period. Replay never returns
        future-available observations.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM sec_text_sentiment_observations "
                "WHERE run_id = ? ORDER BY filing_accession, section_id, chunk_id",
                (run_id,),
            ).fetchall()
        observations = [
            SentimentObservation.model_validate_json(row["payload_json"])
            for row in rows
        ]
        if cutoff is not None:
            observations = [o for o in observations if o.available_at <= cutoff]
        return observations

    def list_section_aggregates_for_run(self, run_id: str) -> list[SectionAggregate]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM sec_text_sentiment_section_aggregates "
                "WHERE run_id = ? ORDER BY filing_accession, section_id",
                (run_id,),
            ).fetchall()
        return [
            SectionAggregate.model_validate_json(row["payload_json"]) for row in rows
        ]

    def list_deltas_for_run(self, run_id: str) -> list[DeltaRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM sec_text_sentiment_deltas "
                "WHERE run_id = ? ORDER BY current_filing_accession, section_id",
                (run_id,),
            ).fetchall()
        return [DeltaRecord.model_validate_json(row["payload_json"]) for row in rows]

    def get_run(self, run_id: str) -> RunSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT snapshot_json FROM sec_text_sentiment_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return RunSnapshot.model_validate_json(row["snapshot_json"])

    def latest_prior_observations_for_section(
        self,
        *,
        entity_id: str,
        section_id: str,
        current_filing_accession: str,
        current_available_at: datetime,
    ) -> list[SentimentObservation]:
        """Return the chunk observations for the most recent prior filing
        (same entity, same section) strictly before ``current_available_at``.

        Returns [] if no prior filing is available, in which case the caller
        skips the delta record entirely.
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT filing_accession
                FROM sec_text_sentiment_observations
                WHERE entity_id = ?
                  AND section_id = ?
                  AND filing_accession != ?
                  AND available_at < ?
                ORDER BY available_at DESC
                LIMIT 1
                """,
                (
                    entity_id,
                    section_id,
                    current_filing_accession,
                    current_available_at.isoformat(),
                ),
            ).fetchone()
            if row is None:
                return []
            prior_accession = row["filing_accession"]
            rows = conn.execute(
                """
                SELECT payload_json
                FROM sec_text_sentiment_observations
                WHERE entity_id = ?
                  AND section_id = ?
                  AND filing_accession = ?
                ORDER BY chunk_id
                """,
                (entity_id, section_id, prior_accession),
            ).fetchall()
        return [
            SentimentObservation.model_validate_json(row["payload_json"])
            for row in rows
        ]

    # ---- Connection helpers --------------------------------------------

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def get_sentiment_observation_store(
    path: str | Path | None = None,
) -> SentimentObservationStore:
    return SentimentObservationStore(path)

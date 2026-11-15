"""Stage D active-scope prepopulation.

Drive-by warm-up of the sentiment cache for filings within the user's active
scope. Pin discipline:

  * Scope MUST be one of: watchlist, portfolio, saved_thesis, named_universe,
    recent_filings. Full-market scope is BLOCKED.
  * Prepopulation is a cache strategy, not a product surface. It NEVER creates
    a whole-market sentiment warehouse.
  * Silent model upgrades do NOT trigger reprocessing of historical filings.
    Bumping (model_id, model_version) requires an explicit migration job;
    Stage D refuses to backfill across model identity changes by default.

The job records its own progress against a local SQLite table that lives in
the same project store as the sentiment observations. Concurrency comes from
SQLite's row-level isolation (this is local-first; no Postgres advisory locks
needed).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal
from uuid import uuid4

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.persistence import get_sentiment_observation_store
from viza.equity.text.resolver import resolve_finance_text_sentiment
from viza.equity.text.types import (
    ParsedSection,
    ResolverFilingSelector,
    ResolverRequest,
    ResolverTarget,
)
from viza.project_store import project_store_path


ALLOWED_SCOPE_TYPES = (
    "watchlist",
    "portfolio",
    "saved_thesis",
    "named_universe",
    "recent_filings",
)


# Explicitly forbidden scope identifiers. These are the easy mistakes a future
# caller might make ("full_market", "all_us_equities", ...). Each match is
# blocked with a stable reason code so downstream tooling can surface the
# refusal.
FORBIDDEN_SCOPE_IDS = frozenset(
    {
        "full_market",
        "all_us_equities",
        "all_equities",
        "everything",
        "world",
        "*",
    }
)


class PrepopulationScopeRefused(ValueError):
    """Raised when the requested scope is forbidden by policy."""

    def __init__(self, *, code: str, scope_type: str, scope_id: str) -> None:
        super().__init__(
            f"prepopulation scope refused: code={code} type={scope_type} id={scope_id!r}"
        )
        self.code = code
        self.scope_type = scope_type
        self.scope_id = scope_id


@dataclass
class PrepopulationScope:
    """The unit of prepopulation: a named scope + the filings it covers."""

    scope_type: Literal[
        "watchlist", "portfolio", "saved_thesis", "named_universe", "recent_filings"
    ]
    scope_id: str
    parsed_sections: list[ParsedSection]


@dataclass
class PrepopulationJob:
    job_id: str
    job_type: str
    scope_type: str
    scope_id: str
    status: str
    checkpoint: dict[str, Any] = field(default_factory=dict)
    filings_total: int = 0
    filings_completed: int = 0
    filings_skipped_cached: int = 0
    filings_failed: int = 0
    model_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sec_text_sentiment_prepopulation_jobs (
  job_id                    TEXT PRIMARY KEY,
  job_type                  TEXT NOT NULL,
  scope_type                TEXT NOT NULL,
  scope_id                  TEXT NOT NULL,
  status                    TEXT NOT NULL,
  checkpoint_json           TEXT NOT NULL DEFAULT '{}',
  filings_total             INTEGER NOT NULL DEFAULT 0,
  filings_completed         INTEGER NOT NULL DEFAULT 0,
  filings_skipped_cached    INTEGER NOT NULL DEFAULT 0,
  filings_failed            INTEGER NOT NULL DEFAULT 0,
  model_metadata_json       TEXT NOT NULL DEFAULT '{}',
  created_at                TEXT NOT NULL,
  updated_at                TEXT NOT NULL
);
"""


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)
    return connection


def validate_scope(scope_type: str, scope_id: str) -> None:
    """Enforce scope policy. Raises PrepopulationScopeRefused on rejection."""
    if scope_type not in ALLOWED_SCOPE_TYPES:
        raise PrepopulationScopeRefused(
            code="scope_type_not_allowed",
            scope_type=scope_type,
            scope_id=scope_id,
        )
    normalized = scope_id.strip().lower()
    if normalized in FORBIDDEN_SCOPE_IDS:
        raise PrepopulationScopeRefused(
            code="full_market_scope_blocked",
            scope_type=scope_type,
            scope_id=scope_id,
        )
    if not scope_id.strip():
        raise PrepopulationScopeRefused(
            code="empty_scope_id",
            scope_type=scope_type,
            scope_id=scope_id,
        )


def prepopulate(
    scope: PrepopulationScope,
    *,
    config: EquityTextConfig | None = None,
    store_path: str | Path | None = None,
    now: datetime | None = None,
) -> PrepopulationJob:
    """Synchronously prepopulate the cache for every filing in the scope.

    This is the simplest possible worker: it iterates parsed_sections,
    issues compute_only resolver calls, and records counters. A future
    enhancement can split this across worker processes using the same
    SQLite-backed job state.
    """
    validate_scope(scope.scope_type, scope.scope_id)
    active = config or EquityTextConfig.from_env()
    if not active.text_prepopulation_enabled:
        raise PermissionError(
            "prepopulation is disabled; set VIZA_EQUITY_TEXT_PREPOPULATION_ENABLED=true"
        )

    current_time = now or datetime.now(timezone.utc)
    db_path = Path(store_path) if store_path else project_store_path()
    job_id = str(uuid4())
    job = PrepopulationJob(
        job_id=job_id,
        job_type="equity_text_sentiment_prepopulation",
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        status="running",
        filings_total=len(scope.parsed_sections),
        created_at=current_time.isoformat(),
        updated_at=current_time.isoformat(),
    )
    _persist_job(db_path, job)

    sentiment_store = get_sentiment_observation_store(db_path)

    for section in scope.parsed_sections:
        try:
            response = resolve_finance_text_sentiment(
                ResolverRequest(
                    target=ResolverTarget(cik=section.cik),
                    filing=ResolverFilingSelector(accession=section.filing_accession),
                    sections=[section.section_id],  # type: ignore[list-item]
                    cache_policy="serve_or_compute",
                    analysis_mode="live_current",
                    package_mode="output_only",
                    persist_run=True,
                    mock_parsed_sections=[section],
                ),
                config=active,
                store=sentiment_store,
                now=current_time,
            )
            if response.source == "cache":
                job.filings_skipped_cached += 1
            else:
                job.filings_completed += 1
            if response.model_metadata and not job.model_metadata:
                job.model_metadata = response.model_metadata
        except Exception:  # pragma: no cover — defensive; failures are recorded
            job.filings_failed += 1

    job.status = "completed" if job.filings_failed == 0 else "completed_with_failures"
    job.updated_at = datetime.now(timezone.utc).isoformat()
    _persist_job(db_path, job)
    return job


def get_job(job_id: str, *, store_path: str | Path | None = None) -> PrepopulationJob | None:
    db_path = Path(store_path) if store_path else project_store_path()
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM sec_text_sentiment_prepopulation_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    if row is None:
        return None
    return PrepopulationJob(
        job_id=row["job_id"],
        job_type=row["job_type"],
        scope_type=row["scope_type"],
        scope_id=row["scope_id"],
        status=row["status"],
        checkpoint=_json_load(row["checkpoint_json"]),
        filings_total=row["filings_total"],
        filings_completed=row["filings_completed"],
        filings_skipped_cached=row["filings_skipped_cached"],
        filings_failed=row["filings_failed"],
        model_metadata=_json_load(row["model_metadata_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _persist_job(db_path: Path, job: PrepopulationJob) -> None:
    import json

    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sec_text_sentiment_prepopulation_jobs(
                job_id, job_type, scope_type, scope_id, status, checkpoint_json,
                filings_total, filings_completed, filings_skipped_cached,
                filings_failed, model_metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                status = excluded.status,
                checkpoint_json = excluded.checkpoint_json,
                filings_total = excluded.filings_total,
                filings_completed = excluded.filings_completed,
                filings_skipped_cached = excluded.filings_skipped_cached,
                filings_failed = excluded.filings_failed,
                model_metadata_json = excluded.model_metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                job.job_id,
                job.job_type,
                job.scope_type,
                job.scope_id,
                job.status,
                json.dumps(job.checkpoint),
                job.filings_total,
                job.filings_completed,
                job.filings_skipped_cached,
                job.filings_failed,
                json.dumps(job.model_metadata),
                job.created_at,
                job.updated_at,
            ),
        )


def _json_load(value: str | None) -> dict:
    import json

    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}

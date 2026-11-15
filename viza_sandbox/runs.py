"""Run orchestration: materialize -> run -> evaluate -> persist."""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pydantic import BaseModel, Field, model_validator

from viza_sandbox.canonical import CanonicalSource
from viza_sandbox.config import SandboxSettings
from viza_sandbox.evaluate import (
    EXECUTION_CONVENTION,
    BacktestSettings,
    EvaluationError,
    evaluate_scores,
)
from viza_sandbox.materialize import MaterializationError, PanelSpec, materialize
from viza_sandbox.runner import Runner, RunLimits
from viza_sandbox.sdk import VizaData
from viza_sandbox.store import SandboxRun, SandboxStore, SandboxUser


class RunRequest(BaseModel):
    code: str = Field(min_length=1)
    start: date
    end: date
    backtest: BacktestSettings

    @model_validator(mode="after")
    def _end_not_before_start(self) -> RunRequest:
        if self.end < self.start:
            raise ValueError("end must be on or after start")
        return self


_JSON_OUTPUT_MAX_BYTES = 1024 * 1024
_RESULT_COLUMNS = ["event_date", "security_id", "score"]


class _OutputRefused(Exception):
    """A run output file the host refuses to read; the message is shown to the user."""


def _check_output_file(path: Path, label: str, max_bytes: int) -> None:
    """Refuse links, non-regular files and oversized files before the host reads ``path``."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise _OutputRefused(f"{label} is missing.") from None
    if path.is_symlink() or path.is_junction() or not stat.S_ISREG(info.st_mode):
        raise _OutputRefused(f"{label} is not a regular file.")
    if info.st_size > max_bytes:
        raise _OutputRefused(f"{label} exceeds the size limit.")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _link_or_copy_panel(panel_dir: Path, link: Path) -> None:
    """Expose the shared panel at ``link`` without ever writing into or deleting the panel."""
    target = panel_dir.resolve()
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if sys.platform == "win32":
        try:
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
            return
        except OSError:
            pass
    shutil.copytree(target, link)


class SandboxService:
    def __init__(
        self,
        settings: SandboxSettings,
        store: SandboxStore,
        source: CanonicalSource,
        runner: Runner,
    ) -> None:
        self._settings = settings
        self._store = store
        self._source = source
        self._runner = runner

    def _limits(self) -> RunLimits:
        return RunLimits(
            wall_clock_seconds=self._settings.wall_clock_seconds,
            memory_gb=self._settings.memory_gb,
            cpus=self._settings.cpus,
        )

    def submit(self, user: SandboxUser, request: RunRequest) -> SandboxRun:
        return self._store.create_run(
            user.user_id,
            request.code,
            request.model_dump(mode="json"),
            self._limits().model_dump(),
        )

    def execute(self, run_id: str) -> SandboxRun:
        try:
            return self._execute(run_id)
        except Exception as exc:  # noqa: BLE001 - never leave a run stuck in "running"
            # Only failures before the runner returns reach here; str(exc) may expose host paths.
            message = (
                str(exc)
                if isinstance(exc, MaterializationError)
                else f"{type(exc).__name__}: could not prepare run."
            )
            return self._store.update_run(
                run_id, status="failed", error=message, finished_at=_utcnow()
            )

    def _execute(self, run_id: str) -> SandboxRun:
        run = self._store.update_run(run_id, status="running", started_at=_utcnow())
        request = RunRequest.model_validate(run.request)
        limits = RunLimits.model_validate(run.limits)

        panel = materialize(
            self._source, PanelSpec(start=request.start, end=request.end), self._settings
        )
        run_dir = (self._settings.runs_dir / run_id).resolve()
        (run_dir / "out").mkdir(parents=True, exist_ok=True)
        (run_dir / "strategy.py").write_text(run.code_text, encoding="utf-8")
        _link_or_copy_panel(panel.directory, run_dir / "data")

        outcome = self._runner.run(run_dir, limits)
        fields: dict = {
            "data_manifest": panel.manifest.model_dump(mode="json"),
            "exit_code": outcome.exit_code,
            "stdout": outcome.stdout,
            "stderr": outcome.stderr,
            "finished_at": _utcnow(),
        }
        out_dir = run_dir / "out"
        try:
            fields.update(self._post_process(outcome, out_dir, panel, request, limits))
        except _OutputRefused as exc:
            fields.update(status="failed", error=str(exc))
        except Exception as exc:  # noqa: BLE001 - outcome fields above must always persist
            fields.update(
                status="failed", error=f"{type(exc).__name__}: could not process run output."
            )
        return self._store.update_run(run_id, **fields)

    def _post_process(
        self, outcome, out_dir: Path, panel, request: RunRequest, limits: RunLimits
    ):
        if outcome.timed_out:
            return {
                "status": "timed_out",
                "error": f"Timed out after {limits.wall_clock_seconds} seconds.",
            }
        if outcome.exit_code != 0:
            error_path = out_dir / "error.json"
            if os.path.lexists(error_path):
                _check_output_file(error_path, "Error file", _JSON_OUTPUT_MAX_BYTES)
                info = json.loads(error_path.read_text(encoding="utf-8"))
                message = f"{info['type']}: {info['message']}"
            else:
                message = f"Run exited with code {outcome.exit_code}."
            return {"status": "failed", "error": message}
        result_path = out_dir / "result.parquet"
        _check_output_file(result_path, "Result file", self._settings.max_result_bytes)
        if pq.read_schema(result_path).names != _RESULT_COLUMNS:
            raise _OutputRefused(
                "Result file must have exactly the columns event_date, security_id, score."
            )
        try:
            long = pd.read_parquet(result_path, engine="pyarrow")
            wide = long.pivot(index="event_date", columns="security_id", values="score")
            wide.index = pd.to_datetime(wide.index)
            close = VizaData(panel.directory).prices("close")
            evaluation = evaluate_scores(wide, close, request.backtest)
        except EvaluationError as exc:
            return {"status": "failed", "error": str(exc)}
        return {
            "status": "completed",
            "evaluation": evaluation.model_dump(mode="json"),
            "result_kind": "scores",
            "result_path": str(out_dir / "result.parquet"),
        }

    def result_header(self, run: SandboxRun) -> dict:
        return result_header(run, self._settings)


def result_header(run: SandboxRun, settings: SandboxSettings | None = None) -> dict:
    settings = settings or SandboxSettings()
    return {
        "run_id": run.run_id,
        "code_hash": run.code_hash,
        "status": run.status,
        "data_manifest": run.data_manifest,
        "limits": run.limits,
        "execution": dict(EXECUTION_CONVENTION),
        "source_rights_state": settings.source_rights_state,
        "price_adjustment_status": settings.price_adjustment_status,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }

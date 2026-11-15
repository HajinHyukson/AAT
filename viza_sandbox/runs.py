"""Run orchestration: materialize -> run -> evaluate -> persist."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field, model_validator

from viza_sandbox.canonical import CanonicalSource
from viza_sandbox.config import SandboxSettings
from viza_sandbox.evaluate import (
    EXECUTION_CONVENTION,
    BacktestSettings,
    EvaluationError,
    evaluate_scores,
)
from viza_sandbox.materialize import PanelSpec, materialize
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
            return self._store.update_run(
                run_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                finished_at=_utcnow(),
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
        if outcome.timed_out:
            fields.update(
                status="timed_out",
                error=f"Timed out after {limits.wall_clock_seconds} seconds.",
            )
        elif outcome.exit_code != 0:
            error_path = out_dir / "error.json"
            if error_path.exists():
                info = json.loads(error_path.read_text(encoding="utf-8"))
                message = f"{info['type']}: {info['message']}"
            else:
                message = f"Run exited with code {outcome.exit_code}."
            fields.update(status="failed", error=message)
        else:
            try:
                long = pd.read_parquet(out_dir / "result.parquet", engine="pyarrow")
                wide = long.pivot(index="event_date", columns="security_id", values="score")
                wide.index = pd.to_datetime(wide.index)
                close = VizaData(panel.directory).prices("close")
                evaluation = evaluate_scores(wide, close, request.backtest)
            except EvaluationError as exc:
                fields.update(status="failed", error=str(exc))
            else:
                fields.update(
                    status="completed",
                    evaluation=evaluation.model_dump(mode="json"),
                    result_kind="scores",
                    result_path=str(out_dir / "result.parquet"),
                )
        return self._store.update_run(run_id, **fields)

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

"""Runners that execute a prepared run directory under resource limits."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

import viza_sandbox

_OUTPUT_CAP = 65536
_REPO_ROOT = Path(viza_sandbox.__file__).resolve().parents[1]


class RunLimits(BaseModel):
    wall_clock_seconds: int = 600
    memory_gb: int = 8
    cpus: int = 2


class RunOutcome(BaseModel):
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    duration_seconds: float


class Runner(Protocol):
    def run(self, run_dir: Path, limits: RunLimits) -> RunOutcome: ...


def _tail(text: str | bytes | None) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text[-_OUTPUT_CAP:]


def _run(cmd: list[str], limits: RunLimits, **kwargs) -> tuple[RunOutcome, bool]:
    """Run ``cmd``; ``subprocess.run`` kills and reaps the child on timeout."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=limits.wall_clock_seconds, **kwargs,
        )
        exit_code, stdout, stderr, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        exit_code, stdout, stderr, timed_out = None, exc.stdout, exc.stderr, True
    outcome = RunOutcome(
        exit_code=exit_code,
        timed_out=timed_out,
        stdout=_tail(stdout),
        stderr=_tail(stderr),
        duration_seconds=time.monotonic() - start,
    )
    return outcome, timed_out


class LocalProcessRunner:
    def run(self, run_dir: Path, limits: RunLimits) -> RunOutcome:
        run_dir = Path(run_dir)
        env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT)}
        cmd = [sys.executable, "-m", "viza_sandbox.runner_entry", str(run_dir)]
        outcome, _ = _run(cmd, limits, cwd=run_dir, env=env)
        return outcome


class DockerRunner:
    def __init__(self, image: str) -> None:
        self.image = image

    def run(self, run_dir: Path, limits: RunLimits) -> RunOutcome:
        run_dir = Path(run_dir).resolve()
        name = f"viza-run-{uuid.uuid4().hex}"
        cmd = [
            "docker", "run", "--rm", "--name", name, "--network", "none",
            "--memory", f"{limits.memory_gb}g", "--cpus", str(limits.cpus),
            "--read-only", "--tmpfs", "/tmp",
            "-v", f"{run_dir / 'strategy.py'}:/run/strategy.py:ro",
            "-v", f"{run_dir / 'data'}:/run/data:ro",
            "-v", f"{run_dir / 'out'}:/run/out:rw",
            self.image, "python", "-m", "viza_sandbox.runner_entry", "/run",
        ]
        outcome, timed_out = _run(cmd, limits)
        if timed_out:
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=30, check=False)
        return outcome


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        probe = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0

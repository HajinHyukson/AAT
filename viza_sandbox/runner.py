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


# Child output is streamed to these files beside out/, never buffered in the host process.
# They sit in the run directory itself, which is not mounted into the container.
STDOUT_FILENAME = "stdout.log"
STDERR_FILENAME = "stderr.log"


def _tail(text: str | bytes | None) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text[-_OUTPUT_CAP:]


def _read_tail(path: Path) -> str:
    """Last ``_OUTPUT_CAP`` characters of ``path``, reading at most 4 bytes per character."""
    try:
        with open(path, "rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            handle.seek(max(0, size - 4 * _OUTPUT_CAP))
            data = handle.read()
    except OSError:
        return ""
    return _tail(data)


def _run(cmd: list[str], limits: RunLimits, log_dir: Path, **kwargs) -> tuple[RunOutcome, bool]:
    """Run ``cmd`` with output to files in ``log_dir``; the child is killed on timeout."""
    stdout_path, stderr_path = log_dir / STDOUT_FILENAME, log_dir / STDERR_FILENAME
    start = time.monotonic()
    with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
        try:
            proc = subprocess.run(
                cmd, stdout=out, stderr=err, timeout=limits.wall_clock_seconds, **kwargs
            )
            exit_code, timed_out = proc.returncode, False
        except subprocess.TimeoutExpired:
            exit_code, timed_out = None, True
    outcome = RunOutcome(
        exit_code=exit_code,
        timed_out=timed_out,
        stdout=_read_tail(stdout_path),
        stderr=_read_tail(stderr_path),
        duration_seconds=time.monotonic() - start,
    )
    return outcome, timed_out


class LocalProcessRunner:
    def run(self, run_dir: Path, limits: RunLimits) -> RunOutcome:
        run_dir = Path(run_dir)
        env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT)}
        cmd = [sys.executable, "-m", "viza_sandbox.runner_entry", str(run_dir)]
        outcome, _ = _run(cmd, limits, run_dir, cwd=run_dir, env=env)
        return outcome


class DockerRunner:
    def __init__(self, image: str) -> None:
        self.image = image

    def _command(self, run_dir: Path, limits: RunLimits, name: str) -> list[str]:
        run_dir = Path(run_dir).resolve()
        cmd = [
            "docker", "run", "--rm", "--name", name, "--network", "none",
            "--memory", f"{limits.memory_gb}g", "--memory-swap", f"{limits.memory_gb}g",
            "--cpus", str(limits.cpus), "--pids-limit", "256",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", "/tmp",
        ]
        if hasattr(os, "getuid"):
            # Match the host owner of out/ so the non-root container can write to it.
            cmd += ["--user", f"{os.getuid()}:{os.getgid()}"]
        cmd += [
            "-v", f"{run_dir / 'strategy.py'}:/run/strategy.py:ro",
            # The data entry is a symlink or junction to the shared panel; mount its target.
            "-v", f"{(run_dir / 'data').resolve()}:/run/data:ro",
            "-v", f"{run_dir / 'out'}:/run/out:rw",
            self.image, "python", "-m", "viza_sandbox.runner_entry", "/run",
        ]
        return cmd

    def run(self, run_dir: Path, limits: RunLimits) -> RunOutcome:
        name = f"viza-run-{uuid.uuid4().hex}"
        cmd = self._command(run_dir, limits, name)
        outcome, timed_out = _run(cmd, limits, Path(run_dir))
        if timed_out:
            try:
                subprocess.run(
                    ["docker", "kill", name], capture_output=True, timeout=30, check=False
                )
            except (OSError, subprocess.SubprocessError):
                pass  # a hung or missing daemon must not hide the timed-out outcome
        return outcome


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        probe = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0

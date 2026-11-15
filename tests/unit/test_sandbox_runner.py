import json
import os
import shutil

import pytest
from sandbox_helpers import make_panel as _panel

from viza_sandbox.runner import DockerRunner, LocalProcessRunner, RunLimits, docker_available


def _run_dir(tmp_path, code):
    rd = tmp_path / "run"
    (rd / "out").mkdir(parents=True)
    shutil.copytree(_panel(tmp_path / "src"), rd / "data")
    (rd / "strategy.py").write_text(code)
    return rd


MOMENTUM = """
from viza_sandbox.sdk import scores
def strategy(data):
    close = data.prices("close")
    return scores(close.pct_change())
"""


def test_local_runner_writes_scores(tmp_path):
    rd = _run_dir(tmp_path, MOMENTUM)
    out = LocalProcessRunner().run(rd, RunLimits(wall_clock_seconds=120))
    assert out.exit_code == 0 and not out.timed_out
    assert json.loads((rd / "out" / "result.json").read_text())["kind"] == "scores"
    assert (rd / "out" / "result.parquet").exists()


def test_local_runner_reports_declaration_error(tmp_path):
    rd = _run_dir(tmp_path, "def strategy(data):\n    return data.prices('close')\n")
    out = LocalProcessRunner().run(rd, RunLimits(wall_clock_seconds=120))
    assert out.exit_code == 1
    err = json.loads((rd / "out" / "error.json").read_text())
    assert err["type"] == "ReturnDeclarationError" and "viza.scores(df)" in err["message"]


def test_local_runner_times_out(tmp_path):
    rd = _run_dir(tmp_path, "import time\ndef strategy(data):\n    time.sleep(30)\n")
    out = LocalProcessRunner().run(rd, RunLimits(wall_clock_seconds=2))
    assert out.timed_out and out.exit_code is None


def test_local_runner_captures_stdout(tmp_path):
    rd = _run_dir(
        tmp_path,
        "from viza_sandbox.sdk import scores\n"
        "def strategy(data):\n"
        "    print('hello from user')\n"
        "    return scores(data.prices('close'))\n",
    )
    out = LocalProcessRunner().run(rd, RunLimits(wall_clock_seconds=120))
    assert "hello from user" in out.stdout


@pytest.mark.skipif(not docker_available(), reason="docker not available")
def test_docker_runner_blocks_network(tmp_path):
    rd = _run_dir(
        tmp_path,
        "import socket\n"
        "from viza_sandbox.sdk import scores\n"
        "def strategy(data):\n"
        "    try:\n"
        "        socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
        "        raise SystemExit(7)\n"
        "    except OSError:\n"
        "        return scores(data.prices('close'))\n",
    )
    out = DockerRunner("viza-sandbox-runtime:latest").run(rd, RunLimits(wall_clock_seconds=120))
    assert out.exit_code == 0, out.stderr


def _docker_cmd(tmp_path):
    return DockerRunner("img:1")._command(tmp_path, RunLimits(), "viza-run-x")


def test_docker_command_runs_as_host_uid(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "getuid", lambda: 1234, raising=False)
    monkeypatch.setattr(os, "getgid", lambda: 5678, raising=False)
    cmd = _docker_cmd(tmp_path)
    assert cmd[cmd.index("--user") + 1] == "1234:5678"
    assert cmd.index("--user") < cmd.index("img:1")


def test_docker_command_has_no_user_flag_without_getuid(tmp_path, monkeypatch):
    monkeypatch.delattr(os, "getuid", raising=False)
    assert "--user" not in _docker_cmd(tmp_path)


def test_local_runner_streams_output_to_host_files_and_keeps_tail(tmp_path):
    rd = _run_dir(
        tmp_path,
        "import sys\n"
        "from viza_sandbox.sdk import scores\n"
        "def strategy(data):\n"
        "    sys.stdout.write('x' * 200000 + 'END-OUT')\n"
        "    sys.stderr.write('y' * 200000 + 'END-ERR')\n"
        "    return scores(data.prices('close'))\n",
    )
    out = LocalProcessRunner().run(rd, RunLimits(wall_clock_seconds=120))
    assert out.exit_code == 0
    assert len(out.stdout) == 65536 and out.stdout.endswith("END-OUT")
    assert len(out.stderr) == 65536 and out.stderr.endswith("END-ERR")
    assert (rd / "stdout.log").stat().st_size >= 200000
    assert (rd / "stderr.log").stat().st_size >= 200000
    assert not (rd / "out" / "stdout.log").exists()


def test_docker_command_hardening_flags(tmp_path):
    cmd = _docker_cmd(tmp_path)
    image_at = cmd.index("img:1")
    assert cmd[cmd.index("--pids-limit") + 1] == "256"
    assert cmd[cmd.index("--cap-drop") + 1] == "ALL"
    assert cmd[cmd.index("--security-opt") + 1] == "no-new-privileges"
    assert cmd[cmd.index("--memory-swap") + 1] == cmd[cmd.index("--memory") + 1] == "8g"
    for flag in ("--pids-limit", "--cap-drop", "--security-opt", "--memory-swap"):
        assert cmd.index(flag) < image_at


def test_docker_command_mounts_resolved_data_target(tmp_path):
    from viza_sandbox.runs import _link_or_copy_panel

    panel = _panel(tmp_path / "src")
    rd = tmp_path / "run"
    (rd / "out").mkdir(parents=True)
    _link_or_copy_panel(panel, rd / "data")
    if (rd / "data").resolve() == (rd / "data").absolute():
        pytest.skip("no symlink or junction support; data was copied")
    cmd = _docker_cmd(rd)
    assert f"{panel.resolve()}:/run/data:ro" in cmd


def test_docker_run_survives_failing_kill_after_timeout(tmp_path, monkeypatch):
    import subprocess

    import viza_sandbox.runner as runner_mod

    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["docker", "kill"]:
            raise FileNotFoundError("docker")
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

    monkeypatch.setattr(runner_mod.subprocess, "run", fake_run)
    rd = tmp_path / "run"
    (rd / "out").mkdir(parents=True)
    out = DockerRunner("img:1").run(rd, RunLimits(wall_clock_seconds=1))
    assert out.timed_out and out.exit_code is None
    assert calls[-1][:2] == ["docker", "kill"]

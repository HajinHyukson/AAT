import json
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

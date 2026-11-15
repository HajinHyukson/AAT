"""In-process entrypoint: run ``strategy.py`` against the panel and write its result."""

from __future__ import annotations

import importlib.util
import json
import sys
import traceback
from pathlib import Path

from viza_sandbox.sdk import VizaData, coerce_return


def _write_error(out_dir: Path, exc: BaseException) -> None:
    (out_dir / "error.json").write_text(json.dumps({
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(exc)),
    }))


def _load_strategy(run_dir: Path):
    spec = importlib.util.spec_from_file_location("user_strategy", run_dir / "strategy.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["user_strategy"] = module
    spec.loader.exec_module(module)
    fn = getattr(module, "strategy", None)
    if not callable(fn):
        raise TypeError("strategy.py must define a callable named 'strategy'.")
    return fn


def main(argv: list[str]) -> int:
    run_dir = Path(argv[0])
    out_dir = run_dir / "out"
    try:
        strategy = _load_strategy(run_dir)
        result = coerce_return(strategy(VizaData(run_dir / "data")))
        long = result.frame.stack().reset_index()
        long.columns = ["event_date", "security_id", "score"]
        long = long.dropna(subset=["score"])
        long.to_parquet(out_dir / "result.parquet", engine="pyarrow", index=False)
        (out_dir / "result.json").write_text(json.dumps({
            "kind": "scores",
            "rows": int(len(long)),
            "securities": int(long["security_id"].nunique()),
            "dates": int(long["event_date"].nunique()),
        }))
        return 0
    except Exception as exc:  # noqa: BLE001 - every user failure is reported, not raised
        _write_error(out_dir, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

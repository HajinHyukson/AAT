from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from db import models
from db.session import session_scope
from engine.attribution.diagnostics import configured_share_stability_threshold_bps, is_share_stable
from jobs.pilot_sp500_common import PILOT_UNIVERSE_NAME, assert_pilot_database_url
from jobs.run_attribution import (
    HIERARCHICAL_BASELINE_MODEL_VERSION,
    RESIDUAL_SAFETY_MODEL_VERSION,
)


LEGACY_MODEL_VERSION = "factor-baseline-v0"
MODEL_VERSION_BY_METHODOLOGY = {
    "legacy": LEGACY_MODEL_VERSION,
    "residual_safety_v1": RESIDUAL_SAFETY_MODEL_VERSION,
    "hierarchical_market_first_v1": HIERARCHICAL_BASELINE_MODEL_VERSION,
}


@dataclass
class MethodologyMetrics:
    methodology: str
    model_version: str
    runs: int
    stable_runs: int
    stable_share_coverage: float
    residual_mae_bps: float | None
    residual_rmse_bps: float | None
    weighted_abs_residual_share: float | None
    gross_leverage_p95: float | None
    residual_leverage_p95: float | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate pilot attribution methodology quality")
    parser.add_argument("--methodologies", nargs="+", default=list(MODEL_VERSION_BY_METHODOLOGY))
    parser.add_argument("--output-dir", default="data/processed/pilot_sp500")
    args = parser.parse_args()

    metrics = evaluate_pilot_methodologies(methodologies=tuple(args.methodologies))
    output_path = write_metrics(metrics=metrics, output_dir=Path(args.output_dir))
    print(f"wrote pilot methodology metrics to {output_path}")
    for item in metrics:
        print(
            f"{item.methodology}: runs={item.runs} stable={item.stable_runs} "
            f"residual_mae_bps={item.residual_mae_bps} weighted_abs_residual_share={item.weighted_abs_residual_share}"
        )


def evaluate_pilot_methodologies(*, methodologies: tuple[str, ...]) -> list[MethodologyMetrics]:
    assert_pilot_database_url()
    metrics = []
    with session_scope() as session:
        for methodology in methodologies:
            if methodology not in MODEL_VERSION_BY_METHODOLOGY:
                raise ValueError(f"unknown pilot methodology {methodology}")
            model_version = MODEL_VERSION_BY_METHODOLOGY[methodology]
            runs = list(
                session.execute(
                    select(models.AttributionRun)
                    .join(models.ModelUniverseMember, models.ModelUniverseMember.security_id == models.AttributionRun.security_id)
                    .where(models.ModelUniverseMember.universe_name == PILOT_UNIVERSE_NAME)
                    .where(models.AttributionRun.model_version == model_version)
                ).scalars()
            )
            contributions = load_contributions_by_run(session=session, runs=runs)
            metrics.append(build_metrics(methodology=methodology, model_version=model_version, runs=runs, contributions=contributions))
    return metrics


def load_contributions_by_run(*, session, runs: list[models.AttributionRun]) -> dict:
    if not runs:
        return {}
    run_ids = [run.attribution_run_id for run in runs]
    rows = session.execute(
        select(models.AttributionContribution).where(models.AttributionContribution.attribution_run_id.in_(run_ids))
    ).scalars()
    grouped = {}
    for row in rows:
        grouped.setdefault(row.attribution_run_id, []).append(row)
    return grouped


def build_metrics(*, methodology: str, model_version: str, runs: list[models.AttributionRun], contributions: dict) -> MethodologyMetrics:
    threshold = configured_share_stability_threshold_bps()
    stable_runs = [run for run in runs if is_share_stable(float(run.observed_return_bps), threshold)]
    residuals = [float(run.unexplained_residual_bps) for run in runs]
    stable_residuals = [float(run.unexplained_residual_bps) for run in stable_runs]
    stable_observed = [abs(float(run.observed_return_bps)) for run in stable_runs]
    gross_leverages = []
    residual_leverages = []
    for run in runs:
        denominator = max(abs(float(run.observed_return_bps)), threshold)
        rows = contributions.get(run.attribution_run_id, [])
        gross = sum(abs(float(row.contribution_bps)) for row in rows if row.driver != "unexplained_residual")
        gross_leverages.append(gross / denominator)
        residual_leverages.append(abs(float(run.unexplained_residual_bps)) / denominator)
    return MethodologyMetrics(
        methodology=methodology,
        model_version=model_version,
        runs=len(runs),
        stable_runs=len(stable_runs),
        stable_share_coverage=len(stable_runs) / len(runs) if runs else 0.0,
        residual_mae_bps=mean_abs(residuals),
        residual_rmse_bps=rmse(residuals),
        weighted_abs_residual_share=(
            sum(abs(value) for value in stable_residuals) / sum(stable_observed)
            if stable_observed and sum(stable_observed) > 0
            else None
        ),
        gross_leverage_p95=percentile(gross_leverages, 0.95),
        residual_leverage_p95=percentile(residual_leverages, 0.95),
    )


def write_metrics(*, metrics: list[MethodologyMetrics], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"methodology_metrics_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps([asdict(item) for item in metrics], indent=2) + "\n", encoding="utf-8")
    return path


def mean_abs(values: list[float]) -> float | None:
    return sum(abs(value) for value in values) / len(values) if values else None


def rmse(values: list[float]) -> float | None:
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[index]


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from db import models
from db.session import session_scope
from engine.audit.replay import evidence_payload_is_visible


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay persisted attribution runs for look-ahead leakage")
    parser.add_argument("--days", type=int, default=252)
    parser.add_argument("--prefer-compose-port", action="store_true")
    args = parser.parse_args()

    checked = run_replay_lookahead_audit(
        days=args.days,
        prefer_compose_port=args.prefer_compose_port,
    )
    print(f"replay look-ahead audit passed; checked {checked} contribution(s)")


def run_replay_lookahead_audit(*, days: int = 252, prefer_compose_port: bool = False) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=days * 2)
    failures: list[str] = []
    checked = 0
    with session_scope(prefer_compose_port=prefer_compose_port) as session:
        runs = session.execute(
            select(models.AttributionRun)
            .where(models.AttributionRun.window_end >= since)
            .order_by(models.AttributionRun.window_end.desc())
        ).scalars()
        for run in runs:
            contributions = session.execute(
                select(models.AttributionContribution)
                .where(models.AttributionContribution.attribution_run_id == run.attribution_run_id)
            ).scalars()
            for contribution in contributions:
                checked += 1
                if not evidence_payload_is_visible(
                    evidence_payload=contribution.evidence_payload,
                    attribution_cutoff=run.attribution_cutoff,
                ):
                    failures.append(
                        f"{run.attribution_run_id}:{contribution.attribution_contribution_id}"
                    )
    if failures:
        raise RuntimeError(f"look-ahead replay audit failed for {len(failures)} contribution(s): {failures[:10]}")
    return checked


if __name__ == "__main__":
    main()

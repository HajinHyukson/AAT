"""Daily refresh chain for the local KOSPI pilot.

Runs after KRX close once the Acquin database has written its post-close rows
(~07:22 UTC / 16:22 KST):

1. Incremental staging import from the Acquin database.
2. Promotion (entities, prices behind the continuity guard, index factor).
3. Attribution for the trailing window across the pilot universe; completed
   windows are skipped, so the daily cost is one new window per ticker/cadence.
4. Frontend summary refresh for the `pilot_kospi_static` universe.

Each step is idempotent; rerunning after a partial failure resumes safely.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from db.session import session_scope
from jobs.import_acquin_snapshot import DEFAULT_BATCH_SIZE, import_acquin_snapshot
from jobs.pilot_kospi_common import (
    DEFAULT_KOSPI_CONFIG,
    PILOT_KOSPI_UNIVERSE_NAME,
    ensure_pilot_kospi_database_url,
    load_kospi_universe_config,
)
from jobs.promote_acquin_data import promote_acquin_data
from jobs.refresh_attribution_summaries import refresh_attribution_summaries
from jobs.run_pilot_kospi_attribution import run_pilot_kospi_attribution


VALID_CADENCES = ("daily", "weekly", "monthly")
# Must exceed one monthly window plus holiday slack: the attribution runner
# drops windows that start before the analysis range.
DEFAULT_ATTRIBUTION_DAYS = 45


@dataclass
class PilotKospiDailyReport:
    imported_rows: int = 0
    bars_promoted: int = 0
    quarantined_bars: int = 0
    new_continuity_suspects: list[str] = field(default_factory=list)
    ran_windows: int = 0
    skipped_windows: int = 0
    already_completed_windows: int = 0
    summaries_refreshed: int = 0
    summaries_available: int = 0

    def render(self) -> str:
        return (
            "pilot KOSPI daily refresh report\n"
            f"  imported_rows={self.imported_rows}\n"
            f"  bars_promoted={self.bars_promoted}\n"
            f"  quarantined_bars={self.quarantined_bars}\n"
            f"  new_continuity_suspects={self.new_continuity_suspects}\n"
            f"  ran_windows={self.ran_windows}\n"
            f"  skipped_windows={self.skipped_windows}\n"
            f"  already_completed_windows={self.already_completed_windows}\n"
            f"  summaries_refreshed={self.summaries_refreshed}\n"
            f"  summaries_available={self.summaries_available}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the daily KOSPI pilot refresh chain")
    parser.add_argument("--config", default=str(DEFAULT_KOSPI_CONFIG))
    parser.add_argument("--attribution-days", type=int, default=DEFAULT_ATTRIBUTION_DAYS)
    parser.add_argument("--cadences", nargs="+", choices=VALID_CADENCES, default=list(VALID_CADENCES))
    parser.add_argument("--lookback-days", type=int, default=252)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--skip-import", action="store_true", help="Reuse already-staged rows")
    args = parser.parse_args()

    report = run_pilot_kospi_daily(
        config_path=Path(args.config),
        attribution_days=args.attribution_days,
        cadences=tuple(args.cadences),
        lookback_days=args.lookback_days,
        batch_size=args.batch_size,
        skip_import=args.skip_import,
    )
    print(report.render())
    if report.new_continuity_suspects:
        print(
            "WARNING: new continuity suspects quarantined; review acquin_validation_issue "
            "rows and resolve or re-import the affected tickers.",
            file=sys.stderr,
        )


def run_pilot_kospi_daily(
    *,
    config_path: Path = DEFAULT_KOSPI_CONFIG,
    attribution_days: int = DEFAULT_ATTRIBUTION_DAYS,
    cadences: tuple[str, ...] = VALID_CADENCES,
    lookback_days: int = 252,
    batch_size: int = DEFAULT_BATCH_SIZE,
    skip_import: bool = False,
    today: date | None = None,
) -> PilotKospiDailyReport:
    ensure_pilot_kospi_database_url()
    report = PilotKospiDailyReport()
    analysis_end = today or date.today()

    if not skip_import:
        import_report = import_acquin_snapshot(batch_size=batch_size)
        report.imported_rows = sum(import_report.imported_counts.values())

    promotion_report = promote_acquin_data(config_path=config_path)
    report.bars_promoted = promotion_report.bars_promoted
    report.quarantined_bars = promotion_report.quarantined_bars
    report.new_continuity_suspects = list(promotion_report.continuity_suspects)

    attribution_report = run_pilot_kospi_attribution(
        config_path=config_path,
        tickers=None,
        start=analysis_end - timedelta(days=attribution_days),
        end=analysis_end,
        cadences=cadences,
        lookback_days=lookback_days,
    )
    report.ran_windows = attribution_report.ran_windows
    report.skipped_windows = attribution_report.skipped_windows
    report.already_completed_windows = attribution_report.already_completed_windows

    universe_version = str(load_kospi_universe_config(config_path)["version"])
    with session_scope() as session:
        summary_report = refresh_attribution_summaries(
            session=session,
            universe_name=PILOT_KOSPI_UNIVERSE_NAME,
            universe_version=universe_version,
        )
    report.summaries_refreshed = summary_report.refreshed
    report.summaries_available = summary_report.available
    return report


if __name__ == "__main__":
    main()

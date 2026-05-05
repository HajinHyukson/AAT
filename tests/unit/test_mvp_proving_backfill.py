from __future__ import annotations

from datetime import date
from pathlib import Path

from jobs.run_mvp_proving_backfill import (
    CoverageReport,
    FMP_SYMBOL_ALIASES,
    default_backfill_start,
    proving_price_tickers,
    proxy_tickers,
    run_proving_backfill,
)
from jobs.seed_mvp_universe import load_config


def test_proving_price_tickers_include_mvp_universe_and_required_proxies() -> None:
    payload = load_config(Path("config/mvp_universe.json"))
    tickers = set(proving_price_tickers(payload))

    assert len([item for item in payload["securities"] if item["ticker"] in tickers]) == 50
    assert proxy_tickers().issubset(tickers)
    assert FMP_SYMBOL_ALIASES["BRK.B"][0] == "BRK-B"


def test_default_backfill_start_includes_one_year_plus_lookback_buffer() -> None:
    start = default_backfill_start(end=date(2026, 5, 4), lookback_days=252)

    assert start < date(2025, 5, 4)


def test_coverage_report_classifies_success_and_skip_reasons() -> None:
    report = CoverageReport(
        attribution_ran=10,
        attribution_skipped=2,
        macro_fetch_failures={"DGS10": "timeout"},
        skip_reasons=["missing_recent_trading_dates", "missing_recent_trading_dates", "no prices"],
    )

    assert report.success
    assert report.top_skip_reasons()[0] == ("missing_recent_trading_dates", 2)
    assert "DGS10" in report.render()
    assert "success=True" in report.render()


def test_proving_backfill_dry_run_records_expected_steps() -> None:
    seen: list[str] = []
    report = run_proving_backfill(
        config_path=Path("config/mvp_universe.json"),
        start=date(2025, 1, 1),
        end=date(2026, 1, 1),
        lookback_days=252,
        dry_run=True,
        step_runner=seen.append,
    )

    assert report.seeded_securities == 50
    assert seen == [
        "alembic_upgrade",
        "seed_universe",
        "seed_mappings",
        "backfill_prices",
        "ingest_french",
        "ingest_fred",
        "build_proxy_returns",
        "generate_event_features",
        "run_expanded_attribution",
        "replay_audit",
    ]

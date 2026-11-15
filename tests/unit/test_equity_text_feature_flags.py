"""Feature-flag tests for the equity text sentiment resolver.

Confirms the brief's non-negotiable constraint: flags default off, and flags
off mean the resolver returns a disabled state without touching SEC, the
model, or the observation store.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.resolver import resolve_finance_text_sentiment
from viza.equity.text.types import (
    ResolverFilingSelector,
    ResolverRequest,
    ResolverTarget,
)


def test_defaults_are_all_off(monkeypatch) -> None:
    for name in (
        "VIZA_EQUITY_SEC_TEXT_ANALYSIS_ENABLED",
        "VIZA_EQUITY_TEXT_SENTIMENT_RESOLVER_ENABLED",
        "VIZA_EQUITY_FINBERT_ENABLED",
        "VIZA_EQUITY_FINBERT_MODEL_DOWNLOAD_ENABLED",
        "VIZA_EQUITY_TEXT_PREPOPULATION_ENABLED",
        "VIZA_EQUITY_TEXT_REPLAY_REFRESH_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)
    config = EquityTextConfig.from_env(load_local_dotenv=False)
    assert config.feature_off() is True
    assert config.section_extraction_off() is True
    assert config.model_inference_off() is True


def test_resolver_returns_disabled_when_flags_off() -> None:
    config = EquityTextConfig()  # all defaults = off
    request = ResolverRequest(
        target=ResolverTarget(cik="0000320193"),
        filing=ResolverFilingSelector(latest=True),
        sections=["risk_factors"],
        analysis_mode="live_current",
    )
    response = resolve_finance_text_sentiment(request, config=config)
    assert response.status == "disabled"
    assert response.observations == []


def test_masked_summary_does_not_leak_paths() -> None:
    config = EquityTextConfig(finbert_cache_dir="/tmp/should/not/leak")
    summary = config.masked_summary()
    assert summary["VIZA_FINBERT_CACHE_DIR_configured"] is True
    assert "/tmp/should/not/leak" not in str(summary)

"""Feature-flag configuration for the equity text sentiment resolver.

Mirrors the ``viza.equity.config.EquityRuntimeConfig`` pattern: dataclass,
``from_env`` constructor, ``masked_summary`` for diagnostics that never leaks
secrets.

ALL flags default off. ``feature_off()`` is the single check the runtime uses
to short-circuit to a disabled response, ensuring the existing wedge behavior
is unchanged when flags are unset.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config.env import load_dotenv


TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class EquityTextConfig:
    """Feature flags + runtime knobs for the finance text sentiment resolver."""

    sec_text_analysis_enabled: bool = False
    text_sentiment_resolver_enabled: bool = False
    finbert_enabled: bool = False
    finbert_model_download_enabled: bool = False
    text_prepopulation_enabled: bool = False
    text_replay_refresh_enabled: bool = False

    finbert_model_id: str = "ProsusAI/finbert"
    finbert_runtime: str = "transformers"
    finbert_cache_dir: str | None = None
    finbert_max_chunk_tokens: int = 256
    finbert_batch_size: int = 32
    finbert_cpu_threads: int = 1

    @classmethod
    def from_env(cls, *, load_local_dotenv: bool = True) -> "EquityTextConfig":
        if load_local_dotenv:
            load_dotenv()
        return cls(
            sec_text_analysis_enabled=_bool_env(
                "VIZA_EQUITY_SEC_TEXT_ANALYSIS_ENABLED", False
            ),
            text_sentiment_resolver_enabled=_bool_env(
                "VIZA_EQUITY_TEXT_SENTIMENT_RESOLVER_ENABLED", False
            ),
            finbert_enabled=_bool_env("VIZA_EQUITY_FINBERT_ENABLED", False),
            finbert_model_download_enabled=_bool_env(
                "VIZA_EQUITY_FINBERT_MODEL_DOWNLOAD_ENABLED", False
            ),
            text_prepopulation_enabled=_bool_env(
                "VIZA_EQUITY_TEXT_PREPOPULATION_ENABLED", False
            ),
            text_replay_refresh_enabled=_bool_env(
                "VIZA_EQUITY_TEXT_REPLAY_REFRESH_ENABLED", False
            ),
            finbert_model_id=os.getenv("VIZA_FINBERT_MODEL_ID") or "ProsusAI/finbert",
            finbert_runtime=_choice_env(
                "VIZA_FINBERT_RUNTIME",
                ("transformers", "onnx", "onnx_int8"),
                "transformers",
            ),
            finbert_cache_dir=os.getenv("VIZA_FINBERT_CACHE_DIR") or None,
            finbert_max_chunk_tokens=_int_env("VIZA_FINBERT_MAX_CHUNK_TOKENS", 256),
            finbert_batch_size=_int_env("VIZA_FINBERT_BATCH_SIZE", 32),
            finbert_cpu_threads=_int_env("VIZA_FINBERT_CPU_THREADS", 1),
        )

    def feature_off(self) -> bool:
        """True iff the resolver should behave as fully disabled.

        Disabled means: registration is still allowed (so callers can introspect
        the resolver_id), but resolve calls return status="disabled" without
        touching the observation store, network, or filesystem.
        """
        return not self.text_sentiment_resolver_enabled

    def section_extraction_off(self) -> bool:
        """True iff SEC filing text section extraction is disabled."""
        return not self.sec_text_analysis_enabled

    def model_inference_off(self) -> bool:
        """True iff FinBERT inference (real or mocked) is disabled."""
        return not self.finbert_enabled

    def masked_summary(self) -> dict[str, object]:
        return {
            "VIZA_EQUITY_SEC_TEXT_ANALYSIS_ENABLED": self.sec_text_analysis_enabled,
            "VIZA_EQUITY_TEXT_SENTIMENT_RESOLVER_ENABLED": self.text_sentiment_resolver_enabled,
            "VIZA_EQUITY_FINBERT_ENABLED": self.finbert_enabled,
            "VIZA_EQUITY_FINBERT_MODEL_DOWNLOAD_ENABLED": self.finbert_model_download_enabled,
            "VIZA_EQUITY_TEXT_PREPOPULATION_ENABLED": self.text_prepopulation_enabled,
            "VIZA_EQUITY_TEXT_REPLAY_REFRESH_ENABLED": self.text_replay_refresh_enabled,
            "VIZA_FINBERT_MODEL_ID": self.finbert_model_id,
            "VIZA_FINBERT_RUNTIME": self.finbert_runtime,
            "VIZA_FINBERT_CACHE_DIR_configured": self.finbert_cache_dir is not None,
            "VIZA_FINBERT_MAX_CHUNK_TOKENS": self.finbert_max_chunk_tokens,
            "VIZA_FINBERT_BATCH_SIZE": self.finbert_batch_size,
            "VIZA_FINBERT_CPU_THREADS": self.finbert_cpu_threads,
        }


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in TRUTHY:
        return True
    if normalized in FALSY:
        return False
    return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw.strip()))
    except ValueError:
        return default


def _choice_env(name: str, choices: tuple[str, ...], default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    return normalized if normalized in choices else default

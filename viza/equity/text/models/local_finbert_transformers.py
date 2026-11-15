"""Stage B local FinBERT implementation via transformers.

Imports of ``transformers`` and ``torch`` are LAZY: they happen inside the
classify call, not at module import time. This keeps the rest of the resolver
functional in environments where transformers is not installed (the mock
implementation continues to work).

Behavior:
  * Not registered at import time. The resolver registers it on first use
    via ``register_transformers_finbert_if_enabled``.
  * If transformers/torch import fails, raises ``FinbertDependencyMissing``
    so the resolver can downgrade to status="missing_model" without leaking
    a traceback to the caller.
  * If the model artifact is not present on disk and
    ``VIZA_EQUITY_FINBERT_MODEL_DOWNLOAD_ENABLED`` is false, raises
    ``ModelArtifactsMissing``.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.hashing import InferenceConfig
from viza.equity.text.model_manager import (
    LocatedArtifact,
    ModelArtifactsMissing,
    locate_local_artifact,
)
from viza.equity.text.models import (
    ModelImplementation,
    SentimentInferenceResult,
    register_model,
)
from viza.equity.text.types import ChunkRecord, ModelMetadata


TRANSFORMERS_IMPLEMENTATION_ID = "local_finbert_transformers"
PROSUS_FINBERT_MODEL_VERSION = "v1.0"


def _default_inference_config(*, runtime_version: str) -> InferenceConfig:
    return {
        "runtime": "transformers",
        "runtime_version": runtime_version,
        "max_seq_length": 256,
        "truncation": "longest_first",
        "fp_precision": "fp32",
        "batch_size": 32,
        "device": "cpu",
        "seed": 0,
    }


class FinbertDependencyMissing(RuntimeError):
    """transformers (and/or torch) is not installed in this environment."""


class LocalFinbertTransformers:
    """ModelImplementation that runs ProsusAI/finbert via transformers.

    The model is loaded lazily the first time ``classify`` is called. Loading
    failure is recorded; subsequent calls re-raise the same error so callers
    see consistent behavior.
    """

    implementation_id = TRANSFORMERS_IMPLEMENTATION_ID

    def __init__(
        self,
        *,
        config: EquityTextConfig,
        artifact: LocatedArtifact | None = None,
    ) -> None:
        self._config = config
        self._artifact = artifact  # may be None until first metadata() call
        self._cached_metadata: ModelMetadata | None = None
        self._cached_pipeline = None
        self._load_error: Exception | None = None

    def metadata(self) -> ModelMetadata:
        if self._cached_metadata is None:
            artifact = self._ensure_artifact()
            runtime_version = _detect_transformers_version()
            self._cached_metadata = artifact.as_metadata(
                model_id=self._config.finbert_model_id,
                model_version=PROSUS_FINBERT_MODEL_VERSION,
                implementation_id=TRANSFORMERS_IMPLEMENTATION_ID,
                inference_config=_default_inference_config(
                    runtime_version=runtime_version,
                ),
                tokenizer_version=None,
                runtime_version=runtime_version,
            )
        return self._cached_metadata

    def classify(
        self,
        chunks: list[ChunkRecord],
    ) -> list[SentimentInferenceResult]:
        pipeline = self._ensure_pipeline()
        results: list[SentimentInferenceResult] = []
        # The transformers pipeline returns label/score for each top class; we
        # request all class scores via return_all_scores=True so the resolver
        # gets the full three-class distribution.
        outputs = pipeline(
            [chunk.text for chunk in chunks],
            truncation=True,
            top_k=None,
            batch_size=self._config.finbert_batch_size,
        )
        for output in outputs:
            distribution = {item["label"].lower(): float(item["score"]) for item in output}
            positive = distribution.get("positive", 0.0)
            neutral = distribution.get("neutral", 0.0)
            negative = distribution.get("negative", 0.0)
            label = max(
                (("positive", positive), ("neutral", neutral), ("negative", negative)),
                key=lambda pair: pair[1],
            )[0]
            result = SentimentInferenceResult()
            result["positive_prob"] = positive
            result["neutral_prob"] = neutral
            result["negative_prob"] = negative
            result["label"] = label
            result["confidence"] = max(positive, neutral, negative)
            results.append(result)
        return results

    # ---- internals -----------------------------------------------------

    def _ensure_artifact(self) -> LocatedArtifact:
        if self._artifact is None:
            try:
                self._artifact = locate_local_artifact(
                    model_id=self._config.finbert_model_id,
                    cache_dir=self._config.finbert_cache_dir,
                )
            except ModelArtifactsMissing as missing:
                if not self._config.finbert_model_download_enabled:
                    raise
                # Caller has explicitly enabled download; we load via
                # transformers' from_pretrained which will populate the HF
                # cache, then re-locate.
                self._load_pipeline_lazy(allow_download=True)
                self._artifact = locate_local_artifact(
                    model_id=self._config.finbert_model_id,
                    cache_dir=self._config.finbert_cache_dir,
                )
        return self._artifact

    def _ensure_pipeline(self):
        if self._load_error is not None:
            raise self._load_error
        if self._cached_pipeline is None:
            try:
                self._cached_pipeline = self._load_pipeline_lazy(
                    allow_download=self._config.finbert_model_download_enabled,
                )
            except Exception as error:  # narrowed below; surfaced to caller
                self._load_error = error
                raise
        return self._cached_pipeline

    def _load_pipeline_lazy(self, *, allow_download: bool):
        try:
            transformers = importlib.import_module("transformers")
        except ImportError as error:
            raise FinbertDependencyMissing(
                "transformers is not installed; install transformers + torch "
                "or use the local_finbert_mock implementation"
            ) from error

        AutoTokenizer = transformers.AutoTokenizer
        AutoModelForSequenceClassification = transformers.AutoModelForSequenceClassification
        pipeline_fn = transformers.pipeline

        kwargs = {}
        if not allow_download:
            kwargs["local_files_only"] = True
        if self._config.finbert_cache_dir:
            kwargs["cache_dir"] = self._config.finbert_cache_dir

        tokenizer = AutoTokenizer.from_pretrained(
            self._config.finbert_model_id, **kwargs
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            self._config.finbert_model_id, **kwargs
        )
        return pipeline_fn(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            framework="pt",
        )


def register_transformers_finbert_if_enabled(
    *,
    config: EquityTextConfig | None = None,
) -> bool:
    """Register the transformers FinBERT implementation if flags allow.

    Returns True if registered, False otherwise. Safe to call multiple times.
    Stage B's resolver wiring (deferred to Stage C alongside the FastAPI
    layer) calls this on startup; Stage A's resolver continues to use the
    mock.
    """
    active = config or EquityTextConfig.from_env()
    if not active.finbert_enabled:
        return False
    try:
        impl = LocalFinbertTransformers(config=active)
        register_model(impl)
    except Exception:
        return False
    return True


def _detect_transformers_version() -> str:
    try:
        transformers = importlib.import_module("transformers")
        version = getattr(transformers, "__version__", "unknown")
        return f"transformers=={version}"
    except ImportError:
        return "transformers==unavailable"

"""Model-implementation registry for the finance text sentiment resolver.

The resolver is model-agnostic: it dispatches to a ``ModelImplementation``
chosen by ``implementation_id``. Stage A ships only the deterministic mock
(``local_finbert_mock``). Stage B adds the real transformers/ONNX
implementations under the same protocol.
"""

from __future__ import annotations

from typing import Protocol

from viza.equity.text.hashing import InferenceConfig
from viza.equity.text.types import ChunkRecord, ModelMetadata


class SentimentInferenceResult(dict):
    """Result of a single chunk inference.

    Carries (positive_prob, neutral_prob, negative_prob, label, confidence).
    Implemented as a dict subclass for cheap (de)serialization; concrete keys
    are documented for type clarity.
    """

    positive_prob: float
    neutral_prob: float
    negative_prob: float
    label: str
    confidence: float


class ModelImplementation(Protocol):
    """The single interface every sentiment model implementation must satisfy.

    The resolver knows nothing about FinBERT specifically: it loads an
    implementation by id and asks it to (a) report its metadata and (b)
    classify chunks. Adding a new implementation (e.g. Loughran-McDonald
    dictionary, FinBERT-FLS, an LLM extractor) means writing a new file under
    ``viza/equity/text/models/`` and registering it here.
    """

    implementation_id: str

    def metadata(self) -> ModelMetadata: ...

    def classify(
        self,
        chunks: list[ChunkRecord],
    ) -> list[SentimentInferenceResult]: ...


_REGISTRY: dict[str, ModelImplementation] = {}


def register_model(implementation: ModelImplementation) -> None:
    _REGISTRY[implementation.implementation_id] = implementation


def get_model(implementation_id: str) -> ModelImplementation:
    impl = _REGISTRY.get(implementation_id)
    if impl is None:
        raise KeyError(
            f"unknown sentiment model implementation_id={implementation_id!r}; "
            f"registered={sorted(_REGISTRY)}"
        )
    return impl


def list_implementations() -> list[str]:
    return sorted(_REGISTRY)


# Eager registration of the mock implementation. Stage B adds the real ones
# behind feature flags so they don't load weights at import time.
from viza.equity.text.models import mock_finbert as _mock_module  # noqa: E402

register_model(_mock_module.build_mock_finbert())

"""ONNX/INT8 FinBERT implementation — Stage B' stub.

Per the design pass, ONNX export + INT8 quantization is deferred to a
follow-up commit that includes accuracy-equivalence tests against the
transformers baseline. Shipping ONNX without such tests would silently change
sentiment outputs across machines.

This stub exists so the resolver can introspect the implementation_id without
crashing; any attempt to classify raises a clear, actionable error.
"""

from __future__ import annotations

from viza.equity.text.models import (
    ModelImplementation,
    SentimentInferenceResult,
)
from viza.equity.text.types import ChunkRecord, ModelMetadata


ONNX_IMPLEMENTATION_ID = "local_finbert_onnx"


class OnnxDeferred(NotImplementedError):
    """ONNX FinBERT is deferred to Stage B'."""


class LocalFinbertOnnx:
    """Stub raising OnnxDeferred on use."""

    implementation_id = ONNX_IMPLEMENTATION_ID

    def metadata(self) -> ModelMetadata:
        raise OnnxDeferred(
            "ONNX/INT8 FinBERT is deferred to Stage B'. "
            "Use implementation_id=local_finbert_transformers or "
            "local_finbert_mock."
        )

    def classify(
        self,
        chunks: list[ChunkRecord],
    ) -> list[SentimentInferenceResult]:
        raise OnnxDeferred(
            "ONNX/INT8 FinBERT classify() is not implemented. "
            "An accuracy-equivalence test against the transformers baseline "
            "must land in the same commit that enables ONNX inference."
        )

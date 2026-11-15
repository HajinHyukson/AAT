"""Deterministic mock FinBERT implementation.

Used in Stage A tests, fixtures, and feature-flag-off behavior. It satisfies
the ``ModelImplementation`` protocol with a closed-form, deterministic mapping
from text hash to a three-class distribution. Critically, it carries the SAME
metadata shape (model_hash, tokenizer_hash, inference_config_hash) as a real
implementation, so the cache_key behavior is identical.

Two designed properties:
  1. Same text hash -> same distribution. This lets cache tests verify
     hit/miss semantics deterministically without loading real weights.
  2. The keyword set in ``viza.equity.text.human_review`` is intentionally
     NOT used to shift mock outputs. Human-review behavior is a separate gate
     that runs upstream of the model; the test suite asserts they compose
     correctly.

This file is also a worked example for Stage B: drop in a transformers-backed
classifier with the same interface, register it, and the resolver picks it up.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from viza.equity.text.hashing import (
    InferenceConfig,
    canonical_json,
    hash_inference_config,
    hash_tokenizer_files,
    sha256_hex,
)
from viza.equity.text.models import SentimentInferenceResult
from viza.equity.text.types import ChunkRecord, ModelMetadata


MOCK_MODEL_ID = "viza.mock/finbert"
MOCK_MODEL_VERSION = "mock_v1"
MOCK_IMPLEMENTATION_ID = "local_finbert_mock"


# A fixed inference config so mock observations have a stable
# inference_config_hash across machines.
MOCK_INFERENCE_CONFIG: InferenceConfig = {
    "runtime": "transformers",
    "runtime_version": "mock==0.0.0",
    "max_seq_length": 256,
    "truncation": "longest_first",
    "fp_precision": "fp32",
    "batch_size": 32,
    "device": "cpu",
    "seed": 0,
}


def _mock_distribution(text_hash: str) -> tuple[float, float, float]:
    """Closed-form deterministic distribution keyed by SHA-256 of the text.

    Splits the 64-char hex digest into three 8-byte buckets, maps each to a
    weight in (0, 1], normalizes to a 3-simplex. Same hash -> same output on
    every machine.
    """
    weights = []
    for offset in (0, 16, 32):
        slice_hex = text_hash[offset : offset + 16]
        value = int(slice_hex, 16) / float(0xFFFFFFFFFFFFFFFF)
        weights.append(max(value, 1e-6))
    total = sum(weights)
    return weights[0] / total, weights[1] / total, weights[2] / total


def _label_from_dist(positive: float, neutral: float, negative: float) -> str:
    pairs = [("positive", positive), ("neutral", neutral), ("negative", negative)]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[0][0]


class MockFinBert:
    """A deterministic three-class classifier mimicking ProsusAI/finbert."""

    implementation_id = MOCK_IMPLEMENTATION_ID

    def __init__(self) -> None:
        # Mock tokenizer "files": fixed byte strings so hash_tokenizer_files
        # produces a stable, reproducible tokenizer_hash.
        self._tokenizer_hash = hash_tokenizer_files(
            tokenizer_json=b'{"mock_tokenizer":"v1"}',
            vocab=b"[PAD]\n[CLS]\n[SEP]\n[UNK]\n",
            merges=None,
            special_tokens_map=b'{"pad_token":"[PAD]"}',
        )
        self._model_hash = sha256_hex(
            canonical_json(
                {
                    "mock_model_id": MOCK_MODEL_ID,
                    "mock_model_version": MOCK_MODEL_VERSION,
                }
            )
        )
        self._inference_config_hash = hash_inference_config(MOCK_INFERENCE_CONFIG)

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_provider="mock",
            model_family="financial_text_sentiment",
            implementation_id=MOCK_IMPLEMENTATION_ID,
            model_id=MOCK_MODEL_ID,
            model_version=MOCK_MODEL_VERSION,
            model_hash=self._model_hash,
            tokenizer_version="mock_v1",
            tokenizer_hash=self._tokenizer_hash,
            runtime=MOCK_INFERENCE_CONFIG["runtime"],
            runtime_version=MOCK_INFERENCE_CONFIG["runtime_version"],
            inference_config_hash=self._inference_config_hash,
            max_tokens_policy=str(MOCK_INFERENCE_CONFIG["max_seq_length"]),
            truncation_policy=MOCK_INFERENCE_CONFIG["truncation"],
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def classify(
        self,
        chunks: list[ChunkRecord],
    ) -> list[SentimentInferenceResult]:
        results: list[SentimentInferenceResult] = []
        for chunk in chunks:
            pos, neu, neg = _mock_distribution(chunk.text_hash)
            label = _label_from_dist(pos, neu, neg)
            confidence = max(pos, neu, neg)
            result = SentimentInferenceResult()
            result["positive_prob"] = pos
            result["neutral_prob"] = neu
            result["negative_prob"] = neg
            result["label"] = label
            result["confidence"] = confidence
            results.append(result)
        return results


def build_mock_finbert() -> MockFinBert:
    return MockFinBert()

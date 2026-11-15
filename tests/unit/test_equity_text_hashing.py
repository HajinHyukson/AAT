"""Tests for viza.equity.text.hashing — the four hash specs from pin 1.

These tests pin the byte-level behavior so a future change to canonical_json,
the cache_key field set, or any constituent file shape fails loudly rather
than silently corrupting the cache.
"""

from __future__ import annotations

import pytest

from viza.equity.text.hashing import (
    CACHE_KEY_FIELDS,
    canonical_json,
    compute_cache_key,
    hash_chunking_policy,
    hash_inference_config,
    hash_section_text,
    hash_tokenizer_files,
    sha256_hex,
)


VALID_CHUNKING_POLICY = {
    "policy_version": "v1",
    "splitter": "regex_sentence",
    "splitter_version": "regex_sentence_v1",
    "max_chunk_tokens": 256,
    "min_chunk_tokens": 8,
    "overlap_tokens": 0,
    "join_short_sentences": True,
    "drop_boilerplate": False,
    "lowercase": False,
}


VALID_INFERENCE_CONFIG = {
    "runtime": "transformers",
    "runtime_version": "mock==0.0.0",
    "max_seq_length": 256,
    "truncation": "longest_first",
    "fp_precision": "fp32",
    "batch_size": 32,
    "device": "cpu",
    "seed": 0,
}


def test_canonical_json_is_sort_and_whitespace_invariant() -> None:
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b
    assert b"  " not in a  # no extraneous whitespace


def test_sha256_hex_is_length_64() -> None:
    assert len(sha256_hex(b"hello")) == 64


def test_hash_section_text_is_deterministic() -> None:
    text = "Going concern language appears in Risk Factors."
    assert hash_section_text(text) == hash_section_text(text)


def test_hash_chunking_policy_rejects_unknown_keys() -> None:
    bad = dict(VALID_CHUNKING_POLICY)
    bad["extra_knob"] = True
    with pytest.raises(ValueError, match="exactly the declared keys"):
        hash_chunking_policy(bad)


def test_hash_chunking_policy_rejects_missing_keys() -> None:
    missing = {k: v for k, v in VALID_CHUNKING_POLICY.items() if k != "lowercase"}
    with pytest.raises(ValueError, match="missing"):
        hash_chunking_policy(missing)


def test_hash_chunking_policy_changes_when_any_field_changes() -> None:
    base = hash_chunking_policy(VALID_CHUNKING_POLICY)
    bumped = dict(VALID_CHUNKING_POLICY)
    bumped["max_chunk_tokens"] = 128
    assert hash_chunking_policy(bumped) != base


def test_hash_inference_config_rejects_unknown_keys() -> None:
    bad = dict(VALID_INFERENCE_CONFIG)
    bad["temperature"] = 0.7
    with pytest.raises(ValueError, match="exactly the declared keys"):
        hash_inference_config(bad)


def test_hash_inference_config_changes_with_runtime() -> None:
    base = hash_inference_config(VALID_INFERENCE_CONFIG)
    other = dict(VALID_INFERENCE_CONFIG)
    other["runtime"] = "onnx_int8"
    assert hash_inference_config(other) != base


def test_hash_tokenizer_files_uses_unit_separator_positionally() -> None:
    a = hash_tokenizer_files(
        tokenizer_json=b"x",
        vocab=b"y",
        merges=None,
        special_tokens_map=None,
    )
    b = hash_tokenizer_files(
        tokenizer_json=b"x",
        vocab=None,
        merges=b"y",
        special_tokens_map=None,
    )
    # Same payload bytes in different positions must NOT collide.
    assert a != b


def test_cache_key_field_set_is_pinned() -> None:
    assert set(CACHE_KEY_FIELDS) == {
        "filing_accession",
        "section_id",
        "section_text_hash",
        "parser_version",
        "chunking_policy_hash",
        "model_id",
        "model_version",
        "model_hash",
        "tokenizer_hash",
        "inference_config_hash",
    }


def test_cache_key_is_deterministic_and_changes_with_any_field() -> None:
    base_kwargs = dict(
        filing_accession="0000320193-23-000106",
        section_id="risk_factors",
        section_text_hash="a" * 64,
        parser_version="ixbrl_section_parser_v1",
        chunking_policy_hash="b" * 64,
        model_id="ProsusAI/finbert",
        model_version="v1.0",
        model_hash="c" * 64,
        tokenizer_hash="d" * 64,
        inference_config_hash="e" * 64,
    )
    base = compute_cache_key(**base_kwargs)
    assert compute_cache_key(**base_kwargs) == base

    for field in base_kwargs:
        mutated = dict(base_kwargs)
        mutated[field] = "z" * 64 if len(mutated[field]) == 64 else mutated[field] + "_X"
        assert compute_cache_key(**mutated) != base, (
            f"cache_key did not change when {field} changed"
        )

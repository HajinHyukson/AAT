"""Pin-1 hash specifications.

These four hashes form the cache_key that protects the resolver from silent
model/parser/chunking upgrades. Every constituent is enumerated and the
serialization is canonical, so the same logical configuration on two machines
produces the same hash, and any change to any field invalidates the cache by
construction.

All hashes are hex-encoded lowercase SHA-256, length 64.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, TypedDict


UNIT_SEPARATOR = b"\x1f"  # ASCII 0x1F, cannot appear inside the constituent files.


class ChunkingPolicy(TypedDict):
    """Frozen, fully enumerated chunking-policy fields.

    Adding a key requires bumping policy_version; that change cascades into a
    new chunking_policy_hash and forces a cache miss on every observation.
    """

    policy_version: str
    splitter: str  # "regex_sentence" | "spacy_sentence"
    splitter_version: str
    max_chunk_tokens: int
    min_chunk_tokens: int
    overlap_tokens: int
    join_short_sentences: bool
    drop_boilerplate: bool
    lowercase: bool


class InferenceConfig(TypedDict):
    """Frozen, fully enumerated inference-config fields."""

    runtime: str  # "transformers" | "onnx" | "onnx_int8"
    runtime_version: str
    max_seq_length: int
    truncation: str  # "longest_first" | "only_first" | "do_not_truncate"
    fp_precision: str  # "fp32" | "fp16" | "int8"
    batch_size: int
    device: str  # "cpu" | "cuda:0"
    seed: int


CHUNKING_POLICY_KEYS = frozenset(ChunkingPolicy.__annotations__.keys())
INFERENCE_CONFIG_KEYS = frozenset(InferenceConfig.__annotations__.keys())

CACHE_KEY_FIELDS = (
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
)


def sha256_hex(payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    assert len(digest) == 64, "sha256 hex must be length 64"
    return digest


def canonical_json(value: Mapping[str, Any]) -> bytes:
    """Canonical JSON: sorted keys, no whitespace, ASCII-escaped, UTF-8 encoded.

    This is the only acceptable serialization for hashing because Python's
    default json.dumps is whitespace-and-ordering-sensitive in ways that would
    silently corrupt the cache.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def hash_weights_file(weights_path: str | Path) -> str:
    """SHA256 of model weights file bytes. Computed once at load time."""
    path = Path(weights_path)
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def hash_tokenizer_files(
    *,
    tokenizer_json: bytes | None,
    vocab: bytes | None,
    merges: bytes | None,
    special_tokens_map: bytes | None,
) -> str:
    """Canonical tokenizer hash.

    canonical_blob = bytes(tokenizer.json)
                  || 0x1F || bytes(vocab.txt OR vocab.json)
                  || 0x1F || bytes(merges.txt if exists else b"")
                  || 0x1F || bytes(special_tokens_map.json if exists else b"")

    Missing files contribute b"" but the separator is still present
    (positional integrity is preserved so two missing files cannot collide
    with one missing file).
    """
    parts = [
        tokenizer_json or b"",
        vocab or b"",
        merges or b"",
        special_tokens_map or b"",
    ]
    return sha256_hex(UNIT_SEPARATOR.join(parts))


def hash_chunking_policy(policy: ChunkingPolicy | Mapping[str, Any]) -> str:
    """Hash of canonical_json of the chunking policy, with key-set validation."""
    keys = set(policy.keys())
    extra = keys - CHUNKING_POLICY_KEYS
    missing = CHUNKING_POLICY_KEYS - keys
    if extra or missing:
        raise ValueError(
            "chunking_policy must have exactly the declared keys; "
            f"extra={sorted(extra)} missing={sorted(missing)}"
        )
    return sha256_hex(canonical_json(dict(policy)))


def hash_inference_config(config: InferenceConfig | Mapping[str, Any]) -> str:
    """Hash of canonical_json of the inference config, with key-set validation."""
    keys = set(config.keys())
    extra = keys - INFERENCE_CONFIG_KEYS
    missing = INFERENCE_CONFIG_KEYS - keys
    if extra or missing:
        raise ValueError(
            "inference_config must have exactly the declared keys; "
            f"extra={sorted(extra)} missing={sorted(missing)}"
        )
    return sha256_hex(canonical_json(dict(config)))


def hash_section_text(text: str) -> str:
    """SHA256 of the raw section text as UTF-8 bytes.

    Section text is normalized before hashing only by encoding; whitespace and
    casing are preserved because they affect tokenization and therefore model
    output.
    """
    return sha256_hex(text.encode("utf-8"))


def compute_cache_key(
    *,
    filing_accession: str,
    section_id: str,
    section_text_hash: str,
    parser_version: str,
    chunking_policy_hash: str,
    model_id: str,
    model_version: str,
    model_hash: str,
    tokenizer_hash: str,
    inference_config_hash: str,
) -> str:
    """Deterministic 9-field cache key per pin 6.

    Any change to any field produces a different cache_key. The key itself is
    the SHA256 of the canonical-JSON of the field dict so it can be stored as
    a single indexed text column.
    """
    payload = {
        "filing_accession": filing_accession,
        "section_id": section_id,
        "section_text_hash": section_text_hash,
        "parser_version": parser_version,
        "chunking_policy_hash": chunking_policy_hash,
        "model_id": model_id,
        "model_version": model_version,
        "model_hash": model_hash,
        "tokenizer_hash": tokenizer_hash,
        "inference_config_hash": inference_config_hash,
    }
    return sha256_hex(canonical_json(payload))

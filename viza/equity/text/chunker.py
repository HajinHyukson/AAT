"""Deterministic sentence-level chunker.

Section text is split into sentence boundaries by a versioned regex, then
sentences are joined into chunks up to ``max_chunk_tokens`` with a token
estimate (whitespace-tokenization). The same input + policy produces
byte-identical chunks across machines.

The chunker emits ``chunking_policy_hash`` per pin 1 so cache_keys break
deterministically when any chunking knob changes.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from viza.equity.text.hashing import (
    ChunkingPolicy,
    canonical_json,
    hash_chunking_policy,
    sha256_hex,
)
from viza.equity.text.types import ChunkRecord, SectionId


REGEX_SENTENCE_SPLITTER_VERSION = "regex_sentence_v1"


# Sentence boundary detection: terminal . / ? / ! followed by whitespace and
# a capital letter, OR end-of-string. Intentionally simple and deterministic.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"“])")


DEFAULT_CHUNKING_POLICY: ChunkingPolicy = {
    "policy_version": "v1",
    "splitter": "regex_sentence",
    "splitter_version": REGEX_SENTENCE_SPLITTER_VERSION,
    "max_chunk_tokens": 256,
    "min_chunk_tokens": 8,
    "overlap_tokens": 0,
    "join_short_sentences": True,
    "drop_boilerplate": False,
    "lowercase": False,
}


def _estimate_tokens(text: str) -> int:
    """Whitespace-tokenization token estimate.

    A real BERT tokenizer would produce ~1.3x this number on financial English;
    this estimate is intentionally conservative-biased so we under-fill rather
    than over-fill chunks. Stage B replaces this with a real tokenizer when
    the model is loaded.
    """
    return len(text.split())


def _split_sentences(text: str) -> list[str]:
    if not text.strip():
        return []
    candidates = _SENTENCE_BOUNDARY.split(text.strip())
    return [s.strip() for s in candidates if s.strip()]


def chunk_section_text(
    *,
    section_text: str,
    section_id: SectionId,
    filing_accession: str,
    parser_version: str,
    section_text_hash: str,
    chunking_policy: ChunkingPolicy = DEFAULT_CHUNKING_POLICY,
    created_at: datetime | None = None,
) -> list[ChunkRecord]:
    """Deterministically chunk a section's text into ``ChunkRecord`` entries.

    Determinism guarantees:
      * Same ``section_text`` + ``chunking_policy`` -> byte-identical chunks
        in the same order with the same chunk_id values.
      * ``chunk_id`` = SHA256 of canonical_json({filing_accession, section_id,
        chunk_index, text_hash, chunking_policy_hash}). This makes chunk_id
        a stable identity that survives renames of the surrounding run.
    """
    if not section_text or section_id == "section_unparseable":
        return []

    policy_hash = hash_chunking_policy(chunking_policy)
    ts = created_at or datetime.now(timezone.utc)

    sentences = _split_sentences(section_text)
    if chunking_policy["lowercase"]:
        sentences = [s.lower() for s in sentences]

    chunks: list[tuple[str, int, int]] = []  # (text, char_start, char_end)
    cursor = 0

    def _find_span(needle: str, start: int) -> tuple[int, int]:
        """Find a substring in the original text starting at ``start`` (or
        later). Falls back to a non-matching span if absent (defensive)."""
        idx = section_text.find(needle, start)
        if idx < 0:
            return start, start + len(needle)
        return idx, idx + len(needle)

    current_text: list[str] = []
    current_sentence_count = 0
    current_start: int | None = None
    current_end = 0

    max_tokens = chunking_policy["max_chunk_tokens"]
    min_tokens = chunking_policy["min_chunk_tokens"]
    join_short = chunking_policy["join_short_sentences"]

    for sentence in sentences:
        s_start, s_end = _find_span(sentence, cursor)
        cursor = s_end
        candidate = " ".join(current_text + [sentence]) if current_text else sentence
        if _estimate_tokens(candidate) > max_tokens and current_text:
            chunks.append(
                (" ".join(current_text), current_start or 0, current_end)
            )
            current_text = [sentence]
            current_sentence_count = 1
            current_start = s_start
            current_end = s_end
        else:
            if current_start is None:
                current_start = s_start
            current_text.append(sentence)
            current_sentence_count += 1
            current_end = s_end

    if current_text:
        chunks.append((" ".join(current_text), current_start or 0, current_end))

    # Merge a final too-short chunk into the previous one if join_short_sentences.
    if (
        join_short
        and len(chunks) >= 2
        and _estimate_tokens(chunks[-1][0]) < min_tokens
    ):
        prev_text, prev_start, _ = chunks[-2]
        last_text, _, last_end = chunks[-1]
        merged_text = f"{prev_text} {last_text}".strip()
        chunks[-2:] = [(merged_text, prev_start, last_end)]

    records: list[ChunkRecord] = []
    for index, (text, char_start, char_end) in enumerate(chunks):
        text_hash = sha256_hex(text.encode("utf-8"))
        chunk_id = sha256_hex(
            canonical_json(
                {
                    "filing_accession": filing_accession,
                    "section_id": section_id,
                    "chunk_index": index,
                    "text_hash": text_hash,
                    "chunking_policy_hash": policy_hash,
                }
            )
        )
        records.append(
            ChunkRecord(
                chunk_id=chunk_id,
                filing_accession=filing_accession,
                section_id=section_id,
                chunk_index=index,
                text=text,
                text_hash=text_hash,
                char_start=char_start,
                char_end=char_end,
                sentence_count=len(_split_sentences(text)),
                token_estimate=_estimate_tokens(text),
                chunking_policy=dict(chunking_policy),
                chunking_policy_hash=policy_hash,
                parser_version=parser_version,
                section_text_hash=section_text_hash,
                created_at=ts,
            )
        )
    return records

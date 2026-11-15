"""Tests for the deterministic sentence-level chunker."""

from __future__ import annotations

from datetime import datetime, timezone

from viza.equity.text.chunker import (
    DEFAULT_CHUNKING_POLICY,
    chunk_section_text,
)


SECTION_TEXT = (
    "Our revenue grew 8% year over year driven by services. "
    "Operating expenses were broadly flat. "
    "We continue to invest in research and development. "
    "Free cash flow remained strong throughout the period."
)


CREATED_AT = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)


def test_chunker_is_deterministic_for_same_input() -> None:
    a = chunk_section_text(
        section_text=SECTION_TEXT,
        section_id="mdna",
        filing_accession="acc-1",
        parser_version="ixbrl_section_parser_v1",
        section_text_hash="x" * 64,
        chunking_policy=DEFAULT_CHUNKING_POLICY,
        created_at=CREATED_AT,
    )
    b = chunk_section_text(
        section_text=SECTION_TEXT,
        section_id="mdna",
        filing_accession="acc-1",
        parser_version="ixbrl_section_parser_v1",
        section_text_hash="x" * 64,
        chunking_policy=DEFAULT_CHUNKING_POLICY,
        created_at=CREATED_AT,
    )
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert [c.text for c in a] == [c.text for c in b]


def test_chunking_policy_change_changes_chunk_ids() -> None:
    base = chunk_section_text(
        section_text=SECTION_TEXT,
        section_id="mdna",
        filing_accession="acc-1",
        parser_version="ixbrl_section_parser_v1",
        section_text_hash="x" * 64,
        chunking_policy=DEFAULT_CHUNKING_POLICY,
        created_at=CREATED_AT,
    )
    bumped_policy = dict(DEFAULT_CHUNKING_POLICY)
    bumped_policy["max_chunk_tokens"] = 4  # forces many small chunks
    bumped = chunk_section_text(
        section_text=SECTION_TEXT,
        section_id="mdna",
        filing_accession="acc-1",
        parser_version="ixbrl_section_parser_v1",
        section_text_hash="x" * 64,
        chunking_policy=bumped_policy,  # type: ignore[arg-type]
        created_at=CREATED_AT,
    )
    # Different policy must produce a different policy hash and different chunk ids.
    assert base[0].chunking_policy_hash != bumped[0].chunking_policy_hash
    assert {c.chunk_id for c in base} != {c.chunk_id for c in bumped}


def test_empty_or_unparseable_section_yields_no_chunks() -> None:
    chunks = chunk_section_text(
        section_text="",
        section_id="risk_factors",
        filing_accession="acc-1",
        parser_version="ixbrl_section_parser_v1",
        section_text_hash="x" * 64,
        chunking_policy=DEFAULT_CHUNKING_POLICY,
    )
    assert chunks == []


def test_chunk_records_carry_policy_hash_and_section_hash() -> None:
    chunks = chunk_section_text(
        section_text=SECTION_TEXT,
        section_id="mdna",
        filing_accession="acc-1",
        parser_version="ixbrl_section_parser_v1",
        section_text_hash="abc" * 21 + "x",
        chunking_policy=DEFAULT_CHUNKING_POLICY,
    )
    assert all(c.chunking_policy_hash == chunks[0].chunking_policy_hash for c in chunks)
    assert all(c.section_text_hash == "abc" * 21 + "x" for c in chunks)

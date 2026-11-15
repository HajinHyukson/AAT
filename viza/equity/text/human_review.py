"""Pin-2 severe-negative human-review gate.

The gate is a regex/keyword pre-filter on raw section text, NOT a FinBERT
confidence threshold. FinBERT's three-class output cannot reliably distinguish
"going concern" disclosure from "going forward" discussion; we therefore
defer that distinction to an explicit, versioned, auditable term list.

A chunk matching any term:
  * emits a ``filing_text_human_review_required`` event,
  * is recorded with ``requires_human_review=True``,
  * receives ``confidence_label="requires_human_review"`` regardless of model
    confidence,
  * propagates ``requires_human_review=True`` to its section aggregate.

The term set is policy-versioned. Bumping ``HUMAN_REVIEW_TERM_SET_VERSION``
invalidates downstream observations only insofar as it changes the
``requires_human_review`` boolean and the recorded version label; it does NOT
change ``section_text_hash`` or ``chunking_policy_hash``, so the cache itself
is unaffected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


HUMAN_REVIEW_TERM_SET_VERSION = "v1"


HUMAN_REVIEW_TERMS: frozenset[str] = frozenset(
    {
        # Going concern
        "going concern",
        "substantial doubt",
        "ability to continue as a going concern",
        # Restatements / control failures
        "material weakness",
        "restatement of",
        "restate our",
        "restated financial",
        "ineffective internal control",
        "remediation plan",
        # Investigations / litigation
        "sec investigation",
        "doj investigation",
        "subpoena",
        "wells notice",
        "consent decree",
        "deferred prosecution",
        "class action",
        "shareholder derivative",
        # Auditor / fraud
        "qualified opinion",
        "adverse opinion",
        "auditor resignation",
        "accounting irregularities",
        "financial misstatement",
        # Bankruptcy
        "chapter 11",
        "chapter 7",
        "petition for relief",
        "debtor-in-possession",
    }
)


@dataclass(frozen=True)
class HumanReviewMatch:
    """A single matched term, with position for downstream UI surfacing.

    The position is in the *normalized* text (lowercased, single-spaced) so
    that callers using ``scan`` against a normalized buffer get usable spans
    without us needing to round-trip back to the original.
    """

    term: str
    start: int
    end: int


@dataclass(frozen=True)
class HumanReviewVerdict:
    """Aggregate verdict for a piece of text."""

    requires_human_review: bool
    matched_terms: tuple[str, ...]
    term_set_version: str

    def as_dict(self) -> dict[str, object]:
        return {
            "requires_human_review": self.requires_human_review,
            "matched_terms": list(self.matched_terms),
            "human_review_term_set_version": self.term_set_version,
        }


_TERM_BOUNDARY = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace.

    Phrase matching is whole-phrase, case-insensitive. We collapse whitespace
    so that line-broken or double-spaced phrases like ``going  concern`` or
    ``going\\nconcern`` still match.
    """
    return _TERM_BOUNDARY.sub(" ", text.lower()).strip()


def scan(text: str) -> list[HumanReviewMatch]:
    """Return every term match in ``text`` (positions in normalized text)."""
    if not text:
        return []
    normalized = _normalize(text)
    matches: list[HumanReviewMatch] = []
    for term in HUMAN_REVIEW_TERMS:
        start = 0
        while True:
            idx = normalized.find(term, start)
            if idx < 0:
                break
            matches.append(HumanReviewMatch(term=term, start=idx, end=idx + len(term)))
            start = idx + len(term)
    matches.sort(key=lambda m: (m.start, m.term))
    return matches


def evaluate(text: str) -> HumanReviewVerdict:
    """Verdict for a chunk of text: any term match triggers human review."""
    matches = scan(text)
    matched_terms = tuple(sorted({m.term for m in matches}))
    return HumanReviewVerdict(
        requires_human_review=bool(matched_terms),
        matched_terms=matched_terms,
        term_set_version=HUMAN_REVIEW_TERM_SET_VERSION,
    )

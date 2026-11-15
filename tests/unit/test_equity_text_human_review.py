"""Tests for pin 2: the keyword/regex human-review pre-filter."""

from __future__ import annotations

from viza.equity.text.human_review import (
    HUMAN_REVIEW_TERM_SET_VERSION,
    HUMAN_REVIEW_TERMS,
    evaluate,
    scan,
)


def test_term_set_is_pinned_to_v1() -> None:
    assert HUMAN_REVIEW_TERM_SET_VERSION == "v1"
    # The term set must contain anchors for each high-priority category.
    assert "going concern" in HUMAN_REVIEW_TERMS
    assert "material weakness" in HUMAN_REVIEW_TERMS
    assert "sec investigation" in HUMAN_REVIEW_TERMS
    assert "chapter 11" in HUMAN_REVIEW_TERMS


def test_clean_text_is_not_flagged() -> None:
    text = "Revenue grew thanks to strong product cycles and operational discipline."
    verdict = evaluate(text)
    assert verdict.requires_human_review is False
    assert verdict.matched_terms == ()


def test_going_concern_triggers_human_review() -> None:
    text = (
        "There is substantial doubt about our ability to continue as a going concern."
    )
    verdict = evaluate(text)
    assert verdict.requires_human_review is True
    # Both phrases should match.
    assert "going concern" in verdict.matched_terms
    assert "substantial doubt" in verdict.matched_terms


def test_match_is_case_insensitive() -> None:
    text = "We received an SEC Investigation notice last quarter."
    verdict = evaluate(text)
    assert verdict.requires_human_review is True
    assert "sec investigation" in verdict.matched_terms


def test_whitespace_collapse_handles_line_breaks() -> None:
    text = "Material\nweakness in internal controls."
    verdict = evaluate(text)
    assert verdict.requires_human_review is True


def test_scan_returns_positions_in_normalized_text() -> None:
    text = "We are pursuing Chapter 11 bankruptcy."
    matches = scan(text)
    assert any(m.term == "chapter 11" for m in matches)


def test_evaluate_carries_term_set_version() -> None:
    verdict = evaluate("Wells notice received from staff.")
    assert verdict.term_set_version == HUMAN_REVIEW_TERM_SET_VERSION
    assert "wells notice" in verdict.matched_terms

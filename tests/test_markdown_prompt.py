"""Unit tests for the Gemma prompt builder."""

from __future__ import annotations

import pytest

from scout.utils.markdown import build_prompt


# ---------------------------------------------------------------------------
# Required content
# ---------------------------------------------------------------------------

def test_prompt_contains_transcript() -> None:
    p = build_prompt("CS446", 1, "2026-04-25", "This is the transcript text.")
    assert "This is the transcript text." in p


def test_prompt_contains_course_name() -> None:
    p = build_prompt("PHYS101", 3, "2026-04-25", "transcript")
    assert "PHYS101" in p


def test_prompt_contains_lecture_number() -> None:
    p = build_prompt("CS446", 12, "2026-04-25", "transcript")
    assert "12" in p


def test_prompt_contains_date() -> None:
    p = build_prompt("CS446", 1, "2026-04-25", "transcript")
    assert "2026-04-25" in p


def test_prompt_heading_rule_present() -> None:
    p = build_prompt("CS446", 5, "2026-04-25", "transcript")
    assert "# CS446" in p
    assert "Lecture 5" in p


def test_prompt_key_takeaways_rule_present() -> None:
    p = build_prompt("CS446", 1, "2026-04-25", "transcript")
    assert "Key Takeaways" in p


def test_prompt_no_preamble_rule_present() -> None:
    p = build_prompt("CS446", 1, "2026-04-25", "transcript")
    assert "No preamble" in p or "no preamble" in p.lower()


# ---------------------------------------------------------------------------
# Custom suffix
# ---------------------------------------------------------------------------

def test_custom_suffix_appended_when_provided() -> None:
    p = build_prompt("CS446", 1, "2026-04-25", "transcript",
                     custom_suffix="Focus on algorithm proofs.")
    assert "Focus on algorithm proofs." in p


def test_empty_suffix_not_added() -> None:
    p = build_prompt("CS446", 1, "2026-04-25", "transcript", custom_suffix="")
    assert "Additional instruction:" not in p


def test_whitespace_only_suffix_not_added() -> None:
    p = build_prompt("CS446", 1, "2026-04-25", "transcript", custom_suffix="   ")
    assert "Additional instruction:" not in p


def test_suffix_label_present_when_suffix_provided() -> None:
    p = build_prompt("CS446", 1, "2026-04-25", "t", custom_suffix="extra")
    assert "Additional instruction:" in p


# ---------------------------------------------------------------------------
# Transcript placement
# ---------------------------------------------------------------------------

def test_transcript_appears_after_rules() -> None:
    transcript = "UNIQUE_TRANSCRIPT_MARKER"
    p = build_prompt("CS446", 1, "2026-04-25", transcript)
    rules_pos = p.index("Rules:")
    transcript_pos = p.index(transcript)
    assert transcript_pos > rules_pos


def test_multi_line_transcript_preserved() -> None:
    transcript = "Line one.\nLine two.\nLine three."
    p = build_prompt("CS446", 1, "2026-04-25", transcript)
    assert transcript in p

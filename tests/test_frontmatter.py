"""Unit tests for frontmatter injection."""

from __future__ import annotations

import pytest

from echos.utils.frontmatter import inject_frontmatter


# ---------------------------------------------------------------------------
# YAML block structure
# ---------------------------------------------------------------------------

def test_output_starts_with_yaml_fence() -> None:
    result = inject_frontmatter("body text", "CS446", 1, "2026-04-25")
    assert result.startswith("---\n")


def test_output_contains_closing_fence() -> None:
    result = inject_frontmatter("body", "CS446", 1, "2026-04-25")
    assert "\n---\n" in result


def test_course_field_present() -> None:
    result = inject_frontmatter("body", "CS446", 5, "2026-04-25")
    assert "course: CS446" in result


def test_lecture_field_present() -> None:
    result = inject_frontmatter("body", "CS446", 12, "2026-04-25")
    assert "lecture: 12" in result


def test_date_field_present() -> None:
    result = inject_frontmatter("body", "CS446", 1, "2026-04-25")
    assert "date: 2026-04-25" in result


def test_echos_version_field_present() -> None:
    result = inject_frontmatter("body", "CS446", 1, "2026-04-25", version="2.0.0")
    assert "echos_version: 2.0.0" in result


# ---------------------------------------------------------------------------
# Tags template
# ---------------------------------------------------------------------------

def test_default_tags_template_substitution() -> None:
    result = inject_frontmatter(
        "body", "CS446", 1, "2026-04-25",
        tags_template="[{course_lower}, lecture, notes]",
    )
    assert "tags: [cs446, lecture, notes]" in result


def test_custom_tags_template() -> None:
    result = inject_frontmatter(
        "body", "MATH301", 3, "2026-04-25",
        tags_template="[math301, {course_lower}, school]",
    )
    assert "tags: [math301, math301, school]" in result


def test_course_lower_is_lowercased() -> None:
    result = inject_frontmatter("body", "PHYS101", 1, "2026-04-25")
    assert "phys101" in result


# ---------------------------------------------------------------------------
# Notes body appended correctly
# ---------------------------------------------------------------------------

def test_body_follows_frontmatter() -> None:
    body = "# CS446 · Lecture 1\n\nSome notes here."
    result = inject_frontmatter(body, "CS446", 1, "2026-04-25")
    # Body must come after the closing --- fence.
    fence_pos = result.index("\n---\n")
    body_pos = result.index(body)
    assert body_pos > fence_pos


def test_body_preserved_exactly() -> None:
    body = "# Heading\n\n- item 1\n- item 2\n\n```python\ncode\n```"
    result = inject_frontmatter(body, "CS446", 1, "2026-04-25")
    assert body in result


def test_empty_body() -> None:
    result = inject_frontmatter("", "CS446", 1, "2026-04-25")
    assert result.startswith("---\n")
    assert result.endswith("\n\n")  # frontmatter ends with double newline before empty body


# ---------------------------------------------------------------------------
# Special characters in course name
# ---------------------------------------------------------------------------

def test_special_chars_in_course_name() -> None:
    result = inject_frontmatter("body", "CS 446: Algorithms & Complexity", 1, "2026-04-25")
    assert "course: CS 446: Algorithms & Complexity" in result


def test_unicode_course_name() -> None:
    result = inject_frontmatter("body", "数学101", 1, "2026-04-25")
    assert "course: 数学101" in result
    assert "数学101" in result  # in tags too (lowercased)

"""Unit tests for ObsidianManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from echos.core.obsidian_manager import ObsidianManager


@pytest.fixture
def mgr() -> ObsidianManager:
    return ObsidianManager()


# ---------------------------------------------------------------------------
# next_lecture_num
# ---------------------------------------------------------------------------

def test_next_lecture_num_missing_folder_returns_one(mgr: ObsidianManager, tmp_path: Path) -> None:
    assert mgr.next_lecture_num(tmp_path, "CS446") == 1


def test_next_lecture_num_empty_folder_returns_one(mgr: ObsidianManager, tmp_path: Path) -> None:
    (tmp_path / "CS446").mkdir()
    assert mgr.next_lecture_num(tmp_path, "CS446") == 1


def test_next_lecture_num_single_file(mgr: ObsidianManager, tmp_path: Path) -> None:
    course_dir = tmp_path / "CS446"
    course_dir.mkdir()
    (course_dir / "Lecture-01.md").write_text("content")
    assert mgr.next_lecture_num(tmp_path, "CS446") == 2


def test_next_lecture_num_multiple_files(mgr: ObsidianManager, tmp_path: Path) -> None:
    course_dir = tmp_path / "CS446"
    course_dir.mkdir()
    for n in [1, 3, 7, 12]:
        (course_dir / f"Lecture-{n:02d}.md").write_text("x")
    assert mgr.next_lecture_num(tmp_path, "CS446") == 13


def test_next_lecture_num_ignores_non_lecture_files(mgr: ObsidianManager, tmp_path: Path) -> None:
    course_dir = tmp_path / "CS446"
    course_dir.mkdir()
    (course_dir / "Lecture-05.md").write_text("x")
    (course_dir / "README.md").write_text("x")
    (course_dir / "notes.txt").write_text("x")
    assert mgr.next_lecture_num(tmp_path, "CS446") == 6


def test_next_lecture_num_case_insensitive(mgr: ObsidianManager, tmp_path: Path) -> None:
    course_dir = tmp_path / "CS446"
    course_dir.mkdir()
    (course_dir / "LECTURE-03.md").write_text("x")
    assert mgr.next_lecture_num(tmp_path, "CS446") == 4


# ---------------------------------------------------------------------------
# note_exists
# ---------------------------------------------------------------------------

def test_note_exists_false_when_no_file(mgr: ObsidianManager, tmp_path: Path) -> None:
    assert mgr.note_exists(tmp_path, "CS446", 1) is False


def test_note_exists_true_when_file_present(mgr: ObsidianManager, tmp_path: Path) -> None:
    course_dir = tmp_path / "CS446"
    course_dir.mkdir()
    (course_dir / "Lecture-01.md").write_text("content")
    assert mgr.note_exists(tmp_path, "CS446", 1) is True


def test_note_exists_false_for_different_number(mgr: ObsidianManager, tmp_path: Path) -> None:
    course_dir = tmp_path / "CS446"
    course_dir.mkdir()
    (course_dir / "Lecture-01.md").write_text("content")
    assert mgr.note_exists(tmp_path, "CS446", 2) is False


# ---------------------------------------------------------------------------
# save_note
# ---------------------------------------------------------------------------

def test_save_note_creates_course_directory(mgr: ObsidianManager, tmp_path: Path) -> None:
    mgr.save_note(tmp_path, "CS446", 1, "notes content", "CS446", "2026-04-25")
    assert (tmp_path / "CS446").is_dir()


def test_save_note_creates_file_with_correct_name(mgr: ObsidianManager, tmp_path: Path) -> None:
    path = mgr.save_note(tmp_path, "CS446", 5, "notes", "CS446", "2026-04-25")
    assert path.name == "Lecture-05.md"
    assert path.exists()


def test_save_note_zero_padded_name(mgr: ObsidianManager, tmp_path: Path) -> None:
    path = mgr.save_note(tmp_path, "MATH", 1, "", "MATH", "2026-04-25")
    assert path.name == "Lecture-01.md"


def test_save_note_large_number(mgr: ObsidianManager, tmp_path: Path) -> None:
    path = mgr.save_note(tmp_path, "CS", 100, "", "CS", "2026-04-25")
    assert path.name == "Lecture-100.md"


def test_save_note_content_written_correctly(mgr: ObsidianManager, tmp_path: Path) -> None:
    content = "# CS446 · Lecture 1\n\nSome notes here."
    path = mgr.save_note(tmp_path, "CS446", 1, content, "CS446", "2026-04-25")
    assert path.read_text(encoding="utf-8") == content


def test_save_note_returns_path_object(mgr: ObsidianManager, tmp_path: Path) -> None:
    result = mgr.save_note(tmp_path, "CS446", 1, "content", "CS446", "2026-04-25")
    assert isinstance(result, Path)


def test_save_note_nested_folder(mgr: ObsidianManager, tmp_path: Path) -> None:
    path = mgr.save_note(tmp_path, "2026/CS446", 1, "x", "CS446", "2026-04-25")
    assert path.exists()


def test_save_note_overwrites_existing_file(mgr: ObsidianManager, tmp_path: Path) -> None:
    mgr.save_note(tmp_path, "CS446", 1, "original", "CS446", "2026-04-25")
    mgr.save_note(tmp_path, "CS446", 1, "updated", "CS446", "2026-04-25")
    path = tmp_path / "CS446" / "Lecture-01.md"
    assert path.read_text(encoding="utf-8") == "updated"

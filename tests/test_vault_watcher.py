"""Unit tests for VaultWatcher.

These tests require a Qt application; pytest-qt's ``qtbot`` fixture provides one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from echos.core.vault_watcher import VaultWatcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vault(root: Path) -> None:
    """Create a small vault tree inside *root*."""
    (root / "CS446").mkdir()
    (root / "CS446" / "Lecture-01.md").write_text("# L1")
    (root / "CS446" / "Lecture-02.md").write_text("# L2")
    (root / "MATH215").mkdir()
    (root / "MATH215" / "Lecture-01.md").write_text("# M1")
    (root / ".obsidian").mkdir()  # should be ignored
    (root / ".obsidian" / "config").write_text("{}")


# ---------------------------------------------------------------------------
# scan()
# ---------------------------------------------------------------------------

def test_scan_returns_empty_for_nonexistent_path(qtbot) -> None:
    watcher = VaultWatcher()
    assert watcher.scan() == []


def test_scan_returns_folders_and_notes(qtbot, tmp_path: Path) -> None:
    _make_vault(tmp_path)
    watcher = VaultWatcher()
    tree = watcher.scan(tmp_path)

    names = {node["name"] for node in tree}
    assert "CS446" in names
    assert "MATH215" in names


def test_scan_ignores_hidden_directories(qtbot, tmp_path: Path) -> None:
    _make_vault(tmp_path)
    watcher = VaultWatcher()
    tree = watcher.scan(tmp_path)

    names = {node["name"] for node in tree}
    assert ".obsidian" not in names


def test_scan_children_are_notes(qtbot, tmp_path: Path) -> None:
    _make_vault(tmp_path)
    watcher = VaultWatcher()
    tree = watcher.scan(tmp_path)

    cs446 = next(n for n in tree if n["name"] == "CS446")
    child_names = {c["name"] for c in cs446["children"]}
    assert "Lecture-01" in child_names
    assert "Lecture-02" in child_names


def test_scan_non_md_files_excluded(qtbot, tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not markdown")
    (tmp_path / "data.csv").write_text("a,b,c")
    watcher = VaultWatcher()
    tree = watcher.scan(tmp_path)
    names = {n["name"] for n in tree}
    assert "notes" not in names
    assert "data" not in names


def test_scan_max_depth_respected(qtbot, tmp_path: Path) -> None:
    deep = tmp_path
    for part in ["a", "b", "c", "d", "e", "f", "g"]:
        deep = deep / part
        deep.mkdir()
    (deep / "note.md").write_text("deep note")

    watcher = VaultWatcher()
    # Default max_depth=5 — the note at depth 7 should not appear
    tree = watcher.scan(tmp_path, max_depth=5)
    # Flatten all node names recursively
    def _all_names(nodes):
        for n in nodes:
            yield n["name"]
            yield from _all_names(n.get("children", []))
    assert "note" not in set(_all_names(tree))


# ---------------------------------------------------------------------------
# watch() / stop()
# ---------------------------------------------------------------------------

def test_watch_registers_vault_directory(qtbot, tmp_path: Path) -> None:
    _make_vault(tmp_path)
    watcher = VaultWatcher()
    watcher.watch(str(tmp_path))
    assert str(tmp_path) in watcher._watcher.directories()
    watcher.stop()


def test_stop_clears_all_watched_paths(qtbot, tmp_path: Path) -> None:
    _make_vault(tmp_path)
    watcher = VaultWatcher()
    watcher.watch(str(tmp_path))
    watcher.stop()
    assert watcher._watcher.directories() == []
    assert watcher._watcher.files() == []


def test_watch_on_nonexistent_path_does_not_raise(qtbot, tmp_path: Path) -> None:
    watcher = VaultWatcher()
    watcher.watch(str(tmp_path / "does_not_exist"))  # should not raise


# ---------------------------------------------------------------------------
# tree_changed signal
# ---------------------------------------------------------------------------

def test_tree_changed_emitted_on_new_file(qtbot, tmp_path: Path) -> None:
    _make_vault(tmp_path)
    watcher = VaultWatcher()
    watcher.watch(str(tmp_path))

    with qtbot.waitSignal(watcher.tree_changed, timeout=2000):
        (tmp_path / "new_note.md").write_text("# New")

    watcher.stop()


def test_tree_changed_emitted_on_new_subfolder(qtbot, tmp_path: Path) -> None:
    _make_vault(tmp_path)
    watcher = VaultWatcher()
    watcher.watch(str(tmp_path))

    with qtbot.waitSignal(watcher.tree_changed, timeout=2000):
        (tmp_path / "NewFolder").mkdir()

    watcher.stop()

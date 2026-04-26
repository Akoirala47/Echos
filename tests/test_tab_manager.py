"""Unit tests for TabManager and EditorTab.

Requires pytest-qt (``qtbot`` fixture supplies a QApplication).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from PyQt6.QtWidgets import QMessageBox, QWidget

from echos.ui.editor_tab import EditorTab
from echos.ui.tab_manager import TabManager


@pytest.fixture
def manager(qtbot) -> TabManager:
    echoes = QWidget()
    mgr = TabManager(echoes)
    qtbot.addWidget(mgr.tab_widget)
    return mgr


@pytest.fixture
def md_file(tmp_path: Path) -> Path:
    f = tmp_path / "note.md"
    f.write_text("# Hello\n\nTest content.")
    return f


# ---------------------------------------------------------------------------
# Echoes tab invariants
# ---------------------------------------------------------------------------

def test_echoes_tab_is_always_index_zero(manager: TabManager) -> None:
    assert manager.tab_widget.count() == 1
    assert manager.tab_widget.tabText(0) == "Echos"


def test_echoes_tab_close_is_ignored(manager: TabManager) -> None:
    manager.close_tab(0)
    assert manager.tab_widget.count() == 1


def test_echoes_tab_has_no_close_button(manager: TabManager) -> None:
    from PyQt6.QtWidgets import QTabBar
    btn = manager.tab_widget.tabBar().tabButton(0, QTabBar.ButtonPosition.RightSide)
    assert btn is None


# ---------------------------------------------------------------------------
# open_file
# ---------------------------------------------------------------------------

def test_open_file_creates_new_tab(manager: TabManager, md_file: Path) -> None:
    manager.open_file(str(md_file))
    assert manager.tab_widget.count() == 2


def test_open_file_sets_tab_label_to_filename(manager: TabManager, md_file: Path) -> None:
    manager.open_file(str(md_file))
    assert manager.tab_widget.tabText(1) == md_file.name


def test_open_file_focuses_new_tab(manager: TabManager, md_file: Path) -> None:
    manager.open_file(str(md_file))
    assert manager.tab_widget.currentIndex() == 1


def test_open_same_file_twice_does_not_duplicate_tab(
    manager: TabManager, md_file: Path
) -> None:
    manager.open_file(str(md_file))
    manager.open_file(str(md_file))
    assert manager.tab_widget.count() == 2


def test_open_same_file_twice_focuses_existing_tab(
    manager: TabManager, md_file: Path
) -> None:
    manager.open_file(str(md_file))
    # Switch back to Echoes tab
    manager.tab_widget.setCurrentIndex(0)
    # Open the same file again — should focus index 1
    manager.open_file(str(md_file))
    assert manager.tab_widget.currentIndex() == 1


def test_open_two_different_files_creates_two_tabs(
    manager: TabManager, tmp_path: Path
) -> None:
    f1 = tmp_path / "a.md"
    f2 = tmp_path / "b.md"
    f1.write_text("# A")
    f2.write_text("# B")
    manager.open_file(str(f1))
    manager.open_file(str(f2))
    assert manager.tab_widget.count() == 3


# ---------------------------------------------------------------------------
# current_editor
# ---------------------------------------------------------------------------

def test_current_editor_is_none_on_echoes_tab(manager: TabManager) -> None:
    assert manager.current_editor() is None


def test_current_editor_returns_editor_tab(manager: TabManager, md_file: Path) -> None:
    manager.open_file(str(md_file))
    assert isinstance(manager.current_editor(), EditorTab)


# ---------------------------------------------------------------------------
# close_tab (no unsaved changes)
# ---------------------------------------------------------------------------

def test_close_file_tab_removes_it(manager: TabManager, md_file: Path) -> None:
    manager.open_file(str(md_file))
    manager.close_tab(1)
    assert manager.tab_widget.count() == 1


def test_close_file_tab_allows_reopening(
    manager: TabManager, md_file: Path
) -> None:
    manager.open_file(str(md_file))
    manager.close_tab(1)
    manager.open_file(str(md_file))
    assert manager.tab_widget.count() == 2


# ---------------------------------------------------------------------------
# EditorTab — load / mode / save
# ---------------------------------------------------------------------------

def test_editor_tab_loads_file_content(qtbot, md_file: Path) -> None:
    tab = EditorTab()
    qtbot.addWidget(tab)
    tab.load_file(str(md_file))
    assert "Hello" in tab.get_content()


def test_editor_tab_starts_in_preview_mode(qtbot, md_file: Path) -> None:
    tab = EditorTab()
    qtbot.addWidget(tab)
    tab.load_file(str(md_file))
    assert tab._mode == "preview"


def test_editor_tab_mode_switch(qtbot, md_file: Path) -> None:
    tab = EditorTab()
    qtbot.addWidget(tab)
    tab.load_file(str(md_file))
    tab.set_mode("edit")
    assert tab._mode == "edit"
    assert not tab._editor.isReadOnly()
    tab.set_mode("raw")
    assert tab._editor.isReadOnly()
    tab.set_mode("preview")
    assert tab._stack.currentIndex() == 0


def test_editor_tab_dirty_flag_after_edit(qtbot, md_file: Path) -> None:
    tab = EditorTab()
    qtbot.addWidget(tab)
    tab.load_file(str(md_file))
    tab.set_mode("edit")
    assert not tab.has_unsaved_changes()
    tab._editor.setPlainText("# Modified")
    assert tab.has_unsaved_changes()


def test_editor_tab_save_clears_dirty(qtbot, md_file: Path) -> None:
    tab = EditorTab()
    qtbot.addWidget(tab)
    tab.load_file(str(md_file))
    tab.set_mode("edit")
    tab._editor.setPlainText("# Modified")
    assert tab.has_unsaved_changes()
    tab.save_file()
    assert not tab.has_unsaved_changes()
    assert md_file.read_text(encoding="utf-8") == "# Modified"


def test_editor_tab_save_is_atomic(qtbot, tmp_path: Path) -> None:
    """save_file must use write-then-rename so no partial writes are visible."""
    f = tmp_path / "atomic.md"
    f.write_text("original")
    tab = EditorTab()
    qtbot.addWidget(tab)
    tab.load_file(str(f))
    tab.set_mode("edit")
    tab._editor.setPlainText("updated")
    tab.save_file()
    assert f.read_text(encoding="utf-8") == "updated"
    # No leftover temp file
    assert not any(tmp_path.glob(".echos_*.tmp"))

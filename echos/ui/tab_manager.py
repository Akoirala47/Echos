"""TabManager — multi-tab wrapper around QTabWidget.

Tab 0 is the pinned Echoes tab (recording + notes view) and cannot be closed.
All other tabs are ``EditorTab`` instances for vault notes.

Keyboard shortcuts (registered on the tab widget):
  ⌘W       — close current file tab
  ⌘⇧T     — reopen last closed file tab

Colours and typography follow ``echos.utils.theme``.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QMessageBox,
    QTabWidget,
    QWidget,
)

from echos.ui.editor_tab import EditorTab
from echos.ui.tab_bar import EchosTabBar
from echos.utils.theme import (
    ACCENT, BORDER_SOFT, PANEL_BG, WINDOW_BG,
    TAB_ACTIVE_TEXT, TAB_INACTIVE_TEXT,
)

_TAB_QSS = f"""
QTabWidget::pane {{
    border: none;
    background: {PANEL_BG};
}}
QTabBar {{
    background: {WINDOW_BG};
    border-bottom: 1px solid {BORDER_SOFT};
}}
QTabBar::tab {{
    background: {WINDOW_BG};
    color: {TAB_INACTIVE_TEXT};
    font-size: 12px;
    font-weight: 500;
    padding: 6px 6px 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
    min-width: 80px;
}}
QTabBar::tab:selected {{
    color: {TAB_ACTIVE_TEXT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TAB_ACTIVE_TEXT};
    background: rgba(0,0,0,0.03);
}}
QTabBar::scroller {{
    width: 20px;
}}
"""


class TabManager:
    """Owns a ``QTabWidget`` and manages file-tab lifecycle.

    Parameters
    ----------
    echoes_widget:
        The main recording/notes widget placed in the pinned Echoes tab.
    """

    def __init__(self, echoes_widget: QWidget) -> None:
        self._tabs = QTabWidget()
        self._tabs.setTabBar(EchosTabBar())
        self._tabs.setStyleSheet(_TAB_QSS)
        self._tabs.setDocumentMode(True)
        # We manage close buttons ourselves (EchosTabBar paints themed × buttons).
        # setTabsClosable(False) prevents Qt from creating its own grey button.
        self._tabs.setTabsClosable(False)
        self._tabs.tabBar().tabCloseRequested.connect(self._on_close_requested)

        # Pinned Echoes tab at index 0 — EchosTabBar strips its close button
        self._tabs.addTab(echoes_widget, "Echos")

        # path → tab index for open file tabs
        self._path_to_index: dict[str, int] = {}
        # LIFO stack for ⌘⇧T reopen
        self._closed_stack: list[str] = []

        # ── Keyboard shortcuts ────────────────────────────────────────────────
        close_sc = QShortcut(QKeySequence("Ctrl+W"), self._tabs)
        close_sc.activated.connect(self._close_current)

        reopen_sc = QShortcut(QKeySequence("Ctrl+Shift+T"), self._tabs)
        reopen_sc.activated.connect(self._reopen_last_closed)

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def tab_widget(self) -> QTabWidget:
        return self._tabs

    def open_file(self, path: str) -> None:
        """Open *path* in an editor tab, or focus it if already open."""
        if path in self._path_to_index:
            self._tabs.setCurrentIndex(self._path_to_index[path])
            return

        tab = EditorTab()
        tab.load_file(path)
        tab.file_saved.connect(self._on_file_saved)

        label = Path(path).name
        idx = self._tabs.addTab(tab, label)
        self._path_to_index[path] = idx
        self._tabs.setCurrentIndex(idx)

    def close_tab(self, index: int) -> None:
        """Close the tab at *index*.  Index 0 (Echoes) is always a no-op."""
        if index == 0:
            return

        widget = self._tabs.widget(index)
        if isinstance(widget, EditorTab) and widget.has_unsaved_changes():
            name = Path(widget.file_path()).name if widget.file_path() else "this file"
            reply = QMessageBox.question(
                self._tabs,
                "Unsaved Changes",
                f"Save changes to \"{name}\" before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Save:
                widget.save_file()

        path = widget.file_path() if isinstance(widget, EditorTab) else None
        self._tabs.removeTab(index)
        if path:
            self._path_to_index.pop(path, None)
            self._closed_stack.append(path)  # push to reopen stack
        self._rebuild_index_map()

    def current_editor(self) -> EditorTab | None:
        """Return the currently visible ``EditorTab``, or ``None`` for Echoes tab."""
        w = self._tabs.currentWidget()
        return w if isinstance(w, EditorTab) else None

    # ── Shortcut handlers ──────────────────────────────────────────────────────

    def _close_current(self) -> None:
        idx = self._tabs.currentIndex()
        if idx > 0:
            self.close_tab(idx)

    def _reopen_last_closed(self) -> None:
        while self._closed_stack:
            path = self._closed_stack.pop()
            if Path(path).exists():
                self.open_file(path)
                return
            # Skip paths that no longer exist on disk and try the next one

    # ── Internal ───────────────────────────────────────────────────────────────

    def _on_close_requested(self, index: int) -> None:
        self.close_tab(index)

    def _on_file_saved(self, path: str) -> None:
        if path in self._path_to_index:
            idx = self._path_to_index[path]
            self._tabs.setTabText(idx, Path(path).name)

    def _rebuild_index_map(self) -> None:
        """Rebuild path→index after a tab removal (indices shift down by one)."""
        self._path_to_index.clear()
        for i in range(1, self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, EditorTab) and w.file_path():
                self._path_to_index[w.file_path()] = i

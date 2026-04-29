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

    def __init__(self, echoes_widget: QWidget | None) -> None:
        self._tabs = QTabWidget()
        self._is_primary = echoes_widget is not None
        self._tabs.setTabBar(EchosTabBar(is_primary=self._is_primary))
        self._tabs.setStyleSheet(_TAB_QSS)
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(False)
        self._tabs.tabBar().tabCloseRequested.connect(self._on_close_requested)

        if echoes_widget is not None:
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

    def open_file(self, path: str, vault_root: str = "") -> None:
        """Open *path* in an editor tab, or focus it if already open."""
        if path in self._path_to_index:
            self._tabs.setCurrentIndex(self._path_to_index[path])
            return

        tab = EditorTab()
        tab.load_file(path, vault_root=vault_root)
        tab.file_saved.connect(self._on_file_saved)

        label = Path(path).name
        idx = self._tabs.addTab(tab, label)
        self._path_to_index[path] = idx
        self._tabs.setCurrentIndex(idx)

    def close_tab(self, index: int) -> None:
        """Close the tab at *index*.

        In the primary pane index 0 is the pinned Echos tab — never closeable.
        In secondary panes every tab is a file tab and can be closed.
        """
        if index == 0 and self._is_primary:
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

    def close_all_tabs(self) -> None:
        """Close all file tabs (no unsaved-changes dialog). Used when pane is closed."""
        start = 1 if self._is_primary else 0
        for i in range(self._tabs.count() - 1, start - 1, -1):
            self._tabs.removeTab(i)
        self._path_to_index.clear()

    def close_tabs_for_path(self, path: str) -> None:
        """Silently close any tab whose file is at *path* (no unsaved-changes dialog)."""
        to_close = [
            i for i in range(self._tabs.count())
            if isinstance(self._tabs.widget(i), EditorTab)
            and self._tabs.widget(i).file_path() == path
        ]
        for idx in sorted(to_close, reverse=True):
            self._path_to_index.pop(path, None)
            self._tabs.removeTab(idx)
        self._rebuild_index_map()

    def rename_tab_path(self, old_path: str, new_path: str) -> None:
        """Update path map and tab label when a vault file is renamed on disk."""
        if old_path not in self._path_to_index:
            return
        idx = self._path_to_index.pop(old_path)
        self._path_to_index[new_path] = idx
        self._tabs.setTabText(idx, Path(new_path).name)
        widget = self._tabs.widget(idx)
        if isinstance(widget, EditorTab):
            widget._path = Path(new_path)

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

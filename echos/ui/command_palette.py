"""CommandPalette — unified quick-open + command launcher.

Opened with Ctrl+Shift+P (⌘⇧P on macOS).

Two result categories:
  Files   — vault .md files matched by fuzzy substring on filename/path
  Commands — internal app actions, prefixed with '>' in the query

Keyboard: ↑/↓ navigate, Enter activates, Escape closes.
Clicking outside the dialog also closes it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from echos.utils.theme import (
    ACCENT, BORDER_SOFT, PANEL_BG, TEXT, TEXT_FAINT, TEXT_MUTED, WINDOW_BG,
)

_ITEM_FILE    = 0
_ITEM_COMMAND = 1


def _fuzzy_score(query: str, target: str) -> float:
    """Subsequence fuzzy match. Returns 0.0 if no match, >0 if match.

    Higher score for consecutive character runs.
    """
    if not query:
        return 1.0
    q = query.lower()
    t = target.lower()
    qi = 0
    consecutive = 0
    score = 0.0
    for ti, ch in enumerate(t):
        if qi < len(q) and ch == q[qi]:
            qi += 1
            consecutive += 1
            score += 1.0 + consecutive * 0.5
        else:
            consecutive = 0
    if qi < len(q):
        return 0.0  # not all chars matched
    return score / max(len(t), 1)


class _ResultItem(QWidget):
    """Two-line item: primary name (bold) + secondary path (muted)."""

    def __init__(
        self,
        primary: str,
        secondary: str = "",
        kind: int = _ITEM_FILE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.primary = primary
        self.secondary = secondary

        lbl_primary = QLabel(primary)
        lbl_primary.setStyleSheet(
            f"font-size: 12.5px; font-weight: 600; color: {TEXT}; background: transparent;"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 5, 12, 5)
        row.setSpacing(8)

        if secondary:
            lbl_secondary = QLabel(secondary)
            lbl_secondary.setStyleSheet(
                f"font-size: 10.5px; color: {TEXT_FAINT}; background: transparent;"
            )
            row.addWidget(lbl_primary, 1)
            row.addWidget(lbl_secondary)
        else:
            row.addWidget(lbl_primary)
            row.addStretch()


class CommandPalette(QDialog):
    """Borderless quick-open dialog."""

    file_selected = pyqtSignal(str)   # absolute path of selected file

    def __init__(
        self,
        vault_path: str,
        commands: list[tuple[str, Callable]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setWindowOpacity(0.97)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setModal(True)
        self.setFixedSize(540, 380)

        self._vault_path = vault_path
        self._commands: list[tuple[str, Callable]] = commands
        self._vault_files: list[Path] = []
        self._load_vault_files()

        self._build_ui()
        self._center_on_parent(parent)

        # Close when focus leaves
        self.installEventFilter(self)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"QDialog {{ background: {PANEL_BG}; border: 1px solid {BORDER_SOFT};"
            f" border-radius: 8px; }}"
        )

        # Search input
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search files or type > for commands…")
        self._search.setFixedHeight(44)
        self._search.setStyleSheet(
            f"QLineEdit {{"
            f" background: {PANEL_BG}; border: none;"
            f" border-bottom: 1px solid {BORDER_SOFT};"
            f" font-size: 14px; color: {TEXT}; padding: 0 14px;"
            f"}}"
            f"QLineEdit:focus {{ border-bottom-color: {ACCENT}; }}"
        )
        self._search.textChanged.connect(self._on_query_changed)

        # Results list
        self._list = QListWidget()
        self._list.setFrameShape(QListWidget.Shape.NoFrame)
        self._list.setStyleSheet(
            f"QListWidget {{ background: {PANEL_BG}; border: none; outline: 0; }}"
            f"QListWidget::item {{ border-radius: 4px; }}"
            f"QListWidget::item:selected {{ background: rgba(194,65,12,0.12); }}"
            f"QListWidget::item:hover:!selected {{ background: rgba(0,0,0,0.04); }}"
        )
        self._list.itemActivated.connect(self._on_activated)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)
        layout.addWidget(self._search)
        layout.addWidget(self._list, 1)

        self._on_query_changed("")

    # ── Vault file loading ────────────────────────────────────────────────────

    def _load_vault_files(self) -> None:
        if not self._vault_path:
            return
        root = Path(self._vault_path)
        if not root.is_dir():
            return
        try:
            self._vault_files = [
                p for p in root.rglob("*.md")
                if not any(part.startswith(".") for part in p.parts)
            ]
        except Exception:
            pass

    # ── Results filtering ─────────────────────────────────────────────────────

    def _on_query_changed(self, query: str) -> None:
        self._list.clear()
        q = query.strip()

        if q.startswith(">"):
            self._populate_commands(q[1:].strip())
        else:
            self._populate_files(q)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _populate_files(self, query: str) -> None:
        root = Path(self._vault_path) if self._vault_path else None
        scored: list[tuple[float, Path]] = []
        for path in self._vault_files:
            rel = str(path.relative_to(root)) if root else path.name
            score = _fuzzy_score(query, rel) if query else 1.0
            if score > 0:
                scored.append((score, path))
        scored.sort(key=lambda x: -x[0])

        for _, path in scored[:50]:
            rel = str(path.relative_to(root)) if root else path.name
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, (_ITEM_FILE, str(path)))
            widget = _ResultItem(path.stem, rel, kind=_ITEM_FILE)
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

    def _populate_commands(self, query: str) -> None:
        for name, cb in self._commands:
            score = _fuzzy_score(query, name) if query else 1.0
            if score > 0:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, (_ITEM_COMMAND, cb))
                widget = _ResultItem(f"> {name}", kind=_ITEM_COMMAND)
                item.setSizeHint(widget.sizeHint())
                self._list.addItem(item)
                self._list.setItemWidget(item, widget)

    # ── Activation ────────────────────────────────────────────────────────────

    def _on_activated(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, payload = data
        self.accept()
        if kind == _ITEM_FILE:
            self.file_selected.emit(payload)
        elif kind == _ITEM_COMMAND and callable(payload):
            payload()

    # ── Keyboard navigation ───────────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self._list.currentItem()
            if item:
                self._on_activated(item)
        elif key == Qt.Key.Key_Up:
            row = self._list.currentRow()
            if row > 0:
                self._list.setCurrentRow(row - 1)
        elif key == Qt.Key.Key_Down:
            row = self._list.currentRow()
            if row < self._list.count() - 1:
                self._list.setCurrentRow(row + 1)
        else:
            # Route typing to the search field
            self._search.setFocus()
            super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.WindowDeactivate:
            self.reject()
        return super().eventFilter(obj, event)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _center_on_parent(self, parent: QWidget | None) -> None:
        if parent:
            geo = parent.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 3
            self.move(x, y)

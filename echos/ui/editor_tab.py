"""EditorTab — a single file tab with Preview / Raw / Edit mode toggle.

Three modes per open file:
  Preview — QTextBrowser renders markdown (same pipeline as NotesPanel)
  Raw     — QTextEdit, monospace, read-only
  Edit    — QTextEdit, monospace, editable; tracks unsaved changes

All colours come from ``echos.utils.theme``.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Literal

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from echos.utils.theme import (
    ACCENT, BORDER_SOFT, PANEL_BG, SIDEBAR_BG,
    TEXT, TEXT_FAINT, TEXT_MUTED,
    border_soft, panel_bg, text, text_faint, text_muted,
    notes_css,
)

logger = logging.getLogger(__name__)

_MODE = Literal["preview", "raw", "edit"]


def _md_to_html(md_text: str) -> str:
    try:
        import markdown
        body = markdown.markdown(
            md_text,
            extensions=["fenced_code", "tables", "nl2br"],
        )
    except Exception:
        import html
        body = f"<pre>{html.escape(md_text)}</pre>"
    css = notes_css()
    return f"<html><head><style>{css}</style></head><body>{body}</body></html>"


def _mode_btn(label: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setCheckable(True)
    btn.setFlat(True)
    btn.setFixedHeight(22)
    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    btn.setStyleSheet(
        f"QPushButton {{"
        f" background: transparent; border: 1px solid {BORDER_SOFT};"
        f" font-size: 10.5px; font-weight: 600; letter-spacing: 0.3px;"
        f" color: {TEXT_MUTED}; padding: 0 9px; border-radius: 4px;"
        f"}}"
        f"QPushButton:checked {{"
        f" background: {ACCENT}; color: #fff; border-color: {ACCENT};"
        f"}}"
        f"QPushButton:hover:!checked {{ color: {TEXT}; }}"
    )
    return btn


class EditorTab(QWidget):
    """One tab for a single vault file."""

    content_changed = pyqtSignal()
    file_saved = pyqtSignal(str)  # emits the file path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path: Path | None = None
        self._mode: _MODE = "preview"
        self._dirty: bool = False

        self.setStyleSheet(f"background: {PANEL_BG};")
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Header ──────────────────────────────────────────────────────────
        self._file_lbl = QLabel("—")
        self._file_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px;"
            f" color: {TEXT_FAINT}; text-transform: uppercase;"
        )

        self._btn_preview = _mode_btn("Preview")
        self._btn_raw     = _mode_btn("Raw")
        self._btn_edit    = _mode_btn("Edit")
        self._btn_preview.setChecked(True)

        self._btn_preview.clicked.connect(lambda: self._switch_mode("preview"))
        self._btn_raw.clicked.connect(lambda: self._switch_mode("raw"))
        self._btn_edit.clicked.connect(lambda: self._switch_mode("edit"))

        self._save_btn = QPushButton("Save")
        self._save_btn.setEnabled(False)
        self._save_btn.setFixedHeight(22)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: {TEXT}; color: #fff; border: none;"
            f" border-radius: 4px; font-size: 10.5px; font-weight: 600; padding: 0 10px; }}"
            f"QPushButton:hover {{ background: #3a3830; }}"
            f"QPushButton:disabled {{ background: {BORDER_SOFT}; color: {TEXT_FAINT}; }}"
        )
        self._save_btn.clicked.connect(self.save_file)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(12, 0, 8, 0)
        header_row.setSpacing(6)
        header_row.addWidget(self._file_lbl)
        header_row.addStretch()
        header_row.addWidget(self._btn_preview)
        header_row.addWidget(self._btn_raw)
        header_row.addWidget(self._btn_edit)
        header_row.addSpacing(8)
        header_row.addWidget(self._save_btn)

        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(
            f"background: {PANEL_BG}; border-bottom: 1px solid {BORDER_SOFT};"
        )
        header.setLayout(header_row)

        # ── Content ──────────────────────────────────────────────────────────
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background: {PANEL_BG}; border: none; }}"
        )
        self._browser.document().setDocumentMargin(24)

        self._editor = QTextEdit()
        self._editor.setAcceptRichText(False)
        self._editor.setStyleSheet(
            f"QTextEdit {{ background: {SIDEBAR_BG}; color: {TEXT}; border: none;"
            f" font-family: 'JetBrains Mono', 'Menlo', 'Monaco', monospace;"
            f" font-size: 12px; line-height: 1.55; }}"
        )
        self._editor.document().setDocumentMargin(20)
        self._editor.textChanged.connect(self._on_text_changed)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._browser)  # 0 = preview
        self._stack.addWidget(self._editor)   # 1 = raw / edit

        # ── Layout ───────────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._stack, 1)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_file(self, path: str) -> None:
        self._path = Path(path)
        try:
            content = self._path.read_text(encoding="utf-8")
        except Exception:
            logger.exception("EditorTab: could not read %s", path)
            content = f"# Could not read file\n\n{path}"

        # Suppress dirty signal while loading
        self._editor.blockSignals(True)
        self._editor.setPlainText(content)
        self._editor.blockSignals(False)

        self._dirty = False
        self._save_btn.setEnabled(False)
        self._file_lbl.setText(self._path.name.upper())
        self._apply_mode(self._mode)

    def get_content(self) -> str:
        return self._editor.toPlainText()

    def save_file(self) -> None:
        if not self._path:
            return
        content = self._editor.toPlainText()
        try:
            fd, tmp = tempfile.mkstemp(
                dir=self._path.parent, suffix=".tmp", prefix=".echos_"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp, self._path)
        except Exception:
            logger.exception("EditorTab: save failed for %s", self._path)
            try:
                os.unlink(tmp)
            except Exception:
                pass
            return
        self._dirty = False
        self._save_btn.setEnabled(False)
        self.file_saved.emit(str(self._path))

    def set_mode(self, mode: _MODE) -> None:
        self._switch_mode(mode)

    def file_path(self) -> str:
        return str(self._path) if self._path else ""

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    # ── Internal ───────────────────────────────────────────────────────────────

    def _switch_mode(self, mode: _MODE) -> None:
        self._mode = mode
        for btn, m in (
            (self._btn_preview, "preview"),
            (self._btn_raw, "raw"),
            (self._btn_edit, "edit"),
        ):
            btn.setChecked(m == mode)
        self._apply_mode(mode)

    def _apply_mode(self, mode: _MODE) -> None:
        if mode == "preview":
            self._browser.setHtml(_md_to_html(self._editor.toPlainText()))
            self._stack.setCurrentIndex(0)
            self._editor.setReadOnly(True)
        elif mode == "raw":
            self._editor.setReadOnly(True)
            self._stack.setCurrentIndex(1)
        else:  # edit
            self._editor.setReadOnly(False)
            self._stack.setCurrentIndex(1)

    def _on_text_changed(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._save_btn.setEnabled(True)
        self.content_changed.emit()

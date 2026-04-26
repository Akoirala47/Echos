from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from echos.utils.theme import border_soft, panel_bg, text, text_faint


def _mini_btn(label: str) -> QPushButton:
    from echos.utils.theme import TEXT, TEXT_FAINT
    btn = QPushButton(label.upper())
    btn.setFlat(True)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; border: none;"
        f" font-size: 10px; font-weight: 600; letter-spacing: 0.5px;"
        f" color: {TEXT_FAINT}; padding: 1px 8px; }}"
        f"QPushButton:hover {{ color: {TEXT}; }}"
    )
    return btn


class TranscriptPanel(QWidget):
    """Live transcript editor — warm panel with mockup-style header."""

    export_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {panel_bg()}; border-right: 1px solid {border_soft()};"
        )

        # Header
        header_lbl = QLabel("LIVE TRANSCRIPT")
        header_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px;"
            f" color: {text_faint()}; text-transform: uppercase;"
        )

        self._clear_btn = _mini_btn("Clear")
        self._clear_btn.clicked.connect(self._on_clear)

        self._export_btn = _mini_btn("Export .txt")
        self._export_btn.clicked.connect(self._on_export)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(12, 0, 8, 0)
        header_row.setSpacing(4)
        header_row.addWidget(header_lbl)
        header_row.addStretch()
        header_row.addWidget(self._clear_btn)
        header_row.addWidget(self._export_btn)

        header_widget = QWidget()
        header_widget.setFixedHeight(32)
        header_widget.setStyleSheet(f"border-bottom: 1px solid {border_soft()};")
        header_widget.setLayout(header_row)

        # Text editor
        self._editor = QTextEdit()
        self._editor.setPlaceholderText(
            "Press Start Recording to begin. The live transcript will appear here as you speak."
        )
        self._editor.setAcceptRichText(False)
        self._editor.setStyleSheet(
            f"QTextEdit {{ background: {panel_bg()}; color: {text()};"
            f" border: none; font-size: 13.5px; line-height: 1.7;"
            f" font-family: -apple-system, 'Inter', sans-serif; }}"
        )
        self._editor.document().setDocumentMargin(18)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header_widget)
        layout.addWidget(self._editor, 1)
        self.setLayout(layout)

    # ── Public API ─────────────────────────────────────────────────────────────

    def append_text(self, text_chunk: str) -> None:
        cursor = self._editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if self._editor.toPlainText():
            cursor.insertText(" ")
        cursor.insertText(text_chunk)
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()

    def get_text(self) -> str:
        return self._editor.toPlainText()

    def clear(self) -> None:
        self._editor.clear()

    def set_read_only(self, read_only: bool) -> None:
        self._editor.setReadOnly(read_only)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_clear(self) -> None:
        self._editor.clear()

    def _on_export(self) -> None:
        text_content = self._editor.toPlainText()
        if not text_content.strip():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Transcript", "transcript.txt", "Text files (*.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text_content)

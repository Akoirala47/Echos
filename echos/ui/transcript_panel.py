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


class TranscriptPanel(QWidget):
    """Live transcript editor.

    Text is appended in real time as AudioWorker emits chunks.
    The user can freely edit the transcript before generating notes.
    """

    export_requested = pyqtSignal(str)  # full transcript text

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Header toolbar
        header = QLabel("LIVE TRANSCRIPT")
        header.setStyleSheet("font-size: 11px; font-weight: 600; color: #888;")

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFlat(True)
        self._clear_btn.setStyleSheet("font-size: 11px; color: #888;")
        self._clear_btn.clicked.connect(self._on_clear)

        self._export_btn = QPushButton("Export .txt")
        self._export_btn.setFlat(True)
        self._export_btn.setStyleSheet("font-size: 11px; color: #888;")
        self._export_btn.clicked.connect(self._on_export)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(header)
        toolbar.addStretch()
        toolbar.addWidget(self._clear_btn)
        toolbar.addWidget(self._export_btn)

        # Text editor
        self._editor = QTextEdit()
        self._editor.setPlaceholderText(
            "Transcript will appear here as you record\u2026"
        )
        self._editor.setAcceptRichText(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.addLayout(toolbar)
        layout.addWidget(self._editor, 1)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_text(self, text: str) -> None:
        """Append a new transcript fragment. Scrolls to the bottom."""
        cursor = self._editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if self._editor.toPlainText():
            cursor.insertText(" ")
        cursor.insertText(text)
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()

    def get_text(self) -> str:
        return self._editor.toPlainText()

    def clear(self) -> None:
        self._editor.clear()

    def set_read_only(self, read_only: bool) -> None:
        self._editor.setReadOnly(read_only)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_clear(self) -> None:
        self._editor.clear()

    def _on_export(self) -> None:
        text = self._editor.toPlainText()
        if not text.strip():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Transcript", "transcript.txt", "Text files (*.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)

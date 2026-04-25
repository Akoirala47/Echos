from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

_DOT_SIZE = 10


class _StatusDot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor("#888888")
        self.setFixedSize(_DOT_SIZE, _DOT_SIZE)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(self._color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, _DOT_SIZE, _DOT_SIZE)
        p.end()


class StatusBarWidget(QWidget):
    """Full-width status bar at the bottom of the main window.

    Signals
    -------
    save_requested
        Emitted when the user clicks "Save to Obsidian".
    open_requested
        Emitted when the user clicks "Open in Obsidian".
    """

    save_requested = pyqtSignal()
    open_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setAutoFillBackground(True)
        self.setStyleSheet("border-top: 1px solid palette(mid);")

        self._dot = _StatusDot(self)
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("font-size: 12px;")

        self._vault_label = QLabel("")
        self._vault_label.setStyleSheet("font-size: 12px; color: palette(placeholderText);")

        self._save_btn = QPushButton("Save to Obsidian")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self.save_requested)

        self._open_btn = QPushButton("Open in Obsidian")
        self._open_btn.setVisible(False)
        self._open_btn.clicked.connect(self.open_requested)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._status_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(QLabel("\u00b7"), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._vault_label, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._open_btn)
        layout.addWidget(self._save_btn)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_status(self, color: str, text: str) -> None:
        self._dot.set_color(color)
        self._status_label.setText(text)

    def set_vault_path(self, path: str) -> None:
        self._vault_label.setText(path)

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_btn.setEnabled(enabled)

    def set_open_visible(self, visible: bool) -> None:
        self._open_btn.setVisible(visible)

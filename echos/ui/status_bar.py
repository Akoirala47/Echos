"""Status bar — bottom strip showing state + vault path + context actions.

Buttons shown per state:
  recording / paused  →  End Session  (triggers confirm dialog)
  stopped / notes_done / saved  →  New Session
  notes_done / saved  →  Save to Obsidian
  saved               →  Open in Obsidian (replaces Save button)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from echos.utils.theme import (
    border, ready_color, recording_color, statusbar_bg, text_faint, text_muted,
)


class _Dot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor("#a09e93")
        self.setFixedSize(7, 7)

    def set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(self._color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 7, 7)
        p.end()


def _ghost_btn(label: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(22)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; border: 1px solid {border()};"
        f" color: {text_muted()}; padding: 0 10px; border-radius: 4px;"
        f" font-size: 11px; font-weight: 500; }}"
        f"QPushButton:hover {{ background: rgba(0,0,0,0.05); }}"
        f"QPushButton:pressed {{ background: rgba(0,0,0,0.09); }}"
    )
    return btn


class StatusBarWidget(QWidget):
    """Full-width status bar at the bottom of the main window."""

    save_requested = pyqtSignal()
    open_requested = pyqtSignal()
    end_session_clicked = pyqtSignal()
    new_session_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(30)
        # WA_StyledBackground ensures our background paints solidly regardless
        # of the Fusion palette — prevents the faint inherited window colour.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            f"StatusBarWidget {{ background: {statusbar_bg()}; }}"
        )
        # Top border drawn as a separate QWidget so it never cascades
        # (kept as a sibling in MainWindow's layout, not a child of this widget)

        self._dot = _Dot(self)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"font-size: 11.5px; color: {text_muted()};")

        self._sep = QLabel("·")
        self._sep.setStyleSheet(f"font-size: 11.5px; color: {text_faint()};")

        self._vault_lbl = QLabel("")
        self._vault_lbl.setStyleSheet(f"font-size: 11.5px; color: {text_faint()};")

        # Action buttons (right side)
        self._end_btn = _ghost_btn("■  End Session")
        self._end_btn.setVisible(False)
        self._end_btn.clicked.connect(self.end_session_clicked)

        self._new_btn = _ghost_btn("＋  New Session")
        self._new_btn.setVisible(False)
        self._new_btn.clicked.connect(self.new_session_clicked)

        self._open_btn = _ghost_btn("Open in Obsidian")
        self._open_btn.setVisible(False)
        self._open_btn.clicked.connect(self.open_requested)

        self._save_btn = QPushButton("Save to Obsidian")
        self._save_btn.setFixedHeight(22)
        self._save_btn.setVisible(False)
        self._save_btn.clicked.connect(self.save_requested)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: {text_muted()}; color: #fff; border: none;"
            f" padding: 0 10px; border-radius: 4px; font-size: 11px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #5a5850; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)
        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._status_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._sep, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._vault_lbl, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._end_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._new_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._open_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._save_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setLayout(layout)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_status(self, color: str, text: str) -> None:
        self._dot.set_color(color)
        self._status_lbl.setText(text)

    def set_vault_path(self, path: str) -> None:
        self._vault_lbl.setText(path)

    def update_for_state(self, state: str, saved_filename: str = "") -> None:
        """Show/hide action buttons based on app state."""
        recording_or_paused = state in ("recording", "paused")
        post_session = state in ("stopped", "generating", "notes_done", "saved")
        can_save = state in ("notes_done",)
        is_saved = state == "saved"

        self._end_btn.setVisible(recording_or_paused)
        self._new_btn.setVisible(post_session)
        self._open_btn.setVisible(is_saved)
        self._save_btn.setVisible(can_save or is_saved)

        if is_saved:
            label = f"✓ Saved · {saved_filename}" if saved_filename else "✓ Saved"
            self._save_btn.setText(label)
            self._save_btn.setStyleSheet(
                f"QPushButton {{ background: {ready_color()}; color: #fff; border: none;"
                f" padding: 0 10px; border-radius: 4px; font-size: 11px; font-weight: 600; }}"
            )
        else:
            self._save_btn.setText("Save to Obsidian")
            self._save_btn.setStyleSheet(
                f"QPushButton {{ background: {text_muted()}; color: #fff; border: none;"
                f" padding: 0 10px; border-radius: 4px; font-size: 11px; font-weight: 600; }}"
                f"QPushButton:hover {{ background: #5a5850; }}"
            )

        # Dot colour
        _dot_map = {
            "idle": "#a09e93",
            "recording": recording_color(),
            "paused": "#c47a17",
            "stopped": "#a09e93",
            "generating": "#2563eb",
            "notes_done": ready_color(),
            "saved": ready_color(),
        }
        self._dot.set_color(_dot_map.get(state, "#a09e93"))

    # Kept for backward compat with AppController
    def set_save_enabled(self, enabled: bool) -> None:
        self._save_btn.setVisible(enabled)

    def set_open_visible(self, visible: bool) -> None:
        self._open_btn.setVisible(visible)

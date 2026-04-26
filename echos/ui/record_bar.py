"""Record bar — two-row layout matching the UI mockup.

Row 1 (header):  colour dot · topic name · breadcrumb path · Session N input
Row 2 (controls): PrimaryButton · status pill · waveform · elapsed timer

The primary button cycles: Start Recording → Pause → Resume.
It NEVER shows "Stop". Stopping the session is done via the End Session
button in the status bar (which shows a confirmation dialog).
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from echos.ui.widgets.waveform import WaveformWidget
from echos.utils.theme import (
    TEXT, TEXT_FAINT, TEXT_MUTED,
    accent, border_soft, paused_color, ready_color, recording_color,
    text, text_faint, text_muted, window_bg,
)


# ── State label / dot colour table ────────────────────────────────────────────

_STATE_INFO: dict[str, tuple[str, str]] = {
    "idle":       ("#a09e93", "Ready"),
    "recording":  ("recording", "Recording"),
    "paused":     ("paused",    "Paused"),
    "stopped":    ("#a09e93",   "Session complete"),
    "generating": ("#2563eb",   "Generating notes…"),
    "notes_done": ("ready",     "Notes ready"),
    "saved":      ("ready",     "Saved"),
}


def _resolve_dot(key: str) -> str:
    """Resolve a colour key (may be a theme alias or a hex literal)."""
    if key == "recording":
        return recording_color()
    if key == "paused":
        return paused_color()
    if key == "ready":
        return ready_color()
    return key


# ── Clickable breadcrumb ──────────────────────────────────────────────────────

class _BreadcrumbWidget(QWidget):
    """Renders a folder path as clickable segments separated by › glyphs.

    Clicking a segment emits ``segment_clicked`` with the cumulative path up to
    and including that segment (e.g. clicking "CS446" in "School/CS446/Lectures"
    emits "School/CS446").
    """

    segment_clicked = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(2)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_path(self, folder_path: str) -> None:
        """Rebuild segments for *folder_path* (e.g. ``"School/CS446/Lectures"``)."""
        # Remove all existing child widgets
        while self._row.count():
            item = self._row.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)  # type: ignore[arg-type]

        parts = [p for p in folder_path.replace("\\", "/").split("/") if p]
        for i, part in enumerate(parts):
            if i > 0:
                sep = QLabel("›")
                sep.setStyleSheet(
                    f"font-size: 10px; color: {TEXT_FAINT}; background: transparent;"
                )
                self._row.addWidget(sep)

            cumulative = "/".join(parts[: i + 1])
            btn = QPushButton(part)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none;"
                f" font-size: 11px; color: {TEXT_FAINT}; padding: 0 2px; }}"
                f"QPushButton:hover {{ color: {TEXT_MUTED}; }}"
            )
            btn.clicked.connect(lambda _checked, p=cumulative: self.segment_clicked.emit(p))
            self._row.addWidget(btn)

        self._row.addStretch()


def _fmt_elapsed(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


# ── Status dot (animated during recording) ────────────────────────────────────

class _StatusDot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor("#a09e93")
        self.setFixedSize(8, 8)

    def set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(self._color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 8, 8)
        p.end()


# ── Primary button ────────────────────────────────────────────────────────────

class _PrimaryButton(QPushButton):
    """Start Recording / Pause / Resume — never Stop."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setMinimumWidth(150)
        self._state = "idle"
        self._refresh()

    def set_state(self, state: str) -> None:
        self._state = state
        self._refresh()

    def _refresh(self) -> None:
        s = self._state
        if s == "idle":
            self.setText("●  Start Recording")
            self.setStyleSheet(
                f"QPushButton {{ background: {recording_color()}; color: #fff; border: none;"
                f" border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 18px; }}"
                f"QPushButton:hover {{ background: #e83535; }}"
                f"QPushButton:pressed {{ background: #b82525; }}"
            )
        elif s == "recording":
            self.setText("⏸  Pause")
            self.setStyleSheet(
                f"QPushButton {{ background: {paused_color()}; color: #fff; border: none;"
                f" border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 18px; }}"
                f"QPushButton:hover {{ background: #d88a25; }}"
                f"QPushButton:pressed {{ background: #b07020; }}"
            )
        elif s == "paused":
            self.setText("▶  Resume")
            self.setStyleSheet(
                f"QPushButton {{ background: {ready_color()}; color: #fff; border: none;"
                f" border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 18px; }}"
                f"QPushButton:hover {{ background: #229c57; }}"
                f"QPushButton:pressed {{ background: #1a7a44; }}"
            )
        else:
            # stopped / generating / notes_done / saved — show a neutral "New Session" button
            self.setText("●  Start New Session")
            self.setStyleSheet(
                f"QPushButton {{ background: #fff; color: {text()}; border: 1px solid {border_soft()};"
                f" border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 18px; }}"
                f"QPushButton:hover {{ background: #f5f3ee; }}"
                f"QPushButton:pressed {{ background: #ece9e2; }}"
            )


# ── Status pill ───────────────────────────────────────────────────────────────

class _StatusPill(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dot = _StatusDot(self)

        self._label = QLabel("Ready", self)
        self._label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {text_muted()};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 12, 5)
        layout.setSpacing(7)
        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setLayout(layout)
        self._apply_idle()

    def set_state(self, state: str) -> None:
        dot_key, label = _STATE_INFO.get(state, ("#a09e93", "Ready"))
        hex_color = _resolve_dot(dot_key)
        self._dot.set_color(hex_color)
        self._label.setText(label)
        self._label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {hex_color};")

        if state == "recording":
            bg = "rgba(217,47,47,0.08)"
            bdr = "rgba(217,47,47,0.20)"
        elif state == "paused":
            bg = "rgba(196,122,23,0.08)"
            bdr = "rgba(196,122,23,0.20)"
        else:
            bg = "rgba(0,0,0,0.03)"
            bdr = border_soft()
        self.setStyleSheet(
            f"background: {bg}; border: 1px solid {bdr}; border-radius: 16px;"
        )

    def _apply_idle(self) -> None:
        self.setStyleSheet(
            f"background: rgba(0,0,0,0.03); border: 1px solid {border_soft()}; border-radius: 16px;"
        )


# ── Main record bar ───────────────────────────────────────────────────────────

class RecordBarWidget(QWidget):
    """Two-row record bar.

    Signals
    -------
    record_clicked
        Emitted for Start / Pause / Resume (primary button).
    end_session_clicked
        Emitted when the user wants to end the session (triggers confirm dialog
        in AppController; actual stop happens after confirmation).
    """

    record_clicked      = pyqtSignal()
    end_session_clicked = pyqtSignal()
    breadcrumb_clicked  = pyqtSignal(str)  # cumulative folder path segment

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._elapsed = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        self._build_ui()
        self.set_state("idle")

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        bg    = window_bg()
        b_soft = border_soft()

        # Use WA_StyledBackground so our background QSS paints even without
        # setAutoFillBackground — and avoid inheriting borders to children.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"RecordBarWidget {{ background: {bg}; }}")

        # ── Row 1: topic header ───────────────────────────────────────────────
        self._dot_lbl = QLabel()
        self._dot_lbl.setFixedSize(9, 9)
        self._dot_lbl.setStyleSheet(
            f"border-radius: 4px; background: #c2410c;"
        )

        self._topic_lbl = QLabel("No topic selected")
        self._topic_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {text()};"
        )

        self._breadcrumb = _BreadcrumbWidget()
        self._breadcrumb.segment_clicked.connect(self.breadcrumb_clicked)

        self._session_spin = QSpinBox()
        self._session_spin.setRange(1, 999)
        self._session_spin.setValue(1)
        self._session_spin.setPrefix("Session  ")
        self._session_spin.setFixedHeight(26)
        self._session_spin.setMinimumWidth(90)
        self._session_spin.setStyleSheet(
            f"QSpinBox {{ font-size: 11px; color: {text_muted()};"
            f" background: transparent; border: 1px solid {b_soft};"
            f" border-radius: 4px; padding: 2px 8px; }}"
            f"QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}"
        )

        header_row = QHBoxLayout()
        header_row.setContentsMargins(18, 10, 18, 8)
        header_row.setSpacing(8)
        header_row.addWidget(self._dot_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self._topic_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self._breadcrumb, 1, Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self._session_spin, 0, Qt.AlignmentFlag.AlignVCenter)

        header_widget = QWidget()
        header_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_widget.setStyleSheet(f"QWidget {{ background: {bg}; }}")
        header_widget.setLayout(header_row)

        # 1-px separator — explicit widget, no CSS cascade
        sep1 = QWidget()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background: {b_soft};")

        # ── Row 2: controls ───────────────────────────────────────────────────
        self._primary_btn = _PrimaryButton()
        self._primary_btn.clicked.connect(self._on_primary_clicked)

        self._status_pill = _StatusPill()

        self.waveform = WaveformWidget()
        self.waveform.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self._timer_lbl = QLabel("0:00")
        self._timer_lbl.setStyleSheet(
            f"font-family: 'Menlo', 'Monaco', monospace;"
            f" font-size: 14px; font-weight: 500; color: {text_muted()};"
            f" min-width: 48px;"
        )
        self._timer_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(18, 10, 18, 10)
        controls_row.setSpacing(14)
        controls_row.addWidget(self._primary_btn)
        controls_row.addWidget(self._status_pill)
        controls_row.addWidget(self.waveform, 1)
        controls_row.addWidget(self._timer_lbl)

        controls_widget = QWidget()
        controls_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        controls_widget.setStyleSheet(f"QWidget {{ background: {bg}; }}")
        controls_widget.setLayout(controls_row)

        # Bottom separator — explicit widget
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {b_soft};")

        # ── Outer layout ──────────────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(header_widget)
        outer.addWidget(sep1)
        outer.addWidget(controls_widget)
        outer.addWidget(sep2)
        self.setLayout(outer)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Update all visual elements for the given app state."""
        self._primary_btn.set_state(state)
        self._status_pill.set_state(state)

        if state == "recording":
            if not self._timer.isActive():
                self._timer.start()
            self.waveform.set_active(True, paused=False)
        elif state == "paused":
            self._timer.stop()
            self.waveform.set_active(True, paused=True)
        else:
            self._timer.stop()
            self.waveform.set_active(False)

    def set_topic(self, name: str, color: str, folder_path: str) -> None:
        """Update the header row.

        *folder_path* is the raw vault-relative path, e.g. ``"School/CS446/Lectures"``.
        Each segment is rendered as a separate clickable button.
        """
        self._topic_lbl.setText(name)
        self._dot_lbl.setStyleSheet(f"border-radius: 4px; background: {color};")
        self._breadcrumb.set_path(folder_path)
        self.waveform.set_accent_color(QColor(color))

    def set_session_num(self, num: int) -> None:
        self._session_spin.setValue(num)

    def get_session_num(self) -> int:
        return self._session_spin.value()

    def reset_timer(self) -> None:
        self._elapsed = 0
        self._timer_lbl.setText("0:00")

    # kept for backward compat with AppController
    def get_lecture_num(self) -> int:
        return self.get_session_num()

    def set_lecture_num(self, num: int) -> None:
        self.set_session_num(num)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_primary_clicked(self) -> None:
        self.record_clicked.emit()

    def _on_tick(self) -> None:
        self._elapsed += 1
        self._timer_lbl.setText(_fmt_elapsed(self._elapsed))

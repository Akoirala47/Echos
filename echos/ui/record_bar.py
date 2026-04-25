from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

from echos.ui.widgets.waveform import WaveformWidget


def _dark() -> bool:
    app = QApplication.instance()
    if app is None:
        return False
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _btn_styles(state: str) -> str:
    dark = _dark()
    base = (
        "border-radius: 8px;"
        "padding: 10px 28px;"
        "font-size: 14px;"
        "font-weight: 600;"
    )
    if state == "recording":
        bg    = "#3D1515" if dark else "#FFF2F1"
        bdr   = "#E74C3C"
        color = "#FF6B6B" if dark else "#C0392B"
        hover = "#4A1A1A" if dark else "#FFE0DE"
    elif state == "paused":
        bg    = "#3A2D00" if dark else "#FFF8E7"
        bdr   = "#F39C12"
        color = "#FFBE44" if dark else "#B7770D"
        hover = "#453400" if dark else "#FFF0C0"
    else:  # idle
        bg    = "#3A3A3A" if dark else "palette(button)"
        bdr   = "#666666" if dark else "#BBBBBB"
        color = "#FFFFFF" if dark else "palette(buttonText)"
        hover = "#444444" if dark else "#EBEBEB"

    return (
        f"QPushButton {{ background: {bg}; border: 1.5px solid {bdr}; color: {color}; {base} }}"
        f"QPushButton:hover {{ background: {hover}; }}"
    )


class RecordBarWidget(QWidget):
    """Top bar: record button, waveform, timer, lecture number."""

    record_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(80)

        # Record / stop button
        self._record_btn = QPushButton("\u25cf  Start Recording")
        self._record_btn.setStyleSheet(_btn_styles("idle"))
        self._record_btn.setFixedHeight(48)
        self._record_btn.setMinimumWidth(190)
        self._record_btn.clicked.connect(self.record_clicked)

        # Pause / resume button (hidden when idle)
        self._pause_btn = QPushButton("\u23f8  Pause")
        self._pause_btn.setVisible(False)
        self._pause_btn.setFixedHeight(38)
        self._pause_btn.setMinimumWidth(100)
        self._pause_btn.clicked.connect(self.pause_clicked)

        # Waveform
        self._waveform = WaveformWidget(self)

        # Timer
        self._timer_label = QLabel("0:00")
        self._timer_label.setStyleSheet(
            "font-size: 15px; font-weight: 500; min-width: 48px;"
        )
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Lecture spinner
        self._lecture_spin = QSpinBox()
        self._lecture_spin.setRange(1, 999)
        self._lecture_spin.setValue(1)
        self._lecture_spin.setPrefix("Lecture ")
        self._lecture_spin.setMinimumWidth(120)
        self._lecture_spin.setFixedHeight(32)

        # Pulsing dot timer
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(600)
        self._pulse_timer.timeout.connect(self._toggle_pulse)
        self._pulse_on = True

        # Elapsed timer
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._elapsed_seconds = 0

        left = QHBoxLayout()
        left.setSpacing(10)
        left.addWidget(self._record_btn)
        left.addWidget(self._pause_btn)

        right = QHBoxLayout()
        right.setSpacing(12)
        right.addWidget(self._waveform, 1)
        right.addWidget(self._timer_label)
        right.addWidget(self._lecture_spin)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(16)
        row.addLayout(left)
        row.addLayout(right, 1)
        self.setLayout(row)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def set_state(self, state: str) -> None:
        if state == "recording":
            self._record_btn.setStyleSheet(_btn_styles("recording"))
            self._record_btn.setText("\u25fc  Stop Recording")
            self._pause_btn.setText("\u23f8  Pause")
            self._pause_btn.setVisible(True)
            self._pulse_timer.start()
            self._elapsed_timer.start()
            self._waveform.set_show_waveform(True)
        elif state == "paused":
            self._record_btn.setStyleSheet(_btn_styles("paused"))
            self._record_btn.setText("\u25fc  Stop Recording")
            self._pause_btn.setText("\u25b6  Resume")
            self._pause_btn.setVisible(True)
            self._pulse_timer.stop()
            self._elapsed_timer.stop()
        else:
            self._record_btn.setStyleSheet(_btn_styles("idle"))
            self._record_btn.setText("\u25cf  Start Recording")
            self._pause_btn.setVisible(False)
            self._pulse_timer.stop()
            self._elapsed_timer.stop()

    def reset_timer(self) -> None:
        self._elapsed_seconds = 0
        self._timer_label.setText("0:00")

    def set_lecture_num(self, num: int) -> None:
        self._lecture_spin.setValue(num)

    def get_lecture_num(self) -> int:
        return self._lecture_spin.value()

    @property
    def waveform(self) -> WaveformWidget:
        return self._waveform

    def _tick_elapsed(self) -> None:
        self._elapsed_seconds += 1
        m, s = divmod(self._elapsed_seconds, 60)
        self._timer_label.setText(f"{m}:{s:02d}")

    def _toggle_pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        dot = "\u25cf" if self._pulse_on else "\u25cb"
        self._record_btn.setText(f"{dot}  Stop Recording")

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from echos.ui.widgets.waveform import WaveformWidget

# Button style sheets for each recording state
_STYLE_IDLE = (
    "QPushButton {"
    "  background: white;"
    "  border: 1.5px solid #AAAAAA;"
    "  border-radius: 6px;"
    "  padding: 8px 24px;"
    "  font-size: 14px;"
    "  font-weight: 600;"
    "}"
    "QPushButton:hover { background: #F5F5F5; }"
)

_STYLE_RECORDING = (
    "QPushButton {"
    "  background: #FFF2F1;"
    "  border: 1.5px solid #E74C3C;"
    "  border-radius: 6px;"
    "  padding: 8px 24px;"
    "  font-size: 14px;"
    "  font-weight: 600;"
    "  color: #C0392B;"
    "}"
    "QPushButton:hover { background: #FFE8E6; }"
)

_STYLE_PAUSED = (
    "QPushButton {"
    "  background: #FFF8E7;"
    "  border: 1.5px solid #F39C12;"
    "  border-radius: 6px;"
    "  padding: 8px 24px;"
    "  font-size: 14px;"
    "  font-weight: 600;"
    "  color: #D68910;"
    "}"
    "QPushButton:hover { background: #FFF3CC; }"
)


class RecordBarWidget(QWidget):
    """Top bar housing the record/stop button, waveform, timer, and lecture number.

    Signals
    -------
    record_clicked
        Emitted when the main record/stop button is pressed.
    pause_clicked
        Emitted when the pause/resume button is pressed.
    """

    record_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setStyleSheet("background: #FAFAFA; border-bottom: 1px solid #E5E5E5;")

        # Record / stop button
        self._record_btn = QPushButton("\u25cf  Start Recording")
        self._record_btn.setStyleSheet(_STYLE_IDLE)
        self._record_btn.setFixedHeight(46)
        self._record_btn.setMinimumWidth(180)
        self._record_btn.clicked.connect(self.record_clicked)

        # Pause / resume button (hidden when idle)
        self._pause_btn = QPushButton("\u23f8  Pause")
        self._pause_btn.setVisible(False)
        self._pause_btn.setFixedHeight(38)
        self._pause_btn.setMinimumWidth(100)
        self._pause_btn.clicked.connect(self.pause_clicked)

        # Waveform
        self._waveform = WaveformWidget(self)

        # Elapsed timer label
        self._timer_label = QLabel("0:00")
        self._timer_label.setStyleSheet(
            "font-size: 14px; font-weight: 500; color: #555; min-width: 48px;"
        )
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Lecture number spinner
        self._lecture_spin = QSpinBox()
        self._lecture_spin.setRange(1, 999)
        self._lecture_spin.setValue(1)
        self._lecture_spin.setPrefix("Lecture ")
        self._lecture_spin.setMinimumWidth(120)
        self._lecture_spin.setFixedHeight(32)

        # Pulsing dot timer (toggles a red dot in the button text while recording)
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(600)
        self._pulse_timer.timeout.connect(self._toggle_pulse)
        self._pulse_on = True

        # Elapsed tick timer
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._elapsed_seconds = 0

        # Layout: left group (record btn + pause btn) | waveform | timer | lecture spinner
        left = QHBoxLayout()
        left.setSpacing(8)
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
        """Update visual state. state: 'idle' | 'recording' | 'paused'."""
        if state == "recording":
            self._record_btn.setStyleSheet(_STYLE_RECORDING)
            self._record_btn.setText("\u25fc  Stop Recording")
            self._pause_btn.setText("\u23f8  Pause")
            self._pause_btn.setVisible(True)
            self._pulse_timer.start()
            self._elapsed_timer.start()
            self._waveform.set_show_waveform(True)

        elif state == "paused":
            self._record_btn.setStyleSheet(_STYLE_PAUSED)
            self._record_btn.setText("\u25fc  Stop Recording")
            self._pause_btn.setText("\u25b6  Resume")
            self._pause_btn.setVisible(True)
            self._pulse_timer.stop()
            self._elapsed_timer.stop()

        else:  # idle / stopped
            self._record_btn.setStyleSheet(_STYLE_IDLE)
            self._record_btn.setText("\u25cf  Start Recording")
            self._pause_btn.setVisible(False)
            self._pulse_timer.stop()
            self._elapsed_timer.stop()

    def reset_timer(self) -> None:
        self._elapsed_seconds = 0
        self._timer_label.setText("0:00")

    # ------------------------------------------------------------------
    # Lecture number
    # ------------------------------------------------------------------

    def set_lecture_num(self, num: int) -> None:
        self._lecture_spin.setValue(num)

    def get_lecture_num(self) -> int:
        return self._lecture_spin.value()

    # ------------------------------------------------------------------
    # Waveform proxy
    # ------------------------------------------------------------------

    @property
    def waveform(self) -> WaveformWidget:
        return self._waveform

    # ------------------------------------------------------------------
    # Internal timers
    # ------------------------------------------------------------------

    def _tick_elapsed(self) -> None:
        self._elapsed_seconds += 1
        m, s = divmod(self._elapsed_seconds, 60)
        self._timer_label.setText(f"{m}:{s:02d}")

    def _toggle_pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        dot = "\u25cf" if self._pulse_on else "\u25cb"
        self._record_btn.setText(f"{dot}  Stop Recording")

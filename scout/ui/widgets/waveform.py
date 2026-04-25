from __future__ import annotations

from PyQt6.QtCore import QRectF, QTimer, Qt, pyqtSlot
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QSizePolicy, QWidget

_BAR_COUNT = 20
_BAR_GAP = 2
_MIN_HEIGHT_RATIO = 0.05   # bars never collapse to zero
_LERP_FACTOR = 0.25        # smoothing per tick (lower = smoother)
_TICK_MS = 33              # ~30 fps


class WaveformWidget(QWidget):
    """Animated bar waveform driven by real RMS audio levels.

    Call set_level(rms) from the AudioWorker's audio_level signal.
    When show_waveform is False the widget renders a flat baseline.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_level: float = 0.0
        self._bar_heights: list[float] = [_MIN_HEIGHT_RATIO] * _BAR_COUNT
        self._show_waveform: bool = True
        self._accent_color: QColor = QColor("#2980B9")

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(32)

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @pyqtSlot(float)
    def set_level(self, rms: float) -> None:
        self._target_level = max(_MIN_HEIGHT_RATIO, min(rms, 1.0))

    def set_show_waveform(self, enabled: bool) -> None:
        self._show_waveform = enabled
        self.update()

    def set_accent_color(self, color: QColor) -> None:
        self._accent_color = color
        self.update()

    # ------------------------------------------------------------------
    # Internal animation tick
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        if not self._show_waveform:
            return
        import math, random
        # Each bar independently lerps toward the current target ±jitter.
        changed = False
        for i in range(_BAR_COUNT):
            # Add per-bar jitter so bars don't all move identically.
            jitter = random.uniform(-0.15, 0.15) * self._target_level
            target = max(_MIN_HEIGHT_RATIO, min(self._target_level + jitter, 1.0))
            current = self._bar_heights[i]
            new_val = current + (target - current) * _LERP_FACTOR
            if abs(new_val - current) > 0.001:
                self._bar_heights[i] = new_val
                changed = True
        if changed:
            self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        bar_w = max(1.0, (w - (_BAR_COUNT - 1) * _BAR_GAP) / _BAR_COUNT)

        color = self._accent_color if self._show_waveform else QColor("#CCCCCC")
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(_BAR_COUNT):
            x = i * (bar_w + _BAR_GAP)
            height_ratio = self._bar_heights[i] if self._show_waveform else _MIN_HEIGHT_RATIO
            bar_h = max(2.0, height_ratio * h)
            y = (h - bar_h) / 2.0
            path = QPainterPath()
            radius = min(bar_w / 2, 2.0)
            path.addRoundedRect(QRectF(x, y, bar_w, bar_h), radius, radius)
            painter.drawPath(path)

        painter.end()

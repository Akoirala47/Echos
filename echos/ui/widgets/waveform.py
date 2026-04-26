"""Animated bar waveform.

Idle    → grey bars at pre-set varying heights (natural frozen look)
Active  → accent-colored bars, driven by real RMS + time-based wave animation
Paused  → accent-colored bars, dimmed, no movement
"""

from __future__ import annotations

import math
import random
import time

from PyQt6.QtCore import QRectF, QTimer, Qt, pyqtSlot
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QSizePolicy, QWidget

_BAR_COUNT   = 36
_BAR_W       = 2.5
_BAR_GAP     = 2.0
_MIN_H       = 0.08
_LERP        = 0.28       # higher = snappier response
_TICK_MS     = 33         # ~30 fps
_WAVE_SPEED  = 3.5        # radians/second
_WAVE_CYCLES = 3.5        # sine cycles across bar span
_MIN_ACTIVE  = 0.18       # guaranteed minimum visual height when recording

# Idle frozen heights — look like a natural waveform snapshot
_IDLE_HEIGHTS: list[float] = [
    0.22, 0.38, 0.52, 0.30, 0.46, 0.27, 0.58, 0.42,
    0.18, 0.47, 0.63, 0.33, 0.24, 0.52, 0.28, 0.44,
    0.20, 0.55, 0.35, 0.28, 0.48, 0.62, 0.32, 0.42,
    0.22, 0.38, 0.52, 0.44, 0.26, 0.58, 0.30, 0.46,
    0.20, 0.36, 0.48, 0.28,
]

_IDLE_COLOR = QColor("#c8c5bc")
_PAUSED_DIM = 0.35


class WaveformWidget(QWidget):
    """36-bar animated waveform.

    When recording:
      • Each bar has a unique sine-wave phase so bars move in a rolling wave.
      • The wave amplitude scales with real RMS audio level (set_level).
      • Even at silence there's always visible movement (floor = _MIN_ACTIVE).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_level: float = 0.0
        self._smooth_level: float = 0.0
        self._bar_heights: list[float] = list(_IDLE_HEIGHTS[:_BAR_COUNT])
        self._is_active: bool = False
        self._is_paused: bool = False

        from echos.utils.theme import ACCENT
        self._accent_color = QColor(ACCENT)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(32)

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ── Public API ────────────────────────────────────────────────────────────

    @pyqtSlot(float)
    def set_level(self, rms: float) -> None:
        """Called ~30× per second from AudioWorker with a 0–1 RMS value."""
        self._target_level = max(0.0, min(rms * 3.0, 1.0))   # boost for visibility

    def set_active(self, active: bool, paused: bool = False) -> None:
        self._is_active = active
        self._is_paused = paused
        if not active:
            self._bar_heights = list(_IDLE_HEIGHTS[:_BAR_COUNT])
            self._target_level = 0.0
            self._smooth_level = 0.0
        self.update()

    def set_accent_color(self, color: QColor) -> None:
        self._accent_color = color
        self.update()

    # ── Animation tick ────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if not self._is_active or self._is_paused:
            return

        # Smooth the incoming RMS level (exponential moving average)
        self._smooth_level += (_target := max(self._target_level, _MIN_ACTIVE)) - self._smooth_level
        self._smooth_level = min(max(self._smooth_level, _MIN_ACTIVE), 1.0)
        level = self._smooth_level

        t = time.monotonic()
        changed = False
        for i in range(_BAR_COUNT):
            # Rolling sine wave with per-bar phase offset
            phase = (i / _BAR_COUNT) * _WAVE_CYCLES * math.pi * 2 + t * _WAVE_SPEED
            wave_h = (math.sin(phase) * 0.5 + 0.5)          # 0…1 sine envelope
            target = max(_MIN_H, min(wave_h * level + random.uniform(-0.04, 0.04), 1.0))

            cur = self._bar_heights[i]
            nv  = cur + (target - cur) * _LERP
            if abs(nv - cur) > 0.001:
                self._bar_heights[i] = nv
                changed = True

        if changed:
            self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._is_paused:
            painter.setOpacity(_PAUSED_DIM)

        color = self._accent_color if self._is_active else _IDLE_COLOR
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)

        h = self.height()
        for i in range(_BAR_COUNT):
            x     = i * (_BAR_W + _BAR_GAP)
            bar_h = max(2.0, self._bar_heights[i] * h)
            y     = (h - bar_h) / 2.0
            path  = QPainterPath()
            path.addRoundedRect(QRectF(x, y, _BAR_W, bar_h), 1.2, 1.2)
            painter.drawPath(path)

        painter.end()

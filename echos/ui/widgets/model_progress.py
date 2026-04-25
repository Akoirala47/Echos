from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_TOTAL_BYTES = 3 * 1024 ** 3  # ~3 GB for Whisper large-v3


def _fmt_bytes(n: int) -> str:
    if n >= 1024 ** 3:
        return f"{n / 1024**3:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024**2:.0f} MB"
    return f"{n / 1024:.0f} KB"


def _fmt_speed(bps: float) -> str:
    mbps = bps / 1024 ** 2
    return f"{mbps:.0f} MB/s" if mbps >= 1 else f"{bps/1024:.0f} KB/s"


def _fmt_eta(remaining_bytes: int, bps: float) -> str:
    if bps <= 0:
        return "…"
    secs = remaining_bytes / bps
    if secs < 60:
        return f"{int(secs)}s left"
    mins = int(secs / 60)
    return f"{mins}m left"


class ModelProgressWidget(QWidget):
    """Download progress bar with stats label and a 'Background' button.

    Signals
    -------
    background_requested
        Emitted when the user clicks "Background" to dismiss the wizard
        and let the download continue invisibly.
    """

    background_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)

        self._stats_label = QLabel("Starting download…")
        self._bg_button = QPushButton("Background")
        self._bg_button.clicked.connect(self.background_requested)

        bottom = QHBoxLayout()
        bottom.addWidget(self._stats_label, 1)
        bottom.addWidget(self._bg_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._bar)
        layout.addLayout(bottom)
        self.setLayout(layout)

        self._last_bytes_done: int = 0
        self._speed_bps: float = 0.0

    def update_progress(
        self,
        bytes_done: int,
        bytes_total: int,
        speed_bps: float = 0.0,
    ) -> None:
        """Refresh the progress bar and stats label."""
        total = bytes_total if bytes_total > 0 else _TOTAL_BYTES
        ratio = min(bytes_done / total, 1.0)
        self._bar.setValue(int(ratio * 1000))

        self._speed_bps = speed_bps
        done_str = _fmt_bytes(bytes_done)
        total_str = _fmt_bytes(total)
        remaining = max(total - bytes_done, 0)

        parts = [f"{done_str} of {total_str}"]
        if speed_bps > 0:
            parts.append(_fmt_speed(speed_bps))
            parts.append(_fmt_eta(remaining, speed_bps))
        self._stats_label.setText(" · ".join(parts))

    def mark_done(self) -> None:
        self._bar.setValue(1000)
        self._stats_label.setText("Download complete.")
        self._bg_button.setEnabled(False)

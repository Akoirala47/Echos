"""Non-intrusive update notification banner shown above the status bar."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QWidget,
)

from echos.utils.theme import (
    ACCENT, ACCENT_SOFT, BORDER_SOFT, TEXT, TEXT_FAINT, TEXT_MUTED,
)


def _action_btn(label: str, primary: bool = False) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(22)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: #fff; border: none; "
            f"padding: 0 12px; border-radius: 4px; font-size: 11px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #a83508; }}"
            f"QPushButton:pressed {{ background: #92300a; }}"
        )
    else:
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {ACCENT}; "
            f"color: {ACCENT}; padding: 0 10px; border-radius: 4px; "
            f"font-size: 11px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: rgba(194,65,12,0.08); }}"
        )
    return btn


class UpdateBanner(QWidget):
    """Slim 36px banner with three internal states: notify / installing / done."""

    update_accepted = pyqtSignal()   # user clicked "Update Now"
    update_dismissed = pyqtSignal()  # user clicked "Later" or ✕

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"UpdateBanner {{ background: {ACCENT_SOFT}; "
            f"border-top: 1px solid {BORDER_SOFT}; }}"
        )
        self.setVisible(False)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_notify_page())   # 0
        self._stack.addWidget(self._build_progress_page()) # 1
        self._stack.addWidget(self._build_done_page())     # 2

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _build_notify_page(self) -> QWidget:
        page = QWidget()
        self._notify_lbl = QLabel()
        self._notify_lbl.setStyleSheet(
            f"font-size: 12px; color: {TEXT}; background: transparent;"
        )

        self._update_btn = _action_btn("Update Now", primary=True)
        self._update_btn.clicked.connect(self.update_accepted)

        self._later_btn = _action_btn("Later")
        self._later_btn.clicked.connect(self.update_dismissed)

        dismiss = QPushButton("✕")
        dismiss.setFixedSize(22, 22)
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"color: {TEXT_FAINT}; font-size: 12px; }}"
            f"QPushButton:hover {{ color: {TEXT}; }}"
        )
        dismiss.clicked.connect(self.update_dismissed)

        lay = QHBoxLayout(page)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)
        lay.addWidget(self._notify_lbl, 1, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._update_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._later_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(dismiss, 0, Qt.AlignmentFlag.AlignVCenter)
        return page

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        self._progress_lbl = QLabel("Downloading update…")
        self._progress_lbl.setStyleSheet(
            f"font-size: 12px; color: {TEXT}; background: transparent;"
        )

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background: rgba(194,65,12,0.15); border: none; "
            f"border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}"
        )

        lay = QHBoxLayout(page)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(10)
        lay.addWidget(self._progress_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._progress_bar, 1, Qt.AlignmentFlag.AlignVCenter)
        return page

    def _build_done_page(self) -> QWidget:
        page = QWidget()
        lbl = QLabel("Update installed — restart Echos to apply it.")
        lbl.setStyleSheet(
            f"font-size: 12px; color: {TEXT}; background: transparent;"
        )

        restart_btn = _action_btn("Restart Now", primary=True)
        restart_btn.clicked.connect(self._on_restart)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"color: {TEXT_FAINT}; font-size: 12px; }}"
            f"QPushButton:hover {{ color: {TEXT}; }}"
        )
        close_btn.clicked.connect(self.setVisible)
        close_btn.clicked.connect(lambda: self.setVisible(False))

        lay = QHBoxLayout(page)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)
        lay.addWidget(lbl, 1, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(restart_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        return page

    # ── Public API ────────────────────────────────────────────────────────────

    def show_update(self, version: str) -> None:
        self._notify_lbl.setText(f"Echos {version} is available")
        self._stack.setCurrentIndex(0)
        self.setVisible(True)

    def show_progress(self, version: str) -> None:
        self._progress_lbl.setText(f"Downloading Echos {version}…")
        self._progress_bar.setValue(0)
        self._stack.setCurrentIndex(1)
        self.setVisible(True)

    def set_progress(self, done: int, total: int) -> None:
        if total > 0:
            self._progress_bar.setValue(int(done * 100 / total))
        else:
            self._progress_bar.setRange(0, 0)  # indeterminate

    def show_done(self) -> None:
        self._stack.setCurrentIndex(2)

    def show_error(self, message: str) -> None:
        self._notify_lbl.setText(f"Update failed: {message}")
        self._stack.setCurrentIndex(0)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _on_restart(self) -> None:
        import subprocess
        import sys

        from PyQt6.QtWidgets import QApplication

        subprocess.Popen(["/Applications/Echos.app/Contents/MacOS/Echos"])
        QApplication.quit()

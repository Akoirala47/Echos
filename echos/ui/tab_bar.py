"""EchosTabBar — warm-parchment styled QTabBar with custom × close buttons.

The Echoes tab (index 0) has no close button.
All other tabs get a hand-painted × button using theme colours.
``tabsClosable`` on the QTabWidget must be set to False — this class
manages all close buttons itself so Qt's default grey square never appears.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QTabBar, QWidget

from echos.utils.theme import TEXT, TEXT_FAINT


class _CloseButton(QAbstractButton):
    """A 16×16 hand-painted × button styled to match the warm-parchment theme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip("Close tab")
        self._hovered = False

    def sizeHint(self) -> QSize:
        return QSize(16, 16)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._hovered:
            p.setBrush(QColor(0, 0, 0, 26))   # rgba(0,0,0,0.10)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(self.rect()), 3, 3)

        color = QColor(TEXT) if self._hovered else QColor(TEXT_FAINT)
        pen = QPen(color, 1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)

        m = 4.5
        w, h = float(self.width()), float(self.height())
        p.drawLine(QPointF(m, m), QPointF(w - m, h - m))
        p.drawLine(QPointF(w - m, m), QPointF(m, h - m))
        p.end()


class EchosTabBar(QTabBar):
    """Custom tab bar that:

    - Replaces Qt's default close button with a theme-coloured × for every
      non-Echoes tab.  Call ``setTabsClosable(False)`` on the parent
      QTabWidget so Qt's own grey button is never created.
    - Ensures index 0 (Echoes) never has a close button.
    """

    def tabInserted(self, index: int) -> None:
        super().tabInserted(index)
        if index > 0:
            btn = _CloseButton(self)
            self.setTabButton(index, QTabBar.ButtonPosition.RightSide, btn)
            # Resolve the current index at click time so rearrangements don't break it
            btn.clicked.connect(lambda _=False, b=btn: self._emit_close_for(b))

        # Always strip any close button from index 0
        self.setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)

    def _emit_close_for(self, btn: QAbstractButton) -> None:
        for i in range(self.count()):
            if self.tabButton(i, QTabBar.ButtonPosition.RightSide) is btn:
                self.tabCloseRequested.emit(i)
                return

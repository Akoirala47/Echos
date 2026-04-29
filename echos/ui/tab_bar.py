"""EchosTabBar — warm-parchment styled QTabBar with custom × close buttons.

The Echoes tab (index 0) has no close button.
All other tabs get a hand-painted × button using theme colours.
``tabsClosable`` on the QTabWidget must be set to False — this class
manages all close buttons itself so Qt's default grey square never appears.

Drag-to-split: dragging any file tab more than DRAG_THRESHOLD pixels emits
``tab_drag_started(index, title)`` which SplitTabArea handles with visual
drop zones.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QMenu, QTabBar, QWidget

from echos.utils.theme import TEXT, TEXT_FAINT

_DRAG_THRESHOLD = 12  # px — intentionally low so drag starts quickly


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
            p.setBrush(QColor(0, 0, 0, 26))
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
    """Custom tab bar with theme close buttons and drag-to-split support."""

    tab_drag_started  = pyqtSignal(int, str)   # (tab_index, title)
    split_requested   = pyqtSignal(str)         # "right" or "down"
    close_pane_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, is_primary: bool = True) -> None:
        super().__init__(parent)
        self._is_primary = is_primary
        self._drag_start: QPoint | None = None
        self._drag_tab_idx: int = -1

    def tabInserted(self, index: int) -> None:
        super().tabInserted(index)
        if self._is_primary:
            # Index 0 is the pinned Echos tab — never gets a close button.
            # All subsequent file tabs do.
            if index > 0:
                btn = _CloseButton(self)
                self.setTabButton(index, QTabBar.ButtonPosition.RightSide, btn)
                btn.clicked.connect(lambda _=False, b=btn: self._emit_close_for(b))
            # Guard: always strip index-0 close button in case Qt re-adds one
            self.setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
            self.setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)
        else:
            # Secondary pane — every tab is a file tab and gets a close button
            btn = _CloseButton(self)
            self.setTabButton(index, QTabBar.ButtonPosition.RightSide, btn)
            btn.clicked.connect(lambda _=False, b=btn: self._emit_close_for(b))

    def _emit_close_for(self, btn: QAbstractButton) -> None:
        for i in range(self.count()):
            if self.tabButton(i, QTabBar.ButtonPosition.RightSide) is btn:
                self.tabCloseRequested.emit(i)
                return

    # ── Drag detection ────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self.tabAt(event.pos())
            # Only allow dragging real file tabs (index > 0)
            if idx > 0:
                self._drag_start = event.pos()
                self._drag_tab_idx = idx
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None and self._drag_tab_idx > 0:
            delta = event.pos() - self._drag_start
            dist = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
            if dist > _DRAG_THRESHOLD:
                idx = self._drag_tab_idx
                title = self.tabText(idx)
                # Clear drag state before emitting so re-entrant moves are no-ops
                self._drag_start = None
                self._drag_tab_idx = -1
                self.tab_drag_started.emit(idx, title)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None
        self._drag_tab_idx = -1
        super().mouseReleaseEvent(event)

    # ── Right-click context menu ──────────────────────────────────────────────

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("Split Right", lambda: self.split_requested.emit("right"))
        menu.addAction("Split Down",  lambda: self.split_requested.emit("down"))
        menu.addSeparator()
        menu.addAction("Close Pane",  self.close_pane_requested.emit)
        menu.exec(event.globalPos())

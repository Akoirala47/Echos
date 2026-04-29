"""SplitTabArea — hosts one or more TabManager panels in a QSplitter.

Drag-to-split flow
──────────────────
1. User starts dragging a file tab beyond the threshold.
2. EchosTabBar emits ``tab_drag_started(index, title)``.
3. SplitTabArea extracts the EditorTab widget from the source manager and
   immediately starts a ``_DragSession``.
4. _DragSession shows:
   • a small ghost label following the cursor
   • a translucent overlay on the SplitTabArea with 4 coloured drop zones
     (left / right / top / bottom, each ~28% of the relevant dimension)
5. When the user releases:
   • over a zone  → split in that orientation and move the tab there
   • outside area → open as a floating TearOffWindow
   • Escape        → cancel; put the tab back in its source manager
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from echos.ui.editor_tab import EditorTab
from echos.ui.tab_manager import TabManager
from echos.utils.theme import ACCENT, BORDER_SOFT, PANEL_BG, TEXT, TEXT_FAINT, WINDOW_BG

_ZONE_FRAC = 0.28   # fraction of width/height that counts as a drop zone


# ── Drag ghost ────────────────────────────────────────────────────────────────

class _DragGhost(QWidget):
    """Small dark label that follows the cursor during a tab drag."""

    def __init__(self, title: str) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "background: #2d2b26; border-radius: 5px; padding: 0;"
        )

        lbl = QLabel(f"  {title}  ")
        lbl.setStyleSheet(
            "color: #f6f5f1; font-size: 12px; font-weight: 500;"
            " padding: 5px 10px; background: transparent;"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(lbl)
        self.adjustSize()

    def follow(self, global_pos: QPoint) -> None:
        self.move(global_pos.x() + 14, global_pos.y() + 10)


# ── Drop-zone overlay ─────────────────────────────────────────────────────────

class _DropZoneOverlay(QWidget):
    """Translucent overlay drawn over the SplitTabArea showing drop zones.

    It is a tool-window (no taskbar entry) positioned to cover the
    SplitTabArea on screen.  Mouse events pass through (WA_TransparentForMouseEvents).
    """

    _INACTIVE = QColor(0, 0, 0, 0)          # transparent — no tint until hovered
    _ACTIVE   = QColor(166, 148, 112, 55)   # warm parchment tint
    _BORDER   = QColor(140, 124, 94, 180)   # darker parchment edge

    def __init__(self, split_area: "SplitTabArea") -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._split_area = split_area
        self._active: str = ""
        self._reposition()

    # ── Public ────────────────────────────────────────────────────────────────

    def set_active(self, zone: str) -> None:
        if zone != self._active:
            self._active = zone
            self.update()

    def zone_at(self, local_pos: QPoint) -> str:
        """Return zone name ("left"/"right"/"top"/"bottom") or "" for centre."""
        w, h = self.width(), self.height()
        x, y = local_pos.x(), local_pos.y()
        fw, fh = int(w * _ZONE_FRAC), int(h * _ZONE_FRAC)
        if x < fw:        return "left"
        if x > w - fw:    return "right"
        if y < fh:        return "top"
        if y > h - fh:    return "bottom"
        return ""

    def reposition(self) -> None:
        self._reposition()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _reposition(self) -> None:
        sa = self._split_area
        origin = sa.mapToGlobal(QPoint(0, 0))
        self.setGeometry(origin.x(), origin.y(), sa.width(), sa.height())

    def _zone_rect(self, zone: str) -> QRect:
        w, h = self.width(), self.height()
        fw, fh = int(w * _ZONE_FRAC), int(h * _ZONE_FRAC)
        if zone == "left":   return QRect(0,      0, fw,     h)
        if zone == "right":  return QRect(w - fw, 0, fw,     h)
        if zone == "top":    return QRect(0,       0, w,     fh)
        if zone == "bottom": return QRect(0, h - fh, w,     fh)
        return QRect()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for zone in ("left", "right", "top", "bottom"):
            rect = self._zone_rect(zone)
            color = self._ACTIVE if zone == self._active else self._INACTIVE
            p.fillRect(rect, color)
        if self._active:
            rect = self._zone_rect(self._active)
            pen = QPen(self._BORDER, 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(rect.adjusted(1, 1, -1, -1))

            # Label hint in the centre of the active zone
            p.setPen(QColor(80, 68, 50, 200))
            label_map = {
                "left": "← Split Left",  "right": "Split Right →",
                "top": "↑ Split Up",     "bottom": "Split Down ↓",
            }
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label_map[self._active])
        p.end()


# ── Drag session (global event filter) ───────────────────────────────────────

class _DragSession(QObject):
    """Manages a tab drag from start to finish via an app-level event filter."""

    finished = pyqtSignal(str)   # "left"/"right"/"top"/"bottom"/"float"/"cancel"

    def __init__(
        self,
        title: str,
        split_area: "SplitTabArea",
    ) -> None:
        super().__init__()
        self._split_area = split_area
        self._done = False

        self._ghost = _DragGhost(title)
        self._ghost.show()

        self._overlay = _DropZoneOverlay(split_area)
        self._overlay.show()
        self._overlay.raise_()

        QApplication.instance().installEventFilter(self)

    # ── QObject event filter ──────────────────────────────────────────────────

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if self._done:
            return False

        t = event.type()

        if t == QEvent.Type.MouseMove:
            pos = QCursor.pos()
            self._ghost.follow(pos)
            self._overlay.reposition()
            local = self._split_area.mapFromGlobal(pos)
            if self._split_area.rect().contains(local):
                self._overlay.set_active(self._overlay.zone_at(local))
            else:
                self._overlay.set_active("")
            return False

        if t == QEvent.Type.MouseButtonRelease:
            pos = QCursor.pos()
            local = self._split_area.mapFromGlobal(pos)
            if self._split_area.rect().contains(local):
                zone = self._overlay.zone_at(local)
                result = zone if zone else "float"
            else:
                result = "float"
            self._end(result)
            return False

        if t == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self._end("cancel")
                return True

        return False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _end(self, result: str) -> None:
        if self._done:
            return
        self._done = True
        QApplication.instance().removeEventFilter(self)
        self._ghost.close()
        self._ghost.deleteLater()
        self._overlay.close()
        self._overlay.deleteLater()
        self.finished.emit(result)


# ── Tear-off floating window ──────────────────────────────────────────────────

class TearOffWindow(QMainWindow):
    """Floating window containing a detached EditorTab."""

    def __init__(
        self,
        editor: EditorTab,
        file_path: str,
        split_area: "SplitTabArea",
    ) -> None:
        super().__init__(None)   # top-level — no parent to avoid parenting issues
        self._editor = editor
        self._file_path = file_path
        self._split_area = split_area

        name = Path(file_path).name if file_path else "Untitled"
        self.setWindowTitle(name)
        self.resize(860, 660)
        self.setStyleSheet(f"background: {WINDOW_BG};")

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {TEXT}; padding: 0 4px;"
        )
        dock_btn = QPushButton("Dock Back")
        dock_btn.setFixedHeight(26)
        dock_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: #fff; border: none;"
            f" border-radius: 4px; font-size: 11px; font-weight: 600; padding: 0 12px; }}"
            f"QPushButton:hover {{ background: #a83509; }}"
        )
        dock_btn.clicked.connect(self._on_dock)

        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet(
            f"background: {WINDOW_BG}; border-bottom: 1px solid {BORDER_SOFT};"
        )
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(12, 0, 12, 0)
        tl.setSpacing(8)
        tl.addWidget(name_lbl, 1)
        tl.addWidget(dock_btn)

        container = QWidget()
        cv = QVBoxLayout(container)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(toolbar)
        cv.addWidget(editor, 1)
        # QTabWidget.removeTab() hides the detached widget — un-hide it here
        # before setting as central widget so the layout renders it correctly.
        editor.show()
        self.setCentralWidget(container)

    def _on_dock(self) -> None:
        self._split_area.dock_tab(self._editor, self._file_path)
        # Remove from tracking list before close so the signal doesn't fire twice
        self._split_area._tearoff_windows.discard(self)
        self.close()

    def closeEvent(self, event) -> None:
        self._split_area._tearoff_windows.discard(self)
        super().closeEvent(event)


# ── SplitTabArea ──────────────────────────────────────────────────────────────

class SplitTabArea(QWidget):
    """Container widget that owns a QSplitter of TabManager panels."""

    def __init__(self, echoes_widget: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._managers: list[TabManager] = []
        self._active_manager_idx: int = 0
        self._tearoff_windows: set[TearOffWindow] = set()
        self._drag_session: _DragSession | None = None

        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {BORDER_SOFT}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._splitter)

        primary = TabManager(echoes_widget)
        self._add_manager(primary)

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def primary_manager(self) -> TabManager:
        return self._managers[0]

    @property
    def active_manager(self) -> TabManager:
        idx = self._active_manager_idx
        return self._managers[idx] if 0 <= idx < len(self._managers) else self._managers[0]

    def open_file(self, path: str, vault_root: str = "") -> None:
        self.active_manager.open_file(path, vault_root=vault_root)

    def split(self, orientation: Qt.Orientation) -> None:
        """Create a new pane and move the active editor tab into it."""
        self._splitter.setOrientation(orientation)
        new_manager = TabManager(None)
        self._add_manager(new_manager)

        # Move the currently active tab to the new pane
        src = self.active_manager
        idx = src.tab_widget.currentIndex()
        if idx > 0:  # Don't move the Echoes tab
            self._move_tab_to(src, idx, new_manager)

        # Equalise sizes
        total = self._splitter.width() if orientation == Qt.Orientation.Horizontal \
                else self._splitter.height()
        n = self._splitter.count()
        self._splitter.setSizes([total // n] * n)
        self._active_manager_idx = len(self._managers) - 1

    def close_pane(self, manager: TabManager) -> None:
        if manager is self._managers[0]:
            return
        idx = self._managers.index(manager)
        manager.close_all_tabs()
        self._splitter.widget(idx).setParent(None)  # type: ignore[arg-type]
        self._managers.pop(idx)
        self._active_manager_idx = max(0, self._active_manager_idx - 1)

    def dock_tab(self, editor: EditorTab, file_path: str) -> None:
        target = self.active_manager
        label = Path(file_path).name if file_path else "Untitled"
        idx = target._tabs.addTab(editor, label)
        if file_path:
            target._path_to_index[file_path] = idx
        target._tabs.setCurrentIndex(idx)
        target._rebuild_index_map()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _add_manager(self, manager: TabManager) -> None:
        self._managers.append(manager)
        self._splitter.addWidget(manager.tab_widget)
        manager.tab_widget.installEventFilter(self)
        self._connect_bar_signals(manager)

    def _connect_bar_signals(self, manager: TabManager) -> None:
        bar = manager.tab_widget.tabBar()
        if hasattr(bar, "tab_drag_started"):
            bar.tab_drag_started.connect(
                lambda idx, title, m=manager: self._on_tab_drag_started(m, idx, title)
            )
        if hasattr(bar, "split_requested"):
            bar.split_requested.connect(self._on_split_requested)
        if hasattr(bar, "close_pane_requested"):
            bar.close_pane_requested.connect(
                lambda m=manager: self.close_pane(m)
            )
        # Auto-remove secondary pane when its last tab is closed.
        # Use singleShot(0) so the check runs after close_tab's removeTab finishes.
        if not manager._is_primary:
            bar.tabCloseRequested.connect(
                lambda _idx, m=manager: QTimer.singleShot(0, lambda: self._auto_close_if_empty(m))
            )

    def _auto_close_if_empty(self, manager: TabManager) -> None:
        """Remove a secondary pane automatically once it has no tabs left."""
        if manager not in self._managers or manager._is_primary:
            return
        if manager.tab_widget.count() == 0:
            self.close_pane(manager)

    def _on_split_requested(self, direction: str) -> None:
        orientation = (
            Qt.Orientation.Horizontal if direction == "right"
            else Qt.Orientation.Vertical
        )
        self.split(orientation)

    def _on_tab_drag_started(self, manager: TabManager, index: int, title: str) -> None:
        """Extract the tab widget and start a drag session."""
        if self._drag_session is not None:
            return  # already dragging

        widget = manager.tab_widget.widget(index)
        if not isinstance(widget, EditorTab):
            return
        file_path = widget.file_path()

        # Extract the widget from its current manager
        manager._path_to_index.pop(file_path, None)
        manager._tabs.removeTab(index)
        manager._rebuild_index_map()

        # Start the drag session — widget is now "homeless" until dropped
        session = _DragSession(title, self)
        self._drag_session = session
        session.finished.connect(
            lambda result, w=widget, fp=file_path, m=manager:
                self._on_drag_finished(result, w, fp, m)
        )

    def _on_drag_finished(
        self,
        result: str,
        editor: EditorTab,
        file_path: str,
        source_manager: TabManager,
    ) -> None:
        self._drag_session = None

        if result == "cancel":
            # Put the tab back where it came from
            label = Path(file_path).name if file_path else "Untitled"
            idx = source_manager._tabs.addTab(editor, label)
            if file_path:
                source_manager._path_to_index[file_path] = idx
            source_manager._tabs.setCurrentIndex(idx)
            source_manager._rebuild_index_map()
            return

        if result in ("left", "right", "top", "bottom"):
            orientation = (
                Qt.Orientation.Horizontal
                if result in ("left", "right")
                else Qt.Orientation.Vertical
            )
            self._splitter.setOrientation(orientation)
            new_manager = TabManager(None)
            self._add_manager(new_manager)

            label = Path(file_path).name if file_path else "Untitled"
            idx = new_manager._tabs.addTab(editor, label)
            if file_path:
                new_manager._path_to_index[file_path] = idx
            new_manager._tabs.setCurrentIndex(idx)
            new_manager._rebuild_index_map()

            total = self._splitter.width() if orientation == Qt.Orientation.Horizontal \
                    else self._splitter.height()
            n = self._splitter.count()
            self._splitter.setSizes([total // n] * n)
            self._active_manager_idx = len(self._managers) - 1
        else:
            # "float" — open in a TearOffWindow
            win = TearOffWindow(editor, file_path, self)
            self._tearoff_windows.add(win)
            win.show()
            # Position near where the user released
            win.move(QCursor.pos() - QPoint(win.width() // 2, 30))

    def _move_tab_to(
        self, src: TabManager, index: int, dst: TabManager
    ) -> None:
        """Detach a tab from src and append it to dst."""
        widget = src.tab_widget.widget(index)
        if not isinstance(widget, EditorTab):
            return
        file_path = widget.file_path()
        src._path_to_index.pop(file_path, None)
        src._tabs.removeTab(index)
        src._rebuild_index_map()

        label = Path(file_path).name if file_path else "Untitled"
        idx = dst._tabs.addTab(widget, label)
        if file_path:
            dst._path_to_index[file_path] = idx
        dst._tabs.setCurrentIndex(idx)
        dst._rebuild_index_map()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FocusIn:
            for i, m in enumerate(self._managers):
                if obj is m.tab_widget:
                    self._active_manager_idx = i
                    break
        return super().eventFilter(obj, event)

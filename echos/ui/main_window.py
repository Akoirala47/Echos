from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from echos.ui.graph_canvas import GraphCanvasWidget
from echos.ui.notes_panel import NotesPanel
from echos.ui.record_bar import RecordBarWidget
from echos.ui.sidebar import SidebarWidget
from echos.ui.status_bar import StatusBarWidget
from echos.ui.tab_manager import TabManager
from echos.ui.transcript_panel import TranscriptPanel
from echos.utils.theme import BORDER_SOFT, border_soft, window_bg


class MainWindow(QMainWindow):
    """Main application window.

    All UI sub-widgets are exposed as public attributes so AppController
    can connect signals without MainWindow needing to know about business logic.

    File tabs are managed by ``tab_manager``.  The Echoes tab (index 0) contains
    the recording + notes view.  Clicking a vault note opens it in a new tab.

    The ``graph_canvas`` widget is stacked over the tab layout and shown/hidden
    via ``show_graph_view()`` / ``hide_graph_view()`` with a 150ms opacity fade.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Echos")
        self.setMinimumSize(960, 640)
        self.resize(1220, 820)

        # ── Sub-widgets (exposed for AppController) ───────────────────────────
        self.sidebar = SidebarWidget()
        self.record_bar = RecordBarWidget()
        self.transcript_panel = TranscriptPanel()
        self.notes_panel = NotesPanel()
        self.status_bar_widget = StatusBarWidget()
        self.graph_canvas = GraphCanvasWidget()

        # ── Panels splitter (transcript | notes) ──────────────────────────────
        panels_splitter = QSplitter(Qt.Orientation.Horizontal)
        panels_splitter.addWidget(self.transcript_panel)
        panels_splitter.addWidget(self.notes_panel)
        panels_splitter.setStretchFactor(0, 1)
        panels_splitter.setStretchFactor(1, 1)
        panels_splitter.setHandleWidth(1)
        panels_splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {border_soft()}; }}"
        )

        # ── Recording area (Echoes tab content) ───────────────────────────────
        recording_area = QWidget()
        recording_area.setStyleSheet(f"background: {window_bg()};")
        ra_layout = QVBoxLayout(recording_area)
        ra_layout.setContentsMargins(0, 0, 0, 0)
        ra_layout.setSpacing(0)
        ra_layout.addWidget(self.record_bar)
        ra_layout.addWidget(panels_splitter, 1)

        # ── Tab manager: Echoes (index 0) + file tabs ─────────────────────────
        self.tab_manager = TabManager(recording_area)

        # ── Content stack: [0] tab widget, [1] graph canvas ───────────────────
        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self.tab_manager.tab_widget)  # index 0
        self._content_stack.addWidget(self.graph_canvas)             # index 1
        # NOTE: No QGraphicsOpacityEffect here — QWebEngineView renders via its
        # own Chromium/OpenGL layer and ignores Qt's compositor, so opacity
        # effects make the WebEngine area appear transparent.

        # ── Top splitter (sidebar | content stack) ────────────────────────────
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.sidebar)
        top_splitter.addWidget(self._content_stack)
        top_splitter.setSizes([248, 972])
        top_splitter.setCollapsible(0, False)
        top_splitter.setCollapsible(1, False)
        top_splitter.setHandleWidth(1)
        top_splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {border_soft()}; }}"
        )

        # 1-px top border for the status bar — explicit widget, not CSS
        status_border = QWidget()
        status_border.setFixedHeight(1)
        status_border.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        status_border.setStyleSheet(f"background: {BORDER_SOFT};")

        # ── Central widget ────────────────────────────────────────────────────
        central = QWidget()
        c_layout = QVBoxLayout(central)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)
        c_layout.addWidget(top_splitter, 1)
        c_layout.addWidget(status_border)
        c_layout.addWidget(self.status_bar_widget)
        self.setCentralWidget(central)

        self._build_menu()

    # ── Graph view transitions ─────────────────────────────────────────────────

    def show_graph_view(self) -> None:
        """Switch the content stack to the graph canvas."""
        self._content_stack.setCurrentIndex(1)

    def hide_graph_view(self) -> None:
        """Switch back to the normal tab view."""
        self._content_stack.setCurrentIndex(0)

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        mb = self.menuBar()

        echos_menu = mb.addMenu("Echos")
        about_action = QAction("About Echos", self)
        echos_menu.addAction(about_action)
        echos_menu.addSeparator()
        self.settings_action = QAction("Settings…", self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        echos_menu.addAction(self.settings_action)
        echos_menu.addSeparator()
        quit_action = QAction("Quit Echos", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        echos_menu.addAction(quit_action)

        file_menu = mb.addMenu("File")
        self.new_recording_action = QAction("New Recording", self)
        self.new_recording_action.setShortcut(QKeySequence("Ctrl+N"))
        file_menu.addAction(self.new_recording_action)
        self.end_session_action = QAction("End Session", self)
        self.end_session_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.end_session_action.setEnabled(False)
        file_menu.addAction(self.end_session_action)
        file_menu.addSeparator()
        self.save_note_action = QAction("Save Note", self)
        self.save_note_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_note_action.setEnabled(False)
        file_menu.addAction(self.save_note_action)
        file_menu.addSeparator()
        self.export_transcript_action = QAction("Export Transcript…", self)
        file_menu.addAction(self.export_transcript_action)

        view_menu = mb.addMenu("View")
        self.toggle_transcript_action = QAction("Toggle Transcript Panel", self)
        view_menu.addAction(self.toggle_transcript_action)
        self.toggle_notes_action = QAction("Toggle Notes Panel", self)
        view_menu.addAction(self.toggle_notes_action)
        self.brain_view_action = QAction("Brain View", self)
        self.brain_view_action.setShortcut(QKeySequence("Ctrl+G"))
        view_menu.addAction(self.brain_view_action)

        help_menu = mb.addMenu("Help")
        self.model_status_action = QAction("Model Status", self)
        help_menu.addAction(self.model_status_action)
        self.open_log_action = QAction("Open Log File", self)
        help_menu.addAction(self.open_log_action)

    def update_course_header(self, course: dict, session_num: int) -> None:
        """Keep window title minimal — topic shown in the record bar header."""
        self.setWindowTitle("Echos")


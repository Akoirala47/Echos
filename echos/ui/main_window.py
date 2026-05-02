from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from echos.ui.notes_panel import NotesPanel
from echos.ui.record_bar import RecordBarWidget
from echos.ui.sidebar import SidebarWidget
from echos.ui.update_banner import UpdateBanner
from echos.ui.split_tab_area import SplitTabArea
from echos.ui.status_bar import StatusBarWidget
from echos.ui.tab_manager import TabManager
from echos.ui.transcript_panel import TranscriptPanel
from echos.utils.theme import BORDER_SOFT, border_soft, window_bg


class MainWindow(QMainWindow):
    """Main application window.

    All UI sub-widgets are exposed as public attributes so AppController
    can connect signals without MainWindow needing to know about business logic.

    File tabs are managed by ``tab_manager`` (primary manager in split_tab_area).
    The Echoes tab (index 0) contains the recording + notes view.
    Clicking a vault note opens it in a new editor tab.
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
        self.update_banner = UpdateBanner()

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

        # ── Split tab area: Echoes (primary) + split panes ───────────────────
        self.split_tab_area = SplitTabArea(recording_area)

        # ── Top splitter (sidebar | split area) ──────────────────────────────
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.sidebar)
        top_splitter.addWidget(self.split_tab_area)
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
        c_layout.addWidget(self.update_banner)
        c_layout.addWidget(status_border)
        c_layout.addWidget(self.status_bar_widget)
        self.setCentralWidget(central)

        self._build_menu()
        self._register_split_shortcuts()

    @property
    def tab_manager(self) -> TabManager:
        """Backward-compat: returns the primary TabManager from the split area."""
        return self.split_tab_area.primary_manager

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
        view_menu.addSeparator()
        self.command_palette_action = QAction("Command Palette", self)
        self.command_palette_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        view_menu.addAction(self.command_palette_action)

        help_menu = mb.addMenu("Help")
        self.model_status_action = QAction("Model Status", self)
        help_menu.addAction(self.model_status_action)
        self.open_log_action = QAction("Open Log File", self)
        help_menu.addAction(self.open_log_action)

    def _register_split_shortcuts(self) -> None:
        from PyQt6.QtGui import QKeySequence, QShortcut
        split_right = QShortcut(QKeySequence("Ctrl+\\"), self)
        split_right.activated.connect(
            lambda: self.split_tab_area.split(Qt.Orientation.Horizontal)
        )
        close_pane = QShortcut(QKeySequence("Ctrl+Shift+\\"), self)
        close_pane.activated.connect(
            lambda: self.split_tab_area.close_pane(self.split_tab_area.active_manager)
        )

    def update_course_header(self, course: dict, session_num: int) -> None:
        """Keep window title minimal — topic shown in the record bar header."""
        self.setWindowTitle("Echos")


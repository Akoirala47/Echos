from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from echos.ui.notes_panel import NotesPanel
from echos.ui.record_bar import RecordBarWidget
from echos.ui.sidebar import SidebarWidget
from echos.ui.status_bar import StatusBarWidget
from echos.ui.transcript_panel import TranscriptPanel


class MainWindow(QMainWindow):
    """Main application window.

    All UI sub-widgets are exposed as public attributes so AppController
    can connect signals without MainWindow needing to know about business logic.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Echos")
        self.setMinimumSize(960, 640)
        self.resize(1200, 780)

        # -- Sub-widgets (exposed for AppController) --
        self.sidebar = SidebarWidget()
        self.record_bar = RecordBarWidget()
        self.transcript_panel = TranscriptPanel()
        self.notes_panel = NotesPanel()
        self.status_bar_widget = StatusBarWidget()

        # -- Course header row --
        self._course_label = QLabel("No course selected")
        self._course_label.setStyleSheet(
            "font-size: 15px; font-weight: 700; padding: 2px 0;"
        )
        self._lecture_label = QLabel("")
        self._lecture_label.setStyleSheet(
            "font-size: 12px; color: #888; padding: 2px 0;"
        )
        course_header = QWidget()
        course_header.setStyleSheet(
            "background: #FFFFFF; border-bottom: 1px solid #E8E8E8;"
        )
        ch_layout = QHBoxLayout(course_header)
        ch_layout.setContentsMargins(14, 8, 14, 8)
        ch_layout.addWidget(self._course_label, 1)
        ch_layout.addWidget(self._lecture_label)
        course_header.setFixedHeight(44)

        # -- Panels splitter (transcript | notes) --
        panels_splitter = QSplitter(Qt.Orientation.Horizontal)
        panels_splitter.addWidget(self.transcript_panel)
        panels_splitter.addWidget(self.notes_panel)
        panels_splitter.setStretchFactor(0, 1)
        panels_splitter.setStretchFactor(1, 1)

        # -- Main content area --
        main_area = QWidget()
        main_area.setStyleSheet("background: #FFFFFF;")
        ma_layout = QVBoxLayout(main_area)
        ma_layout.setContentsMargins(0, 0, 0, 0)
        ma_layout.setSpacing(0)
        ma_layout.addWidget(course_header)
        ma_layout.addWidget(self.record_bar)
        ma_layout.addWidget(panels_splitter, 1)

        # -- Top splitter (sidebar | main area) --
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.sidebar)
        top_splitter.addWidget(main_area)
        top_splitter.setSizes([210, 990])
        top_splitter.setCollapsible(0, False)
        top_splitter.setCollapsible(1, False)
        top_splitter.setHandleWidth(1)

        # -- Central widget --
        central = QWidget()
        c_layout = QVBoxLayout(central)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)
        c_layout.addWidget(top_splitter, 1)
        c_layout.addWidget(self.status_bar_widget)
        self.setCentralWidget(central)

        # -- Menu bar --
        self._build_menu()

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # Scout menu
        scout_menu = mb.addMenu("Echos")
        about_action = QAction("About Scout", self)
        scout_menu.addAction(about_action)
        scout_menu.addSeparator()
        self.settings_action = QAction("Settings\u2026", self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        scout_menu.addAction(self.settings_action)
        scout_menu.addSeparator()
        quit_action = QAction("Quit Scout", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        scout_menu.addAction(quit_action)

        # File menu
        file_menu = mb.addMenu("File")
        self.new_recording_action = QAction("New Recording", self)
        self.new_recording_action.setShortcut(QKeySequence("Ctrl+N"))
        file_menu.addAction(self.new_recording_action)
        self.save_note_action = QAction("Save Note", self)
        self.save_note_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_note_action.setEnabled(False)
        file_menu.addAction(self.save_note_action)
        file_menu.addSeparator()
        self.export_transcript_action = QAction("Export Transcript\u2026", self)
        file_menu.addAction(self.export_transcript_action)

        # View menu
        view_menu = mb.addMenu("View")
        self.toggle_transcript_action = QAction("Toggle Transcript Panel", self)
        view_menu.addAction(self.toggle_transcript_action)
        self.toggle_notes_action = QAction("Toggle Notes Panel", self)
        view_menu.addAction(self.toggle_notes_action)
        view_menu.addSeparator()
        self.toggle_preview_action = QAction("Toggle Markdown Preview", self)
        view_menu.addAction(self.toggle_preview_action)

        # Help menu
        help_menu = mb.addMenu("Help")
        self.model_status_action = QAction("Model Status", self)
        help_menu.addAction(self.model_status_action)
        self.open_log_action = QAction("Open Log File", self)
        help_menu.addAction(self.open_log_action)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def update_course_header(self, course: dict, lecture_num: int) -> None:
        self._course_label.setText(course.get("name", ""))
        self._lecture_label.setText(f"Lecture {lecture_num}")
        self.setWindowTitle(f"Scout \u2014 {course.get('name', '')}")

from __future__ import annotations

import logging
import subprocess
from datetime import date as _date
from enum import Enum, auto
from pathlib import Path

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QMessageBox

from echos.config.config_manager import ConfigManager
from echos.core.audio_worker import AudioWorker
from echos.core.connection_resolver import ConnectionResolver
from echos.core.embedding_engine import EmbeddingEngine
from echos.core.fingerprint import FingerprintEngine
from echos.core.index_worker import IndexWorker
from echos.core.model_manager import ModelDownloadWorker, ModelManager
from echos.core.notes_worker import NotesWorker
from echos.core.obsidian_manager import ObsidianManager
from echos.core.updater import UpdateChecker, UpdateInstaller
from echos.core.vault_index import VaultIndex
from echos.ui.main_window import MainWindow
from echos.ui.onboarding import OnboardingWizard
from echos.ui.settings_window import SettingsWindow
from echos.utils.dialogs import ask_yes_no, show_error, show_info, show_warning
from echos.utils.frontmatter import inject_frontmatter

logger = logging.getLogger(__name__)


class AppState(Enum):
    IDLE = auto()
    RECORDING = auto()
    PAUSED = auto()
    STOPPED = auto()
    GENERATING = auto()
    NOTES_DONE = auto()
    SAVED = auto()


class AppController:
    """Wires all modules together and owns the application state machine.

    Receives references to the main window (for UI access) and service objects.
    All inter-component communication goes through this class.
    """

    def __init__(
        self,
        window: MainWindow,
        config_manager: ConfigManager,
        model_manager: ModelManager,
        obsidian_manager: ObsidianManager,
    ) -> None:
        self._window = window
        self._config_mgr = config_manager
        self._config = config_manager.load()
        self._model_manager = model_manager
        self._obsidian = obsidian_manager

        self._state = AppState.IDLE
        self._current_course: dict | None = None
        self._lecture_num: int = 1
        self._audio_worker: AudioWorker | None = None
        self._notes_worker: NotesWorker | None = None
        self._auto_gen_worker: NotesWorker | None = None
        self._model_load_worker: ModelDownloadWorker | None = None
        self._update_checker: UpdateChecker | None = None
        self._update_installer: UpdateInstaller | None = None
        self._pending_update_version: str = ""
        self._pending_update_url: str = ""

        # Fingerprint stored after notes generation; used at save time
        self._notes_fingerprint: str = ""

        # Real-time auto-gen tracking
        self._transcript_processed_up_to: int = 0  # chars already sent to auto-gen
        self._auto_gen_in_progress: bool = False

        # macOS power assertion token (None on non-macOS)
        self._power_assertion = None

        # Vault indexing pipeline
        self._vault_index: VaultIndex | None = None
        self._embed_engine: EmbeddingEngine | None = None
        self._index_worker: IndexWorker | None = None

        self._connect_signals()
        self._apply_initial_ui_state()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        w = self._window

        # Sidebar
        w.sidebar.course_selected.connect(self._on_course_selected)
        w.sidebar.course_added.connect(self._on_course_added)
        w.sidebar.course_deleted.connect(self._on_course_deleted)
        w.sidebar.courses_reordered.connect(self._on_courses_reordered)
        w.sidebar.settings_clicked.connect(self._on_settings)
        w.sidebar.vault_folder_selected.connect(self._on_vault_folder_selected)
        w.sidebar.note_selected.connect(self._on_note_selected)
        w.sidebar.file_deleted.connect(self._on_file_deleted)
        w.sidebar.file_renamed.connect(self._on_file_renamed)
        w.record_bar.breadcrumb_clicked.connect(self._on_breadcrumb_clicked)

        # Record bar — primary cycles Start/Pause/Resume; no Stop button
        w.record_bar.record_clicked.connect(self._on_record_clicked)

        # Notes panel
        w.notes_panel.generate_requested.connect(self._on_generate_notes)
        w.notes_panel.regenerate_requested.connect(self._on_regenerate_notes)

        # Status bar
        w.status_bar_widget.save_requested.connect(self._on_save)
        w.status_bar_widget.open_requested.connect(self._on_open_in_obsidian)
        w.status_bar_widget.end_session_clicked.connect(self._on_end_session_requested)
        w.status_bar_widget.new_session_clicked.connect(self._on_new_recording)

        # Menu bar
        w.settings_action.triggered.connect(self._on_settings)
        w.save_note_action.triggered.connect(self._on_save)
        w.new_recording_action.triggered.connect(self._on_new_recording)
        w.end_session_action.triggered.connect(self._on_end_session_requested)
        w.export_transcript_action.triggered.connect(
            lambda: w.transcript_panel._on_export()
        )
        w.model_status_action.triggered.connect(self._on_model_status)
        w.open_log_action.triggered.connect(self._on_open_log)
        w.command_palette_action.triggered.connect(self._on_command_palette)

        # Update banner
        w.update_banner.update_accepted.connect(self._on_update_accepted)
        w.update_banner.update_dismissed.connect(self._on_update_dismissed)
        w.sidebar.update_requested.connect(self._on_update_requested)

        # Brain View / graph canvas
        w.brain_view_action.triggered.connect(self._on_brain_view)
        w.graph_canvas.back_requested.connect(self._window.show_recording_view)
        w.graph_canvas.node_clicked.connect(self._on_graph_node_clicked)

        # Vault watcher → re-index debounce
        w.sidebar._watcher.reindex_ready.connect(self._on_reindex_ready)

        # Keyboard shortcuts per SPEC addendum §A:
        #   ⌘R  → Start (IDLE) or Resume (PAUSED) only
        #   ⌘P  → Pause (RECORDING) only
        #   ⌘⇧E → End Session (with confirm)
        record_sc_str = self._config.get("record_shortcut", "Ctrl+R")
        self._record_shortcut = QShortcut(QKeySequence(record_sc_str), w)
        self._record_shortcut.activated.connect(self._on_start_or_resume)

        self._pause_shortcut = QShortcut(QKeySequence("Ctrl+P"), w)
        self._pause_shortcut.activated.connect(self._on_pause_only)

        self._end_shortcut = QShortcut(QKeySequence("Ctrl+Shift+E"), w)
        self._end_shortcut.activated.connect(self._on_end_session_requested)

    def _apply_initial_ui_state(self) -> None:
        vault = self._config.get("vault_path", "")
        self._window.status_bar_widget.set_vault_path(vault)
        self._window.status_bar_widget.update_for_state("idle")

        courses = self._config.get("courses", [])
        self._window.sidebar.load_courses(courses)
        if vault:
            self._window.sidebar.set_vault_path(vault)

        # Disable generate button until recording stops.
        self._window.notes_panel.set_generate_enabled(False)

        # Restore persisted update badge (user previously dismissed the banner).
        pending = self._config.get("pending_update")
        if pending and isinstance(pending, dict):
            version = pending.get("version", "")
            url = pending.get("url", "")
            if version and url:
                self._pending_update_version = version
                self._pending_update_url = url
                self._window.sidebar.show_update_badge(version)

        # Check for updates 8 seconds after launch so it never competes with
        # the model load / UI paint during startup.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(8000, self._start_update_check)

        # Boot the vault indexing pipeline for any previously configured vault.
        self._init_indexing_pipeline()

        # If model not loaded, show status.
        if not self._model_manager.is_loaded():
            if self._model_manager.is_fully_cached():
                self._window.status_bar_widget.set_status("#F39C12", "Loading model\u2026")
                self._start_model_load()
            elif self._model_manager.is_cached():
                # Partial download — resume automatically instead of asking user.
                self._window.status_bar_widget.set_status(
                    "#F39C12", "Resuming incomplete download\u2026"
                )
                self._start_model_download()
            else:
                # Model not detected — start downloading automatically so the
                # user sees real progress instead of a dead status line.
                self._window.status_bar_widget.set_status(
                    "#F39C12", "Model not found \u2014 starting download\u2026"
                )
                self._start_model_download()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _start_model_load(self) -> None:
        from PyQt6.QtCore import QThread, pyqtSignal

        class _LoadWorker(QThread):
            load_failed = pyqtSignal(str)

            def __init__(self, mgr: ModelManager, parent=None) -> None:
                super().__init__(parent)
                self._mgr = mgr

            def run(self) -> None:
                try:
                    self._mgr.load()
                except Exception as exc:
                    logger.exception("Model load failed")
                    self.load_failed.emit(str(exc))

        self._load_worker = _LoadWorker(self._model_manager)
        self._load_worker.finished.connect(self._on_model_loaded)
        self._load_worker.load_failed.connect(self._on_model_load_failed)
        self._load_worker.start()

    def _on_model_loaded(self) -> None:
        if self._model_manager.is_loaded():
            self._window.status_bar_widget.set_status("#27AE60", "Model ready")

    def _on_model_load_failed(self, message: str) -> None:
        logger.error("Model load failed: %s", message)
        self._window.status_bar_widget.set_status("#E74C3C", "Model failed to load")
        # Show the full error so it can be reported / debugged.
        show_error(
            self._window,
            "Model Failed to Load",
            f"All loading strategies failed for {self._model_manager.MODEL_ID}.\n\n"
            f"{message}\n\n"
            "Check the log file (Help → Open Log File) for full details.\n"
            "You can also try re-downloading the model in Settings → Transcription.",
        )

    # ------------------------------------------------------------------
    # Auto-update
    # ------------------------------------------------------------------

    def _start_update_check(self) -> None:
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.start()

    def _on_update_available(self, version: str, url: str) -> None:
        self._pending_update_version = version
        self._pending_update_url = url
        self._window.update_banner.show_update(version)
        self._window.sidebar.show_update_badge(version)

    def _on_update_dismissed(self) -> None:
        self._window.update_banner.setVisible(False)
        # Persist so the sidebar badge survives app restarts.
        cfg = self._config_mgr.load()
        cfg["pending_update"] = {
            "version": self._pending_update_version,
            "url": self._pending_update_url,
        }
        self._config_mgr.save(cfg)
        self._config = cfg

    def _on_update_requested(self) -> None:
        """Sidebar badge clicked — re-show the banner."""
        if self._pending_update_version:
            self._window.update_banner.show_update(self._pending_update_version)

    def _on_update_accepted(self) -> None:
        if not self._pending_update_url:
            return
        self._window.update_banner.show_progress(self._pending_update_version)
        self._update_installer = UpdateInstaller(self._pending_update_url)
        self._update_installer.progress.connect(self._on_install_progress)
        self._update_installer.install_done.connect(self._on_install_done)
        self._update_installer.install_failed.connect(self._on_install_failed)
        self._update_installer.start()

    def _on_install_progress(self, done: int, total: int) -> None:
        self._window.update_banner.set_progress(done, total)

    def _on_install_done(self) -> None:
        self._window.update_banner.show_done()
        self._window.sidebar.hide_update_badge()
        # Clear the persisted pending update now that it's installed.
        cfg = self._config_mgr.load()
        cfg["pending_update"] = None
        self._config_mgr.save(cfg)
        self._config = cfg

    def _on_install_failed(self, message: str) -> None:
        logger.error("Update install failed: %s", message)
        self._window.update_banner.show_error(message)

    # ------------------------------------------------------------------
    # Course management
    # ------------------------------------------------------------------

    def _on_course_selected(self, course: dict) -> None:
        self._current_course = course
        vault_path = self._config.get("vault_path", "")
        if vault_path:
            vault = Path(vault_path)
            self._lecture_num = self._obsidian.next_lecture_num(
                vault, course.get("folder", "")
            )
        else:
            self._lecture_num = 1
        self._window.record_bar.set_lecture_num(self._lecture_num)

        # Update record bar topic header with the raw folder path (each segment
        # is rendered as an individual clickable breadcrumb button).
        self._window.record_bar.set_topic(
            course.get("name", ""),
            course.get("color", "#c2410c"),
            course.get("folder", ""),
        )
        self._window.update_course_header(course, self._lecture_num)

    def _on_course_added(self, course: dict) -> None:
        courses = self._config.get("courses", [])
        courses.append(course)
        self._config["courses"] = courses
        self._config_mgr.save(self._config)

    def _on_course_deleted(self, course_id: str) -> None:
        courses = [c for c in self._config.get("courses", []) if c["id"] != course_id]
        self._config["courses"] = courses
        self._config_mgr.save(self._config)

    def _on_courses_reordered(self, courses: list) -> None:
        self._config["courses"] = courses
        self._config_mgr.save(self._config)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _on_record_clicked(self) -> None:
        """Primary button full cycle: Start → Pause → Resume → New Session."""
        if self._state == AppState.IDLE:
            self._start_recording()
        elif self._state == AppState.RECORDING:
            self._pause_recording()
        elif self._state == AppState.PAUSED:
            self._resume_recording()
        else:
            # stopped / generating / notes_done / saved → new session
            self._on_new_recording()

    def _on_start_or_resume(self) -> None:
        """⌘R: Start when IDLE, Resume when PAUSED, no-op otherwise."""
        if self._state == AppState.IDLE:
            self._start_recording()
        elif self._state == AppState.PAUSED:
            self._resume_recording()

    def _on_pause_only(self) -> None:
        """⌘P: Pause only when RECORDING."""
        if self._state == AppState.RECORDING:
            self._pause_recording()

    def _on_end_session_requested(self) -> None:
        """End Session button in status bar — show confirm dialog first."""
        from PyQt6.QtWidgets import QMessageBox as _MB
        reply = _MB.question(
            self._window,
            "End this session?",
            "You won't be able to add more audio after ending.\n"
            "Pause instead if you only need a short break.",
            _MB.StandardButton.Yes | _MB.StandardButton.No,
            _MB.StandardButton.No,
        )
        if reply == _MB.StandardButton.Yes:
            self._stop_recording()

    def _on_vault_folder_selected(self, rel_path: str) -> None:
        """User clicked a folder in the vault tree — update save target."""
        if self._current_course:
            self._current_course = dict(self._current_course)
            self._current_course["folder"] = rel_path

    def _on_note_selected(self, path_str: str) -> None:
        """User clicked a .md file in the vault tree — open in a new editor tab."""
        vault_root = self._config.get("vault_path", "")
        self._window.tab_manager.open_file(path_str, vault_root=vault_root)

    def _on_file_deleted(self, path: str) -> None:
        """Vault file deleted from sidebar — close any open editor tab for it."""
        self._window.tab_manager.close_tabs_for_path(path)

    def _on_file_renamed(self, old_path: str, new_path: str) -> None:
        """Vault file renamed from sidebar — update open editor tab if present."""
        self._window.tab_manager.rename_tab_path(old_path, new_path)

    def _on_breadcrumb_clicked(self, folder_path: str) -> None:
        """User clicked a breadcrumb segment — scroll the sidebar tree to that folder."""
        self._window.sidebar.scroll_to_folder(folder_path)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _start_recording(self) -> None:
        if not self._model_manager.is_loaded():
            show_warning(
                self._window, "Model Not Ready",
                "The transcription model is not loaded yet. Please wait."
            )
            return

        if self._current_course is None:
            show_warning(
                self._window, "No Course Selected",
                "Please select or create a course before recording."
            )
            return

        self._window.transcript_panel.clear()
        self._window.notes_panel.clear()
        self._window.record_bar.reset_timer()
        self._window.notes_panel.set_generate_enabled(False)
        self._window.save_note_action.setEnabled(False)

        # Reset auto-gen tracking for the new session
        self._transcript_processed_up_to = 0
        self._auto_gen_in_progress = False

        self._audio_worker = AudioWorker(
            model_manager=self._model_manager,
            chunk_seconds=float(self._config.get("chunk_seconds", 6)),
            overlap_seconds=float(self._config.get("chunk_overlap", 0.5)),
        )
        self._audio_worker.transcript_chunk.connect(
            self._window.transcript_panel.append_text
        )
        self._audio_worker.transcript_chunk.connect(self._on_transcript_chunk_received)
        self._audio_worker.audio_level.connect(
            self._window.record_bar.waveform.set_level
        )
        self._audio_worker.error.connect(self._on_audio_error)
        self._audio_worker.start()

        self._set_state(AppState.RECORDING)
        self._begin_power_assertion()
        self._set_dock_badge(True)

    def _stop_recording(self) -> None:
        if self._audio_worker:
            self._audio_worker.stop()
            self._audio_worker.wait(5000)
            self._audio_worker = None

        self._lecture_num = self._window.record_bar.get_lecture_num()
        self._set_state(AppState.STOPPED)
        self._end_power_assertion()
        self._set_dock_badge(False)

        # If auto-gen already covered the full transcript and isn't still running,
        # go straight to NOTES_DONE so the Save button appears immediately.
        full_transcript = self._window.transcript_panel.get_text()
        remaining = full_transcript[self._transcript_processed_up_to:].strip()
        existing_notes = self._window.notes_panel.get_notes().strip()

        if existing_notes and not remaining and not self._auto_gen_in_progress:
            self._set_state(AppState.NOTES_DONE)
            self._window.save_note_action.setEnabled(True)
        else:
            self._window.notes_panel.set_generate_enabled(True)

    def _pause_recording(self) -> None:
        if self._audio_worker:
            self._audio_worker.pause()
        self._set_state(AppState.PAUSED)
        self._end_power_assertion()

    def _resume_recording(self) -> None:
        if self._audio_worker:
            self._audio_worker.resume()
        self._set_state(AppState.RECORDING)
        self._begin_power_assertion()

    # ------------------------------------------------------------------
    # Real-time auto-gen (fires during recording at each token threshold)
    # ------------------------------------------------------------------

    def _on_transcript_chunk_received(self, text: str) -> None:
        """Called for every new transcription chunk during recording."""
        from echos.core.notes_worker import CHUNK_CHAR_LIMIT

        if self._state not in (AppState.RECORDING, AppState.PAUSED):
            return
        if self._auto_gen_in_progress:
            return

        api_key = self._config.get("google_api_key", "")
        if not api_key:
            return

        full_transcript = self._window.transcript_panel.get_text()
        unprocessed_len = len(full_transcript) - self._transcript_processed_up_to
        if unprocessed_len >= CHUNK_CHAR_LIMIT:
            self._trigger_auto_notes()

    def _trigger_auto_notes(self) -> None:
        """Fire a NotesWorker for the unprocessed portion of the transcript."""
        api_key = self._config.get("google_api_key", "")
        if not api_key:
            return

        full_transcript = self._window.transcript_panel.get_text()
        new_text = full_transcript[self._transcript_processed_up_to:].strip()
        if not new_text:
            return

        existing_notes = self._window.notes_panel.get_notes().strip()
        is_continuation = bool(existing_notes)
        notes_tail = existing_notes[-400:] if len(existing_notes) > 400 else existing_notes

        # Advance the processed pointer before launching so overlapping
        # transcript chunks don't trigger a second concurrent worker.
        self._transcript_processed_up_to = len(full_transcript)
        self._auto_gen_in_progress = True

        self._window.notes_panel.show_auto_gen_banner()

        course = self._current_course or {}
        today = _date.today().isoformat()

        self._auto_gen_worker = NotesWorker(
            transcript=new_text,
            course_name=course.get("name", "Unknown"),
            lecture_num=self._lecture_num,
            date=today,
            api_key=api_key,
            model_id=self._config.get("gemma_model", "gemma-4-31b-it"),
            temperature=float(self._config.get("temperature", 0.2)),
            max_tokens=int(self._config.get("max_tokens", 8192)),
            is_continuation=is_continuation,
            existing_notes_tail=notes_tail,
        )
        self._auto_gen_worker.chunk_ready.connect(self._window.notes_panel.append_chunk)
        self._auto_gen_worker.done.connect(self._on_auto_notes_done)
        self._auto_gen_worker.error.connect(self._on_auto_notes_error)
        self._auto_gen_worker.start()

    def _on_auto_notes_done(self, added_text: str) -> None:
        """Auto-gen completed — update panel; flip to NOTES_DONE if session ended."""
        self._auto_gen_in_progress = False
        self._window.notes_panel.hide_auto_gen_banner()
        self._window.notes_panel.set_notes(self._window.notes_panel.get_notes())
        self._window.notes_panel._regen_btn.setEnabled(True)

        # Session ended while this auto-gen was still in flight — enable saving now.
        if self._state == AppState.STOPPED:
            full_transcript = self._window.transcript_panel.get_text()
            remaining = full_transcript[self._transcript_processed_up_to:].strip()
            if not remaining:
                self._set_state(AppState.NOTES_DONE)
                self._window.save_note_action.setEnabled(True)
            else:
                self._window.notes_panel.set_generate_enabled(True)

    def _on_auto_notes_error(self, message: str) -> None:
        self._auto_gen_in_progress = False
        self._window.notes_panel.hide_auto_gen_banner()
        logger.warning("Auto-gen failed: %s", message)
        self._window.status_bar_widget.set_status("#E74C3C", f"Auto-gen failed: {message[:60]}")

    # ------------------------------------------------------------------
    # Notes generation
    # ------------------------------------------------------------------

    def _on_generate_notes(self) -> None:
        self._launch_notes_worker("")

    def _on_regenerate_notes(self, instruction: str) -> None:
        self._launch_notes_worker(instruction)

    def _launch_notes_worker(self, custom_instruction: str) -> None:
        api_key = self._config.get("google_api_key", "")
        if not api_key:
            show_warning(
                self._window, "API Key Missing",
                "Add your Google AI API key in Settings (⌘,)."
            )
            return

        full_transcript = self._window.transcript_panel.get_text()
        if not full_transcript.strip():
            show_warning(
                self._window, "No Transcript",
                "There is no transcript to generate notes from."
            )
            return

        # If a regeneration was requested (custom_instruction provided), process
        # the full transcript from scratch and clear existing notes.
        if custom_instruction:
            transcript = full_transcript
            is_continuation = False
            notes_tail = ""
            self._window.notes_panel.clear()
            self._transcript_processed_up_to = 0
        else:
            # Normal "Generate Notes" — only process the remaining unprocessed delta.
            transcript = full_transcript[self._transcript_processed_up_to:].strip()
            existing_notes = self._window.notes_panel.get_notes().strip()
            is_continuation = bool(existing_notes)
            notes_tail = existing_notes[-400:] if len(existing_notes) > 400 else existing_notes
            if not transcript:
                # Nothing new to process — if notes exist, just enable saving.
                if self._window.notes_panel.get_notes().strip():
                    self._set_state(AppState.NOTES_DONE)
                    self._window.save_note_action.setEnabled(True)
                return

        course = self._current_course or {}
        today = _date.today().isoformat()

        self._window.notes_panel.set_generating(True)
        self._set_state(AppState.GENERATING)
        self._notes_fingerprint = ""

        self._notes_worker = NotesWorker(
            transcript=transcript,
            course_name=course.get("name", "Unknown"),
            lecture_num=self._lecture_num,
            date=today,
            api_key=api_key,
            model_id=self._config.get("gemma_model", "gemma-4-31b-it"),
            temperature=float(self._config.get("temperature", 0.2)),
            max_tokens=int(self._config.get("max_tokens", 8192)),
            custom_instruction=custom_instruction,
            is_continuation=is_continuation,
            existing_notes_tail=notes_tail,
        )
        self._notes_worker.chunk_ready.connect(self._window.notes_panel.append_chunk)
        self._notes_worker.done.connect(self._on_notes_done)
        self._notes_worker.error.connect(self._on_notes_error)
        self._notes_worker.start()
        self._transcript_processed_up_to = len(full_transcript)

    def _on_notes_done(self, added_text: str) -> None:
        # Compose the full notes: everything already in the panel + the new addition.
        existing = self._window.notes_panel.get_notes().strip()
        if existing and added_text.strip() and added_text.strip() not in existing:
            full_notes = existing + "\n\n" + added_text.strip()
        elif added_text.strip():
            full_notes = added_text.strip()
        else:
            full_notes = existing
        self._window.notes_panel.set_notes(full_notes)
        self._window.notes_panel.set_generating(False)
        self._set_state(AppState.NOTES_DONE)
        self._window.save_note_action.setEnabled(True)
        if self._notes_worker is not None:
            self._notes_fingerprint = getattr(self._notes_worker, "fingerprint_str", "")

    def _on_notes_error(self, message: str) -> None:
        self._window.notes_panel.set_generating(False)
        self._set_state(AppState.STOPPED)
        show_error(self._window, "Notes Generation Failed", message)

    # ------------------------------------------------------------------
    # Save to Obsidian
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        if self._state not in (AppState.NOTES_DONE, AppState.SAVED):
            return

        vault_path = self._config.get("vault_path", "")
        if not vault_path or not Path(vault_path).exists():
            show_warning(
                self._window, "Vault Not Found",
                "Obsidian vault path is not set or does not exist.\n"
                "Update it in Settings (⌘,)."
            )
            return

        vault = Path(vault_path)
        course = self._current_course or {}
        folder = course.get("folder", "Notes")
        num = self._lecture_num
        today = _date.today().isoformat()

        if self._obsidian.note_exists(vault, folder, num):
            from PyQt6.QtWidgets import QMessageBox as _MB
            reply = _MB.question(
                self._window,
                "File Already Exists",
                f"Lecture-{num:02d}.md already exists in {folder}.\n"
                "Overwrite it?",
                _MB.StandardButton.Yes | _MB.StandardButton.No | _MB.StandardButton.Cancel,
            )
            if reply == _MB.StandardButton.Cancel:
                return
            if reply == _MB.StandardButton.No:
                num = self._obsidian.next_lecture_num(vault, folder)

        notes_body = self._window.notes_panel.get_notes()
        if self._config.get("include_frontmatter", True):
            content = inject_frontmatter(
                notes_body=notes_body,
                course=course.get("name", ""),
                lecture_num=num,
                date=today,
                tags_template=self._config.get(
                    "frontmatter_tags", "[{course_lower}, lecture, notes]"
                ),
                version="1.0.0",
                fingerprint=self._notes_fingerprint or None,
            )
        else:
            content = notes_body

        try:
            saved_path = self._obsidian.save_note(vault, folder, num, content, course.get("name", ""), today)
            self._saved_file_name = saved_path.name
            self._saved_vault_name = vault.name
            self._saved_file_path = f"{folder}/{saved_path.name}"
            self._set_state(AppState.SAVED)

            if self._config.get("auto_open_obsidian", False):
                self._on_open_in_obsidian()

        except Exception as exc:
            logger.exception("Save failed")
            show_error(self._window, "Save Failed", str(exc))

    def _on_open_in_obsidian(self) -> None:
        try:
            self._obsidian.open_in_obsidian(
                getattr(self, "_saved_vault_name", ""),
                getattr(self, "_saved_file_path", ""),
            )
        except Exception as exc:
            logger.warning("open_in_obsidian failed: %s", exc)

    # ------------------------------------------------------------------
    # New recording
    # ------------------------------------------------------------------

    def _on_new_recording(self) -> None:
        if self._state in (AppState.RECORDING, AppState.PAUSED):
            if not ask_yes_no(
                self._window, "Stop Recording?",
                "A recording is in progress. Stop it and start fresh?",
            ):
                return
            self._stop_recording()

        # Cancel any in-flight auto-gen worker
        if self._auto_gen_worker is not None and self._auto_gen_worker.isRunning():
            self._auto_gen_worker.quit()
            self._auto_gen_worker = None
        self._auto_gen_in_progress = False
        self._transcript_processed_up_to = 0

        self._window.transcript_panel.clear()
        self._window.notes_panel.clear()
        self._window.notes_panel.hide_auto_gen_banner()
        self._window.record_bar.reset_timer()
        self._window.notes_panel.set_generate_enabled(False)
        self._window.save_note_action.setEnabled(False)
        self._saved_file_name = ""
        self._set_state(AppState.IDLE)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _on_command_palette(self) -> None:
        from echos.ui.command_palette import CommandPalette
        vault_path = self._config.get("vault_path", "")
        commands = [
            ("New Recording",      self._on_new_recording),
            ("Settings",           self._on_settings),
            ("Save Note",          self._on_save),
            ("End Session",        self._on_end_session_requested),
            ("Toggle Transcript",  self._window.transcript_panel.setVisible
                                   if hasattr(self._window, "transcript_panel") else lambda: None),
        ]
        palette = CommandPalette(vault_path, commands, parent=self._window)
        vault_root = self._config.get("vault_path", "")
        palette.file_selected.connect(
            lambda p: self._window.tab_manager.open_file(p, vault_root=vault_root)
        )
        palette.exec()

    def _on_settings(self) -> None:
        dlg = SettingsWindow(self._config, self._model_manager, self._window)
        dlg.exec()
        # Always save even if dismissed via redownload (dlg.accept() was called).
        updated = dlg.get_config()
        self._config.update(updated)
        self._config_mgr.save(self._config)
        self._window.sidebar.load_courses(self._config.get("courses", []))
        vault = self._config.get("vault_path", "")
        self._window.status_bar_widget.set_vault_path(vault)
        if vault:
            self._window.sidebar.set_vault_path(vault)
        new_device = self._config.get("inference_device", "auto")
        self._model_manager.set_device(new_device)
        self._init_indexing_pipeline()

        if dlg._redownload_requested:
            self._start_model_download()

    # ------------------------------------------------------------------
    # Vault indexing pipeline
    # ------------------------------------------------------------------

    def _init_indexing_pipeline(self) -> None:
        vault_path = self._config.get("vault_path", "")
        if not vault_path or not Path(vault_path).is_dir():
            return

        self._vault_index = VaultIndex(vault_path)
        self._embed_engine = EmbeddingEngine(vault_index=self._vault_index)

        # Give the sidebar watcher a reference so it can mark dirty files.
        self._window.sidebar._watcher.set_vault_index(self._vault_index)

        # Update graph canvas header.
        self._window.graph_canvas.set_vault_name(Path(vault_path).name)

        # Queue any unindexed or stale notes for first-run indexing.
        self._queue_initial_dirty_notes(vault_path)
        if self._vault_index.get_dirty_notes():
            self._trigger_index_worker()

    def _queue_initial_dirty_notes(self, vault_path: str) -> None:
        root = Path(vault_path)
        existing = {n["path"]: n for n in self._vault_index.get_all_nodes()}  # type: ignore[union-attr]
        for md in root.rglob("*.md"):
            if any(part.startswith(".") for part in md.parts):
                continue
            path_str = str(md)
            try:
                mtime = md.stat().st_mtime
            except OSError:
                continue
            note_id = str(md.relative_to(root))
            if path_str not in existing:
                self._vault_index.upsert_note(note_id, path_str, mtime, dirty=1)  # type: ignore[union-attr]
            elif existing[path_str].get("dirty", 0) == 0:
                if mtime > existing[path_str].get("modified_at", 0.0):
                    self._vault_index.set_dirty(path_str)  # type: ignore[union-attr]

    def _on_reindex_ready(self) -> None:
        self._trigger_index_worker()

    def _trigger_index_worker(self) -> None:
        if self._vault_index is None or self._embed_engine is None:
            return
        if self._index_worker is not None and self._index_worker.isRunning():
            return

        fp_engine = FingerprintEngine(embedding_engine=self._embed_engine)
        api_key = self._config.get("google_api_key", "")
        model_id = self._config.get("gemma_model", "gemma-4-31b-it")

        self._index_worker = IndexWorker(
            self._vault_index,
            self._embed_engine,
            fp_engine,
            api_key=api_key,
            model_id=model_id,
        )
        self._index_worker.indexing_finished.connect(self._on_indexing_finished)
        self._index_worker.start()

    def _on_indexing_finished(self) -> None:
        self._refresh_graph()

    def _refresh_graph(self) -> None:
        if self._vault_index is None:
            return
        nodes, edges = ConnectionResolver.resolve(self._vault_index)
        node_dicts = [
            {
                "id": n.id,
                "label": n.label,
                "kind": n.kind,
                "color": n.color,
                "domain": n.domain,
                "dir_id": n.dir_id,
                "fingerprint": n.fingerprint,
                "path": n.path,
            }
            for n in nodes
        ]
        edge_dicts = [
            {
                "source": e.source,
                "target": e.target,
                "edge_type": e.edge_type,
                "strength": e.strength,
            }
            for e in edges
        ]
        self._window.graph_canvas.set_graph_data(node_dicts, edge_dicts)

    def _on_brain_view(self) -> None:
        self._refresh_graph()
        self._window.show_brain_view()

    def _on_graph_node_clicked(self, path: str) -> None:
        vault_root = self._config.get("vault_path", "")
        self._window.tab_manager.open_file(path, vault_root=vault_root)
        self._window.show_recording_view()

    # ------------------------------------------------------------------
    # Model download (triggered from settings re-download or incomplete cache)
    # ------------------------------------------------------------------

    def _start_model_download(self) -> None:
        self._window.status_bar_widget.set_status("#F39C12", "Starting download\u2026")
        self._download_worker = ModelDownloadWorker(self._model_manager)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.done.connect(self._on_download_done)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.start()

    def _on_download_progress(self, done: int, total: int) -> None:
        # Clamp values defensively — HF metadata can occasionally report bogus
        # sizes (None, 0, or negative) that would otherwise produce "-1.0 GB".
        safe_total = max(total, 3 * 1024 ** 3)  # never below 3 GB (Whisper large-v3)
        safe_done = max(0, min(done, safe_total))
        pct = int(safe_done / safe_total * 100)
        gb_done = safe_done / 1024 ** 3
        gb_total = safe_total / 1024 ** 3
        self._window.status_bar_widget.set_status(
            "#F39C12",
            f"Downloading model\u2026 {gb_done:.1f} / {gb_total:.1f} GB ({pct}%)",
        )

    def _on_download_done(self) -> None:
        self._window.status_bar_widget.set_status("#F39C12", "Download complete \u2014 loading model\u2026")
        self._start_model_load()

    def _on_download_error(self, message: str) -> None:
        self._window.status_bar_widget.set_status(
            "#E74C3C", f"Download failed: {message[:80]}"
        )

    # ------------------------------------------------------------------
    # Help menu actions
    # ------------------------------------------------------------------

    def _on_model_status(self) -> None:
        if self._model_manager.is_loaded():
            msg = f"Loaded · device={self._model_manager.device}"
        elif self._model_manager.is_cached():
            msg = "Cached but not loaded"
        else:
            msg = "Not downloaded"
        show_info(self._window, "Model Status", msg)

    def _on_open_log(self) -> None:
        log_dir = Path.home() / "Library" / "Logs" / "Echos"
        log_file = log_dir / "echos.log"
        if log_file.exists():
            subprocess.run(["open", str(log_file)], check=False)
        else:
            show_info(self._window, "Log File", f"No log file found at {log_file}")

    # ------------------------------------------------------------------
    # Audio errors
    # ------------------------------------------------------------------

    def _on_audio_error(self, message: str) -> None:
        logger.warning("AudioWorker error: %s", message)
        self._window.status_bar_widget.set_status("#F39C12", f"Audio: {message[:60]}")

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    _STATE_KEY = {
        AppState.IDLE: "idle",
        AppState.RECORDING: "recording",
        AppState.PAUSED: "paused",
        AppState.STOPPED: "stopped",
        AppState.GENERATING: "generating",
        AppState.NOTES_DONE: "notes_done",
        AppState.SAVED: "saved",
    }

    def _set_state(self, state: AppState) -> None:
        self._state = state
        key = self._STATE_KEY.get(state, "idle")
        self._window.record_bar.set_state(key)
        self._window.status_bar_widget.update_for_state(
            key,
            saved_filename=getattr(self, "_saved_file_name", ""),
        )
        # End Session menu item is only meaningful while a session is live
        recording_live = state in (AppState.RECORDING, AppState.PAUSED)
        self._window.end_session_action.setEnabled(recording_live)

    # ------------------------------------------------------------------
    # macOS power assertion
    # ------------------------------------------------------------------

    def _begin_power_assertion(self) -> None:
        try:
            from Foundation import NSProcessInfo, NSActivityLatencyCritical
            info = NSProcessInfo.processInfo()
            self._power_assertion = info.beginActivityWithOptions_reason_(
                NSActivityLatencyCritical,
                "Scout recording in progress",
            )
        except Exception:
            pass

    def _end_power_assertion(self) -> None:
        if self._power_assertion is not None:
            try:
                from Foundation import NSProcessInfo
                NSProcessInfo.processInfo().endActivity_(self._power_assertion)
            except Exception:
                pass
            self._power_assertion = None

    # ------------------------------------------------------------------
    # Dock badge
    # ------------------------------------------------------------------

    def _set_dock_badge(self, recording: bool) -> None:
        try:
            from AppKit import NSApplication
            tile = NSApplication.sharedApplication().dockTile()
            tile.setBadgeLabel_("\u2022" if recording else "")
        except Exception:
            pass

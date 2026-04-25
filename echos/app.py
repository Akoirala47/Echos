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
from echos.core.model_manager import ModelDownloadWorker, ModelManager
from echos.core.notes_worker import NotesWorker
from echos.core.obsidian_manager import ObsidianManager
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
        self._model_load_worker: ModelDownloadWorker | None = None

        # macOS power assertion token (None on non-macOS)
        self._power_assertion = None

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

        # Record bar
        w.record_bar.record_clicked.connect(self._on_record_clicked)
        w.record_bar.pause_clicked.connect(self._on_pause_clicked)

        # Notes panel
        w.notes_panel.generate_requested.connect(self._on_generate_notes)
        w.notes_panel.regenerate_requested.connect(self._on_regenerate_notes)

        # Status bar
        w.status_bar_widget.save_requested.connect(self._on_save)
        w.status_bar_widget.open_requested.connect(self._on_open_in_obsidian)

        # Menu bar
        w.settings_action.triggered.connect(self._on_settings)
        w.save_note_action.triggered.connect(self._on_save)
        w.new_recording_action.triggered.connect(self._on_new_recording)
        w.export_transcript_action.triggered.connect(
            lambda: w.transcript_panel._on_export()
        )
        w.model_status_action.triggered.connect(self._on_model_status)
        w.open_log_action.triggered.connect(self._on_open_log)

        # Keyboard shortcuts — respects user-configured record shortcut.
        record_sc_str = self._config.get("record_shortcut", "Ctrl+R")
        self._record_shortcut = QShortcut(QKeySequence(record_sc_str), w)
        self._record_shortcut.activated.connect(self._on_record_clicked)

        self._pause_shortcut = QShortcut(QKeySequence("Ctrl+P"), w)
        self._pause_shortcut.activated.connect(self._on_pause_clicked)

    def _apply_initial_ui_state(self) -> None:
        vault = self._config.get("vault_path", "")
        self._window.status_bar_widget.set_vault_path(vault)
        self._window.status_bar_widget.set_status("#888888", "Ready")

        courses = self._config.get("courses", [])
        self._window.sidebar.load_courses(courses)

        # Disable generate button until recording stops.
        self._window.notes_panel.set_generate_enabled(False)

        # If model not loaded, show status.
        if not self._model_manager.is_loaded():
            if self._model_manager.is_fully_cached():
                self._window.status_bar_widget.set_status("#F39C12", "Loading model\u2026")
                self._start_model_load()
            elif self._model_manager.is_cached():
                # Partial download — don't attempt to load, would crash PyTorch.
                self._window.status_bar_widget.set_status(
                    "#F39C12", "Download incomplete \u2014 re-open Settings to finish"
                )
            else:
                self._window.status_bar_widget.set_status("#E74C3C", "Model not downloaded")

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
        self._window.status_bar_widget.set_status(
            "#E74C3C", "Model failed to load \u2014 try re-downloading in Settings"
        )

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
        if self._state == AppState.IDLE:
            self._start_recording()
        elif self._state in (AppState.RECORDING, AppState.PAUSED):
            self._stop_recording()

    def _on_pause_clicked(self) -> None:
        if self._state == AppState.RECORDING:
            self._pause_recording()
        elif self._state == AppState.PAUSED:
            self._resume_recording()

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
        self._window.status_bar_widget.set_status("#E74C3C", "Recording")
        self._window.status_bar_widget.set_save_enabled(False)
        self._window.status_bar_widget.set_open_visible(False)
        self._window.notes_panel.set_generate_enabled(False)
        self._window.save_note_action.setEnabled(False)

        self._audio_worker = AudioWorker(
            model_manager=self._model_manager,
            chunk_seconds=float(self._config.get("chunk_seconds", 6)),
            overlap_seconds=float(self._config.get("chunk_overlap", 0.5)),
        )
        self._audio_worker.transcript_chunk.connect(
            self._window.transcript_panel.append_text
        )
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

        self._window.status_bar_widget.set_status("#888888", "Recording stopped")
        self._window.notes_panel.set_generate_enabled(True)

    def _pause_recording(self) -> None:
        if self._audio_worker:
            self._audio_worker.pause()
        self._set_state(AppState.PAUSED)
        self._window.status_bar_widget.set_status("#F39C12", "Paused")
        self._end_power_assertion()

    def _resume_recording(self) -> None:
        if self._audio_worker:
            self._audio_worker.resume()
        self._set_state(AppState.RECORDING)
        self._window.status_bar_widget.set_status("#E74C3C", "Recording")
        self._begin_power_assertion()

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

        transcript = self._window.transcript_panel.get_text()
        if not transcript.strip():
            show_warning(
                self._window, "No Transcript",
                "There is no transcript to generate notes from."
            )
            return

        course = self._current_course or {}
        today = _date.today().isoformat()

        self._window.notes_panel.clear()
        self._window.notes_panel.set_generating(True)
        self._set_state(AppState.GENERATING)
        self._window.status_bar_widget.set_status("#2980B9", "Generating notes\u2026")

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
        )
        self._notes_worker.chunk_ready.connect(self._window.notes_panel.append_chunk)
        self._notes_worker.done.connect(self._on_notes_done)
        self._notes_worker.error.connect(self._on_notes_error)
        self._notes_worker.start()

    def _on_notes_done(self, full_text: str) -> None:
        self._window.notes_panel.set_notes(full_text)
        self._window.notes_panel.set_generating(False)
        self._set_state(AppState.NOTES_DONE)
        self._window.status_bar_widget.set_status("#27AE60", "Notes ready")
        self._window.status_bar_widget.set_save_enabled(True)
        self._window.save_note_action.setEnabled(True)

    def _on_notes_error(self, message: str) -> None:
        self._window.notes_panel.set_generating(False)
        self._set_state(AppState.STOPPED)
        self._window.status_bar_widget.set_status("#E74C3C", "Notes generation failed")
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
            )
        else:
            content = notes_body

        try:
            saved_path = self._obsidian.save_note(vault, folder, num, content, course.get("name", ""), today)
            self._set_state(AppState.SAVED)
            self._window.status_bar_widget.set_status(
                "#27AE60", f"Saved \u2014 {saved_path.name}"
            )
            self._window.status_bar_widget.set_open_visible(True)
            self._saved_vault_name = vault.name
            self._saved_file_path = f"{folder}/{saved_path.name}"

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

        self._window.transcript_panel.clear()
        self._window.notes_panel.clear()
        self._window.record_bar.reset_timer()
        self._window.status_bar_widget.set_status("#888888", "Ready")
        self._window.status_bar_widget.set_save_enabled(False)
        self._window.status_bar_widget.set_open_visible(False)
        self._window.notes_panel.set_generate_enabled(False)
        self._window.save_note_action.setEnabled(False)
        self._set_state(AppState.IDLE)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _on_settings(self) -> None:
        dlg = SettingsWindow(self._config, self._model_manager, self._window)
        if dlg.exec():
            updated = dlg.get_config()
            self._config.update(updated)
            self._config_mgr.save(self._config)
            # Reload courses in sidebar in case they changed.
            self._window.sidebar.load_courses(self._config.get("courses", []))
            # Update vault path in status bar.
            self._window.status_bar_widget.set_vault_path(
                self._config.get("vault_path", "")
            )
            # Apply device change if needed.
            new_device = self._config.get("inference_device", "auto")
            self._model_manager.set_device(new_device)

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

    def _set_state(self, state: AppState) -> None:
        self._state = state
        bar = self._window.record_bar
        if state == AppState.RECORDING:
            bar.set_state("recording")
        elif state == AppState.PAUSED:
            bar.set_state("paused")
        else:
            bar.set_state("idle")

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

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_PRESET_COLORS = [
    "#2980B9", "#27AE60", "#E74C3C", "#F39C12",
    "#8E44AD", "#16A085", "#D35400", "#7F8C8D",
]

# ---------------------------------------------------------------------------
# Inline API key test worker
# ---------------------------------------------------------------------------

class _KeyTestWorker(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, api_key: str, model_id: str, parent=None) -> None:
        super().__init__(parent)
        self._api_key = api_key
        self._model_id = model_id

    def run(self) -> None:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            m = genai.GenerativeModel(self._model_id)
            m.generate_content(
                "Reply with one word: ok",
                generation_config=genai.types.GenerationConfig(max_output_tokens=5),
            )
            self.result.emit(True, "")
        except Exception as exc:
            self.result.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Tab helpers
# ---------------------------------------------------------------------------

def _labeled_row(label: str, widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.addWidget(QLabel(label), 1)
    row.addWidget(widget, 2)
    return row


def _int_slider(lo: int, hi: int, value: int, step: int = 1) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setValue(value)
    return s


# ---------------------------------------------------------------------------
# Tab 1 — General
# ---------------------------------------------------------------------------

class _GeneralTab(QWidget):
    def __init__(self, config: dict, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Vault path
        self._vault_edit = QLineEdit(config.get("vault_path", ""))
        browse_btn = QPushButton("Browse\u2026")
        browse_btn.clicked.connect(self._browse_vault)
        vault_row = QHBoxLayout()
        vault_row.addWidget(self._vault_edit, 1)
        vault_row.addWidget(browse_btn)

        vault_group = QGroupBox("Obsidian Vault")
        vault_group.setLayout(vault_row)
        layout.addWidget(vault_group)

        # Toggles
        self._auto_open = QCheckBox("Auto-open in Obsidian after save")
        self._auto_open.setChecked(config.get("auto_open_obsidian", False))

        self._prevent_sleep = QCheckBox("Prevent sleep during recording")
        self._prevent_sleep.setChecked(config.get("prevent_sleep", True))

        self._show_waveform = QCheckBox("Show waveform")
        self._show_waveform.setChecked(config.get("show_waveform", True))

        toggles_group = QGroupBox("Behaviour")
        tg_layout = QVBoxLayout()
        tg_layout.addWidget(self._auto_open)
        tg_layout.addWidget(self._prevent_sleep)
        tg_layout.addWidget(self._show_waveform)
        toggles_group.setLayout(tg_layout)
        layout.addWidget(toggles_group)

        # Keyboard shortcut
        self._shortcut_edit = QKeySequenceEdit()
        from PyQt6.QtGui import QKeySequence
        self._shortcut_edit.setKeySequence(
            QKeySequence(config.get("record_shortcut", "Ctrl+R"))
        )
        shortcut_group = QGroupBox("Record Shortcut")
        sg_layout = QHBoxLayout()
        sg_layout.addWidget(QLabel("Start / Stop recording:"))
        sg_layout.addWidget(self._shortcut_edit)
        shortcut_group.setLayout(sg_layout)
        layout.addWidget(shortcut_group)

        layout.addStretch()
        self.setLayout(layout)

    def _browse_vault(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Obsidian Vault")
        if path:
            self._vault_edit.setText(path)

    def apply_to(self, config: dict) -> None:
        config["vault_path"] = self._vault_edit.text().strip()
        config["auto_open_obsidian"] = self._auto_open.isChecked()
        config["prevent_sleep"] = self._prevent_sleep.isChecked()
        config["show_waveform"] = self._show_waveform.isChecked()
        config["record_shortcut"] = self._shortcut_edit.keySequence().toString()


# ---------------------------------------------------------------------------
# Tab 2 — API Keys
# ---------------------------------------------------------------------------

class _ApiKeysTab(QWidget):
    def __init__(self, config: dict, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._key_edit = QLineEdit(config.get("google_api_key", ""))
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        key_link = QLabel('<a href="https://aistudio.google.com/apikey">Get a free key \u2192</a>')
        key_link.setOpenExternalLinks(True)

        self._model_edit = QLineEdit(config.get("gemma_model", "gemma-4-31b-it"))

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._test_connection)
        self._test_label = QLabel("")

        form = QFormLayout()
        form.addRow("Google AI API key:", self._key_edit)
        form.addRow("", key_link)
        form.addRow("Gemma model ID:", self._model_edit)

        api_group = QGroupBox("Google AI")
        api_group.setLayout(form)
        layout.addWidget(api_group)

        test_row = QHBoxLayout()
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_label, 1)
        layout.addLayout(test_row)
        layout.addStretch()
        self.setLayout(layout)

        self._worker: _KeyTestWorker | None = None

    def _test_connection(self) -> None:
        key = self._key_edit.text().strip()
        model = self._model_edit.text().strip()
        if not key:
            self._test_label.setText("\u26a0\ufe0f Enter an API key first.")
            return
        self._test_btn.setEnabled(False)
        self._test_label.setText("Testing\u2026")
        self._worker = _KeyTestWorker(key, model, self)
        self._worker.result.connect(self._on_test_result)
        self._worker.start()

    def _on_test_result(self, ok: bool, message: str) -> None:
        self._test_btn.setEnabled(True)
        if ok:
            self._test_label.setText("\u2713 Connection successful")
        else:
            short = message[:100] if message else "Unknown error"
            self._test_label.setText(f"\u2717 {short}")

    def apply_to(self, config: dict) -> None:
        config["google_api_key"] = self._key_edit.text().strip()
        config["gemma_model"] = self._model_edit.text().strip()


# ---------------------------------------------------------------------------
# Tab 3 — Transcription
# ---------------------------------------------------------------------------

class _TranscriptionTab(QWidget):
    def __init__(self, config: dict, model_manager: Any, parent=None) -> None:
        super().__init__(parent)
        self._model_manager = model_manager
        layout = QVBoxLayout(self)

        # Model selector (v1: single option)
        self._model_combo = QComboBox()
        self._model_combo.addItem("Canary-Qwen 2.5B", "nvidia/canary-qwen-2.5b")
        self._model_combo.setEnabled(False)  # only one option in v1

        # Chunk size slider 3–10s
        self._chunk_slider = _int_slider(3, 10, config.get("chunk_seconds", 6))
        self._chunk_label = QLabel(f"{config.get('chunk_seconds', 6)}s")
        self._chunk_slider.valueChanged.connect(
            lambda v: self._chunk_label.setText(f"{v}s")
        )

        chunk_row = QHBoxLayout()
        chunk_row.addWidget(self._chunk_slider, 1)
        chunk_row.addWidget(self._chunk_label)

        # Overlap slider 0–10 (tenths of a second)
        overlap_val = int(config.get("chunk_overlap", 0.5) * 10)
        self._overlap_slider = _int_slider(0, 10, overlap_val)
        self._overlap_label = QLabel(f"{config.get('chunk_overlap', 0.5):.1f}s")
        self._overlap_slider.valueChanged.connect(
            lambda v: self._overlap_label.setText(f"{v / 10:.1f}s")
        )

        overlap_row = QHBoxLayout()
        overlap_row.addWidget(self._overlap_slider, 1)
        overlap_row.addWidget(self._overlap_label)

        # Device selector
        self._device_combo = QComboBox()
        for label, value in [("Auto (MPS if available)", "auto"), ("MPS", "mps"), ("CPU", "cpu")]:
            self._device_combo.addItem(label, value)
        current_device = config.get("inference_device", "auto")
        idx = self._device_combo.findData(current_device)
        if idx >= 0:
            self._device_combo.setCurrentIndex(idx)

        # Model status
        status = "Not loaded"
        if model_manager and model_manager.is_loaded():
            status = f"Loaded \u00b7 {model_manager.device}"
        elif model_manager and model_manager.is_cached():
            status = "Cached (not loaded)"
        self._status_label = QLabel(status)

        # Re-download button
        self._redownload_btn = QPushButton("Re-download Model")
        self._redownload_btn.clicked.connect(self._redownload)

        form = QFormLayout()
        form.addRow("Model:", self._model_combo)
        form.addRow("Chunk size:", chunk_row)
        form.addRow("Overlap:", overlap_row)
        form.addRow("Inference device:", self._device_combo)
        form.addRow("Model status:", self._status_label)
        form.addRow("", self._redownload_btn)

        group = QGroupBox("Canary-Qwen ASR")
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        self.setLayout(layout)

    def _redownload(self) -> None:
        reply = QMessageBox.question(
            self,
            "Re-download Model",
            "This will delete the cached model weights and start a fresh ~5 GB download. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import shutil
                from huggingface_hub import constants as hf_constants
                cache_dir = (
                    Path(hf_constants.HF_HUB_CACHE)
                    / "models--nvidia--canary-qwen-2.5b"
                )
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                # Signal AppController to start download — close settings first.
                self._needs_redownload = True
                # Find and accept the parent SettingsWindow dialog.
                p = self.parent()
                while p is not None:
                    if hasattr(p, "_redownload_requested"):
                        p._redownload_requested = True
                        p.accept()
                        return
                    p = p.parent()
            except Exception as exc:
                QMessageBox.warning(self, "Error", str(exc))

    def apply_to(self, config: dict) -> None:
        config["chunk_seconds"] = self._chunk_slider.value()
        config["chunk_overlap"] = self._overlap_slider.value() / 10.0
        config["inference_device"] = self._device_combo.currentData()


# ---------------------------------------------------------------------------
# Tab 4 — Notes
# ---------------------------------------------------------------------------

class _NotesTab(QWidget):
    def __init__(self, config: dict, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Temperature: 0–100 maps to 0.0–1.0
        temp_val = int(config.get("temperature", 0.2) * 100)
        self._temp_slider = _int_slider(0, 100, temp_val)
        self._temp_label = QLabel(f"{config.get('temperature', 0.2):.2f}")
        self._temp_slider.valueChanged.connect(
            lambda v: self._temp_label.setText(f"{v / 100:.2f}")
        )
        temp_row = QHBoxLayout()
        temp_row.addWidget(self._temp_slider, 1)
        temp_row.addWidget(self._temp_label)

        # Max tokens 1000–16000 in steps of 100
        self._tokens_slider = _int_slider(1000, 16000, config.get("max_tokens", 8192), 100)
        self._tokens_label = QLabel(str(config.get("max_tokens", 8192)))
        self._tokens_slider.valueChanged.connect(
            lambda v: self._tokens_label.setText(str(v))
        )
        tokens_row = QHBoxLayout()
        tokens_row.addWidget(self._tokens_slider, 1)
        tokens_row.addWidget(self._tokens_label)

        # Language
        self._lang_combo = QComboBox()
        for lang in ["English", "French", "Spanish", "German", "Japanese", "Chinese"]:
            self._lang_combo.addItem(lang)
        current_lang = config.get("note_language", "English")
        idx = self._lang_combo.findText(current_lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)

        # Front matter
        self._frontmatter_check = QCheckBox("Include YAML front matter")
        self._frontmatter_check.setChecked(config.get("include_frontmatter", True))

        self._tags_edit = QLineEdit(
            config.get("frontmatter_tags", "[{course_lower}, lecture, notes]")
        )

        # Custom prompt suffix
        self._prompt_suffix = QTextEdit()
        self._prompt_suffix.setPlainText(config.get("custom_prompt_suffix", ""))
        self._prompt_suffix.setFixedHeight(80)
        self._prompt_suffix.setPlaceholderText(
            "Optional extra instructions appended to the Gemma prompt\u2026"
        )

        form = QFormLayout()
        form.addRow("Temperature:", temp_row)
        form.addRow("Max output tokens:", tokens_row)
        form.addRow("Note language:", self._lang_combo)
        form.addRow("", self._frontmatter_check)
        form.addRow("Tags template:", self._tags_edit)
        form.addRow("Custom prompt suffix:", self._prompt_suffix)

        group = QGroupBox("Gemma Notes Generation")
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        self.setLayout(layout)

    def apply_to(self, config: dict) -> None:
        config["temperature"] = self._temp_slider.value() / 100.0
        config["max_tokens"] = self._tokens_slider.value()
        config["note_language"] = self._lang_combo.currentText()
        config["include_frontmatter"] = self._frontmatter_check.isChecked()
        config["frontmatter_tags"] = self._tags_edit.text().strip()
        config["custom_prompt_suffix"] = self._prompt_suffix.toPlainText().strip()


# ---------------------------------------------------------------------------
# SettingsWindow
# ---------------------------------------------------------------------------

class SettingsWindow(QDialog):
    """Settings dialog (⌘,) with four tabs.

    Call exec() to show modally.  On accept the caller should retrieve the
    updated config via get_config() and persist it.
    """

    def __init__(
        self,
        config: dict,
        model_manager: Any = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Echos Settings")
        self.setMinimumSize(520, 440)

        self._redownload_requested = False  # set by _TranscriptionTab._redownload()
        self._config = dict(config)

        self._tabs = QTabWidget()
        self._general_tab = _GeneralTab(self._config, self)
        self._api_tab = _ApiKeysTab(self._config, self)
        self._transcription_tab = _TranscriptionTab(self._config, model_manager, self)
        self._notes_tab = _NotesTab(self._config, self)

        self._tabs.addTab(self._general_tab, "General")
        self._tabs.addTab(self._api_tab, "API Keys")
        self._tabs.addTab(self._transcription_tab, "Transcription")
        self._tabs.addTab(self._notes_tab, "Notes")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _on_save(self) -> None:
        self._general_tab.apply_to(self._config)
        self._api_tab.apply_to(self._config)
        self._transcription_tab.apply_to(self._config)
        self._notes_tab.apply_to(self._config)
        self.accept()

    def get_config(self) -> dict:
        """Return the updated config dict after the dialog is accepted."""
        return dict(self._config)

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QHBoxLayout,
    QSizePolicy,
)

from echos.core.model_manager import ModelDownloadWorker, ModelManager
from echos.ui.widgets.model_progress import ModelProgressWidget

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Async API-key validator
# ---------------------------------------------------------------------------

class _ApiKeyValidator(QThread):
    """Makes a minimal Google API call to verify the key."""

    validated = pyqtSignal(bool, str)  # (ok, message)

    def __init__(self, api_key: str, model_id: str, parent=None) -> None:
        super().__init__(parent)
        self._api_key = api_key
        self._model_id = model_id

    def run(self) -> None:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            model = genai.GenerativeModel(self._model_id)
            model.generate_content(
                "Reply with one word: ok",
                generation_config=genai.types.GenerationConfig(max_output_tokens=5),
            )
            self.validated.emit(True, "")
        except Exception as exc:
            self.validated.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Page 1 — Welcome
# ---------------------------------------------------------------------------

class WelcomePage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Welcome to Scout")

        intro = QLabel(
            "AI-powered lecture notes for Mac.\n\n"
            "We'll set up three things:\n"
            "  \u2726  Your Obsidian vault location\n"
            "  \u2726  Your Google AI API key\n"
            "  \u2726  The local transcription model"
        )
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(intro)
        layout.addStretch()
        self.setLayout(layout)


# ---------------------------------------------------------------------------
# Page 2 — Vault + API Key
# ---------------------------------------------------------------------------

class SetupPage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Configure Scout")
        self.setSubTitle("Set your Obsidian vault and Google AI API key.")

        # Vault path row
        self._vault_edit = QLineEdit()
        self._vault_edit.setPlaceholderText("/Users/you/Documents/obsidian/vault")
        browse_btn = QPushButton("Browse\u2026")
        browse_btn.clicked.connect(self._browse_vault)

        vault_row = QHBoxLayout()
        vault_row.addWidget(self._vault_edit)
        vault_row.addWidget(browse_btn)

        # API key row
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText("AIza\u2026")

        key_link = QLabel('<a href="https://aistudio.google.com/apikey">Get a free key \u2192</a>')
        key_link.setOpenExternalLinks(True)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)

        self._validate_btn = QPushButton("Validate Key")
        self._validate_btn.clicked.connect(self._validate_key)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Obsidian vault folder:"))
        layout.addLayout(vault_row)
        layout.addSpacing(12)
        layout.addWidget(QLabel("Google AI API key:"))
        layout.addWidget(self._key_edit)
        layout.addWidget(key_link)
        layout.addSpacing(8)
        layout.addWidget(self._validate_btn)
        layout.addWidget(self._status_label)
        layout.addStretch()
        self.setLayout(layout)

        # Register fields so QWizard can read them.
        self.registerField("vault_path*", self._vault_edit)
        self.registerField("api_key*", self._key_edit)

        self._key_valid = False
        self._validator: _ApiKeyValidator | None = None

    def isComplete(self) -> bool:
        vault = self._vault_edit.text().strip()
        key = self._key_edit.text().strip()
        return bool(vault) and bool(key) and self._key_valid

    def _browse_vault(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Obsidian Vault")
        if path:
            self._vault_edit.setText(path)
            self.completeChanged.emit()

    def _validate_key(self) -> None:
        key = self._key_edit.text().strip()
        if not key:
            self._status_label.setText("\u26a0\ufe0f Enter an API key first.")
            return
        self._validate_btn.setEnabled(False)
        self._status_label.setText("Validating\u2026")
        self._key_valid = False

        model_id = "gemma-4-31b-it"  # lightweight model for key validation
        self._validator = _ApiKeyValidator(key, model_id, self)
        self._validator.validated.connect(self._on_validated)
        self._validator.start()

    def _on_validated(self, ok: bool, message: str) -> None:
        self._validate_btn.setEnabled(True)
        if ok:
            self._key_valid = True
            self._status_label.setText("\u2713 API key is valid.")
        else:
            self._key_valid = False
            short = message[:120] if message else "Unknown error"
            self._status_label.setText(f"\u2717 {short}")
        self.completeChanged.emit()


# ---------------------------------------------------------------------------
# Page 3 — Model Download
# ---------------------------------------------------------------------------

class DownloadPage(QWizardPage):
    def __init__(self, model_manager: ModelManager, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Download Transcription Model")
        self.setSubTitle(
            "Canary-Qwen 2.5B runs fully on your Mac. "
            "Your audio never leaves your device."
        )

        self._model_manager = model_manager
        self._progress_widget = ModelProgressWidget()
        self._progress_widget.background_requested.connect(self._go_background)

        self._info = QLabel("This happens once (\u223c5 GB).")
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._done = False
        self._worker: ModelDownloadWorker | None = None

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self._info)
        layout.addSpacing(12)
        layout.addWidget(self._progress_widget)
        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self) -> None:  # noqa: N802
        # Only skip download if ALL files are present — partial cache still needs downloading.
        if self._model_manager.is_fully_cached():
            self._progress_widget.mark_done()
            self._done = True
            self.completeChanged.emit()
            return
        self._start_download()

    def isComplete(self) -> bool:
        return self._done

    def _start_download(self) -> None:
        # No parent — worker must outlive this page when "Background" is clicked.
        self._worker = ModelDownloadWorker(self._model_manager, parent=None)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        # Compute approximate speed from consecutive calls (~1s apart).
        self._progress_widget.update_progress(done, total)

    def _on_done(self) -> None:
        self._progress_widget.mark_done()
        self._done = True
        self.completeChanged.emit()

    def _on_error(self, message: str) -> None:
        self._info.setText(f"\u26a0\ufe0f Download failed: {message[:100]}")

    def _go_background(self) -> None:
        # Disconnect signals so the destroyed page can't receive callbacks,
        # but leave the worker running — it has no parent so Qt won't kill it.
        if self._worker and self._worker.isRunning():
            try:
                self._worker.progress.disconnect(self._on_progress)
                self._worker.done.disconnect(self._on_done)
                self._worker.error.disconnect(self._on_error)
            except RuntimeError:
                pass
        if self.wizard():
            self.wizard().accept()


# ---------------------------------------------------------------------------
# OnboardingWizard
# ---------------------------------------------------------------------------

class OnboardingWizard(QWizard):
    """Three-page setup wizard shown on first launch.

    After exec() completes, read vault_path and api_key from
    wizard.field('vault_path') and wizard.field('api_key').
    """

    def __init__(self, model_manager: ModelManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scout Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(480, 360)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)

        self.addPage(WelcomePage(self))
        self.addPage(SetupPage(self))
        self.addPage(DownloadPage(model_manager, self))

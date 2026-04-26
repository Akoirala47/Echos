from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_NOTES_CSS = """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
    font-size: 13px;
    line-height: 1.6;
    color: #1A1A1A;
    margin: 0;
    padding: 0;
}
h1 { font-size: 18px; font-weight: 700; margin: 16px 0 6px 0; }
h2 {
    font-size: 15px; font-weight: 600; margin: 14px 0 5px 0;
    padding-left: 8px;
    border-left: 3px solid #2980B9;
}
h3 { font-size: 13px; font-weight: 600; margin: 10px 0 4px 0; }
p { margin: 4px 0 8px 0; }
ul, ol { padding-left: 20px; margin: 4px 0 8px 0; }
li { margin: 3px 0; }
code {
    font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
    font-size: 12px;
    background: #F5F5F2;
    padding: 2px 5px;
    border: 1px solid #E0E0DC;
    border-radius: 3px;
}
pre {
    background: #F5F5F2;
    padding: 12px;
    border: 1px solid #E0E0DC;
    border-radius: 4px;
    overflow: auto;
    margin: 8px 0;
}
pre code {
    background: none;
    border: none;
    padding: 0;
}
strong { font-weight: 600; }
em { font-style: italic; }
"""


def _md_to_html(text: str) -> str:
    """Convert markdown to HTML using a theme-aware CSS stylesheet."""
    try:
        import markdown
        body = markdown.markdown(
            text,
            extensions=["fenced_code", "tables", "nl2br"],
        )
    except Exception:
        import html
        body = f"<pre>{html.escape(text)}</pre>"
    try:
        from echos.utils.theme import notes_css
        css = notes_css()
    except Exception:
        css = _NOTES_CSS
    return f"<html><head><style>{css}</style></head><body>{body}</body></html>"


class NotesPanel(QWidget):
    """Right panel: rendered markdown preview + raw edit view.

    Signals
    -------
    generate_requested
        Emitted when the user clicks "Generate Notes".
    regenerate_requested : str
        Emitted with an optional custom instruction when "Regenerate" is clicked.
    copy_requested
        Emitted when the user clicks "Copy".
    """

    generate_requested = pyqtSignal()
    regenerate_requested = pyqtSignal(str)
    copy_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._raw_markdown: str = ""
        self._show_raw: bool = False

        _muted = "font-size: 11px; font-weight: 600; color: palette(placeholderText);"
        _action = "font-size: 11px; color: palette(placeholderText);"

        # -- Header toolbar --
        header = QLabel("STRUCTURED NOTES")
        header.setStyleSheet(_muted)

        self._toggle_btn = QPushButton("Raw")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setStyleSheet(_action)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.toggled.connect(self._toggle_view)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setFlat(True)
        self._copy_btn.setStyleSheet(_action)
        self._copy_btn.clicked.connect(self._on_copy)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(header)
        toolbar.addStretch()
        toolbar.addWidget(self._copy_btn)
        toolbar.addWidget(self._toggle_btn)

        # -- Rendered view --
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setStyleSheet("border: none; background: palette(base);")

        # -- Raw edit view --
        self._raw_edit = QTextEdit()
        self._raw_edit.setAcceptRichText(False)
        self._raw_edit.setStyleSheet(
            "font-family: 'Menlo', 'Monaco', monospace; font-size: 12px; border: none;"
        )

        self._stack = QStackedWidget()
        self._stack.addWidget(self._browser)   # index 0 = rendered
        self._stack.addWidget(self._raw_edit)  # index 1 = raw

        # -- Action buttons --
        self._generate_btn = QPushButton("Generate Notes")
        self._generate_btn.setEnabled(False)
        self._generate_btn.setFixedHeight(36)
        self._generate_btn.clicked.connect(self.generate_requested)

        self._regen_btn = QPushButton("Regenerate\u2026")
        self._regen_btn.setEnabled(False)
        self._regen_btn.setFixedHeight(36)
        self._regen_btn.clicked.connect(self._on_regenerate)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._generate_btn, 1)
        btn_row.addWidget(self._regen_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.addLayout(toolbar)
        layout.addWidget(self._stack, 1)
        layout.addLayout(btn_row)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_notes(self, markdown: str) -> None:
        """Replace the notes content entirely (called when generation is complete)."""
        try:
            self._raw_markdown = markdown
            self._browser.setHtml(_md_to_html(markdown))
            self._raw_edit.setPlainText(markdown)
            self._regen_btn.setEnabled(True)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("set_notes failed")

    def append_chunk(self, text: str) -> None:
        """Append a streaming fragment and re-render."""
        try:
            self._raw_markdown += text
            self._browser.setHtml(_md_to_html(self._raw_markdown))
            self._raw_edit.setPlainText(self._raw_markdown)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("append_chunk failed")

    def get_notes(self) -> str:
        """Return the current notes (raw edit takes precedence if in raw view)."""
        if self._show_raw:
            return self._raw_edit.toPlainText()
        return self._raw_markdown

    def set_generate_enabled(self, enabled: bool) -> None:
        self._generate_btn.setEnabled(enabled)

    def set_generating(self, generating: bool) -> None:
        if generating:
            self._generate_btn.setText("Generating\u2026")
            self._generate_btn.setEnabled(False)
            self._regen_btn.setEnabled(False)
        else:
            self._generate_btn.setText("Generate Notes")

    def clear(self) -> None:
        self._raw_markdown = ""
        self._browser.clear()
        self._raw_edit.clear()
        self._regen_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _toggle_view(self, checked: bool) -> None:
        self._show_raw = checked
        self._toggle_btn.setText("Preview" if checked else "Raw")
        if checked:
            # Sync raw editor from current markdown before switching.
            self._raw_edit.setPlainText(self._raw_markdown)
            self._stack.setCurrentIndex(1)
        else:
            # Sync rendered view from raw editor before switching.
            self._raw_markdown = self._raw_edit.toPlainText()
            self._browser.setHtml(_md_to_html(self._raw_markdown))
            self._stack.setCurrentIndex(0)

    def _on_regenerate(self) -> None:
        instruction, ok = QInputDialog.getText(
            self,
            "Regenerate Notes",
            "Any specific focus? (optional)",
        )
        if ok:
            self.regenerate_requested.emit(instruction.strip())

    def _on_copy(self) -> None:
        text = self.get_notes()
        if text:
            QApplication.clipboard().setText(text)

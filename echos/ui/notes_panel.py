from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer, pyqtSignal
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

from echos.utils.theme import (
    ACCENT, ACCENT_SOFT,
    border_soft, panel_bg, text, text_faint, text_muted,
    ready_color, notes_css,
)

logger = logging.getLogger(__name__)


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block (--- ... ---) if present."""
    if not text.startswith('---'):
        return text
    end = text.find('\n---', 3)
    if end == -1:
        return text
    return text[end + 4:].lstrip('\n')


def _md_to_html(md_text: str) -> str:
    body_src = _strip_frontmatter(md_text)
    try:
        import markdown
        body = markdown.markdown(
            body_src,
            extensions=["fenced_code", "tables"],
        )
    except Exception:
        import html
        body = f"<pre>{html.escape(body_src)}</pre>"
    try:
        css = notes_css()
    except Exception:
        css = ""
    return f"<html><head><style>{css}</style></head><body>{body}</body></html>"


def _mini_btn(label: str) -> QPushButton:
    from echos.utils.theme import TEXT, TEXT_FAINT
    btn = QPushButton(label.upper())
    btn.setFlat(True)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; border: none;"
        f" font-size: 10px; font-weight: 600; letter-spacing: 0.5px;"
        f" color: {TEXT_FAINT}; padding: 1px 8px; }}"
        f"QPushButton:hover {{ color: {TEXT}; }}"
    )
    return btn


class NotesPanel(QWidget):
    """Right panel: rendered markdown notes with mockup-style header + footer."""

    generate_requested = pyqtSignal()
    regenerate_requested = pyqtSignal(str)
    copy_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._raw_markdown: str = ""
        self._show_raw: bool = False

        self.setStyleSheet(f"background: {panel_bg()};")

        # ── Header ────────────────────────────────────────────────────────────
        header_lbl = QLabel("STRUCTURED NOTES")
        header_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px;"
            f" color: {text_faint()}; text-transform: uppercase;"
        )

        self._copy_btn = _mini_btn("Copy")
        self._copy_btn.clicked.connect(self._on_copy)

        self._toggle_btn = _mini_btn("Raw")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.toggled.connect(self._toggle_view)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(12, 0, 8, 0)
        header_row.setSpacing(4)
        header_row.addWidget(header_lbl)
        header_row.addStretch()
        header_row.addWidget(self._copy_btn)
        header_row.addWidget(self._toggle_btn)

        header_widget = QWidget()
        header_widget.setFixedHeight(32)
        header_widget.setStyleSheet(f"border-bottom: 1px solid {border_soft()};")
        header_widget.setLayout(header_row)

        # ── Content ───────────────────────────────────────────────────────────
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background: {panel_bg()}; border: none; }}"
        )
        self._browser.document().setDocumentMargin(22)

        self._raw_edit = QTextEdit()
        self._raw_edit.setAcceptRichText(False)
        self._raw_edit.setStyleSheet(
            f"QTextEdit {{ background: {panel_bg()}; color: {text()}; border: none;"
            f" font-family: 'Menlo', 'Monaco', monospace; font-size: 12px; }}"
        )
        self._raw_edit.document().setDocumentMargin(22)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._browser)   # 0 = rendered
        self._stack.addWidget(self._raw_edit)  # 1 = raw

        # ── Footer ────────────────────────────────────────────────────────────
        self._generate_btn = QPushButton("Generate Notes")
        self._generate_btn.setEnabled(False)
        self._generate_btn.setFixedHeight(30)
        self._generate_btn.clicked.connect(self.generate_requested)
        self._generate_btn.setStyleSheet(
            f"QPushButton {{ background: {text()}; color: #fff; border: none;"
            f" border-radius: 6px; font-size: 12.5px; font-weight: 600; padding: 0 14px; }}"
            f"QPushButton:hover {{ background: #3a3830; }}"
            f"QPushButton:disabled {{ background: {border_soft()}; color: {text_faint()}; }}"
        )

        self._regen_btn = QPushButton("Regenerate…")
        self._regen_btn.setEnabled(False)
        self._regen_btn.setFixedHeight(30)
        self._regen_btn.clicked.connect(self._on_regenerate)
        self._regen_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {text_muted()};"
            f" border: 1px solid {border_soft()}; border-radius: 6px;"
            f" font-size: 12px; font-weight: 500; padding: 0 12px; }}"
            f"QPushButton:hover {{ background: rgba(0,0,0,0.04); }}"
            f"QPushButton:disabled {{ color: {text_faint()}; border-color: {border_soft()}; }}"
        )

        self._model_chip = QLabel("gemma-4-31b · streaming")
        self._model_chip.setStyleSheet(
            f"font-size: 11px; color: {text_faint()};"
        )

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(14, 8, 14, 10)
        footer_row.setSpacing(8)
        footer_row.addWidget(self._generate_btn)
        footer_row.addWidget(self._regen_btn)
        footer_row.addStretch()
        footer_row.addWidget(self._model_chip)

        footer_widget = QWidget()
        footer_widget.setStyleSheet(f"border-top: 1px solid {border_soft()};")
        footer_widget.setLayout(footer_row)

        # ── Auto-gen notification banner ──────────────────────────────────────
        self._banner = QLabel()
        self._banner.setStyleSheet(
            f"QLabel {{ background: {ACCENT_SOFT}; color: {ACCENT};"
            f" font-size: 11px; font-weight: 600; padding: 5px 14px;"
            f" border-bottom: 1px solid {ACCENT}22; }}"
        )
        self._banner.hide()

        # ── Outer layout ──────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header_widget)
        layout.addWidget(self._banner)
        layout.addWidget(self._stack, 1)
        layout.addWidget(footer_widget)
        self.setLayout(layout)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_notes(self, markdown: str) -> None:
        try:
            self._raw_markdown = markdown
            self._browser.setHtml(_md_to_html(markdown))
            self._raw_edit.setPlainText(markdown)
            self._regen_btn.setEnabled(True)
        except Exception:
            logger.exception("set_notes failed")

    def append_chunk(self, chunk: str) -> None:
        try:
            self._raw_markdown += chunk
            self._browser.setHtml(_md_to_html(self._raw_markdown))
            self._raw_edit.setPlainText(self._raw_markdown)
        except Exception:
            logger.exception("append_chunk failed")

    def get_notes(self) -> str:
        if self._show_raw:
            return self._raw_edit.toPlainText()
        return self._raw_markdown

    def set_generate_enabled(self, enabled: bool) -> None:
        self._generate_btn.setEnabled(enabled)

    def set_generating(self, generating: bool) -> None:
        if generating:
            self._generate_btn.setText("Generating…")
            self._generate_btn.setEnabled(False)
            self._regen_btn.setEnabled(False)
        else:
            self._generate_btn.setText("Generate Notes")

    def clear(self) -> None:
        self._raw_markdown = ""
        self._browser.clear()
        self._raw_edit.clear()
        self._regen_btn.setEnabled(False)

    def set_model_name(self, name: str) -> None:
        self._model_chip.setText(f"{name} · streaming")

    def show_auto_gen_banner(self, msg: str = "") -> None:
        """Show the amber notification strip above the notes content."""
        self._banner.setText(msg or "⚡ Auto-generating notes from new transcript…")
        self._banner.show()

    def hide_auto_gen_banner(self) -> None:
        self._banner.hide()

    # ── Internal slots ─────────────────────────────────────────────────────────

    def _toggle_view(self, checked: bool) -> None:
        self._show_raw = checked
        self._toggle_btn.setText("Preview" if checked else "Raw")
        if checked:
            self._raw_edit.setPlainText(self._raw_markdown)
            self._stack.setCurrentIndex(1)
        else:
            self._raw_markdown = self._raw_edit.toPlainText()
            self._browser.setHtml(_md_to_html(self._raw_markdown))
            self._stack.setCurrentIndex(0)

    def _on_regenerate(self) -> None:
        instruction, ok = QInputDialog.getText(
            self, "Regenerate Notes", "Any specific focus? (optional)",
        )
        if ok:
            self.regenerate_requested.emit(instruction.strip())

    def _on_copy(self) -> None:
        text_content = self.get_notes()
        if text_content:
            QApplication.clipboard().setText(text_content)

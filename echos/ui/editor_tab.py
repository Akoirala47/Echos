"""EditorTab — a single file tab with Preview / Raw / Edit mode toggle.

Three modes per open file:
  Preview — QTextBrowser renders markdown (same pipeline as NotesPanel)
  Raw     — QTextEdit, monospace, read-only
  Edit    — QTextEdit, monospace, editable; tracks unsaved changes

All colours come from ``echos.utils.theme``.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from PyQt6.QtCore import QPoint, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QImage
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from echos.utils.theme import (
    ACCENT, BORDER_SOFT, PANEL_BG, SIDEBAR_BG,
    TEXT, TEXT_FAINT, TEXT_MUTED,
    border_soft, panel_bg, text, text_faint, text_muted,
    notes_css,
)

logger = logging.getLogger(__name__)

_MODE = Literal["preview", "raw"]
_WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]')
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


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
    css = notes_css()
    return f"<html><head><style>{css}</style></head><body>{body}</body></html>"


def _mode_btn(label: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setCheckable(True)
    btn.setFlat(True)
    btn.setFixedHeight(22)
    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    btn.setStyleSheet(
        f"QPushButton {{"
        f" background: transparent; border: 1px solid {BORDER_SOFT};"
        f" font-size: 10.5px; font-weight: 600; letter-spacing: 0.3px;"
        f" color: {TEXT_MUTED}; padding: 0 9px; border-radius: 4px;"
        f"}}"
        f"QPushButton:checked {{"
        f" background: {ACCENT}; color: #fff; border-color: {ACCENT};"
        f"}}"
        f"QPushButton:hover:!checked {{ color: {TEXT}; }}"
    )
    return btn


# ── Wikilink hover preview widget ─────────────────────────────────────────────

class _WikilinkPreview(QWidget):
    """Frameless tooltip-style widget that renders the first 15 lines of a vault note."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet(
            f"background: {PANEL_BG}; border: 1px solid {BORDER_SOFT}; border-radius: 6px;"
        )
        self.setFixedSize(380, 220)

        self._title = QLabel()
        self._title.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {TEXT}; padding: 0;"
        )

        self._path_lbl = QLabel()
        self._path_lbl.setStyleSheet(
            f"font-size: 10px; color: {TEXT_FAINT}; padding: 0;"
        )

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background: {PANEL_BG}; border: none; }}"
        )
        self._browser.document().setDocumentMargin(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        layout.addWidget(self._title)
        layout.addWidget(self._path_lbl)
        layout.addWidget(self._browser, 1)

    def show_for(self, target_path: Path, vault_root: Path | None, cursor_global: QPoint) -> None:
        try:
            lines = target_path.read_text(encoding="utf-8", errors="replace").splitlines()
            preview_text = "\n".join(lines[:15])
        except Exception:
            preview_text = f"*Could not read {target_path.name}*"

        self._title.setText(target_path.stem)
        if vault_root:
            try:
                rel = str(target_path.relative_to(vault_root))
            except ValueError:
                rel = target_path.name
        else:
            rel = target_path.name
        self._path_lbl.setText(rel)
        self._browser.setHtml(_md_to_html(preview_text))

        # Position below cursor, nudging left if near screen edge
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = cursor_global.x()
        y = cursor_global.y() + 20
        if x + self.width() > screen.right():
            x = screen.right() - self.width() - 4
        if y + self.height() > screen.bottom():
            y = cursor_global.y() - self.height() - 8
        self.move(x, y)
        self.show()
        self.raise_()


# ── Markdown editor with image paste and wikilink hover ───────────────────────

class _MarkdownEditor(QTextEdit):
    """QTextEdit subclass that handles image paste/drop and wikilink hover previews."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vault_root: Path | None = None
        self._file_path: Path | None = None
        self._preview: _WikilinkPreview | None = None
        self._hover_target: str = ""
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(500)
        self._hover_timer.timeout.connect(self._show_wikilink_preview)
        self.setMouseTracking(True)

    def set_vault_root(self, root: Path) -> None:
        self._vault_root = root

    def set_file_path(self, path: Path) -> None:
        self._file_path = path

    # ── Image paste ───────────────────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        is_paste = (
            event.key() == Qt.Key.Key_V and
            (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
        )
        if is_paste and self._try_paste_image():
            return
        super().keyPressEvent(event)

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                local = url.toLocalFile()
                if local and Path(local).suffix.lower() in _IMAGE_EXTS:
                    if self._save_and_insert_image_file(Path(local)):
                        event.acceptProposedAction()
                        return
        super().dropEvent(event)

    def _try_paste_image(self) -> bool:
        mime = QApplication.clipboard().mimeData()
        if mime.hasImage():
            img: QImage = mime.imageData()
            if not img.isNull():
                return self._save_and_insert_qimage(img)
        if mime.hasUrls():
            for url in mime.urls():
                local = url.toLocalFile()
                if local and Path(local).suffix.lower() in _IMAGE_EXTS:
                    if self._save_and_insert_image_file(Path(local)):
                        return True
        return False

    def _assets_dir(self) -> Path:
        # Always store images next to the note so relative `.assets/` links work
        if self._file_path:
            return self._file_path.parent / ".assets"
        if self._vault_root:
            return self._vault_root / ".assets"
        return Path(".assets")

    def _save_and_insert_qimage(self, img: QImage) -> bool:
        assets = self._assets_dir()
        try:
            assets.mkdir(parents=True, exist_ok=True)
            filename = f"pasted_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            save_path = assets / filename
            if not img.save(str(save_path), "PNG"):
                return False
            self.insertPlainText(f"![image](.assets/{filename})")
            return True
        except Exception as exc:
            logger.warning("_MarkdownEditor: image save failed: %s", exc)
            return False

    def _save_and_insert_image_file(self, src: Path) -> bool:
        import shutil
        assets = self._assets_dir()
        try:
            assets.mkdir(parents=True, exist_ok=True)
            filename = src.name
            dest = assets / filename
            if not dest.exists():
                shutil.copy2(str(src), str(dest))
            self.insertPlainText(f"![image](.assets/{filename})")
            return True
        except Exception as exc:
            logger.warning("_MarkdownEditor: image file copy failed: %s", exc)
            return False

    # ── Wikilink hover ────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        cursor = self.cursorForPosition(event.pos())
        block_text = cursor.block().text()
        col = cursor.positionInBlock()

        target = self._wikilink_at(block_text, col)
        if target != self._hover_target:
            self._hover_target = target
            self._hover_timer.stop()
            if self._preview and self._preview.isVisible():
                self._preview.hide()
            if target:
                self._hover_timer.start()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._hover_timer.stop()
        self._hover_target = ""
        if self._preview:
            self._preview.hide()

    @staticmethod
    def _wikilink_at(line: str, col: int) -> str:
        for m in _WIKILINK_RE.finditer(line):
            if m.start() <= col <= m.end():
                return m.group(1).strip()
        return ""

    def _show_wikilink_preview(self) -> None:
        if not self._hover_target or not self._vault_root:
            return
        target_path = self._resolve_wikilink(self._hover_target)
        if not target_path:
            return

        if self._preview is None:
            self._preview = _WikilinkPreview()

        from PyQt6.QtGui import QCursor
        self._preview.show_for(target_path, self._vault_root, QCursor.pos())

    def _resolve_wikilink(self, stem: str) -> Path | None:
        if not self._vault_root:
            return None
        stem_lower = stem.lower()
        for md in self._vault_root.rglob("*.md"):
            if md.stem.lower() == stem_lower:
                return md
        return None


# ── EditorTab ─────────────────────────────────────────────────────────────────

class EditorTab(QWidget):
    """One tab for a single vault file."""

    content_changed = pyqtSignal()
    file_saved = pyqtSignal(str)  # emits the file path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path: Path | None = None
        self._vault_root: str = ""
        self._mode: _MODE = "preview"
        self._dirty: bool = False

        self.setStyleSheet(f"background: {PANEL_BG};")
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Header ──────────────────────────────────────────────────────────
        self._file_lbl = QLabel("—")
        self._file_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px;"
            f" color: {TEXT_FAINT}; text-transform: uppercase;"
        )

        self._btn_preview = _mode_btn("Preview")
        self._btn_raw     = _mode_btn("Raw")
        self._btn_preview.setChecked(True)

        self._btn_preview.clicked.connect(lambda: self._switch_mode("preview"))
        self._btn_raw.clicked.connect(lambda: self._switch_mode("raw"))

        self._save_btn = QPushButton("Save")
        self._save_btn.setEnabled(False)
        self._save_btn.setFixedHeight(22)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: {TEXT}; color: #fff; border: none;"
            f" border-radius: 4px; font-size: 10.5px; font-weight: 600; padding: 0 10px; }}"
            f"QPushButton:hover {{ background: #3a3830; }}"
            f"QPushButton:disabled {{ background: {BORDER_SOFT}; color: {TEXT_FAINT}; }}"
        )
        self._save_btn.clicked.connect(self.save_file)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(12, 0, 8, 0)
        header_row.setSpacing(6)
        header_row.addWidget(self._file_lbl)
        header_row.addStretch()
        header_row.addWidget(self._btn_preview)
        header_row.addWidget(self._btn_raw)
        header_row.addSpacing(8)
        header_row.addWidget(self._save_btn)

        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(
            f"background: {PANEL_BG}; border-bottom: 1px solid {BORDER_SOFT};"
        )
        header.setLayout(header_row)

        # ── Content ──────────────────────────────────────────────────────────
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background: {PANEL_BG}; border: none; }}"
        )
        self._browser.document().setDocumentMargin(24)

        self._editor = _MarkdownEditor()
        self._editor.setAcceptRichText(False)
        self._editor.setStyleSheet(
            f"QTextEdit {{ background: {SIDEBAR_BG}; color: {TEXT}; border: none;"
            f" font-family: 'JetBrains Mono', 'Menlo', 'Monaco', monospace;"
            f" font-size: 12px; line-height: 1.55; }}"
        )
        self._editor.document().setDocumentMargin(20)
        self._editor.textChanged.connect(self._on_text_changed)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._browser)  # 0 = preview
        self._stack.addWidget(self._editor)   # 1 = raw / edit

        # ── Layout ───────────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._stack, 1)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_file(self, path: str, vault_root: str = "") -> None:
        self._path = Path(path)
        self._vault_root = vault_root
        self._editor.set_file_path(self._path)
        if vault_root:
            self._editor.set_vault_root(Path(vault_root))

        try:
            content = self._path.read_text(encoding="utf-8")
        except Exception:
            logger.exception("EditorTab: could not read %s", path)
            content = f"# Could not read file\n\n{path}"

        self._editor.blockSignals(True)
        self._editor.setPlainText(content)
        self._editor.blockSignals(False)

        self._dirty = False
        self._save_btn.setEnabled(False)
        self._file_lbl.setText(self._path.name.upper())
        self._apply_mode(self._mode)

    def get_content(self) -> str:
        return self._editor.toPlainText()

    def save_file(self) -> None:
        if not self._path:
            return
        content = self._editor.toPlainText()
        try:
            fd, tmp = tempfile.mkstemp(
                dir=self._path.parent, suffix=".tmp", prefix=".echos_"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp, self._path)
        except Exception:
            logger.exception("EditorTab: save failed for %s", self._path)
            try:
                os.unlink(tmp)
            except Exception:
                pass
            return
        self._dirty = False
        self._save_btn.setEnabled(False)
        self.file_saved.emit(str(self._path))

    def set_mode(self, mode: str) -> None:
        if mode in ("preview", "raw"):
            self._switch_mode(mode)  # type: ignore[arg-type]

    def file_path(self) -> str:
        return str(self._path) if self._path else ""

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    # ── Internal ───────────────────────────────────────────────────────────────

    def _switch_mode(self, mode: _MODE) -> None:
        self._mode = mode
        self._btn_preview.setChecked(mode == "preview")
        self._btn_raw.setChecked(mode == "raw")
        self._apply_mode(mode)

    def _apply_mode(self, mode: _MODE) -> None:
        if mode == "preview":
            html = _md_to_html(self._editor.toPlainText())
            if self._path:
                from PyQt6.QtCore import QUrl
                # setHtml(str) only — set base URL on the document first so
                # relative .assets/ image paths resolve correctly.
                self._browser.document().setBaseUrl(
                    QUrl.fromLocalFile(str(self._path.parent) + "/")
                )
            self._browser.setHtml(html)
            self._stack.setCurrentIndex(0)
            self._editor.setReadOnly(True)
        else:  # raw — fully editable
            self._editor.setReadOnly(False)
            self._stack.setCurrentIndex(1)

    def _on_text_changed(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._save_btn.setEnabled(True)
        self.content_changed.emit()

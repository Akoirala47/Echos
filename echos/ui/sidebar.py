"""Sidebar — vault tree + topics, matching the UI mockup exactly."""

from __future__ import annotations

import uuid
from pathlib import Path

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from echos.core.vault_watcher import VaultWatcher
from echos.utils.theme import (
    ACCENT, BORDER, BORDER_SOFT, SELECTED_STRONG, SIDEBAR_BG,
    TEXT, TEXT_FAINT, TEXT_MUTED,
)

_PRESET_COLORS = [
    "#c2410c", "#be185d", "#1c8b4a", "#1d4ed8",
    "#7c3aed", "#0369a1", "#76746b", "#92400e",
]

# ── Icon helpers ──────────────────────────────────────────────────────────────

def _folder_icon(size: int = 16, fill: str = "#d1cfc4", stroke: str = "#a8a69a") -> QIcon:
    """Paint a folder shape matching the mockup SVG."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = size / 14.0
    path = QPainterPath()
    # Closed folder outline from mockup SVG
    path.moveTo(1.5*s, 3*s)
    path.quadTo(1.5*s, 2*s, 2.5*s, 2*s)
    path.lineTo(5*s,  2*s)
    path.lineTo(6*s,  3*s)
    path.lineTo(11*s, 3*s)
    path.quadTo(12*s, 3*s, 12*s, 4*s)
    path.lineTo(12*s, 11*s)
    path.quadTo(12*s, 12*s, 11*s, 12*s)
    path.lineTo(2.5*s, 12*s)
    path.quadTo(1.5*s, 12*s, 1.5*s, 11*s)
    path.closeSubpath()

    p.fillPath(path, QColor(fill))
    pen = QPen(QColor(stroke))
    pen.setWidthF(0.9 * s)
    p.setPen(pen)
    p.drawPath(path)
    p.end()
    return QIcon(px)


def _note_icon(size: int = 14, color: str = "#76746b") -> QIcon:
    """Paint a document icon matching the mockup SVG."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setOpacity(0.7)

    s = size / 12.0
    pen = QPen(QColor(color))
    pen.setWidthF(0.85 * s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # Document body
    body = QPainterPath()
    body.moveTo(3*s,   1.5*s)
    body.lineTo(8*s,   1.5*s)
    body.lineTo(10*s,  3.5*s)
    body.lineTo(10*s,  10*s)
    body.quadTo(10*s,  10.5*s, 9.5*s, 10.5*s)
    body.lineTo(3*s,   10.5*s)
    body.quadTo(2.5*s, 10.5*s, 2.5*s, 10*s)
    body.lineTo(2.5*s, 2*s)
    body.quadTo(2.5*s, 1.5*s, 3*s, 1.5*s)
    body.closeSubpath()
    p.drawPath(body)

    # Folded corner
    corner = QPainterPath()
    corner.moveTo(8*s, 1.5*s)
    corner.lineTo(8*s, 3.5*s)
    corner.lineTo(10*s, 3.5*s)
    p.drawPath(corner)

    # Text lines
    from PyQt6.QtCore import QLineF
    p.drawLine(QLineF(4*s, 6*s,   8*s, 6*s))
    p.drawLine(QLineF(4*s, 7.6*s, 8*s, 7.6*s))
    p.drawLine(QLineF(4*s, 9.2*s, 6.5*s, 9.2*s))
    p.end()
    return QIcon(px)


_ICON_FOLDER      = None
_ICON_FOLDER_WARM = None
_ICON_NOTE        = None


def _get_folder_icon(warm: bool = False) -> QIcon:
    global _ICON_FOLDER, _ICON_FOLDER_WARM
    if warm:
        if _ICON_FOLDER_WARM is None:
            _ICON_FOLDER_WARM = _folder_icon(fill="#ddb18d", stroke="#c49870")
        return _ICON_FOLDER_WARM
    if _ICON_FOLDER is None:
        _ICON_FOLDER = _folder_icon()
    return _ICON_FOLDER


def _get_note_icon() -> QIcon:
    global _ICON_NOTE
    if _ICON_NOTE is None:
        _ICON_NOTE = _note_icon()
    return _ICON_NOTE


# ── Collapsible section header ────────────────────────────────────────────────

class _SectionHeader(QWidget):
    toggled = pyqtSignal(bool)  # True = expanded

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = True

        self._chev = QLabel("▾")
        self._chev.setStyleSheet(f"font-size: 9px; color: {TEXT_FAINT}; min-width: 10px;")

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px; color: {TEXT_FAINT};"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 9, 8, 4)
        row.setSpacing(5)
        row.addWidget(self._chev)
        row.addWidget(self._lbl)
        row.addStretch()
        self.setLayout(row)
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def add_right_widget(self, w: QWidget) -> None:
        self.layout().addWidget(w)

    def mousePressEvent(self, _event) -> None:
        self._expanded = not self._expanded
        self._chev.setText("▾" if self._expanded else "▸")
        self.toggled.emit(self._expanded)


# ── Vault tree ────────────────────────────────────────────────────────────────

class _VaultTree(QTreeWidget):
    folder_selected = pyqtSignal(str)
    note_selected   = pyqtSignal(str)   # emits str(Path)
    record_here     = pyqtSignal(str)

    _MAX_DEPTH = 5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vault_root: Path | None = None

        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.setAnimated(True)
        self.setFrameShape(QTreeWidget.Shape.NoFrame)
        self.setIconSize(QSize(14, 14))
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformRowHeights(True)
        self.setStyleSheet(f"""
            QTreeWidget {{
                background: transparent;
                color: {TEXT};
                font-size: 12.5px;
                outline: 0;
                border: none;
                show-decoration-selected: 1;
            }}
            QTreeWidget::item {{
                height: 24px;
                padding-left: 2px;
                border-radius: 4px;
            }}
            QTreeWidget::item:selected {{
                background: {SELECTED_STRONG};
                color: {TEXT};
            }}
            QTreeWidget::item:hover:!selected {{
                background: rgba(0,0,0,0.04);
            }}
            QTreeWidget::branch {{
                background: transparent;
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: none;
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                image: none;
            }}
        """)
        self.itemClicked.connect(self._on_item_clicked)

    def load_vault(self, vault_path: str) -> None:
        self.clear()
        root = Path(vault_path)
        if not root.is_dir():
            return
        self._vault_root = root
        self._populate(None, root, 0)

    def _populate(self, parent: QTreeWidgetItem | None, path: Path, depth: int) -> None:
        if depth > self._MAX_DEPTH:
            return
        try:
            entries = sorted(
                path.iterdir(),
                key=lambda e: (e.is_file(), e.name.lower()),
            )
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") or entry.name in (".obsidian", "__pycache__"):
                continue
            if entry.is_dir():
                item = QTreeWidgetItem([entry.name])
                item.setIcon(0, _get_folder_icon(warm=False))
                item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "folder", "path": entry})
                item.setForeground(0, QColor(TEXT))
                if parent is None:
                    self.addTopLevelItem(item)
                else:
                    parent.addChild(item)
                self._populate(item, entry, depth + 1)
            elif entry.suffix.lower() == ".md":
                item = QTreeWidgetItem([entry.stem])
                item.setIcon(0, _get_note_icon())
                item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "note", "path": entry})
                item.setForeground(0, QColor(TEXT_MUTED))
                if parent is None:
                    self.addTopLevelItem(item)
                else:
                    parent.addChild(item)

    def expand_to_path(self, folder_path: str) -> None:
        """Expand and select the tree item matching *folder_path* (relative to vault)."""
        parts = [p for p in folder_path.replace("\\", "/").split("/") if p]
        if not parts:
            return
        item = self._find_item_by_parts(self.invisibleRootItem(), parts)
        if item:
            self.expandItem(item)
            self.setCurrentItem(item)
            self.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)

    def _find_item_by_parts(
        self, parent: QTreeWidgetItem, parts: list[str]
    ) -> QTreeWidgetItem | None:
        if not parts:
            return None
        target = parts[0]
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.text(0) == target:
                if len(parts) == 1:
                    return child
                self.expandItem(child)
                return self._find_item_by_parts(child, parts[1:])
        return None

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if data.get("kind") == "folder" and self._vault_root:
            rel = str(data["path"].relative_to(self._vault_root))
            self.folder_selected.emit(rel)
        elif data.get("kind") == "note":
            self.note_selected.emit(str(data["path"]))


# ── Color swatch ──────────────────────────────────────────────────────────────

class _ColorSwatch(QWidget):
    clicked = pyqtSignal()

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self._selected = False
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _set_selected(self, v: bool) -> None:
        self._selected = v
        self.update()

    def mousePressEvent(self, _event) -> None:
        self.clicked.emit()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(self._color))
        p.setPen(QPen(QColor(TEXT), 1.5) if self._selected else Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 16, 16)
        p.end()


# ── Vault folder picker dialog (used by AddTopicDialog) ───────────────────────

class _FolderPickerDialog(QDialog):
    """Compact dialog that shows the vault tree so the user can pick a folder."""

    def __init__(self, vault_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose Vault Folder")
        self.setMinimumSize(300, 360)

        self._selected: str = ""

        self._tree = _VaultTree()
        self._tree.folder_selected.connect(self._on_folder_selected)
        if vault_path:
            self._tree.load_vault(vault_path)

        self._ok_btn = QPushButton("Select")
        self._ok_btn.setEnabled(False)
        self._ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._ok_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._tree, 1)
        layout.addLayout(btn_row)

    def _on_folder_selected(self, path: str) -> None:
        self._selected = path
        self._ok_btn.setEnabled(True)

    def selected_path(self) -> str:
        return self._selected


# ── Add Topic dialog ──────────────────────────────────────────────────────────

class AddTopicDialog(QDialog):
    def __init__(self, vault_path: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Topic")
        self.setFixedWidth(360)
        self._vault_path = vault_path

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. CS446, Work Meetings, Research")
        self._name_edit.textChanged.connect(self._on_name_changed)

        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("e.g. School/CS446/Lectures")

        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setEnabled(bool(vault_path))
        self._browse_btn.setFixedHeight(26)
        self._browse_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11.5px; padding: 0 10px; }}"
        )
        self._browse_btn.clicked.connect(self._on_browse)

        folder_container = QWidget()
        folder_row = QHBoxLayout(folder_container)
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(6)
        folder_row.addWidget(self._folder_edit, 1)
        folder_row.addWidget(self._browse_btn)

        self._selected_color = _PRESET_COLORS[0]
        swatches = QHBoxLayout()
        swatches.setSpacing(6)
        self._swatches: list[_ColorSwatch] = []
        for c in _PRESET_COLORS:
            sw = _ColorSwatch(c)
            sw.clicked.connect(self._make_handler(sw))
            swatches.addWidget(sw)
            self._swatches.append(sw)
        self._swatches[0]._set_selected(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Name:", self._name_edit)
        form.addRow("Vault folder:", folder_container)
        form.addRow("Color:", swatches)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _make_handler(self, sw: _ColorSwatch):
        def _h():
            for s in self._swatches:
                s._set_selected(False)
            sw._set_selected(True)
            self._selected_color = sw._color
        return _h

    def _on_browse(self) -> None:
        dlg = _FolderPickerDialog(self._vault_path, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            path = dlg.selected_path()
            if path:
                self._folder_edit.setText(path)

    def _on_name_changed(self, name: str) -> None:
        if not self._folder_edit.text():
            self._folder_edit.setText(name.strip().replace(" ", "-"))

    def get_topic(self) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "name": self._name_edit.text().strip(),
            "folder": self._folder_edit.text().strip(),
            "color": self._selected_color,
        }


# ── Topic row ─────────────────────────────────────────────────────────────────

class _TopicRow(QWidget):
    clicked = pyqtSignal()

    # Selection fill: rgba(194,65,12, 0.18)
    _SEL_COLOR   = QColor(194, 65, 12, 46)
    # Hover fill: rgba(0,0,0, 0.04)
    _HOVER_COLOR = QColor(0, 0, 0, 10)

    def __init__(self, topic: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._topic = topic
        self._selected = False
        self._hovered  = False

        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        dot = QLabel()
        dot.setFixedSize(9, 9)
        dot.setStyleSheet(
            f"border-radius: 4px; background: {topic.get('color', ACCENT)};"
        )

        self._name_lbl = QLabel(topic.get("name", ""))
        self._name_lbl.setStyleSheet(f"font-size: 12.5px; color: {TEXT}; background: transparent;")

        folder = topic.get("folder", "")
        parts = folder.replace("\\", "/").split("/")
        tail  = " / ".join(parts[-2:]) if len(parts) >= 2 else folder
        self._path_lbl = QLabel(tail)
        self._path_lbl.setStyleSheet(f"font-size: 10.5px; color: {TEXT_FAINT}; background: transparent;")
        self._path_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)
        row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._name_lbl, 1)
        row.addWidget(self._path_lbl, 0)
        self.setLayout(row)

    def set_selected(self, v: bool) -> None:
        self._selected = v
        weight = "600" if v else "400"
        self._name_lbl.setStyleSheet(
            f"font-size: 12.5px; font-weight: {weight}; color: {TEXT}; background: transparent;"
        )
        self.update()

    # ── Events ────────────────────────────────────────────────────────────────

    def mousePressEvent(self, _event) -> None:
        self.clicked.emit()

    def enterEvent(self, _event) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, _event) -> None:
        self._hovered = False
        self.update()

    def paintEvent(self, _event) -> None:
        if self._selected or self._hovered:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(self._SEL_COLOR if self._selected else self._HOVER_COLOR)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(self.rect().adjusted(0, 1, 0, -1)), 5, 5)
            p.end()


# ── Sidebar ───────────────────────────────────────────────────────────────────

class SidebarWidget(QWidget):
    """Left sidebar: vault tree + topics."""

    course_selected      = pyqtSignal(dict)
    course_added         = pyqtSignal(dict)
    course_deleted       = pyqtSignal(str)
    courses_reordered    = pyqtSignal(list)
    settings_clicked     = pyqtSignal()
    vault_folder_selected = pyqtSignal(str)
    note_selected        = pyqtSignal(str)   # emits str(Path) of .md file

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._courses: list[dict] = []
        self._active_id: str | None = None
        self._topic_rows: list[_TopicRow] = []
        self._vault_path: str = ""

        self._watcher = VaultWatcher(self)
        self._watcher.tree_changed.connect(self._on_vault_changed)

        self.setFixedWidth(248)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"SidebarWidget {{ background: {SIDEBAR_BG}; border-right: 1px solid {BORDER}; }}"
        )
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Vault header ──────────────────────────────────────────────────────
        vault_icon = QLabel()
        vault_icon.setFixedSize(14, 14)
        vault_icon.setPixmap(_folder_icon(14, "#7e6e57", "#5e5040").pixmap(14, 14))

        self._vault_name_lbl = QLabel("No vault")
        self._vault_name_lbl.setStyleSheet(
            f"font-size: 12.5px; font-weight: 600; color: {TEXT};"
        )

        self._vault_path_lbl = QLabel("")
        self._vault_path_lbl.setStyleSheet(f"font-size: 10px; color: {TEXT_FAINT};")
        self._vault_path_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        vault_hdr = QWidget()
        vault_hdr.setFixedHeight(38)
        vault_hdr.setStyleSheet(
            f"background: {SIDEBAR_BG}; border-bottom: 1px solid {BORDER_SOFT};"
        )
        vhr = QHBoxLayout(vault_hdr)
        vhr.setContentsMargins(12, 0, 12, 0)
        vhr.setSpacing(7)
        vhr.addWidget(vault_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        vhr.addWidget(self._vault_name_lbl, 1)
        vhr.addWidget(self._vault_path_lbl)

        # ── VAULT section ─────────────────────────────────────────────────────
        vault_sec_hdr = _SectionHeader("Vault")
        _btn_style = (
            f"QPushButton {{ background: transparent; border: none;"
            f" font-size: 11px; color: {TEXT_MUTED}; padding: 0; }}"
            f"QPushButton:hover {{ color: {TEXT}; }}"
        )
        vault_add_btn = QPushButton("+")
        vault_add_btn.setFixedSize(18, 18)
        vault_add_btn.setToolTip("New folder")
        vault_add_btn.setStyleSheet(_btn_style)
        vault_add_btn.clicked.connect(self._on_create_folder)
        vault_sec_hdr.add_right_widget(vault_add_btn)

        vault_refresh_btn = QPushButton("⟳")
        vault_refresh_btn.setFixedSize(18, 18)
        vault_refresh_btn.setToolTip("Refresh")
        vault_refresh_btn.setStyleSheet(_btn_style)
        vault_refresh_btn.clicked.connect(self._on_vault_changed)
        vault_sec_hdr.add_right_widget(vault_refresh_btn)

        self._vault_tree = _VaultTree()
        self._vault_tree.folder_selected.connect(self.vault_folder_selected)
        self._vault_tree.note_selected.connect(self.note_selected)
        vault_sec_hdr.toggled.connect(self._vault_tree.setVisible)

        # T-B66: empty-state label — shown when vault is not set or is empty
        self._vault_empty_lbl = QLabel()
        self._vault_empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vault_empty_lbl.setWordWrap(True)
        self._vault_empty_lbl.setStyleSheet(
            f"color: {TEXT_FAINT}; font-size: 11.5px; padding: 16px 12px;"
            f" background: transparent;"
        )
        self._vault_empty_lbl.hide()

        vault_section = QWidget()
        vault_section.setStyleSheet(
            f"background: {SIDEBAR_BG}; border-bottom: 1px solid {BORDER_SOFT};"
        )
        vsl = QVBoxLayout(vault_section)
        vsl.setContentsMargins(0, 0, 0, 4)
        vsl.setSpacing(0)
        vsl.addWidget(vault_sec_hdr)
        vsl.addWidget(self._vault_tree, 1)
        vsl.addWidget(self._vault_empty_lbl)

        # ── TOPICS section ────────────────────────────────────────────────────
        topics_sec_hdr = _SectionHeader("Topics")
        add_btn = QPushButton("+")
        add_btn.setFixedSize(18, 18)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" font-size: 14px; font-weight: 500; color: {TEXT_MUTED}; padding: 0; line-height: 1; }}"
            f"QPushButton:hover {{ color: {TEXT}; }}"
        )
        add_btn.clicked.connect(self._on_add_topic)
        topics_sec_hdr.add_right_widget(add_btn)

        self._topics_container = QWidget()
        self._topics_container.setStyleSheet(f"background: {SIDEBAR_BG};")
        self._topics_layout = QVBoxLayout(self._topics_container)
        self._topics_layout.setContentsMargins(6, 2, 6, 4)
        self._topics_layout.setSpacing(1)
        topics_sec_hdr.toggled.connect(self._topics_container.setVisible)

        topics_section = QWidget()
        topics_section.setStyleSheet(f"background: {SIDEBAR_BG};")
        tsl = QVBoxLayout(topics_section)
        tsl.setContentsMargins(0, 0, 0, 0)
        tsl.setSpacing(0)
        tsl.addWidget(topics_sec_hdr)
        tsl.addWidget(self._topics_container)

        # ── Scroll area ───────────────────────────────────────────────────────
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background: {SIDEBAR_BG};")
        scl = QVBoxLayout(scroll_content)
        scl.setContentsMargins(0, 0, 0, 0)
        scl.setSpacing(0)
        scl.addWidget(vault_section, 3)
        scl.addWidget(topics_section, 0)
        scl.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(scroll_content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {SIDEBAR_BG}; border: none;")

        # ── Footer ────────────────────────────────────────────────────────────
        settings_btn = QPushButton("⚙  Settings")
        settings_btn.setFlat(True)
        settings_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; text-align: left;"
            f" font-size: 12px; color: {TEXT_MUTED}; padding: 6px 10px; }}"
            f"QPushButton:hover {{ color: {TEXT}; }}"
        )
        settings_btn.clicked.connect(self.settings_clicked)

        footer = QWidget()
        footer.setFixedHeight(36)
        footer.setStyleSheet(
            f"background: {SIDEBAR_BG}; border-top: 1px solid {BORDER_SOFT};"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(settings_btn)

        # ── Outer layout ──────────────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(vault_hdr)
        outer.addWidget(scroll, 1)
        outer.addWidget(footer)
        self.setLayout(outer)

        # Initial empty state (no vault set yet)
        self._update_vault_state()

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_vault_path(self, vault_path: str) -> None:
        if not vault_path:
            return
        self._vault_path = vault_path
        p = Path(vault_path)
        self._vault_name_lbl.setText(p.name)
        home = str(Path.home())
        display = vault_path.replace(home, "~")
        self._vault_path_lbl.setText(str(Path(display).parent))
        self._vault_tree.load_vault(vault_path)
        self._watcher.watch(vault_path)
        self._update_vault_state()

    def load_courses(self, courses: list[dict]) -> None:
        self._courses = list(courses)
        self._rebuild_topics()

    def current_course(self) -> dict | None:
        return next((c for c in self._courses if c["id"] == self._active_id), None)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _rebuild_topics(self) -> None:
        for row in self._topic_rows:
            row.setParent(None)
        self._topic_rows.clear()

        for course in self._courses:
            row = _TopicRow(course)
            row.clicked.connect(self._make_handler(course, row))
            row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            row.customContextMenuRequested.connect(
                lambda pos, c=course, r=row: self._show_menu(c, r, pos)
            )
            self._topics_layout.addWidget(row)
            self._topic_rows.append(row)

        self._topics_layout.addStretch(1)
        self._refresh_active()

    def _make_handler(self, course: dict, row: _TopicRow):
        def _h():
            self._active_id = course["id"]
            self._refresh_active()
            self.course_selected.emit(course)
        return _h

    def _refresh_active(self) -> None:
        for i, row in enumerate(self._topic_rows):
            if i < len(self._courses):
                row.set_selected(self._courses[i]["id"] == self._active_id)

    def scroll_to_folder(self, folder_path: str) -> None:
        """Expand the vault section and scroll to *folder_path* in the tree."""
        if not folder_path:
            return
        self._vault_tree.expand_to_path(folder_path)

    def _update_vault_state(self) -> None:
        """Show/hide the vault tree and empty-state label based on current state."""
        if not self._vault_path:
            self._vault_tree.hide()
            self._vault_empty_lbl.setText(
                "Set a vault path in Settings to browse your notes."
            )
            self._vault_empty_lbl.show()
        elif self._vault_tree.topLevelItemCount() == 0:
            self._vault_tree.hide()
            self._vault_empty_lbl.setText(
                "Vault is empty — your notes will appear here once created."
            )
            self._vault_empty_lbl.show()
        else:
            self._vault_empty_lbl.hide()
            self._vault_tree.show()

    def _on_add_topic(self) -> None:
        dlg = AddTopicDialog(vault_path=self._vault_path, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            topic = dlg.get_topic()
            if topic["name"] and topic["folder"]:
                self._courses.append(topic)
                self.course_added.emit(topic)
                self._rebuild_topics()

    def _show_menu(self, course: dict, row: _TopicRow, pos) -> None:
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Topic")
        action = menu.exec(row.mapToGlobal(pos))
        if action == delete_action:
            confirm = QMessageBox.question(
                self, "Delete Topic",
                f"Delete \"{course['name']}\"? This only removes it from Echos — "
                "vault files are not affected.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self._courses = [c for c in self._courses if c["id"] != course["id"]]
                if self._active_id == course["id"]:
                    self._active_id = None
                self.course_deleted.emit(course["id"])
                self._rebuild_topics()

    def _on_vault_changed(self) -> None:
        if self._vault_path:
            self._vault_tree.load_vault(self._vault_path)
            self._update_vault_state()

    def _on_create_folder(self) -> None:
        if not self._vault_path:
            QMessageBox.warning(self, "No Vault", "Set a vault path in Settings first.")
            return
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        name = name.strip()
        if not ok or not name:
            return
        folder = Path(self._vault_path) / name
        try:
            folder.mkdir(parents=True, exist_ok=True)
            self._vault_tree.load_vault(self._vault_path)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not create folder:\n{exc}")

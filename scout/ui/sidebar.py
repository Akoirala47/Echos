from __future__ import annotations

import uuid

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

_PRESET_COLORS = [
    "#2980B9", "#27AE60", "#E74C3C", "#F39C12",
    "#8E44AD", "#16A085", "#D35400", "#7F8C8D",
]

_ITEM_HEIGHT = 36
_DOT_RADIUS = 5


# ---------------------------------------------------------------------------
# Custom delegate — draws colour dot + course name
# ---------------------------------------------------------------------------

class _CourseDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()

        # Selection background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        course: dict = index.data(Qt.ItemDataRole.UserRole) or {}
        color = QColor(course.get("color", _PRESET_COLORS[0]))
        name = course.get("name", "")

        # Color dot
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        cx = option.rect.left() + 14
        cy = option.rect.center().y()
        painter.drawEllipse(cx - _DOT_RADIUS, cy - _DOT_RADIUS, _DOT_RADIUS * 2, _DOT_RADIUS * 2)

        # Course name
        text_rect = option.rect.adjusted(28, 0, -8, 0)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())
        font = painter.font()
        font.setPointSize(13)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, name)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(180, _ITEM_HEIGHT)


# ---------------------------------------------------------------------------
# Add Course dialog
# ---------------------------------------------------------------------------

class _ColorSwatch(QPushButton):
    def __init__(self, color: str, parent=None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(24, 24)
        self._set_selected(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _set_selected(self, selected: bool) -> None:
        border = "#333" if selected else "transparent"
        self.setStyleSheet(
            f"background-color: {self._color};"
            f"border-radius: 12px;"
            f"border: 2px solid {border};"
        )

    @property
    def color(self) -> str:
        return self._color


class AddCourseDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Course")
        self.setFixedWidth(340)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. CS446")
        self._name_edit.textChanged.connect(self._on_name_changed)

        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("e.g. CS446")

        self._selected_color = _PRESET_COLORS[0]
        swatches_layout = QHBoxLayout()
        self._swatches: list[_ColorSwatch] = []
        for c in _PRESET_COLORS:
            sw = _ColorSwatch(c)
            sw.clicked.connect(lambda _, sw=sw: self._select_color(sw))
            swatches_layout.addWidget(sw)
        self._swatches = [_ColorSwatch(c) for c in _PRESET_COLORS]
        # Rebuild with proper references
        for i in reversed(range(swatches_layout.count())):
            swatches_layout.itemAt(i).widget().deleteLater()
        self._swatches = []
        for c in _PRESET_COLORS:
            sw = _ColorSwatch(c)
            sw.clicked.connect(self._make_swatch_handler(sw))
            swatches_layout.addWidget(sw)
            self._swatches.append(sw)
        self._swatches[0]._set_selected(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Course name:", self._name_edit)
        form.addRow("Vault folder:", self._folder_edit)
        form.addRow("Color:", swatches_layout)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _make_swatch_handler(self, sw: _ColorSwatch):
        def handler():
            self._select_color(sw)
        return handler

    def _select_color(self, chosen: _ColorSwatch) -> None:
        for sw in self._swatches:
            sw._set_selected(sw is chosen)
        self._selected_color = chosen.color

    def _on_name_changed(self, text: str) -> None:
        # Auto-fill folder from name if folder is empty or was previously auto-filled.
        safe = "".join(c for c in text if c.isalnum() or c in "-_ ").strip()
        self._folder_edit.setText(safe)

    def get_course(self) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "name": self._name_edit.text().strip(),
            "folder": self._folder_edit.text().strip(),
            "color": self._selected_color,
        }


# ---------------------------------------------------------------------------
# SidebarWidget
# ---------------------------------------------------------------------------

class _DroppableList(QListWidget):
    """QListWidget that emits a signal after an internal drag-drop reorder."""

    order_changed = pyqtSignal()

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        self.order_changed.emit()


class SidebarWidget(QWidget):
    """Left sidebar: course list with add/delete/reorder + Settings button.

    Signals
    -------
    course_selected : dict
        Emitted when the user clicks a course.
    course_added : dict
        Emitted when a new course is confirmed in the dialog.
    course_deleted : str
        Emitted with the course id when a course is deleted.
    courses_reordered : list[dict]
        Emitted with the new ordered list after drag-drop.
    settings_clicked
        Emitted when the ⚙ Settings button is pressed.
    """

    course_selected = pyqtSignal(dict)
    course_added = pyqtSignal(dict)
    course_deleted = pyqtSignal(str)
    courses_reordered = pyqtSignal(list)
    settings_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(186)
        # Use palette-aware background so the sidebar adapts to dark mode.
        self.setStyleSheet("background: palette(window);")

        # Header label
        header = QLabel("COURSES")
        header.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #999; padding: 10px 10px 4px 10px;"
        )

        # Course list
        self._list = _DroppableList()
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setItemDelegate(_CourseDelegate())
        self._list.setSpacing(0)
        self._list.setFrameShape(QListWidget.Shape.NoFrame)
        self._list.setStyleSheet("background: transparent; outline: 0;")
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.order_changed.connect(self._on_order_changed)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)

        # Add course button
        add_btn = QPushButton("+ Course")
        add_btn.setFlat(True)
        add_btn.setStyleSheet(
            "color: #555; font-size: 12px; padding: 4px 10px; text-align: left;"
        )
        add_btn.clicked.connect(self._on_add_course)

        # Separator + Settings button
        settings_btn = QPushButton("\u2699  Settings")
        settings_btn.setFlat(True)
        settings_btn.setStyleSheet(
            "color: #666; font-size: 12px; padding: 6px 10px; text-align: left;"
        )
        settings_btn.clicked.connect(self.settings_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._list, 1)
        layout.addWidget(add_btn)
        layout.addWidget(settings_btn)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_courses(self, courses: list[dict]) -> None:
        """Populate the list from a list of course dicts."""
        self._list.clear()
        for course in courses:
            self._add_item(course)

    def add_course(self, course: dict) -> None:
        self._add_item(course)

    def current_course(self) -> dict | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_item(self, course: dict) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, course)
        item.setSizeHint(QSize(180, _ITEM_HEIGHT))
        self._list.addItem(item)

    def _on_selection_changed(self, current: QListWidgetItem, _) -> None:
        if current is not None:
            course = current.data(Qt.ItemDataRole.UserRole)
            self.course_selected.emit(course)

    def _on_order_changed(self) -> None:
        courses = self._all_courses()
        self.courses_reordered.emit(courses)

    def _on_add_course(self) -> None:
        dlg = AddCourseDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            course = dlg.get_course()
            if course["name"] and course["folder"]:
                self._add_item(course)
                self.course_added.emit(course)

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Course")
        action = menu.exec(self._list.mapToGlobal(pos))
        if action == delete_action:
            course = item.data(Qt.ItemDataRole.UserRole)
            confirm = QMessageBox.question(
                self,
                "Delete Course",
                f"Delete \"{course['name']}\"? This only removes it from Scout — "
                "vault files are not affected.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                row = self._list.row(item)
                self._list.takeItem(row)
                self.course_deleted.emit(course["id"])

    def _all_courses(self) -> list[dict]:
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QWidget,
)

_DOT_SIZE = 10


class ColorDot(QWidget):
    """Small filled circle indicating a course colour."""

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(_DOT_SIZE, _DOT_SIZE)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, _DOT_SIZE, _DOT_SIZE)
        painter.end()


class CourseItemWidget(QWidget):
    """Composite widget: colour dot + course name label.

    Used as a custom widget inside QListWidget items via
    QListWidget.setItemWidget().
    """

    def __init__(
        self,
        name: str,
        color: str = "#2980B9",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._dot = ColorDot(color, self)
        self._label = QLabel(name, self)
        self._label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._label, 1)
        self.setLayout(layout)

    # Allow Qt stylesheets to paint the background (needed for selection highlight).
    def paintEvent(self, event) -> None:  # noqa: N802
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def set_name(self, name: str) -> None:
        self._label.setText(name)

    def set_color(self, color: str) -> None:
        self._dot.set_color(color)

    @property
    def name(self) -> str:
        return self._label.text()

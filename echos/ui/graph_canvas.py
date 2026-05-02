"""GraphCanvasWidget — QWebEngineView host for the D3.js knowledge graph."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    _WEB_ENGINE_AVAILABLE = True
except (ImportError, TypeError):
    _WEB_ENGINE_AVAILABLE = False


class _EchosGraphBridge(QObject):
    """QWebChannel object exposed as *echosGraphBridge* to JavaScript."""

    node_clicked = pyqtSignal(str)
    graph_ready = pyqtSignal()

    @pyqtSlot(str)
    def onNodeClicked(self, path: str) -> None:
        self.node_clicked.emit(path)

    @pyqtSlot()
    def onReady(self) -> None:
        self.graph_ready.emit()


class _GraphToolbar(QWidget):
    """Floating toolbar: back button, vault label, search field."""

    back_clicked = pyqtSignal()
    search_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._back_btn = QPushButton("←")
        self._back_btn.setFixedWidth(32)
        self._back_btn.clicked.connect(lambda _=False: self.back_clicked.emit())
        layout.addWidget(self._back_btn)

        self._vault_lbl = QLabel()
        layout.addWidget(self._vault_lbl)

        layout.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self.search_changed)
        layout.addWidget(self._search)

    def set_vault_name(self, name: str) -> None:
        self._vault_lbl.setText(name)


class GraphCanvasWidget(QWidget):
    """Container for the WebGL graph canvas (QWebEngineView + D3 graph.html)."""

    back_requested = pyqtSignal()
    node_clicked = pyqtSignal(str)
    search_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toolbar = _GraphToolbar()
        self._toolbar.back_clicked.connect(self.back_requested)
        self._toolbar.search_changed.connect(self.search_changed)
        layout.addWidget(self._toolbar)

        self._bridge = _EchosGraphBridge()
        self._bridge.node_clicked.connect(self.node_clicked)

        self._view: QWebEngineView | None = None
        self._channel: QWebChannel | None = None

        if _WEB_ENGINE_AVAILABLE:
            self._view = QWebEngineView()
            self._channel = QWebChannel()
            self._channel.registerObject("echosGraphBridge", self._bridge)
            self._view.page().setWebChannel(self._channel)
            layout.addWidget(self._view)
            self._load_html()
        else:
            layout.addWidget(QLabel("Graph view requires PyQt6-WebEngine."))

    def _load_html(self) -> None:
        import echos
        html_path = Path(echos.__file__).parent / "assets" / "graph.html"
        if html_path.exists():
            self._view.load(QUrl.fromLocalFile(str(html_path)))  # type: ignore[union-attr]

    def set_graph_data(self, nodes: list[dict], edges: list[dict]) -> None:
        payload = json.dumps({"nodes": nodes, "edges": edges}, default=str)
        if self._view is not None:
            js = f"if(window.echosGraph){{window.echosGraph.loadGraph({payload});}}"
            self._view.page().runJavaScript(js)

    def set_vault_name(self, name: str) -> None:
        self._toolbar.set_vault_name(name)

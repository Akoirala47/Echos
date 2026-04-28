"""GraphCanvasWidget — wraps the D3 graph.html page in a QWebEngineView.

Provides a Python-side API for loading graph data and reacting to node clicks.
A floating toolbar overlay (Back button + vault label + search field) sits atop
the web view, matching the warm-parchment design language.

Signals
-------
back_requested
    Emitted when the user clicks the "← Back" ghost button.
node_clicked(path: str)
    Emitted when the user clicks a file node in the graph.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from echos.utils.theme import (
    BORDER_SOFT, CANVAS_BG, PANEL_BG, TEXT, TEXT_FAINT, TEXT_MUTED, WINDOW_BG,
)

logger = logging.getLogger(__name__)

# ── Try to import WebEngine (optional — app still launches without it) ──────────
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    _WEB_ENGINE_AVAILABLE = True
except ImportError:
    _WEB_ENGINE_AVAILABLE = False
    logger.warning("PyQt6.QtWebEngineWidgets not available — graph view disabled")


# ── QWebChannel bridge object ─────────────────────────────────────────────────

class _EchosGraphBridge(QObject):
    """Object exposed to JavaScript as ``echosGraphBridge``.

    JS calls ``onNodeClicked`` and ``onReady`` via the bridge.
    Python calls into JS with ``loadGraph`` / ``expandDirectory`` etc.
    """

    node_clicked = pyqtSignal(str)   # JS → Python
    graph_ready  = pyqtSignal()      # JS → Python (onReady called)

    @pyqtSlot(str)
    def onNodeClicked(self, path: str) -> None:  # noqa: N802
        """Called by JS when a file node is clicked."""
        logger.debug("Graph node clicked: %s", path)
        self.node_clicked.emit(path)

    @pyqtSlot()
    def onReady(self) -> None:  # noqa: N802
        """Called by JS once the page has initialised."""
        self.graph_ready.emit()


# ── Toolbar overlay ───────────────────────────────────────────────────────────

class _GraphToolbar(QWidget):
    """Floating toolbar shown in the top-left corner of the graph canvas."""

    back_clicked = pyqtSignal()
    search_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )

        # Back button
        self._back_btn = QPushButton("← Back")
        self._back_btn.setFixedHeight(28)
        self._back_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._back_btn.setCursor(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.CursorShape.PointingHandCursor
        )
        self._back_btn.setStyleSheet(
            f"QPushButton {{"
            f" background: {PANEL_BG}; border: 1px solid {BORDER_SOFT};"
            f" color: {TEXT}; font-size: 12px; font-weight: 500;"
            f" padding: 0 10px; border-radius: 6px;"
            f"}}"
            f"QPushButton:hover {{ background: #f4f2eb; }}"
        )
        self._back_btn.clicked.connect(self.back_clicked)

        # Vault name label
        self._vault_lbl = QLabel("")
        self._vault_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
        )

        # Search field
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter nodes…")
        self._search.setFixedHeight(28)
        self._search.setFixedWidth(180)
        self._search.setStyleSheet(
            f"QLineEdit {{"
            f" background: {PANEL_BG}; border: 1px solid {BORDER_SOFT};"
            f" color: {TEXT}; font-size: 12px; padding: 0 8px; border-radius: 6px;"
            f"}}"
            f"QLineEdit:focus {{ border-color: #c2410c; }}"
        )
        self._search.textChanged.connect(self.search_changed)

        # Layout
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self._back_btn)
        row.addWidget(self._vault_lbl)
        row.addStretch()
        row.addWidget(self._search)

        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_vault_name(self, name: str) -> None:
        self._vault_lbl.setText(name)


# ── GraphCanvasWidget ─────────────────────────────────────────────────────────

class GraphCanvasWidget(QWidget):
    """Full-screen graph canvas widget.

    Wraps a ``QWebEngineView`` loading ``echos/assets/graph.html`` and provides
    a Python API to load data and react to node-click events.

    If ``QtWebEngineWidgets`` is not available, a fallback label is shown instead.
    """

    back_requested = pyqtSignal()          # ← Back button
    node_clicked   = pyqtSignal(str)       # file path clicked in graph

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge: _EchosGraphBridge | None = None
        self._channel: QWebChannel | None = None
        self._view = None
        self._pending_data: tuple[list, list] | None = None
        self._graph_ready = False

        self.setStyleSheet(f"background: {CANVAS_BG};")
        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Toolbar strip — warm parchment header, same pattern as every other
        # panel header in the app (record bar, editor tab, transcript panel).
        toolbar_wrap = QWidget()
        toolbar_wrap.setAttribute(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )
        toolbar_wrap.setStyleSheet(
            f"background: {WINDOW_BG};"
            f" border-bottom: 1px solid {BORDER_SOFT};"
        )
        toolbar_wrap.setFixedHeight(52)
        tw_layout = QHBoxLayout(toolbar_wrap)
        tw_layout.setContentsMargins(12, 0, 12, 0)

        self._toolbar = _GraphToolbar()
        self._toolbar.back_clicked.connect(self.back_requested)
        self._toolbar.search_changed.connect(self._on_search_changed)
        tw_layout.addWidget(self._toolbar)

        outer.addWidget(toolbar_wrap)

        if _WEB_ENGINE_AVAILABLE:
            self._view = QWebEngineView()
            self._view.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )

            # Install a custom page that forwards JS console messages to Python
            # so we can debug graph.html issues in the terminal.
            try:
                from PyQt6.QtWebEngineCore import QWebEnginePage as _QWEPage

                class _DebugPage(_QWEPage):
                    def javaScriptConsoleMessage(self, level, message, line, src):
                        print(f"[JS] {message}")

                self._view.setPage(_DebugPage(self._view))
            except Exception:
                pass  # non-critical — just lose JS console forwarding

            # Disable HTTP cache so subsequent edits to graph.html aren't masked
            # by a cached page on next launch.
            try:
                from PyQt6.QtWebEngineCore import QWebEngineProfile
                profile = self._view.page().profile()
                profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
                profile.clearHttpCache()
            except Exception as exc:
                logger.debug("Could not disable WebEngine HTTP cache: %s", exc)

            # Set up QWebChannel
            self._bridge  = _EchosGraphBridge()
            self._channel = QWebChannel()
            self._channel.registerObject("echosGraphBridge", self._bridge)
            self._view.page().setWebChannel(self._channel)

            self._bridge.node_clicked.connect(self._on_node_clicked)
            self._bridge.graph_ready.connect(self._on_graph_ready)

            # Load the graph HTML — read from disk and inject via setHtml() so
            # we bypass any Chromium disk cache and always run the current JS.
            html_path = Path(__file__).parent.parent / "assets" / "graph.html"
            try:
                html_str = html_path.read_text(encoding="utf-8")
                base_url = QUrl.fromLocalFile(str(html_path.parent) + "/")
                self._view.setHtml(html_str, base_url)
            except Exception as exc:
                logger.warning("Falling back to setUrl for graph.html: %s", exc)
                self._view.setUrl(QUrl.fromLocalFile(str(html_path)))

            outer.addWidget(self._view, 1)
        else:
            # Fallback: plain label
            fallback = QLabel(
                "Graph view requires PyQt6-WebEngine.\n"
                "Install it with: pip install PyQt6-WebEngine"
            )
            fallback.setStyleSheet(
                f"color: {TEXT_FAINT}; font-size: 13px; background: transparent;"
            )
            from PyQt6.QtCore import Qt
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(fallback, 1)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_vault_name(self, name: str) -> None:
        """Set the vault name shown in the toolbar."""
        self._toolbar.set_vault_name(name)

    def set_graph_data(self, nodes: list, edges: list) -> None:
        """Serialise *nodes* + *edges* and call ``loadGraph`` in JS.

        If the page is not ready yet the data is stored and sent once ``onReady``
        fires from JS.
        """
        if not _WEB_ENGINE_AVAILABLE or self._view is None:
            return
        payload = json.dumps({"nodes": nodes, "edges": edges}, default=str)
        if self._graph_ready:
            self._call_js(f"window.echosGraph && window.echosGraph.loadGraph({payload});")
        else:
            self._pending_data = (nodes, edges)

    def expand_directory(self, dir_id: str) -> None:
        """Tell the graph to expand a collapsed directory cluster."""
        if not _WEB_ENGINE_AVAILABLE or self._view is None:
            return
        safe_id = dir_id.replace("\\", "\\\\").replace("'", "\\'")
        self._call_js(f"window.echosGraph && window.echosGraph.expandDirectory('{safe_id}');")

    def collapse_directory(self, dir_id: str) -> None:
        """Tell the graph to collapse an expanded directory cluster."""
        if not _WEB_ENGINE_AVAILABLE or self._view is None:
            return
        safe_id = dir_id.replace("\\", "\\\\").replace("'", "\\'")
        self._call_js(f"window.echosGraph && window.echosGraph.collapseDirectory('{safe_id}');")

    def recenter(self) -> None:
        """Re-centre the D3 view to the current viewport.

        Useful after the QStackedWidget switches to this page — the WebView
        may have just been resized and the JS-side layout needs to refresh.
        """
        if not _WEB_ENGINE_AVAILABLE or self._view is None:
            return
        self._call_js(
            "window.echosGraph && window.echosGraph.recenter && window.echosGraph.recenter();"
        )

    # ── Qt event hooks ────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().showEvent(event)
        # Defer one event-loop tick so the WebView has its final size.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self.recenter)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _call_js(self, script: str) -> None:
        if self._view is not None:
            self._view.page().runJavaScript(script)

    def _on_graph_ready(self) -> None:
        self._graph_ready = True
        if self._pending_data is not None:
            nodes, edges = self._pending_data
            self._pending_data = None
            self.set_graph_data(nodes, edges)

    def _on_node_clicked(self, path: str) -> None:
        self.node_clicked.emit(path)

    def _on_search_changed(self, text: str) -> None:
        safe = text.replace("\\", "\\\\").replace("'", "\\'")
        self._call_js(f"window.echosGraph && window.echosGraph.filterNodes('{safe}');")

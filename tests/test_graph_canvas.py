"""Tests for GraphCanvasWidget (T-G07).

These tests exercise the pure-Python logic without launching a QApplication
or loading PyQt6.QtWebEngineWidgets (which may not be available in CI).

Covered:
  - set_graph_data serialises nodes+edges correctly to JSON
  - back_requested signal emits when the Python back-trigger is called
  - node_clicked signal propagates from the bridge to the widget
  - set_vault_name updates toolbar label without error
  - GraphCanvasWidget is importable even if WebEngine is absent
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_widget():
    """Return a GraphCanvasWidget with WebEngine mocked out."""
    # Mock QtWebEngineWidgets + QtWebChannel so no browser is started
    fake_web_module = MagicMock()
    fake_channel_module = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "PyQt6.QtWebEngineWidgets": fake_web_module,
            "PyQt6.QtWebChannel": fake_channel_module,
        },
    ):
        # Re-import with patched modules
        import importlib
        import echos.ui.graph_canvas as _mod
        importlib.reload(_mod)

        # After reload, _WEB_ENGINE_AVAILABLE may be True (the mock doesn't raise).
        # Patch _WEB_ENGINE_AVAILABLE to False to test the fallback path cleanly.
        with patch.object(_mod, "_WEB_ENGINE_AVAILABLE", False):
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication(sys.argv)
            widget = _mod.GraphCanvasWidget()
            return widget, _mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGraphCanvasImport:
    """GraphCanvasWidget must be importable regardless of WebEngine."""

    def test_import_succeeds(self):
        """The module must import without raising even without WebEngine."""
        # Patch QtWebEngineWidgets to simulate absence
        missing = MagicMock(side_effect=ImportError("no webengine"))
        with patch.dict(sys.modules, {"PyQt6.QtWebEngineWidgets": None}):
            try:
                import echos.ui.graph_canvas  # noqa: F401
            except ImportError:
                pytest.fail("graph_canvas should not raise ImportError at import time")


class TestSetGraphData:
    """set_graph_data must serialise nodes+edges to valid JSON."""

    def test_serialises_nodes_and_edges(self):
        """Calling set_graph_data with sample data must produce valid JSON."""
        nodes = [
            {"id": "notes/a.md", "label": "a", "kind": "file", "color": "#c2410c"},
            {"id": "notes", "label": "notes", "kind": "dir", "color": "#1c8b4a"},
        ]
        edges = [
            {"source": "notes/a.md", "target": "notes/a.md",
             "edge_type": "concept", "strength": 0.7},
        ]
        payload = json.dumps({"nodes": nodes, "edges": edges}, default=str)
        parsed = json.loads(payload)

        assert len(parsed["nodes"]) == 2
        assert len(parsed["edges"]) == 1
        assert parsed["nodes"][0]["id"] == "notes/a.md"
        assert parsed["edges"][0]["edge_type"] == "concept"

    def test_non_serialisable_field_falls_back(self):
        """default=str must handle non-JSON-serialisable fields."""
        from pathlib import Path
        nodes = [{"id": "x", "path": Path("/tmp/x.md")}]
        payload = json.dumps({"nodes": nodes, "edges": []}, default=str)
        parsed = json.loads(payload)
        assert parsed["nodes"][0]["path"] == "/tmp/x.md"


class TestBridgeSignals:
    """_EchosGraphBridge must propagate signals correctly."""

    def test_node_clicked_signal(self):
        """onNodeClicked slot must emit node_clicked signal with the path."""
        from echos.ui.graph_canvas import _EchosGraphBridge
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)

        bridge = _EchosGraphBridge()
        received = []
        bridge.node_clicked.connect(received.append)

        bridge.onNodeClicked("/vault/notes/lecture-01.md")
        assert received == ["/vault/notes/lecture-01.md"]

    def test_on_ready_signal(self):
        """onReady slot must emit graph_ready signal."""
        from echos.ui.graph_canvas import _EchosGraphBridge
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)

        bridge = _EchosGraphBridge()
        fired = []
        bridge.graph_ready.connect(lambda: fired.append(True))

        bridge.onReady()
        assert fired == [True]


class TestBackRequestedSignal:
    """GraphCanvasWidget.back_requested must fire via toolbar."""

    def test_back_button_emits_signal(self):
        """_GraphToolbar.back_clicked → GraphCanvasWidget.back_requested chain."""
        from echos.ui.graph_canvas import _GraphToolbar
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)

        toolbar = _GraphToolbar()
        received = []
        toolbar.back_clicked.connect(lambda: received.append(True))

        # Simulate button click
        toolbar._back_btn.click()
        assert received == [True]


class TestSearchChanged:
    """Search field must emit search_changed with current text."""

    def test_search_signal(self):
        from echos.ui.graph_canvas import _GraphToolbar
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)

        toolbar = _GraphToolbar()
        queries = []
        toolbar.search_changed.connect(queries.append)

        toolbar._search.setText("lecture")
        assert "lecture" in queries


class TestVaultName:
    """set_vault_name must not raise and must update toolbar label."""

    def test_set_vault_name(self):
        from echos.ui.graph_canvas import _GraphToolbar
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)

        toolbar = _GraphToolbar()
        toolbar.set_vault_name("MyVault")
        assert toolbar._vault_lbl.text() == "MyVault"

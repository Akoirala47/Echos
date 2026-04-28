import sys
from pathlib import Path
content = Path('ui/graph_canvas.py').read_text()
if 'class WebEnginePage(QWebEnginePage):' not in content:
    patch = """
from PySide6.QtWebEngineCore import QWebEnginePage

class WebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS] {message} (line {lineNumber})")

"""
    content = content.replace("from PySide6.QtWebEngineWidgets import QWebEngineView", "from PySide6.QtWebEngineWidgets import QWebEngineView\n" + patch)
    content = content.replace("self._view = QWebEngineView()", "self._view = QWebEngineView()\n            self._view.setPage(WebEnginePage(self._view))")
    Path('ui/graph_canvas.py').write_text(content)
    print("Patched graph_canvas.py")

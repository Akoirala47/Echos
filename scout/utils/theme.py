"""Dark-mode detection and palette-aware colour helpers.

PyQt6 on macOS Ventura+ automatically propagates the system dark/light palette
to native controls.  Custom stylesheets that hardcode light colours need to
query this module instead.
"""

from __future__ import annotations

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication


def is_dark_mode() -> bool:
    """Return True when the active Qt palette indicates a dark colour scheme."""
    app = QApplication.instance()
    if app is None:
        return False
    bg = app.palette().color(QPalette.ColorRole.Window)
    return bg.lightness() < 128


def sidebar_bg() -> str:
    return "#1E1E1E" if is_dark_mode() else "#F8F8F6"


def status_bar_bg() -> str:
    return "#2A2A2A" if is_dark_mode() else "#F2F2F0"


def status_bar_border() -> str:
    return "#3A3A3A" if is_dark_mode() else "#DCDCDC"


def panel_bg() -> str:
    return "#1A1A1A" if is_dark_mode() else "white"


def header_bg() -> str:
    return "#252525" if is_dark_mode() else "white"


def header_border() -> str:
    return "#3A3A3A" if is_dark_mode() else "#EBEBEB"


def muted_text() -> str:
    return "#999999" if is_dark_mode() else "#888888"


def primary_text() -> str:
    return "#F0F0F0" if is_dark_mode() else "#1A1A1A"


def notes_css() -> str:
    """Return a CSS string for the QTextBrowser markdown renderer."""
    if is_dark_mode():
        return """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
    font-size: 13px; line-height: 1.6;
    color: #E8E8E8; background: #1A1A1A;
    margin: 0; padding: 0;
}
h1 { font-size: 18px; font-weight: 700; margin: 16px 0 6px 0; color: #F5F5F5; }
h2 { font-size: 15px; font-weight: 600; margin: 14px 0 5px 0;
     padding-left: 8px; border-left: 3px solid #5DADE2; color: #F0F0F0; }
h3 { font-size: 13px; font-weight: 600; margin: 10px 0 4px 0; color: #E8E8E8; }
p  { margin: 4px 0 8px 0; }
ul, ol { padding-left: 20px; margin: 4px 0 8px 0; }
li { margin: 3px 0; }
code { font-family: 'Menlo','Monaco','Courier New',monospace; font-size: 12px;
       background: #2D2D2D; padding: 2px 5px;
       border: 1px solid #3A3A3A; border-radius: 3px; }
pre  { background: #2D2D2D; padding: 12px; border: 1px solid #3A3A3A;
       border-radius: 4px; overflow: auto; margin: 8px 0; }
pre code { background: none; border: none; padding: 0; }
strong { font-weight: 600; }
"""
    return """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
    font-size: 13px; line-height: 1.6;
    color: #1A1A1A; background: white;
    margin: 0; padding: 0;
}
h1 { font-size: 18px; font-weight: 700; margin: 16px 0 6px 0; }
h2 { font-size: 15px; font-weight: 600; margin: 14px 0 5px 0;
     padding-left: 8px; border-left: 3px solid #2980B9; }
h3 { font-size: 13px; font-weight: 600; margin: 10px 0 4px 0; }
p  { margin: 4px 0 8px 0; }
ul, ol { padding-left: 20px; margin: 4px 0 8px 0; }
li { margin: 3px 0; }
code { font-family: 'Menlo','Monaco','Courier New',monospace; font-size: 12px;
       background: #F5F5F2; padding: 2px 5px;
       border: 1px solid #E0E0DC; border-radius: 3px; }
pre  { background: #F5F5F2; padding: 12px; border: 1px solid #E0E0DC;
       border-radius: 4px; overflow: auto; margin: 8px 0; }
pre code { background: none; border: none; padding: 0; }
strong { font-weight: 600; }
"""

"""Warm-parchment design tokens — light mode only, matching the UI mockup exactly.

All values taken verbatim from ui-mockup/site/index.html CSS variables.
No dark-mode branching anywhere in this file.
"""

from __future__ import annotations

# ── Backgrounds ───────────────────────────────────────────────────────────────
BG           = "#f6f5f1"   # outer page bg (not used in app; kept for reference)
WINDOW_BG    = "#fbfaf6"   # main window / record bar
SIDEBAR_BG   = "#f1efe8"   # sidebar panel
PANEL_BG     = "#ffffff"   # transcript + notes panels
STATUSBAR_BG = "#ecebe4"   # status bar strip

# ── Borders ───────────────────────────────────────────────────────────────────
BORDER      = "#dcdacf"    # stronger dividers (sidebar edge, status bar top)
BORDER_SOFT = "#e5e3d9"    # subtle internal dividers

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT       = "#1d1c19"    # primary text
TEXT_MUTED = "#76746b"    # secondary text
TEXT_FAINT = "#a09e93"    # placeholders, labels, faint UI text

# ── Accent / state ────────────────────────────────────────────────────────────
ACCENT          = "#c2410c"   # primary accent (amber)
ACCENT_SOFT     = "#fff1e6"
RECORDING       = "#d92f2f"   # red — recording state
PAUSED          = "#c47a17"   # amber — paused state
READY           = "#1c8b4a"   # green — notes ready / saved

# ── Interactive ───────────────────────────────────────────────────────────────
HOVER           = "rgba(0,0,0,0.04)"
SELECTED        = "rgba(194,65,12,0.10)"
SELECTED_STRONG = "rgba(194,65,12,0.18)"


# ── Simple accessors (called as functions so other modules import them
#    consistently; no logic, just returns the constant) ─────────────────────────

def window_bg()      -> str: return WINDOW_BG
def sidebar_bg()     -> str: return SIDEBAR_BG
def panel_bg()       -> str: return PANEL_BG
def statusbar_bg()   -> str: return STATUSBAR_BG
def border()         -> str: return BORDER
def border_soft()    -> str: return BORDER_SOFT
def text()           -> str: return TEXT
def text_muted()     -> str: return TEXT_MUTED
def text_faint()     -> str: return TEXT_FAINT
def accent()         -> str: return ACCENT
def recording_color()-> str: return RECORDING
def paused_color()   -> str: return PAUSED
def ready_color()    -> str: return READY
def hover_bg()       -> str: return HOVER
def selected_bg()    -> str: return SELECTED_STRONG


# ── Graph canvas (Brain View) ─────────────────────────────────────────────────
CANVAS_BG          = "#f0ede4"   # warm parchment canvas (matches SIDEBAR_BG family)
CANVAS_NODE_DEFAULT = "#A38300"  # muted warm node fill on light bg
CANVAS_EDGE_STRONG = ACCENT      # strong/wikilink edges
CANVAS_EDGE_WEAK   = BORDER      # weak/vector similarity edges
CANVAS_LABEL       = "TEXT_FAINT"  # node label text

# Warm + muted 6-colour domain palette (used for concept clusters)
DOMAIN_PALETTE = [
    "#c2410c",  # burnt orange  (accent)
    "#1c8b4a",  # sage green
    "#1d4ed8",  # cobalt blue
    "#be185d",  # rose
    "#b45309",  # amber
    "#7c3aed",  # warm violet
]

def canvas_bg()           -> str: return CANVAS_BG
def canvas_node_default() -> str: return CANVAS_NODE_DEFAULT
def canvas_edge_strong()  -> str: return CANVAS_EDGE_STRONG
def canvas_edge_weak()    -> str: return CANVAS_EDGE_WEAK
def canvas_label()        -> str: return CANVAS_LABEL
def domain_palette()      -> list: return list(DOMAIN_PALETTE)


# ── Tab bar ───────────────────────────────────────────────────────────────────
TAB_BG               = WINDOW_BG    # tab bar background
TAB_ACTIVE_TEXT      = TEXT         # active tab label colour
TAB_INACTIVE_TEXT    = TEXT_MUTED   # inactive tab label colour
TAB_ACTIVE_UNDERLINE = ACCENT       # 2px underline on active tab

def tab_bg()               -> str: return TAB_BG
def tab_active_text()      -> str: return TAB_ACTIVE_TEXT
def tab_inactive_text()    -> str: return TAB_INACTIVE_TEXT
def tab_active_underline() -> str: return TAB_ACTIVE_UNDERLINE


# ── Notes CSS (QTextBrowser renderer) ─────────────────────────────────────────

def notes_css() -> str:
    return f"""
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Helvetica Neue', sans-serif;
    font-size: 13px; line-height: 1.65;
    color: {TEXT}; background: transparent;
    margin: 0; padding: 0;
}}
h1 {{ font-size: 18px; font-weight: 700; margin: 4px 0 6px; }}
h2 {{
    font-size: 14.5px; font-weight: 700; margin: 14px 0 4px;
    padding-left: 8px; border-left: 3px solid {ACCENT};
}}
h3 {{ font-size: 13px; font-weight: 600; margin: 10px 0 3px; }}
h4 {{ font-size: 12px; font-weight: 600; margin: 8px 0 3px; color: {TEXT_MUTED}; }}
p  {{ margin: 4px 0 6px; }}
ul, ol {{ padding-left: 20px; margin: 4px 0 6px; }}
li {{ margin: 2px 0; }}
em {{ color: {TEXT_MUTED}; font-style: italic; }}
strong {{ font-weight: 600; }}
code {{
    font-family: 'JetBrains Mono', 'Menlo', 'Monaco', monospace;
    font-size: 11.5px;
    background: #f4f1ea; padding: 1px 5px;
    border-radius: 3px; border: 1px solid {BORDER_SOFT};
}}
pre {{
    background: #f6f3ec; border: 1px solid {BORDER_SOFT};
    border-radius: 5px; padding: 10px 12px; overflow: auto; margin: 8px 0;
}}
pre code {{ background: none; border: none; padding: 0; font-size: 11.5px; }}
"""

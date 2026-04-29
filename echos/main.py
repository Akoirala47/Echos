from __future__ import annotations

import ctypes
import logging
import logging.handlers
import sys
from pathlib import Path


def _find_dylib(stem: str) -> Path | None:
    """Search for a native dylib in all locations relevant to both dev and .app contexts.

    Search order:
      1. Contents/Frameworks/ (the canonical py2app bundle location)
      2. Inside the soundfile / sounddevice wheel data dirs (works in dev venv)
      3. Homebrew system paths (fallback for dev machines)
    """
    candidates: list[Path] = []

    # 1. Contents/Frameworks/ — set by py2app when 'frameworks' option is used.
    exe = Path(sys.executable).resolve()
    if exe.parent.name == "MacOS":
        frameworks = exe.parent.parent / "Frameworks"
        if frameworks.is_dir():
            candidates += sorted(frameworks.glob(f"{stem}*.dylib"))

    # Also check relative to __file__ in case the bundle layout differs.
    this_file = Path(__file__).resolve()
    for ancestor in this_file.parents:
        fw = ancestor / "Frameworks"
        if fw.is_dir():
            candidates += sorted(fw.glob(f"{stem}*.dylib"))
            break

    # 2. Wheel data directories bundled alongside the package.
    #    soundfile ships libsndfile_arm64.dylib inside _soundfile_data/
    #    sounddevice ships libportaudio.dylib inside _sounddevice_data/portaudio-binaries/
    import site
    site_dirs = []
    try:
        site_dirs += site.getsitepackages()
    except AttributeError:
        pass
    try:
        site_dirs.append(site.getusersitepackages())
    except AttributeError:
        pass
    # Also check sibling dirs of the current package (handles py2app lib/ trees)
    site_dirs.append(str(this_file.parent.parent))

    pkg_data_map = {
        "libsndfile": ["_soundfile_data"],
        "libportaudio": [
            "_sounddevice_data/portaudio-binaries",
            "_sounddevice_data",
        ],
    }
    for data_subdir in pkg_data_map.get(stem, []):
        for sp in site_dirs:
            data_dir = Path(sp) / data_subdir
            if data_dir.is_dir():
                candidates += sorted(data_dir.glob(f"{stem}*.dylib"))
                candidates += sorted(data_dir.glob("*.dylib"))

    # 3. Homebrew / system paths.
    for brew_path in (
        f"/opt/homebrew/lib/{stem}.dylib",
        f"/opt/homebrew/lib/{stem}.2.dylib",
        f"/usr/local/lib/{stem}.dylib",
        f"/usr/local/lib/{stem}.2.dylib",
    ):
        candidates.append(Path(brew_path))

    for p in candidates:
        if p.is_file():
            return p
    return None


def _fix_native_audio_libs() -> None:
    """Pre-load libsndfile and libportaudio and patch ctypes.util.find_library.

    In a py2app .app bundle Python packages are sometimes placed inside
    python3XX.zip.  dlopen() cannot open paths inside a zip archive (errno=20,
    ENOTDIR).  soundfile's module-level code tries its bundled dylib first,
    then falls back to ctypes.util.find_library — which on the build machine
    returns a Homebrew path that does *not* exist on end-user machines.

    Strategy:
      • Locate the dylibs via _find_dylib() which checks Contents/Frameworks/
        (the py2app bundle location), wheel data dirs, and Homebrew paths.
      • Pre-load each dylib with RTLD_GLOBAL *immediately* so that when
        soundfile's .pyc runs ctypes.CDLL(name) at module import time the
        already-loaded library is found in the dynamic linker's global table.
      • Patch ctypes.util.find_library so any subsequent name-based lookups
        also resolve to the bundled copies.
      • Set SOUNDFILE_LIBSNDFILE env var (respected by soundfile ≥ 0.12) as
        an additional belt-and-suspenders hint.

    This function MUST be called before soundfile or sounddevice are imported
    by any code path (including transitive imports from transformers).
    """
    import ctypes.util as _ctypes_util
    import os

    sndfile_path = _find_dylib("libsndfile")
    portaudio_path = _find_dylib("libportaudio")

    # Set env var hint for soundfile ≥ 0.12 (checked before any ctypes call).
    if sndfile_path is not None:
        os.environ.setdefault("SOUNDFILE_LIBSNDFILE", str(sndfile_path))

    # Pre-load with RTLD_GLOBAL so bare ctypes.CDLL(name) calls resolve via
    # the dynamic linker's already-loaded table rather than dlopen(path).
    for p in (sndfile_path, portaudio_path):
        if p is not None:
            try:
                ctypes.CDLL(str(p), mode=ctypes.RTLD_GLOBAL)
            except OSError as exc:
                # Log but don't abort — the patched find_library below is the
                # primary fix; RTLD_GLOBAL pre-load is belt-and-suspenders.
                print(f"[echos] WARNING: could not pre-load {p}: {exc}", file=sys.stderr)

    _original_find_library = _ctypes_util.find_library

    def _patched_find_library(name: str) -> str | None:
        if name in ("sndfile", "libsndfile") and sndfile_path is not None:
            return str(sndfile_path)
        if name in ("portaudio", "portaudio-2.0", "libportaudio") and portaudio_path is not None:
            return str(portaudio_path)
        return _original_find_library(name)

    _ctypes_util.find_library = _patched_find_library


# Run the native-lib patch at *module import time* so that py2app's frozen
# bootstrap cannot trigger a soundfile import before main() is called.
_fix_native_audio_libs()


def _setup_logging() -> None:
    log_dir = Path.home() / "Library" / "Logs" / "Echos"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "echos.log"

    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.DEBUG)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def main() -> None:
    _setup_logging()
    _fix_native_audio_libs()
    logger = logging.getLogger(__name__)
    logger.info("Echos starting up")

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    # QtWebEngineWidgets MUST be imported before QApplication is created on macOS.
    # Without this, the import fails at module load time even if the package is installed.
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401 — side-effect import, order matters
    except ImportError:
        pass  # Optional dependency — graph view shows fallback label if absent

    app = QApplication(sys.argv)
    app.setApplicationName("Echos")
    app.setOrganizationName("Echos")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    # Use Fusion style so Qt renders every widget using QPalette, not native Cocoa.
    # This gives us full control over the warm parchment look from the mockup.
    from PyQt6.QtWidgets import QStyleFactory
    app.setStyle(QStyleFactory.create("Fusion"))

    from PyQt6.QtGui import QColor, QPalette
    from echos.utils.theme import (
        WINDOW_BG, PANEL_BG, SIDEBAR_BG, BORDER, BORDER_SOFT,
        TEXT, TEXT_MUTED, TEXT_FAINT, ACCENT, SELECTED_STRONG,
    )

    pal = QPalette()
    _c = QColor  # shorthand

    # Active group (focused window)
    pal.setColor(QPalette.ColorRole.Window,           _c(WINDOW_BG))
    pal.setColor(QPalette.ColorRole.WindowText,       _c(TEXT))
    pal.setColor(QPalette.ColorRole.Base,             _c(PANEL_BG))
    pal.setColor(QPalette.ColorRole.AlternateBase,    _c("#f6f4ef"))
    pal.setColor(QPalette.ColorRole.Text,             _c(TEXT))
    pal.setColor(QPalette.ColorRole.Button,           _c(SIDEBAR_BG))
    pal.setColor(QPalette.ColorRole.ButtonText,       _c(TEXT))
    pal.setColor(QPalette.ColorRole.BrightText,       _c("#ffffff"))
    pal.setColor(QPalette.ColorRole.Highlight,        _c("#e8c0ab"))   # soft amber selection
    pal.setColor(QPalette.ColorRole.HighlightedText,  _c(TEXT))
    pal.setColor(QPalette.ColorRole.PlaceholderText,  _c(TEXT_FAINT))
    pal.setColor(QPalette.ColorRole.ToolTipBase,      _c("#fffae8"))
    pal.setColor(QPalette.ColorRole.ToolTipText,      _c(TEXT))
    pal.setColor(QPalette.ColorRole.Link,             _c(ACCENT))
    pal.setColor(QPalette.ColorRole.Mid,              _c(BORDER))
    pal.setColor(QPalette.ColorRole.Midlight,         _c(BORDER_SOFT))
    pal.setColor(QPalette.ColorRole.Light,            _c("#f8f6f2"))
    pal.setColor(QPalette.ColorRole.Dark,             _c("#ccc9bc"))
    pal.setColor(QPalette.ColorRole.Shadow,           _c("#b0ae9e"))

    # Inactive group (unfocused window) — keep same so nothing goes grey
    for role in [
        QPalette.ColorRole.Window, QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Base, QPalette.ColorRole.Text,
        QPalette.ColorRole.Button, QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.Highlight, QPalette.ColorRole.HighlightedText,
    ]:
        pal.setColor(QPalette.ColorGroup.Inactive, role,
                     pal.color(QPalette.ColorGroup.Active, role))

    # Disabled group — faded but still warm
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,  _c(TEXT_FAINT))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,        _c(TEXT_FAINT))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,  _c(TEXT_FAINT))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button,      _c("#e8e6de"))

    app.setPalette(pal)

    app.setStyleSheet(f"""
        /* ── Global font ───────────────────────────────────────────────── */
        * {{
            font-family: -apple-system, 'Inter', 'Helvetica Neue', sans-serif;
        }}

        /* ── Windows & dialogs ─────────────────────────────────────────── */
        QMainWindow {{
            background: {WINDOW_BG};
        }}
        QDialog {{
            background: {WINDOW_BG};
        }}
        QMessageBox {{
            background: {WINDOW_BG};
        }}
        QMessageBox QLabel {{
            color: {TEXT};
            font-size: 13px;
            line-height: 1.5;
            background: transparent;
        }}

        /* ── Buttons ───────────────────────────────────────────────────── */
        QPushButton {{
            background: {SIDEBAR_BG};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 5px 16px;
            font-size: 12px;
            font-weight: 500;
            min-height: 24px;
        }}
        QPushButton:hover {{
            background: #e8e5dc;
            border-color: #c9c7bc;
        }}
        QPushButton:pressed {{
            background: #dddad0;
            border-color: #b8b6ac;
        }}
        QPushButton:disabled {{
            background: #edeae2;
            color: {TEXT_FAINT};
            border-color: {BORDER_SOFT};
        }}
        QPushButton:default {{
            background: #fff4ed;
            border: 1.5px solid {ACCENT};
            color: {ACCENT};
            font-weight: 600;
        }}
        QPushButton:default:hover {{
            background: #ffe8d6;
        }}
        QPushButton:default:pressed {{
            background: #ffd4b8;
        }}

        /* ── Text inputs ────────────────────────────────────────────────── */
        QTextEdit, QTextBrowser {{
            background: {PANEL_BG};
            color: {TEXT};
            border: none;
            selection-background-color: rgba(194,65,12,0.22);
        }}
        QLineEdit {{
            background: {PANEL_BG};
            color: {TEXT};
            border: 1px solid {BORDER_SOFT};
            border-radius: 6px;
            padding: 5px 9px;
            selection-background-color: rgba(194,65,12,0.22);
        }}
        QLineEdit:focus {{
            border-color: {ACCENT};
        }}
        QLineEdit:disabled {{
            background: {SIDEBAR_BG};
            color: {TEXT_FAINT};
        }}
        QPlainTextEdit {{
            background: {PANEL_BG};
            color: {TEXT};
            border: 1px solid {BORDER_SOFT};
            border-radius: 6px;
            padding: 5px;
            selection-background-color: rgba(194,65,12,0.22);
        }}
        QPlainTextEdit:focus {{
            border-color: {ACCENT};
        }}

        /* ── Spin boxes ─────────────────────────────────────────────────── */
        QSpinBox, QDoubleSpinBox {{
            background: {PANEL_BG};
            color: {TEXT};
            border: 1px solid {BORDER_SOFT};
            border-radius: 6px;
            padding: 4px 6px;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {ACCENT};
        }}
        QSpinBox::up-button, QSpinBox::down-button,
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
            background: transparent;
            border: none;
            width: 14px;
        }}

        /* ── Combo box ──────────────────────────────────────────────────── */
        QComboBox {{
            background: {PANEL_BG};
            color: {TEXT};
            border: 1px solid {BORDER_SOFT};
            border-radius: 6px;
            padding: 4px 9px;
        }}
        QComboBox:focus {{
            border-color: {ACCENT};
        }}
        QComboBox:hover {{
            border-color: #c9c7bc;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background: {PANEL_BG};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            selection-background-color: {SELECTED_STRONG};
            outline: 0;
            padding: 2px;
        }}

        /* ── Group boxes ────────────────────────────────────────────────── */
        QGroupBox {{
            font-size: 11px;
            font-weight: 600;
            color: {TEXT_MUTED};
            border: 1px solid {BORDER_SOFT};
            border-radius: 8px;
            margin-top: 14px;
            padding: 10px 8px 8px 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
            background: {WINDOW_BG};
            color: {TEXT_MUTED};
        }}

        /* ── Labels ─────────────────────────────────────────────────────── */
        QLabel {{
            color: {TEXT};
            background: transparent;
        }}

        /* ── Checkboxes & radios ────────────────────────────────────────── */
        QCheckBox {{
            color: {TEXT};
            spacing: 7px;
        }}
        QCheckBox::indicator {{
            width: 15px; height: 15px;
            border: 1.5px solid {BORDER};
            border-radius: 4px;
            background: {PANEL_BG};
        }}
        QCheckBox::indicator:checked {{
            background: {ACCENT};
            border-color: {ACCENT};
            image: url("");
        }}
        QCheckBox::indicator:hover {{
            border-color: {ACCENT};
        }}
        QRadioButton {{
            color: {TEXT};
            spacing: 7px;
        }}

        /* ── Key sequence edit ──────────────────────────────────────────── */
        QKeySequenceEdit {{
            background: {PANEL_BG};
            color: {TEXT};
            border: 1px solid {BORDER_SOFT};
            border-radius: 6px;
            padding: 4px 8px;
        }}

        /* ── Menus ──────────────────────────────────────────────────────── */
        QMenuBar {{
            background: {WINDOW_BG};
            color: {TEXT};
            border-bottom: 1px solid {BORDER_SOFT};
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 4px 10px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background: rgba(194,65,12,0.10);
        }}
        QMenu {{
            background: {WINDOW_BG};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 8px;
            padding: 3px;
        }}
        QMenu::item {{
            padding: 6px 20px 6px 14px;
            border-radius: 5px;
        }}
        QMenu::item:selected {{
            background: rgba(194,65,12,0.10);
            color: {TEXT};
        }}
        QMenu::separator {{
            height: 1px;
            background: {BORDER_SOFT};
            margin: 3px 8px;
        }}

        /* ── Scrollbars ─────────────────────────────────────────────────── */
        QScrollBar:vertical {{
            width: 7px; background: transparent; margin: 0; border: none;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(0,0,0,0.13); border-radius: 3px; min-height: 28px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(0,0,0,0.20);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
        QScrollBar:horizontal {{
            height: 7px; background: transparent; margin: 0; border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: rgba(0,0,0,0.13); border-radius: 3px; min-width: 28px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: rgba(0,0,0,0.20);
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}

        /* ── Splitter ───────────────────────────────────────────────────── */
        QSplitter::handle {{
            background: {BORDER_SOFT};
        }}

        /* ── Tab bars (settings dialog) ────────────────────────────────── */
        QTabWidget::pane {{
            border: 1px solid {BORDER_SOFT};
            border-top: none;
            background: {PANEL_BG};
        }}
        QTabBar::tab {{
            background: {SIDEBAR_BG};
            color: {TEXT_MUTED};
            border: 1px solid {BORDER_SOFT};
            border-bottom: none;
            border-radius: 5px 5px 0 0;
            padding: 6px 16px;
            font-size: 12px;
        }}
        QTabBar::tab:selected {{
            background: {PANEL_BG};
            color: {TEXT};
            font-weight: 600;
        }}
        QTabBar::tab:hover:!selected {{
            background: #eae8e0;
        }}

        /* ── Sliders ────────────────────────────────────────────────────── */
        QSlider::groove:horizontal {{
            height: 4px;
            background: {BORDER_SOFT};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 14px; height: 14px;
            background: {ACCENT};
            border-radius: 7px;
            margin: -5px 0;
        }}
        QSlider::sub-page:horizontal {{
            background: {ACCENT};
            border-radius: 2px;
        }}

        /* ── Progress bars ──────────────────────────────────────────────── */
        QProgressBar {{
            background: {BORDER_SOFT};
            border: none;
            border-radius: 4px;
            height: 6px;
            text-align: center;
            color: transparent;
        }}
        QProgressBar::chunk {{
            background: {ACCENT};
            border-radius: 4px;
        }}

        /* ── Tooltips ───────────────────────────────────────────────────── */
        QToolTip {{
            background: #fffae8;
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 5px;
            padding: 5px 9px;
            font-size: 12px;
        }}

        /* ── Dialog button box ──────────────────────────────────────────── */
        QDialogButtonBox QPushButton {{
            min-width: 72px;
        }}
    """)

    from echos.config.config_manager import ConfigManager
    from echos.core.model_manager import ModelManager
    from echos.core.obsidian_manager import ObsidianManager
    from echos.ui.main_window import MainWindow

    config_mgr = ConfigManager()
    model_manager = ModelManager()
    obsidian_mgr = ObsidianManager()

    # First-launch: show onboarding wizard before the main window.
    if config_mgr.is_first_launch():
        from echos.ui.onboarding import OnboardingWizard

        wizard = OnboardingWizard(model_manager)
        result = wizard.exec()
        if result != OnboardingWizard.DialogCode.Accepted and not config_mgr.is_first_launch() is False:
            # User cancelled onboarding on a truly first launch — save minimal config
            # so we don't re-show the wizard on every launch.
            pass
        # Persist vault path + API key entered in the wizard.
        vault = wizard.field("vault_path") or ""
        api_key = wizard.field("api_key") or ""
        if vault or api_key:
            cfg = config_mgr.load()
            if vault:
                cfg["vault_path"] = vault
            if api_key:
                cfg["google_api_key"] = api_key
            config_mgr.save(cfg)
        logger.info("Onboarding complete")

    # Build main window and controller.
    window = MainWindow()

    from echos.app import AppController
    controller = AppController(window, config_mgr, model_manager, obsidian_mgr)  # noqa: F841

    # If model is cached but not yet loaded, AppController already kicked off the
    # background load in its __init__.  Nothing else needed here.

    window.show()
    logger.info("Main window shown")

    # macOS: make title bar blend with the warm parchment window background
    try:
        from AppKit import NSApplication, NSColor
        nsapp = NSApplication.sharedApplication()
        if nsapp.windows():
            nswin = nsapp.windows()[0]
            nswin.setTitlebarAppearsTransparent_(True)
            nswin.setTitleVisibility_(1)   # NSWindowTitleHidden
            nswin.setBackgroundColor_(
                NSColor.colorWithSRGBRed_green_blue_alpha_(
                    0xfb / 255.0, 0xfa / 255.0, 0xf6 / 255.0, 1.0
                )
            )
            nswin.setMovableByWindowBackground_(True)
    except Exception:
        pass

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

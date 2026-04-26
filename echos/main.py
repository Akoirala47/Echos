from __future__ import annotations

import ctypes
import logging
import logging.handlers
import sys
from pathlib import Path


def _find_framework_dylib(stem: str) -> Path | None:
    """Return the first matching dylib from Contents/Frameworks or system paths."""
    exe = Path(sys.executable).resolve()
    if exe.parent.name == "MacOS":
        frameworks = exe.parent.parent / "Frameworks"
        if frameworks.is_dir():
            for candidate in frameworks.glob(f"{stem}*.dylib"):
                if candidate.is_file():
                    return candidate
    for brew_path in (f"/opt/homebrew/lib/{stem}.dylib", f"/opt/homebrew/lib/{stem}.2.dylib",
                      f"/usr/local/lib/{stem}.dylib", f"/usr/local/lib/{stem}.2.dylib"):
        p = Path(brew_path)
        if p.is_file():
            return p
    return None


def _fix_native_audio_libs() -> None:
    """Patch ctypes.util.find_library for soundfile (libsndfile) and sounddevice (portaudio).

    py2app zips Python packages into python3XX.zip.  Both soundfile and sounddevice
    bundle their native dylibs inside the package data directory, but dlopen() cannot
    open files inside a zip (errno=20, ENOTDIR).  They then fall back to
    ctypes.util.find_library which returns the build-machine Homebrew path — a path
    that does not exist in the deployed .app bundle.

    We bundle both dylibs into Contents/Frameworks/ via the py2app 'frameworks' option,
    then intercept find_library here so each package finds the correct bundled path.

    Must be called BEFORE soundfile or sounddevice are imported.
    """
    import ctypes.util as _ctypes_util

    sndfile_path = _find_framework_dylib("libsndfile")
    portaudio_path = _find_framework_dylib("libportaudio")

    # Pre-load with RTLD_GLOBAL so bare-name ctypes.CDLL calls also find them.
    for p in (sndfile_path, portaudio_path):
        if p is not None:
            try:
                ctypes.CDLL(str(p), mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass

    _original_find_library = _ctypes_util.find_library

    def _patched_find_library(name: str) -> str | None:
        if name in ("sndfile", "libsndfile") and sndfile_path is not None:
            return str(sndfile_path)
        if name in ("portaudio", "portaudio-2.0", "libportaudio") and portaudio_path is not None:
            return str(portaudio_path)
        return _original_find_library(name)

    _ctypes_util.find_library = _patched_find_library


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
        * {{
            font-family: -apple-system, 'Inter', 'Helvetica Neue', sans-serif;
        }}
        QMainWindow, QDialog {{
            background: {WINDOW_BG};
        }}
        QTextEdit, QTextBrowser {{
            background: {PANEL_BG};
            color: {TEXT};
            border: none;
            selection-background-color: rgba(194,65,12,0.25);
        }}
        QLineEdit {{
            background: {PANEL_BG};
            color: {TEXT};
            border: 1px solid {BORDER_SOFT};
            border-radius: 5px;
            padding: 4px 8px;
            selection-background-color: rgba(194,65,12,0.25);
        }}
        QLineEdit:focus {{
            border-color: {ACCENT};
        }}
        QSpinBox {{
            background: {PANEL_BG};
            color: {TEXT};
            border: 1px solid {BORDER_SOFT};
            border-radius: 4px;
            padding: 2px 6px;
        }}
        QComboBox {{
            background: {SIDEBAR_BG};
            color: {TEXT};
            border: 1px solid {BORDER_SOFT};
            border-radius: 5px;
            padding: 4px 8px;
        }}
        QMenuBar {{
            background: {WINDOW_BG};
            color: {TEXT};
            border-bottom: 1px solid {BORDER_SOFT};
        }}
        QMenuBar::item:selected {{
            background: rgba(194,65,12,0.10);
        }}
        QMenu {{
            background: {WINDOW_BG};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 8px;
        }}
        QMenu::item:selected {{
            background: rgba(194,65,12,0.10);
        }}
        QScrollBar:vertical {{
            width: 8px; background: transparent; margin: 0; border: none;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(0,0,0,0.12); border-radius: 4px; min-height: 30px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
        QScrollBar:horizontal {{
            height: 8px; background: transparent; margin: 0; border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: rgba(0,0,0,0.12); border-radius: 4px; min-width: 30px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}
        QSplitter::handle {{
            background: {BORDER_SOFT};
        }}
        QTabBar::tab {{
            background: {SIDEBAR_BG};
            color: {TEXT_MUTED};
            border: 1px solid {BORDER_SOFT};
            padding: 6px 14px;
        }}
        QTabBar::tab:selected {{
            background: {PANEL_BG};
            color: {TEXT};
            border-bottom: none;
        }}
        QTabWidget::pane {{
            border: 1px solid {BORDER_SOFT};
            background: {PANEL_BG};
        }}
        QToolTip {{
            background: #fffae8;
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
        }}
        QCheckBox {{
            color: {TEXT};
            spacing: 6px;
        }}
        QRadioButton {{
            color: {TEXT};
            spacing: 6px;
        }}
        QGroupBox {{
            color: {TEXT_MUTED};
            border: 1px solid {BORDER_SOFT};
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 8px;
            font-size: 11px;
            font-weight: 600;
        }}
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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

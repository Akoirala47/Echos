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

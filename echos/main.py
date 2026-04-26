from __future__ import annotations

import ctypes
import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _fix_libsndfile() -> None:
    """Work around the py2app + soundfile dylib issue.

    py2app zips Python packages into python311.zip, so soundfile's bundled
    libsndfile_arm64.dylib ends up at a path like:
        .../python311.zip/_soundfile_data/libsndfile_arm64.dylib
    which cannot be dlopen'd (errno=20, ENOTDIR — it's inside a zip).
    soundfile then falls back to ctypes.util.find_library('sndfile'), which
    returns the build-machine Homebrew path that doesn't exist in the bundle.

    Fix: monkey-patch ctypes.util.find_library so that any 'sndfile' lookup
    returns our bundled dylib from Contents/Frameworks/, where py2app copied
    it via the 'frameworks' setup.py option.  Also pre-load it with RTLD_GLOBAL
    so cffi/ctypes find it already resident in the process if they use a bare
    library name.

    Must be called BEFORE soundfile (or transformers.audio_utils) is imported.
    """
    import ctypes.util as _ctypes_util

    # 1. Locate libsndfile: prefer bundle-internal copy, then source-tree, then system.
    dylib_path: Path | None = None

    # a) Inside py2app bundle: Contents/Frameworks/libsndfile*.dylib
    exe = Path(sys.executable).resolve()
    if exe.parent.name == "MacOS":
        frameworks = exe.parent.parent / "Frameworks"
        for candidate in frameworks.glob("libsndfile*.dylib"):
            if candidate.is_file():
                dylib_path = candidate
                break

    # b) soundfile wheel's own _soundfile_data directory (works from source)
    if dylib_path is None:
        try:
            import soundfile as _sf  # noqa: WPS433
            sf_data = Path(_sf.__file__).parent / "_soundfile_data"
            if not sf_data.is_dir():
                # May be inside zip; try to construct real filesystem path.
                sf_data = Path(os.path.dirname(os.path.realpath(_sf.__file__))) / "_soundfile_data"
            for candidate in sf_data.glob("libsndfile*.dylib"):
                if candidate.is_file():
                    dylib_path = candidate
                    break
        except Exception:
            pass

    # c) Homebrew / system paths
    if dylib_path is None:
        for system_path_str in (
            "/opt/homebrew/lib/libsndfile.dylib",
            "/opt/homebrew/lib/libsndfile.1.dylib",
            "/usr/local/lib/libsndfile.dylib",
            "/usr/local/lib/libsndfile.1.dylib",
        ):
            p = Path(system_path_str)
            if p.is_file():
                dylib_path = p
                break

    if dylib_path is None:
        return  # nothing found — let soundfile raise its own error

    dylib_str = str(dylib_path)

    # 2. Pre-load with RTLD_GLOBAL so bare-name lookups (ctypes.CDLL('libsndfile'))
    #    succeed even if soundfile's cffi uses a different strategy.
    try:
        ctypes.CDLL(dylib_str, mode=ctypes.RTLD_GLOBAL)
    except OSError:
        pass

    # 3. Monkey-patch find_library so soundfile's fallback chain returns our path
    #    instead of the missing Homebrew path.  This is the critical fix for the
    #    zip case: bundled dylib fails → find_library is called → we intercept.
    _original_find_library = _ctypes_util.find_library

    def _patched_find_library(name: str) -> str | None:
        if name in ("sndfile", "libsndfile", "libsndfile.dylib"):
            return dylib_str
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
    _fix_libsndfile()
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

from __future__ import annotations

import ctypes
import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _preload_libsndfile() -> None:
    """Load libsndfile.dylib eagerly so soundfile can find it in py2app bundles.

    py2app copies dylibs into ``Contents/Frameworks/`` but soundfile uses
    ctypes.util.find_library(), which searches DYLD paths and misses bundle
    locations.  Pre-loading via ctypes registers the library in the process
    dyld table so soundfile's later lookup succeeds.
    """
    candidates: list[Path] = []

    # Inside a py2app bundle, sys.executable is .../Contents/MacOS/Echos and
    # frameworks live in .../Contents/Frameworks/.
    exe = Path(sys.executable).resolve()
    if exe.parent.name == "MacOS":
        frameworks = exe.parent.parent / "Frameworks"
        if frameworks.is_dir():
            candidates.extend(frameworks.glob("libsndfile*.dylib"))

    # Fall back to the soundfile wheel's bundled copy when running from source.
    try:
        import soundfile  # noqa: WPS433
        sf_data = Path(soundfile.__file__).parent / "_soundfile_data"
        if sf_data.is_dir():
            candidates.extend(sf_data.glob("*.dylib"))
    except Exception:
        pass

    # Finally, the standard system locations.
    for system_path in (
        "/opt/homebrew/lib/libsndfile.dylib",
        "/opt/homebrew/lib/libsndfile.1.dylib",
        "/usr/local/lib/libsndfile.dylib",
        "/usr/local/lib/libsndfile.1.dylib",
    ):
        candidates.append(Path(system_path))

    for path in candidates:
        try:
            if path.is_file():
                ctypes.CDLL(str(path), mode=ctypes.RTLD_GLOBAL)
                os.environ.setdefault("SOUNDFILE_LIBRARY", str(path))
                return
        except OSError:
            continue


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
    _preload_libsndfile()
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

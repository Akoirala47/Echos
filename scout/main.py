from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


def _setup_logging() -> None:
    log_dir = Path.home() / "Library" / "Logs" / "Scout"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "scout.log"

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
    logger = logging.getLogger(__name__)
    logger.info("Scout starting up")

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Scout")
    app.setOrganizationName("Scout")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    from scout.config.config_manager import ConfigManager
    from scout.core.model_manager import ModelManager
    from scout.core.obsidian_manager import ObsidianManager
    from scout.ui.main_window import MainWindow

    config_mgr = ConfigManager()
    model_manager = ModelManager()
    obsidian_mgr = ObsidianManager()

    # First-launch: show onboarding wizard before the main window.
    if config_mgr.is_first_launch():
        from scout.ui.onboarding import OnboardingWizard

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

    from scout.app import AppController
    controller = AppController(window, config_mgr, model_manager, obsidian_mgr)  # noqa: F841

    # If model is cached but not yet loaded, AppController already kicked off the
    # background load in its __init__.  Nothing else needed here.

    window.show()
    logger.info("Main window shown")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

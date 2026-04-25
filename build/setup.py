"""py2app build configuration for Scout.

Run from the project root:
    python build/setup.py py2app
"""

from setuptools import setup

APP = ["scout/main.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/icon.icns",
    "plist": {
        "CFBundleName": "Scout",
        "CFBundleDisplayName": "Scout",
        "CFBundleIdentifier": "com.scout.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleExecutable": "Scout",
        # Privacy usage descriptions required by macOS sandbox
        "NSMicrophoneUsageDescription": (
            "Scout needs microphone access to transcribe your lectures."
        ),
        "NSDocumentsFolderUsageDescription": (
            "Scout needs access to your Documents folder to save notes to Obsidian."
        ),
        # macOS Ventura minimum
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        # Suppress "app is not optimized for your Mac" warning on Apple Silicon
        "LSArchitecturePriority": ["arm64", "x86_64"],
        # Keep dock icon visible (not a background-only app)
        "LSUIElement": False,
    },
    "packages": [
        "PyQt6",
        "torch",
        "transformers",
        "sounddevice",
        "numpy",
        "google.generativeai",
        "huggingface_hub",
        "markdown",
        "soundfile",
        "scout",
    ],
    "includes": [
        "scout.main",
        "scout.app",
        "scout.config.config_manager",
        "scout.config.defaults",
        "scout.core.audio_worker",
        "scout.core.model_manager",
        "scout.core.notes_worker",
        "scout.core.obsidian_manager",
        "scout.ui.main_window",
        "scout.ui.onboarding",
        "scout.ui.notes_panel",
        "scout.ui.record_bar",
        "scout.ui.settings_window",
        "scout.ui.sidebar",
        "scout.ui.status_bar",
        "scout.ui.transcript_panel",
        "scout.ui.widgets.course_item",
        "scout.ui.widgets.model_progress",
        "scout.ui.widgets.waveform",
        "scout.utils.audio_utils",
        "scout.utils.frontmatter",
        "scout.utils.markdown",
    ],
    "excludes": [
        "tkinter",
        "matplotlib",
        "scipy",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "black",
        "ruff",
    ],
    # Keep debug symbols for crash reports; set to 1 for release.
    "strip": False,
    "optimize": 0,
    # Embed the Python framework inside the .app bundle.
    "semi_standalone": False,
    "site_packages": True,
}

setup(
    name="Scout",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)

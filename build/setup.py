"""py2app build configuration for Echos.

Run from the project root:
    python build/setup.py py2app
"""

import glob
import os
import sys
# modulegraph recursively walks torch's import graph which exceeds the default
# limit of 1000.  5000 is sufficient; 10000 is a safe upper bound.
sys.setrecursionlimit(10000)

from setuptools import setup


def _find_libsndfile() -> list[str]:
    """Locate libsndfile.dylib for bundling.

    Tries soundfile's wheel-bundled copy first (preferred — self-contained),
    then falls back to Homebrew install paths so the .app works without the
    user installing libsndfile system-wide.
    """
    paths: list[str] = []
    try:
        import soundfile  # noqa: WPS433
        sf_data = os.path.join(os.path.dirname(soundfile.__file__), "_soundfile_data")
        if os.path.isdir(sf_data):
            paths.extend(glob.glob(os.path.join(sf_data, "*.dylib")))
    except Exception:
        pass
    for candidate in (
        "/opt/homebrew/lib/libsndfile.dylib",
        "/opt/homebrew/lib/libsndfile.1.dylib",
        "/usr/local/lib/libsndfile.dylib",
        "/usr/local/lib/libsndfile.1.dylib",
    ):
        if os.path.isfile(candidate) and candidate not in paths:
            paths.append(candidate)
    return paths


APP = ["echos/main.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/icon.icns",
    "plist": {
        "CFBundleName": "Echos",
        "CFBundleDisplayName": "Echos",
        "CFBundleIdentifier": "com.echos.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleExecutable": "Echos",
        # Privacy usage descriptions required by macOS sandbox
        "NSMicrophoneUsageDescription": (
            "Echos needs microphone access to transcribe your lectures."
        ),
        "NSDocumentsFolderUsageDescription": (
            "Echos needs access to your Documents folder to save notes to Obsidian."
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
        "huggingface_hub",
        "markdown",
        "soundfile",
        "echos",
        # google.generativeai is a PEP 420 namespace package; imp.find_module()
        # cannot locate it so it must NOT be listed here.  modulegraph traces it
        # automatically via the import in notes_worker.py.
    ],
    "includes": [
        # google.generativeai is a namespace package; include submodules explicitly
        # so modulegraph doesn't miss them.
        "google",
        "google.generativeai",
        "google.generativeai.types",
        "google.ai.generativelanguage_v1beta",
        # Echos modules
        "echos.main",
        "echos.app",
        "echos.config.config_manager",
        "echos.config.defaults",
        "echos.core.audio_worker",
        "echos.core.model_manager",
        "echos.core.notes_worker",
        "echos.core.obsidian_manager",
        "echos.ui.main_window",
        "echos.ui.onboarding",
        "echos.ui.notes_panel",
        "echos.ui.record_bar",
        "echos.ui.settings_window",
        "echos.ui.sidebar",
        "echos.ui.status_bar",
        "echos.ui.transcript_panel",
        "echos.ui.widgets.course_item",
        "echos.ui.widgets.model_progress",
        "echos.ui.widgets.waveform",
        "echos.utils.audio_utils",
        "echos.utils.frontmatter",
        "echos.utils.markdown",
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
        # Torch internals that modulegraph doesn't need to trace —
        # they are included via the "packages" list as binary copies.
        "torch.testing",
        "torch.utils.benchmark",
        "torch.utils.bottleneck",
        "torch.distributed",
        "torch.fx",
        "caffe2",
    ],
    # Keep debug symbols for crash reports; set to 1 for release.
    "strip": False,
    "optimize": 0,
    # Embed the Python framework inside the .app bundle.
    "semi_standalone": False,
    "site_packages": True,
    # Do not zip Python packages — soundfile's bundled libsndfile_arm64.dylib
    # must live on the real filesystem (dlopen cannot open paths inside a zip).
    "no_zip": True,
    # Bundle libsndfile.dylib into Contents/Frameworks so soundfile can find
    # it even when no_zip is not fully honoured by the installed py2app.
    "frameworks": _find_libsndfile(),
}

setup(
    name="Echos",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)

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


def _collect_native_libs() -> list[str]:
    """Locate libsndfile and libportaudio dylibs for bundling into Contents/Frameworks.

    sounddevice (portaudio) and soundfile (libsndfile) both bundle their own
    dylibs inside their wheel's data directory.  py2app copies Python files
    into python3XX.zip where dlopen() cannot reach them, so we pull the dylibs
    out and place them in Contents/Frameworks/ explicitly.  The _fix_* helpers
    in main.py then intercept ctypes.util.find_library so the packages find
    the bundled copies at runtime.
    """
    paths: list[str] = []

    def _add(path: str) -> None:
        if os.path.isfile(path) and path not in paths:
            paths.append(path)

    # soundfile → libsndfile
    try:
        import soundfile  # noqa: WPS433
        sf_data = os.path.join(os.path.dirname(soundfile.__file__), "_soundfile_data")
        for p in glob.glob(os.path.join(sf_data, "*.dylib")):
            _add(p)
    except Exception:
        pass
    for p in ("/opt/homebrew/lib/libsndfile.dylib", "/opt/homebrew/lib/libsndfile.1.dylib",
              "/usr/local/lib/libsndfile.dylib", "/usr/local/lib/libsndfile.1.dylib"):
        _add(p)

    # sounddevice → libportaudio
    try:
        import sounddevice  # noqa: WPS433
        pa_data = os.path.join(
            os.path.dirname(sounddevice.__file__), "_sounddevice_data", "portaudio-binaries"
        )
        for p in glob.glob(os.path.join(pa_data, "*.dylib")):
            _add(p)
    except Exception:
        pass
    for p in ("/opt/homebrew/lib/libportaudio.dylib", "/opt/homebrew/lib/libportaudio.2.dylib",
              "/usr/local/lib/libportaudio.dylib", "/usr/local/lib/libportaudio.2.dylib"):
        _add(p)

    return paths


APP = ["echos/main.py"]


def _extra_data_files() -> list:
    """Copy sounddevice and soundfile data directories into lib/python3.11/ inside the bundle.

    soundfile locates _soundfile_data via os.path.dirname(soundfile.__file__),
    i.e. it expects _soundfile_data to be a sibling of soundfile/__init__.py.
    py2app places Python packages in Contents/Resources/lib/python3.11/, so
    the data dirs must live there too — not at the bundle root.

    The dest prefix 'lib/python3.11' is relative to Contents/Resources/ and
    matches what py2app uses for site-packages.
    """
    import platform
    import site
    import sys
    ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    dest = f"lib/python{ver}"
    extras = []
    checked = set()
    for sp in site.getsitepackages():
        for data_dir in ("_sounddevice_data", "_soundfile_data"):
            full = os.path.join(sp, data_dir)
            if os.path.isdir(full) and full not in checked:
                checked.add(full)
                extras.append((dest, [full]))
    return extras


DATA_FILES = _extra_data_files()
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/icon.icns",
    "plist": {
        "CFBundleName": "Echos",
        "CFBundleDisplayName": "Echos",
        "CFBundleIdentifier": "com.echos.app",
        "CFBundleVersion": "1.0.8",
        "CFBundleShortVersionString": "1.0.8",
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
        # sounddevice uses cffi.  _sounddevice is the cffi module definition
        # (a pure-Python .py generated by cffi) that sounddevice imports at
        # runtime via a dynamic 'import _sounddevice'.  modulegraph cannot trace
        # this, so we include it explicitly.  _cffi_backend is the compiled C
        # extension that powers all cffi modules.
        "_sounddevice",
        "_soundfile",
        "_cffi_backend",
        "cffi",
        "cffi._cffi_include",
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
    # py2app 0.28+ respects zip_unsafe as a per-package blocklist; older
    # versions honour no_zip alone.  List both to cover all versions.
    "zip_unsafe": [
        "soundfile",
        "sounddevice",
        "_soundfile",
        "_sounddevice",
        "cffi",
        "_cffi_backend",
    ],
    # Bundle libsndfile + libportaudio into Contents/Frameworks so soundfile
    # and sounddevice can find them even when no_zip is not fully honoured.
    "frameworks": _collect_native_libs(),
}

setup(
    name="Echos",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)

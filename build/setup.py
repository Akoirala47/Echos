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

    soundfile is a single .py file (not a package), so soundfile.__file__ is
    site-packages/soundfile.py and _soundfile_data lives right next to it at
    site-packages/_soundfile_data/.

    sounddevice IS a package, so _sounddevice_data lives at the site-packages
    level as well (not inside the sounddevice/ subdirectory).
    """
    import site as _site
    paths: list[str] = []

    def _add(path: str) -> None:
        if os.path.isfile(path) and path not in paths:
            print(f"[setup] bundling native lib: {path}")
            paths.append(path)

    # ---- soundfile → libsndfile ----------------------------------------
    # Strategy 1: find via soundfile module (works in any venv/system Python)
    try:
        import soundfile  # noqa: WPS433
        # soundfile.__file__ == site-packages/soundfile.py  (single-file module)
        # so dirname gives us site-packages/ directly.
        sf_site = os.path.dirname(soundfile.__file__)          # site-packages/
        sf_data = os.path.join(sf_site, "_soundfile_data")    # site-packages/_soundfile_data/
        for p in glob.glob(os.path.join(sf_data, "*.dylib")):
            _add(p)
    except Exception as e:
        print(f"[setup] WARNING: could not locate soundfile data dir: {e}")

    # Strategy 2: walk all site-packages dirs
    try:
        for sp in _site.getsitepackages():
            for p in glob.glob(os.path.join(sp, "_soundfile_data", "*.dylib")):
                _add(p)
    except Exception:
        pass

    # Strategy 3: Homebrew / system fallback (CI runner has these)
    for p in (
        "/opt/homebrew/lib/libsndfile.dylib",
        "/opt/homebrew/lib/libsndfile.1.dylib",
        "/usr/local/lib/libsndfile.dylib",
        "/usr/local/lib/libsndfile.1.dylib",
    ):
        _add(p)

    # ---- sounddevice → libportaudio ------------------------------------
    # Strategy 1: find via sounddevice module
    try:
        import sounddevice  # noqa: WPS433
        # sounddevice IS a package, so dirname(__file__) is site-packages/sounddevice/
        sd_pkg  = os.path.dirname(sounddevice.__file__)   # site-packages/sounddevice/
        sd_site = os.path.dirname(sd_pkg)                 # site-packages/
        for search in (
            os.path.join(sd_site, "_sounddevice_data", "portaudio-binaries"),
            os.path.join(sd_site, "_sounddevice_data"),
            os.path.join(sd_pkg,  "_sounddevice_data", "portaudio-binaries"),
        ):
            for p in glob.glob(os.path.join(search, "*.dylib")):
                _add(p)
    except Exception as e:
        print(f"[setup] WARNING: could not locate sounddevice data dir: {e}")

    # Strategy 2: walk all site-packages dirs
    try:
        for sp in _site.getsitepackages():
            for sub in ("_sounddevice_data/portaudio-binaries", "_sounddevice_data"):
                for p in glob.glob(os.path.join(sp, sub, "*.dylib")):
                    _add(p)
    except Exception:
        pass

    # Strategy 3: Homebrew / system fallback
    for p in (
        "/opt/homebrew/lib/libportaudio.dylib",
        "/opt/homebrew/lib/libportaudio.2.dylib",
        "/usr/local/lib/libportaudio.dylib",
        "/usr/local/lib/libportaudio.2.dylib",
    ):
        _add(p)

    if not any("sndfile" in p for p in paths):
        print("[setup] ERROR: libsndfile was NOT found — the bundle will fail to load!")
        print("[setup] Install with: brew install libsndfile")
        # Don't raise here — allow the build to continue and catch it in build.sh

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
        # sklearn (scikit-learn) is a transitive dep pulled in by transformers'
        # generation module.  It imports scipy unconditionally at the module level,
        # so scipy must be bundled whenever sklearn is present.
        "sklearn",
        "scipy",
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

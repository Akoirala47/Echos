#!/usr/bin/env bash
# Full Echos build pipeline: assets → .app (py2app) → .dmg (create-dmg)
# Run from the project root:
#   chmod +x build/build.sh && ./build/build.sh
set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve project root (the directory containing this script's parent)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

VERSION="${VERSION:-1.0.1}"
APP_NAME="Echos"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"

echo "=== Echos Build Script v${VERSION} ==="
echo "Project root: $PROJECT_ROOT"

# ---------------------------------------------------------------------------
# Step 1 — Generate assets (icon, DMG background) if not present
# ---------------------------------------------------------------------------
echo ""
echo "=== [1/4] Generating assets ==="
python3 assets/create_assets.py

if [[ ! -f "assets/icon.icns" ]]; then
  echo "ERROR: assets/icon.icns not found. Run 'python3 assets/create_assets.py' on macOS."
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 2 — Clean previous build artefacts
# ---------------------------------------------------------------------------
echo ""
echo "=== [2/4] Cleaning previous build ==="
rm -rf build/build build/dist dist/
mkdir -p dist

# ---------------------------------------------------------------------------
# Step 3 — Build .app bundle with py2app
# ---------------------------------------------------------------------------
echo ""
echo "=== [3/4] Building ${APP_NAME}.app with py2app ==="

# py2app writes build/ and dist/ relative to setup.py; we want them in the
# project root so we pass explicit --build-lib and --dist-dir options.
python3 build/setup.py py2app \
  --dist-dir "dist"

APP_PATH="dist/${APP_NAME}.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: ${APP_PATH} not found after py2app build."
  exit 1
fi
echo "Built: $APP_PATH"

# ---------------------------------------------------------------------------
# Step 3b — Explicitly copy native dylibs into Contents/Frameworks/
# py2app's 'frameworks' and 'no_zip' options are not always honoured by all
# versions.  Belt-and-suspenders: find and copy libsndfile + libportaudio
# right after the py2app step so the bundle is always self-contained.
# ---------------------------------------------------------------------------
FRAMEWORKS_DIR="${APP_PATH}/Contents/Frameworks"
mkdir -p "$FRAMEWORKS_DIR"

echo ""
echo "=== [3b] Copying native audio dylibs to Contents/Frameworks ==="

# Find libsndfile — prefer the wheel-bundled arm64 dylib, fall back to Homebrew
SNDFILE_SRC="$(python3 - <<'PYEOF'
import glob, os, site, sys
candidates = []
# Wheel-bundled copy (site-packages/_soundfile_data/)
for sp in site.getsitepackages():
    candidates += glob.glob(os.path.join(sp, "_soundfile_data", "*.dylib"))
# Homebrew fallbacks
for p in ["/opt/homebrew/lib/libsndfile.dylib", "/opt/homebrew/lib/libsndfile.1.dylib",
          "/usr/local/lib/libsndfile.dylib", "/usr/local/lib/libsndfile.1.dylib"]:
    if os.path.isfile(p):
        candidates.append(p)
print(candidates[0] if candidates else "")
PYEOF
)"

if [[ -z "$SNDFILE_SRC" ]]; then
  echo "ERROR: Cannot find libsndfile dylib. Install with: brew install libsndfile"
  exit 1
fi
cp -f "$SNDFILE_SRC" "$FRAMEWORKS_DIR/libsndfile.dylib"
echo "  Copied libsndfile: $SNDFILE_SRC → $FRAMEWORKS_DIR/libsndfile.dylib"

# Find libportaudio
PORTAUDIO_SRC="$(python3 - <<'PYEOF'
import glob, os, site, sys
candidates = []
for sp in site.getsitepackages():
    candidates += glob.glob(os.path.join(sp, "_sounddevice_data", "portaudio-binaries", "*.dylib"))
    candidates += glob.glob(os.path.join(sp, "_sounddevice_data", "*.dylib"))
for p in ["/opt/homebrew/lib/libportaudio.dylib", "/opt/homebrew/lib/libportaudio.2.dylib",
          "/usr/local/lib/libportaudio.dylib", "/usr/local/lib/libportaudio.2.dylib"]:
    if os.path.isfile(p):
        candidates.append(p)
print(candidates[0] if candidates else "")
PYEOF
)"

if [[ -n "$PORTAUDIO_SRC" ]]; then
  cp -f "$PORTAUDIO_SRC" "$FRAMEWORKS_DIR/libportaudio.dylib"
  echo "  Copied libportaudio: $PORTAUDIO_SRC → $FRAMEWORKS_DIR/libportaudio.dylib"
else
  echo "  WARNING: libportaudio not found — audio recording may fail"
fi

# Sanity check
echo ""
echo "Contents/Frameworks dylibs:"
ls -lh "$FRAMEWORKS_DIR"/*.dylib 2>/dev/null || echo "  (none found)"

# ---------------------------------------------------------------------------
# Step 3c — Unzip python311.zip onto the real filesystem
# py2app's no_zip:True is not reliably honoured across all versions.  When it
# is ignored, soundfile.py and _soundfile_data end up inside python311.zip.
# dlopen() cannot open paths inside a zip archive (errno=20, ENOTDIR), so
# soundfile's bundled libsndfile_arm64.dylib becomes unreachable at runtime.
#
# Fix: extract the zip contents to lib/python3.11/ (where they should have
# been placed by no_zip in the first place), then replace the zip with an
# empty archive.  Python's zipimport skips empty archives harmlessly, and
# the real-filesystem copies are found via sys.path in the normal way.
# ---------------------------------------------------------------------------
PYZIP="${APP_PATH}/Contents/Resources/lib/python311.zip"
PYLIB="${APP_PATH}/Contents/Resources/lib/python3.11"

echo ""
echo "=== [3c] Ensuring Python packages are on real filesystem (no_zip workaround) ==="

if [[ -f "$PYZIP" ]]; then
    python3 - "$PYZIP" "$PYLIB" <<'PYEOF'
import zipfile, os, sys

zip_path, dest = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(zip_path, 'r') as z:
    names = z.namelist()

if not names:
    print("  python311.zip is already empty — nothing to do")
    sys.exit(0)

print(f"  Found {len(names)} entries in python311.zip — extracting to lib/python3.11/")
os.makedirs(dest, exist_ok=True)
with zipfile.ZipFile(zip_path, 'r') as z:
    z.extractall(dest)
print(f"  Extracted {len(names)} entries")
PYEOF

    # Replace with empty zip so py2app's boot sys.path entry remains valid
    python3 -c "
import zipfile, sys
with zipfile.ZipFile(sys.argv[1], 'w') as z:
    pass
print('  Replaced python311.zip with empty archive')
" "$PYZIP"
else
    echo "  python311.zip not present — no action needed"
fi

echo ""
echo "Contents/Resources/lib/python3.11 soundfile check:"
ls "${PYLIB}/_soundfile_data/"*.dylib 2>/dev/null \
    && echo "  libsndfile dylib is on real filesystem" \
    || echo "  WARNING: _soundfile_data dylib not found in lib/python3.11"

# ---------------------------------------------------------------------------
# Step 3e — Re-apply ad-hoc signature after bundle modifications
# Steps 3b/3c modify the bundle after py2app signs it, which invalidates the
# signature.  An invalid (broken) signature causes macOS 15+ to show "app is
# damaged" with no "Open Anyway" option.  Re-signing with an ad-hoc identity
# (-s -) fixes the bundle without requiring a paid Developer ID certificate.
# ---------------------------------------------------------------------------
echo ""
echo "=== [3e] Re-signing bundle with ad-hoc identity ==="
codesign --deep --force --sign - "$APP_PATH"
echo "Ad-hoc signature applied."

# ---------------------------------------------------------------------------
# (Optional) Replace the ad-hoc signature above with a Developer ID signature
# for full notarisation and Gatekeeper approval without any user workaround.
# ---------------------------------------------------------------------------
# DEVELOPER_ID="Developer ID Application: Your Name (TEAMID)"
# codesign --deep --force --verify --verbose \
#   --sign "$DEVELOPER_ID" \
#   --entitlements build/entitlements.plist \
#   --options runtime \
#   "$APP_PATH"

# ---------------------------------------------------------------------------
# Step 4 — Create .dmg with create-dmg
# ---------------------------------------------------------------------------
echo ""
echo "=== [4/4] Creating ${DMG_NAME} ==="

# Require create-dmg (install via: npm install -g create-dmg  or  brew install create-dmg)
if ! command -v create-dmg &>/dev/null; then
  echo "ERROR: create-dmg not found."
  echo "Install with:  npm install -g create-dmg"
  echo "          or:  brew install create-dmg"
  exit 1
fi

DMG_OUT="dist/${DMG_NAME}"

create-dmg \
  --volname        "${APP_NAME}" \
  --background     "assets/dmg_background.png" \
  --window-size    540 380 \
  --icon-size      100 \
  --icon           "${APP_NAME}.app" 130 190 \
  --app-drop-link  410 190 \
  "$DMG_OUT" \
  "$APP_PATH"

echo ""
echo "=== Build complete ==="
echo "Output: $DMG_OUT"
echo ""
echo "To distribute without a Developer account:"
echo "  Users must right-click the .app on first launch and choose 'Open'."
echo "  Document this in your README."

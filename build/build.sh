#!/usr/bin/env bash
# Full Scout build pipeline: assets → .app (py2app) → .dmg (create-dmg)
# Run from the project root:
#   chmod +x build/build.sh && ./build/build.sh
set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve project root (the directory containing this script's parent)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

VERSION="1.0.0"
APP_NAME="Scout"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"

echo "=== Scout Build Script v${VERSION} ==="
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
# (Optional) Code-sign the .app
# Uncomment and fill in your Developer ID to sign before notarisation.
# ---------------------------------------------------------------------------
# DEVELOPER_ID="Developer ID Application: Your Name (TEAMID)"
# echo ""
# echo "=== Signing ${APP_NAME}.app ==="
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

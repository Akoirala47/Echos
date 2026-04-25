#!/usr/bin/env python3
"""Generate placeholder app icon and DMG background for Echos.

Run once before building:
    python assets/create_assets.py

Requires: macOS (uses iconutil).  Produces:
    assets/icon_512.png       — 512×512 source PNG
    assets/icon.icns          — macOS icon bundle
    assets/dmg_background.png — 540×380 DMG window background
"""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ASSETS = Path(__file__).parent

# ---------------------------------------------------------------------------
# Minimal PNG encoder (stdlib only — no Pillow needed)
# ---------------------------------------------------------------------------

def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _encode_png(width: int, height: int, pixels: list[tuple[int, int, int, int]]) -> bytes:
    """Encode an RGBA pixel list (row-major) as PNG bytes."""
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter = None
        for x in range(width):
            r, g, b, a = pixels[y * width + x]
            raw += bytes([r, g, b, a])
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr_data)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + _png_chunk(b"IEND", b"")
    )


def _write_png(path: Path, width: int, height: int, pixels: list[tuple[int, int, int, int]]) -> None:
    path.write_bytes(_encode_png(width, height, pixels))
    print(f"  wrote {path}")


# ---------------------------------------------------------------------------
# Icon pixel generator
# ---------------------------------------------------------------------------

# Echos brand blue
_BLUE = (41, 128, 185)
_DARK_BLUE = (31, 97, 141)
_WHITE = (255, 255, 255)


def _icon_pixels(size: int) -> list[tuple[int, int, int, int]]:
    """Return RGBA pixels for a size×size Echos icon.

    Design: deep blue rounded square with a white compass-needle 'S' shape.
    """
    pixels = []
    cx = cy = size / 2
    outer_r = size * 0.46
    corner_r = size * 0.18  # rounded-rect corner radius approximation

    for y in range(size):
        for x in range(size):
            fx, fy = x + 0.5, y + 0.5
            dx, dy = fx - cx, fy - cy

            # Rounded square test: clamp corners
            cdx = max(0.0, abs(dx) - (outer_r - corner_r))
            cdy = max(0.0, abs(dy) - (outer_r - corner_r))
            in_bg = math.hypot(cdx, cdy) <= corner_r

            if not in_bg:
                pixels.append((255, 255, 255, 0))  # transparent outside
                continue

            # Subtle radial gradient on background
            dist = math.hypot(dx, dy) / outer_r
            r = int(_BLUE[0] + (_DARK_BLUE[0] - _BLUE[0]) * dist * 0.5)
            g = int(_BLUE[1] + (_DARK_BLUE[1] - _BLUE[1]) * dist * 0.5)
            b = int(_BLUE[2] + (_DARK_BLUE[2] - _BLUE[2]) * dist * 0.5)

            # Draw a bold "S" glyph using Bézier-approximated rectangles
            # Normalised coords: -0.5 .. +0.5 inside the icon square
            nx = dx / size  # -0.5 .. +0.5
            ny = dy / size

            # Top bar of S
            in_top    = (-0.14 < nx < 0.14) and (-0.20 < ny < -0.12)
            # Top-right of S
            in_tr     = (0.06 < nx < 0.14) and (-0.20 < ny < -0.04)
            # Middle bar of S
            in_mid    = (-0.14 < nx < 0.14) and (-0.04 < ny < 0.04)
            # Bottom-left of S
            in_bl     = (-0.14 < nx < -0.06) and (0.04 < ny < 0.20)
            # Bottom bar of S
            in_bot    = (-0.14 < nx < 0.14) and (0.12 < ny < 0.20)

            # Rounded caps on each bar
            cap_tl = math.hypot(nx + 0.14, ny + 0.20) < 0.04
            cap_tr = math.hypot(nx - 0.14, ny + 0.20) < 0.04
            cap_ml = math.hypot(nx + 0.14, ny)        < 0.04
            cap_mr = math.hypot(nx - 0.14, ny)        < 0.04
            cap_bl = math.hypot(nx + 0.14, ny - 0.20) < 0.04
            cap_br = math.hypot(nx - 0.14, ny - 0.20) < 0.04

            in_s = (in_top or in_tr or in_mid or in_bl or in_bot
                    or cap_tl or cap_tr or cap_ml or cap_mr or cap_bl or cap_br)

            if in_s:
                pixels.append((*_WHITE, 255))
            else:
                pixels.append((r, g, b, 255))

    return pixels


# ---------------------------------------------------------------------------
# DMG background generator
# ---------------------------------------------------------------------------

def _dmg_bg_pixels(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """Light grey gradient background with a subtle grid hint."""
    pixels = []
    for y in range(height):
        for x in range(width):
            # Soft top-to-bottom gradient: #F0F0EE → #E4E4E2
            t = y / height
            base = int(240 - t * 12)
            r = g = base
            b = base - 2

            # Very faint 40-px grid lines
            if x % 40 == 0 or y % 40 == 0:
                r = max(r - 4, 0)
                g = max(g - 4, 0)
                b = max(b - 4, 0)

            pixels.append((r, g, b, 255))
    return pixels


# ---------------------------------------------------------------------------
# iconutil helper
# ---------------------------------------------------------------------------

_ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]


def _make_icns(source_png: Path, out_icns: Path) -> None:
    """Build a .icns bundle from a high-resolution source PNG via iconutil."""
    if sys.platform != "darwin":
        print("  [skip] iconutil requires macOS — .icns not generated")
        return

    iconset_dir = source_png.parent / "Echos.iconset"
    iconset_dir.mkdir(exist_ok=True)

    # Resize source PNG to each required size using sips (macOS built-in).
    for sz in _ICNS_SIZES:
        for scale, suffix in [(1, ""), (2, "@2x")]:
            actual = sz * scale
            if actual > 1024:
                continue
            dest = iconset_dir / f"icon_{sz}x{sz}{suffix}.png"
            subprocess.run(
                ["sips", "-z", str(actual), str(actual), str(source_png),
                 "--out", str(dest)],
                check=True, capture_output=True,
            )

    subprocess.run(
        ["iconutil", "--convert", "icns", "--output", str(out_icns), str(iconset_dir)],
        check=True,
    )
    shutil.rmtree(iconset_dir)
    print(f"  wrote {out_icns}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Generating Echos assets…")

    icon_png = ASSETS / "icon_512.png"
    icon_icns = ASSETS / "icon.icns"
    dmg_bg = ASSETS / "dmg_background.png"

    # icon_512.png
    if not icon_png.exists():
        print("Creating icon_512.png…")
        pixels = _icon_pixels(512)
        _write_png(icon_png, 512, 512, pixels)
    else:
        print(f"  {icon_png} already exists, skipping")

    # icon.icns
    if not icon_icns.exists():
        print("Creating icon.icns…")
        _make_icns(icon_png, icon_icns)
    else:
        print(f"  {icon_icns} already exists, skipping")

    # dmg_background.png
    if not dmg_bg.exists():
        print("Creating dmg_background.png…")
        pixels = _dmg_bg_pixels(540, 380)
        _write_png(dmg_bg, 540, 380, pixels)
    else:
        print(f"  {dmg_bg} already exists, skipping")

    print("Done.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate Echos app icon and DMG background.

Run once before building:
    python assets/create_assets.py

Requires PyQt6 for the icon (already a project dependency).
Produces:
    assets/icon_1024.png       — 1024×1024 source PNG
    assets/icon.icns           — macOS icon bundle
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
# Minimal PNG encoder (stdlib only — for DMG background)
# ---------------------------------------------------------------------------

def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _encode_png(width: int, height: int, pixels: list[tuple[int, int, int, int]]) -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
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
# Qt-based icon generator
# ---------------------------------------------------------------------------

def _generate_icon_qt(size: int) -> bytes:
    """Render the Echos icon at `size`×`size` using QPainter and return PNG bytes.

    Design: warm cream rounded square, concentric pastel rings (rainbow),
    stylised alien-listener face in the centre — mint orbs, golden eyes,
    teal ear pads — inspired by the concept art.
    """
    from PyQt6.QtCore import QBuffer, QByteArray, QPointF, QRectF, Qt
    from PyQt6.QtGui import (
        QBrush, QColor, QPainter, QPainterPath,
        QPen, QPixmap, QRadialGradient,
    )
    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication(sys.argv)

    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    cx = cy = size / 2.0

    # Rounded-square clip
    corner_r = size * 0.22
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size, size), corner_r, corner_r)
    p.setClipPath(clip)

    # Background: warm cream radial gradient
    bg_grad = QRadialGradient(QPointF(cx, cy * 0.75), size * 0.65)
    bg_grad.setColorAt(0.0, QColor("#faf8f4"))
    bg_grad.setColorAt(1.0, QColor("#ece8de"))
    p.fillPath(clip, QBrush(bg_grad))

    # Concentric pastel rings (outermost → innermost)
    ring_palette = [
        "#d4b8d4",  # lavender
        "#b4d4c8",  # seafoam
        "#f2c4a0",  # peach
        "#f5dca0",  # golden yellow
        "#a8d8c0",  # mint
        "#b8c8e8",  # sky blue
        "#e8b4c0",  # rose
        "#c0d4b0",  # sage
        "#d8c0d8",  # mauve
        "#b0d8c8",  # aqua
    ]
    outer_r = size * 0.488
    inner_r = size * 0.275
    n_rings = len(ring_palette)
    slot = (outer_r - inner_r) / n_rings
    stroke_w = slot * 0.58

    p.setBrush(Qt.BrushStyle.NoBrush)
    for i, hex_color in enumerate(ring_palette):
        r = outer_r - i * slot - slot * 0.25
        pen = QPen(QColor(hex_color))
        pen.setWidthF(stroke_w)
        p.setPen(pen)
        p.drawEllipse(QPointF(cx, cy), r, r)

    # ── Face oval ─────────────────────────────────────────────────────────────
    face_rx = size * 0.172
    face_ry = size * 0.198
    face_grad = QRadialGradient(QPointF(cx - face_rx * 0.2, cy - face_ry * 0.3), face_rx * 1.4)
    face_grad.setColorAt(0.0, QColor("#e8f0ec"))
    face_grad.setColorAt(1.0, QColor("#d0dcd8"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(face_grad))
    p.drawEllipse(QPointF(cx, cy), face_rx, face_ry)

    # ── Forehead orbs (vertical stack of 5 — crown to brow only) ─────────────
    orb_r = size * 0.0235
    orb_top_y = cy - face_ry * 0.74
    for oi in range(5):
        oy = orb_top_y + oi * orb_r * 2.10
        og = QRadialGradient(QPointF(cx - orb_r * 0.35, oy - orb_r * 0.35), orb_r)
        og.setColorAt(0.0, QColor("#7dd8b8"))
        og.setColorAt(1.0, QColor("#52b898"))
        p.setBrush(QBrush(og))
        p.drawEllipse(QPointF(cx, oy), orb_r, orb_r)

    # ── Golden eyes ───────────────────────────────────────────────────────────
    eye_rx = size * 0.053
    eye_ry = size * 0.029
    eye_cy = cy - size * 0.016
    for ex in (cx - size * 0.068, cx + size * 0.068):
        # Iris gradient
        eg = QRadialGradient(QPointF(ex - eye_rx * 0.3, eye_cy - eye_ry * 0.3), eye_rx)
        eg.setColorAt(0.0, QColor("#f8c84a"))
        eg.setColorAt(1.0, QColor("#c88020"))
        p.setBrush(QBrush(eg))
        p.drawEllipse(QPointF(ex, eye_cy), eye_rx, eye_ry)
        # Pupil
        p.setBrush(QBrush(QColor("#7a4808")))
        p.drawEllipse(QPointF(ex, eye_cy), eye_rx * 0.38, eye_ry * 0.40)
        # Highlight
        p.setBrush(QBrush(QColor("#fffbe8")))
        p.drawEllipse(QPointF(ex - eye_rx * 0.22, eye_cy - eye_ry * 0.25), eye_rx * 0.18, eye_ry * 0.20)

    # ── Teal ear pads ─────────────────────────────────────────────────────────
    ear_rx = size * 0.036
    ear_ry = size * 0.045
    ear_cy = cy + face_ry * 0.10
    for ear_x in (cx - face_rx * 1.06, cx + face_rx * 1.06):
        eg2 = QRadialGradient(QPointF(ear_x - ear_rx * 0.3, ear_cy - ear_ry * 0.3), ear_rx * 1.2)
        eg2.setColorAt(0.0, QColor("#7dd8b8"))
        eg2.setColorAt(1.0, QColor("#42a880"))
        p.setBrush(QBrush(eg2))
        p.drawEllipse(QPointF(ear_x, ear_cy), ear_rx, ear_ry)

    # ── Subtle mouth ──────────────────────────────────────────────────────────
    mouth_pen = QPen(QColor("#8899a8"))
    mouth_pen.setWidthF(size * 0.009)
    mouth_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(mouth_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    mouth_path = QPainterPath()
    mouth_path.moveTo(cx - size * 0.037, cy + face_ry * 0.50)
    mouth_path.quadTo(cx, cy + face_ry * 0.64, cx + size * 0.037, cy + face_ry * 0.50)
    p.drawPath(mouth_path)

    p.end()

    # Save to PNG bytes via QBuffer
    byte_arr = QByteArray()
    buf = QBuffer(byte_arr)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    px.save(buf, "PNG")
    buf.close()
    return bytes(byte_arr)


# ---------------------------------------------------------------------------
# DMG background generator
# ---------------------------------------------------------------------------

def _dmg_bg_pixels(width: int, height: int) -> list[tuple[int, int, int, int]]:
    pixels = []
    for y in range(height):
        for x in range(width):
            t = y / height
            base = int(240 - t * 12)
            r = g = base
            b = base - 2
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
    if sys.platform != "darwin":
        print("  [skip] iconutil requires macOS — .icns not generated")
        return

    iconset_dir = source_png.parent / "Echos.iconset"
    iconset_dir.mkdir(exist_ok=True)

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

    icon_png = ASSETS / "icon_1024.png"
    icon_icns = ASSETS / "icon.icns"
    dmg_bg = ASSETS / "dmg_background.png"

    # icon_1024.png — generated with Qt for crisp anti-aliasing
    if not icon_png.exists():
        print("Creating icon_1024.png…")
        try:
            png_bytes = _generate_icon_qt(1024)
            icon_png.write_bytes(png_bytes)
            print(f"  wrote {icon_png}")
        except Exception as exc:
            print(f"  Qt rendering failed ({exc}), skipping icon generation")
    else:
        print(f"  {icon_png} already exists, skipping")

    # icon.icns
    if not icon_icns.exists() and icon_png.exists():
        print("Creating icon.icns…")
        _make_icns(icon_png, icon_icns)
    else:
        print(f"  {icon_icns} already exists or source missing, skipping")

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

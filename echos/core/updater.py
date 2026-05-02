"""GitHub release checker and DMG installer."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from echos.version import APP_VERSION, GITHUB_REPO

logger = logging.getLogger(__name__)

_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.lstrip("v").split(".") if x.isdigit())


def newer_than_current(tag: str) -> bool:
    return _parse_version(tag) > _parse_version(APP_VERSION)


class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str)  # (tag, dmg_url)
    up_to_date = pyqtSignal()
    check_failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            req = urllib.request.Request(
                _API_URL,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": f"Echos/{APP_VERSION}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            tag = data["tag_name"]
            dmg_url = next(
                (a["browser_download_url"] for a in data.get("assets", [])
                 if a["name"].endswith(".dmg")),
                None,
            )
            if dmg_url is None:
                self.check_failed.emit("No DMG asset found in latest release.")
                return

            if newer_than_current(tag):
                self.update_available.emit(tag, dmg_url)
            else:
                self.up_to_date.emit()
        except Exception as exc:
            logger.debug("Update check failed: %s", exc)
            self.check_failed.emit(str(exc))


class UpdateInstaller(QThread):
    """Downloads the DMG, mounts it, and copies the .app to /Applications."""

    progress = pyqtSignal(int, int)   # (bytes_done, bytes_total)
    install_done = pyqtSignal()
    install_failed = pyqtSignal(str)

    def __init__(self, download_url: str, parent=None) -> None:
        super().__init__(parent)
        self._url = download_url
        self._tmp_dir: Path | None = None

    def run(self) -> None:
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="echos_update_"))
        dmg_path = self._tmp_dir / "Echos_update.dmg"
        mount_point: str | None = None

        try:
            self._download(dmg_path)
            mount_point = self._mount(dmg_path)
            self._install(mount_point)
            self.install_done.emit()
        except Exception as exc:
            logger.exception("Update install failed")
            self.install_failed.emit(str(exc))
        finally:
            if mount_point:
                subprocess.run(
                    ["hdiutil", "detach", "-quiet", "-force", mount_point],
                    capture_output=True,
                )
            if self._tmp_dir:
                shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _download(self, dest: Path) -> None:
        with urllib.request.urlopen(self._url, timeout=180) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            with open(dest, "wb") as fh:
                while True:
                    block = resp.read(256 * 1024)
                    if not block:
                        break
                    fh.write(block)
                    done += len(block)
                    self.progress.emit(done, total or done)

    def _mount(self, dmg_path: Path) -> str:
        result = subprocess.run(
            ["hdiutil", "attach", "-nobrowse", "-quiet", str(dmg_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"hdiutil attach failed: {result.stderr.strip()}")
        # Last non-empty tab-separated line: /dev/diskNsN \t Apple_HFS \t /Volumes/X
        for line in reversed(result.stdout.strip().splitlines()):
            parts = line.split("\t")
            if len(parts) >= 3 and parts[-1].strip():
                return parts[-1].strip()
        raise RuntimeError("Could not parse hdiutil mount point.")

    def _install(self, mount_point: str) -> None:
        app_src = Path(mount_point) / "Echos.app"
        app_dst = Path("/Applications/Echos.app")

        if not app_src.exists():
            raise RuntimeError(f"Echos.app not found in {mount_point}")

        # Try ditto directly; fall back to osascript for admin rights.
        result = subprocess.run(
            ["ditto", str(app_src), str(app_dst)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return

        # Elevated copy via osascript.
        script = (
            f'do shell script "ditto {shlex_quote(str(app_src))} '
            f'{shlex_quote(str(app_dst))}" with administrator privileges'
        )
        result2 = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True,
        )
        if result2.returncode != 0:
            raise RuntimeError(
                f"Could not install update: {result2.stderr.strip() or result.stderr.strip()}"
            )


def shlex_quote(s: str) -> str:
    """Minimal shell-safe quoting for osascript strings (no import needed)."""
    return "'" + s.replace("'", "'\\''") + "'"

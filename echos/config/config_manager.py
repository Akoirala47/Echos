import json
import os
import tempfile
from pathlib import Path

from .defaults import DEFAULT_CONFIG

_APP_SUPPORT = Path.home() / "Library" / "Application Support" / "Echos"
_CONFIG_PATH = _APP_SUPPORT / "config.json"


class ConfigManager:
    def __init__(self, config_path: Path = _CONFIG_PATH) -> None:
        self._path = config_path

    def is_first_launch(self) -> bool:
        return not self._path.exists()

    def load(self) -> dict:
        if not self._path.exists():
            return dict(DEFAULT_CONFIG)
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                saved = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_CONFIG)
        merged = dict(DEFAULT_CONFIG)
        merged.update(saved)
        return self._migrate(merged)

    @staticmethod
    def _migrate(config: dict) -> dict:
        """Apply version-to-version migrations and return the updated config."""
        version = config.get("version", "1.0")
        if version == "1.0":
            # 1.0 → 1.1: course.folder now supports multi-segment paths (e.g.
            # "School/CS446/Lectures").  No data transformation needed — Path
            # already handles "/" in folder strings — just bump the version so
            # the migration doesn't run again on the next load.
            config = dict(config)
            config["version"] = "1.1"
        return config

    def save(self, config: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp file in same directory, then rename.
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(config, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

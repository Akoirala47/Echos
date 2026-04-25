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
        return merged

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

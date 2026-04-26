"""VaultWatcher — keeps the sidebar vault tree in sync with disk.

Uses QFileSystemWatcher so changes made in Obsidian (new notes, renamed folders)
are reflected within ~1 second without polling.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QObject, pyqtSignal

_IGNORE_NAMES = {".obsidian", ".git", ".DS_Store", "__pycache__", "node_modules"}


class VaultWatcher(QObject):
    """Wraps QFileSystemWatcher; emits `tree_changed` on any vault mutation."""

    tree_changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_changed)
        self._watcher.fileChanged.connect(self._on_changed)
        self._root: Path | None = None

    # ── Public ────────────────────────────────────────────────────────────────

    def watch(self, vault_path: str) -> None:
        """Start watching `vault_path` and all its subdirectories."""
        # Remove all previously watched paths
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        if self._watcher.files():
            self._watcher.removePaths(self._watcher.files())

        root = Path(vault_path)
        if not root.is_dir():
            return
        self._root = root
        self._add_recursive(root)

    def stop(self) -> None:
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        if self._watcher.files():
            self._watcher.removePaths(self._watcher.files())

    def scan(self, root: Path | None = None, max_depth: int = 5) -> list[dict]:
        """Return a nested list of {name, kind, path, children} dicts."""
        target = root or self._root
        if target is None or not target.is_dir():
            return []
        return self._scan_dir(target, 0, max_depth)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _add_recursive(self, path: Path, depth: int = 0, max_depth: int = 5) -> None:
        if depth > max_depth:
            return
        self._watcher.addPath(str(path))
        try:
            for entry in path.iterdir():
                if entry.name in _IGNORE_NAMES or entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    self._add_recursive(entry, depth + 1, max_depth)
        except PermissionError:
            pass

    def _on_changed(self, path: str) -> None:
        # Re-add newly created directories to the watch list
        p = Path(path)
        if p.is_dir():
            self._watcher.addPath(path)
        self.tree_changed.emit()

    def _scan_dir(self, path: Path, depth: int, max_depth: int) -> list[dict]:
        if depth > max_depth:
            return []
        result: list[dict] = []
        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except PermissionError:
            return result
        for entry in entries:
            if entry.name in _IGNORE_NAMES or entry.name.startswith("."):
                continue
            if entry.is_dir():
                result.append({
                    "name": entry.name,
                    "kind": "folder",
                    "path": entry,
                    "children": self._scan_dir(entry, depth + 1, max_depth),
                })
            elif entry.suffix.lower() == ".md":
                result.append({
                    "name": entry.stem,
                    "kind": "note",
                    "path": entry,
                    "children": [],
                })
        return result

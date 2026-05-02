"""IndexWorker — QThread batch processor for vault note indexing."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

_WIKILINK_RE = re.compile(r'\[\[([^\]|#\n]+?)(?:[|#][^\]]*?)?\]\]')


class IndexWorker(QThread):
    """Processes all dirty notes: embed → fingerprint → write edges."""

    note_indexed = pyqtSignal(str)   # full path of processed note
    progress = pyqtSignal(int, int)  # (done, total)
    indexing_finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        vault_index,
        embed_engine,
        fp_engine,
        *,
        api_key: str = "",
        model_id: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._vi = vault_index
        self._embed = embed_engine
        self._fp = fp_engine
        self._api_key = api_key
        self._model_id = model_id
        self._stop_flag = False

    def stop(self) -> None:
        self._stop_flag = True

    def run(self) -> None:
        dirty = self._vi.get_dirty_notes()
        total = len(dirty)
        done = 0

        for row in dirty:
            if self._stop_flag:
                break
            note_id = row["id"]
            path = row["path"]
            try:
                self._process_note(note_id, path)
                done += 1
                self.progress.emit(done, total)
                self.note_indexed.emit(path)
            except Exception as exc:
                logger.warning("IndexWorker: error on %s: %s", path, exc)
                self.error.emit(f"{path}: {exc}")

        self.indexing_finished.emit()

    def _process_note(self, note_id: str, path: str) -> None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Note not found: {path}")

        body = p.read_text(encoding="utf-8", errors="replace")

        vec = self._embed.embed(body)
        vec_blob = vec.tobytes()

        existing_fps = [
            n["fingerprint_text"]
            for n in self._vi.get_all_nodes()
            if n.get("fingerprint_text") and n["id"] != note_id
        ]
        fp = self._fp.generate(body, existing_fps, self._api_key, self._model_id)
        fp_text = fp.to_string()

        self._vi.upsert_note(
            note_id, path, p.stat().st_mtime,
            fingerprint_text=fp_text,
            vector_blob=vec_blob,
            dirty=0,
        )

        self._vi.delete_outgoing_edges(note_id)
        self._index_wikilinks(body, note_id)

    def _index_wikilinks(self, body: str, source_id: str) -> None:
        all_nodes = {n["id"]: n for n in self._vi.get_all_nodes()}

        for m in _WIKILINK_RE.finditer(body):
            target_name = m.group(1).strip()
            for node_id in all_nodes:
                if Path(node_id).stem.lower() == target_name.lower():
                    if node_id != source_id:
                        self._vi.upsert_edge(source_id, node_id, 1.0, "wikilink", "wikilink")
                    break

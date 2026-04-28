"""IndexWorker — background QThread that processes dirty vault notes.

For each dirty note it:
  1. Reads content from disk
  2. Computes an embedding vector via EmbeddingEngine
  3. Generates a concept fingerprint via FingerprintEngine
  4. Stores updated metadata (marks dirty=0)
  5. Parses wikilinks and stores them as edges

Errors for individual notes are reported via the error() signal and do not
abort the rest of the batch — indexing is always best-effort.
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from echos.core.vault_index import VaultIndex

logger = logging.getLogger(__name__)

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")

_BATCH_SIZE = 25


class IndexWorker(QThread):
    """Processes dirty notes in batches, updating the VaultIndex."""

    progress = pyqtSignal(int, int)       # (done, total)
    note_indexed = pyqtSignal(str)        # path of successfully indexed note
    error = pyqtSignal(str)              # human-readable error message
    indexing_finished = pyqtSignal()     # emitted when all batches complete

    def __init__(
        self,
        vault_index: VaultIndex,
        embedding_engine,
        fingerprint_engine,
        api_key: str = "",
        model_id: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._vault_index = vault_index
        self._embedding_engine = embedding_engine
        self._fingerprint_engine = fingerprint_engine
        self._api_key = api_key
        self._model_id = model_id
        self._stop_event = threading.Event()

    # ── Public API ───────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Request a clean stop after the current note finishes."""
        self._stop_event.set()

    # ── QThread.run ──────────────────────────────────────────────────────────

    def run(self) -> None:
        dirty = self._vault_index.get_dirty_notes()
        total = len(dirty)
        done = 0

        for batch_start in range(0, total, _BATCH_SIZE):
            if self._stop_event.is_set():
                break
            batch = dirty[batch_start : batch_start + _BATCH_SIZE]
            for note in batch:
                if self._stop_event.is_set():
                    break
                try:
                    self._process_note(note)
                    done += 1
                    self.note_indexed.emit(note.get("path", ""))
                    self.progress.emit(done, total)
                except Exception as exc:
                    path = note.get("path", "?")
                    logger.warning("IndexWorker: error processing %s: %s", path, exc)
                    self.error.emit(f"Error indexing {Path(path).name}: {exc}")

        self.indexing_finished.emit()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _process_note(self, note: dict) -> None:
        path = note["path"]
        note_id = note["id"]

        content = Path(path).read_text(encoding="utf-8", errors="replace")

        # 1. Embed the note content (or fingerprint concepts string if available)
        vec = self._embedding_engine.embed(content[:2000])
        vector_blob = vec.tobytes() if vec is not None else None

        # 2. Generate fingerprint (best-effort; may fail if no API key)
        fingerprint_text = note.get("fingerprint_text") or ""
        content_hash = ""
        if self._fingerprint_engine is not None and self._api_key:
            existing_fps = [
                n["fingerprint_text"]
                for n in self._vault_index.get_all_nodes()
                if n.get("fingerprint_text") and n["id"] != note_id
            ]
            fp = self._fingerprint_engine.generate(
                content, existing_fps, self._api_key, self._model_id
            )
            fingerprint_text = fp.to_string()
            content_hash = fp.content_hash

        # 3. Persist — mark dirty=0
        self._vault_index.upsert_note(
            id=note_id,
            path=path,
            modified_at=Path(path).stat().st_mtime,
            content_hash=content_hash,
            fingerprint_text=fingerprint_text,
            vector_blob=vector_blob,
            dirty=0,
        )

        # 4. Recompute wikilink edges
        self._vault_index.delete_outgoing_edges(note_id)
        self._index_wikilinks(note_id, content)

    def _index_wikilinks(self, note_id: str, content: str) -> None:
        links = _WIKILINK_RE.findall(content)
        if not links:
            return
        all_nodes = self._vault_index.get_all_nodes()
        stem_to_id = {Path(n["path"]).stem.lower(): n["id"] for n in all_nodes}
        for link_text in links:
            target_key = link_text.strip().lower()
            target_id = stem_to_id.get(target_key)
            if target_id and target_id != note_id:
                self._vault_index.upsert_edge(
                    source_id=note_id,
                    target_id=target_id,
                    strength=1.0,
                    reason="wikilink",
                    edge_type="wikilink",
                )

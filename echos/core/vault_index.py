"""VaultIndex — SQLite-backed index of vault notes, edges, and tags.

Database lives at {vault_root}/.echoes/vault.index.db.
All writes are wrapped in transactions; a single connection is kept open
for the process lifetime and guarded by a threading.Lock.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS notes (
    id              TEXT PRIMARY KEY,
    path            TEXT UNIQUE,
    modified_at     REAL,
    content_hash    TEXT,
    fingerprint_text TEXT,
    vector_blob     BLOB,
    dirty           INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS edges (
    source_id   TEXT,
    target_id   TEXT,
    strength    REAL,
    reason      TEXT,
    edge_type   TEXT,
    created_at  REAL,
    PRIMARY KEY (source_id, target_id)
);

CREATE TABLE IF NOT EXISTS tags (
    note_id TEXT,
    tag     TEXT,
    source  TEXT CHECK(source IN ('llm', 'user')),
    PRIMARY KEY (note_id, tag)
);
"""


class VaultIndex:
    """SQLite-backed persistence layer for vault metadata."""

    _ECHOES_DIR = ".echoes"
    _DB_NAME = "vault.index.db"

    def __init__(self, vault_root: "Path | str") -> None:
        self._root = Path(vault_root)
        echoes_dir = self._root / self._ECHOES_DIR
        echoes_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = echoes_dir / self._DB_NAME
        self._lock = threading.Lock()
        self._con: sqlite3.Connection = sqlite3.connect(
            str(self._db_path), check_same_thread=False
        )
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.executescript(_SCHEMA)
            self._con.commit()

    @property
    def root(self) -> Path:
        return self._root

    # ── Notes ─────────────────────────────────────────────────────────────

    def upsert_note(
        self,
        id: str,
        path: str,
        modified_at: float,
        content_hash: str = "",
        fingerprint_text: str = "",
        vector_blob: bytes | None = None,
        dirty: int = 1,
    ) -> None:
        with self._lock:
            self._con.execute(
                """
                INSERT INTO notes (id, path, modified_at, content_hash,
                                   fingerprint_text, vector_blob, dirty)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    path             = excluded.path,
                    modified_at      = excluded.modified_at,
                    content_hash     = excluded.content_hash,
                    fingerprint_text = excluded.fingerprint_text,
                    vector_blob      = excluded.vector_blob,
                    dirty            = excluded.dirty
                """,
                (id, path, modified_at, content_hash, fingerprint_text, vector_blob, dirty),
            )
            self._con.commit()

    def set_dirty(self, path: str) -> None:
        rel = self._rel_id(path)
        with self._lock:
            self._con.execute(
                "UPDATE notes SET dirty=1 WHERE path=? OR id=?", (path, rel)
            )
            self._con.commit()

    def get_dirty_notes(self) -> list[dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM notes WHERE dirty=1"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_nodes(self) -> list[dict]:
        with self._lock:
            rows = self._con.execute("SELECT * FROM notes").fetchall()
            return [dict(r) for r in rows]

    def delete_note(self, path: str) -> None:
        rel = self._rel_id(path)
        with self._lock:
            row = self._con.execute(
                "SELECT id FROM notes WHERE path=? OR id=?", (path, rel)
            ).fetchone()
            if row:
                nid = row["id"]
                self._con.execute(
                    "DELETE FROM edges WHERE source_id=? OR target_id=?", (nid, nid)
                )
                self._con.execute("DELETE FROM tags WHERE note_id=?", (nid,))
                self._con.execute("DELETE FROM notes WHERE id=?", (nid,))
            self._con.commit()

    # ── Edges ─────────────────────────────────────────────────────────────

    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        strength: float,
        reason: str,
        edge_type: str,
    ) -> None:
        now = time.time()
        with self._lock:
            self._con.execute(
                """
                INSERT INTO edges (source_id, target_id, strength, reason, edge_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id) DO UPDATE SET
                    strength   = excluded.strength,
                    reason     = excluded.reason,
                    edge_type  = excluded.edge_type,
                    created_at = excluded.created_at
                """,
                (source_id, target_id, strength, reason, edge_type, now),
            )
            self._con.commit()

    def delete_outgoing_edges(self, note_id: str) -> None:
        with self._lock:
            self._con.execute("DELETE FROM edges WHERE source_id=?", (note_id,))
            self._con.commit()

    def get_edges(self, note_id: str) -> list[dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM edges WHERE source_id=? OR target_id=?",
                (note_id, note_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_edges(self) -> list[dict]:
        with self._lock:
            rows = self._con.execute("SELECT * FROM edges").fetchall()
            return [dict(r) for r in rows]

    # ── Misc ──────────────────────────────────────────────────────────────

    def clear_index(self) -> None:
        with self._lock:
            self._con.execute("DELETE FROM notes")
            self._con.execute("DELETE FROM edges")
            self._con.execute("DELETE FROM tags")
            self._con.commit()

    def close(self) -> None:
        with self._lock:
            if self._con:
                self._con.close()

    # ── Internal ──────────────────────────────────────────────────────────

    def _rel_id(self, path: str) -> str:
        """Return path relative to vault root, or the original string on failure."""
        try:
            return str(Path(path).relative_to(self._root))
        except ValueError:
            return path

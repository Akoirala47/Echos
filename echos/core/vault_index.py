"""VaultIndex — thread-safe SQLite index: notes, edges, tags."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class VaultIndex:
    """Persistent SQLite store for vault notes, concept edges, and tags."""

    def __init__(self, vault_path: str | Path) -> None:
        root = Path(vault_path)
        echoes = root / ".echoes"
        echoes.mkdir(parents=True, exist_ok=True)
        db = echoes / "vault.index.db"

        self._lock = threading.Lock()
        self._con = sqlite3.connect(str(db), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._con.executescript("""
                CREATE TABLE IF NOT EXISTS notes (
                    id               TEXT PRIMARY KEY,
                    path             TEXT NOT NULL,
                    modified_at      REAL NOT NULL DEFAULT 0,
                    content_hash     TEXT,
                    fingerprint_text TEXT,
                    vector_blob      BLOB,
                    dirty            INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS edges (
                    source_id  TEXT NOT NULL,
                    target_id  TEXT NOT NULL,
                    strength   REAL NOT NULL DEFAULT 0.5,
                    reason     TEXT,
                    edge_type  TEXT NOT NULL DEFAULT 'concept',
                    created_at REAL NOT NULL DEFAULT (unixepoch()),
                    PRIMARY KEY (source_id, target_id)
                );

                CREATE TABLE IF NOT EXISTS tags (
                    note_id TEXT NOT NULL,
                    tag     TEXT NOT NULL,
                    source  TEXT NOT NULL
                        CHECK(source IN ('frontmatter','llm','wikilink','domain')),
                    PRIMARY KEY (note_id, tag)
                );
            """)

    # ── Notes ─────────────────────────────────────────────────────────────────

    def upsert_note(
        self,
        note_id: str,
        path: str,
        modified_at: float,
        *,
        content_hash: str | None = None,
        fingerprint_text: str | None = None,
        vector_blob: bytes | None = None,
        dirty: int = 1,
    ) -> None:
        with self._lock:
            self._con.execute(
                """
                INSERT INTO notes
                    (id, path, modified_at, content_hash, fingerprint_text, vector_blob, dirty)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    path             = excluded.path,
                    modified_at      = excluded.modified_at,
                    content_hash     = COALESCE(excluded.content_hash,     content_hash),
                    fingerprint_text = COALESCE(excluded.fingerprint_text, fingerprint_text),
                    vector_blob      = COALESCE(excluded.vector_blob,      vector_blob),
                    dirty            = excluded.dirty
                """,
                (note_id, path, modified_at, content_hash, fingerprint_text, vector_blob, dirty),
            )
            self._con.commit()

    def get_dirty_notes(self) -> list[dict]:
        with self._lock:
            rows = self._con.execute("SELECT * FROM notes WHERE dirty = 1").fetchall()
        return [dict(r) for r in rows]

    def get_all_nodes(self) -> list[dict]:
        with self._lock:
            rows = self._con.execute("SELECT * FROM notes").fetchall()
        return [dict(r) for r in rows]

    def set_dirty(self, path: str) -> None:
        with self._lock:
            self._con.execute("UPDATE notes SET dirty = 1 WHERE path = ?", (path,))
            self._con.commit()

    def delete_note(self, path: str) -> None:
        with self._lock:
            row = self._con.execute(
                "SELECT id FROM notes WHERE path = ?", (path,)
            ).fetchone()
            if row:
                nid = row["id"]
                self._con.execute(
                    "DELETE FROM edges WHERE source_id = ? OR target_id = ?", (nid, nid)
                )
                self._con.execute("DELETE FROM tags WHERE note_id = ?", (nid,))
                self._con.execute("DELETE FROM notes WHERE id = ?", (nid,))
            self._con.commit()

    # ── Edges ─────────────────────────────────────────────────────────────────

    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        strength: float,
        reason: str,
        edge_type: str,
    ) -> None:
        with self._lock:
            self._con.execute(
                """
                INSERT INTO edges (source_id, target_id, strength, reason, edge_type, created_at)
                VALUES (?, ?, ?, ?, ?, unixepoch())
                ON CONFLICT(source_id, target_id) DO UPDATE SET
                    strength   = excluded.strength,
                    reason     = excluded.reason,
                    edge_type  = excluded.edge_type,
                    created_at = excluded.created_at
                """,
                (source_id, target_id, strength, reason, edge_type),
            )
            self._con.commit()

    def get_all_edges(self) -> list[dict]:
        with self._lock:
            rows = self._con.execute("SELECT * FROM edges").fetchall()
        return [dict(r) for r in rows]

    def get_edges(self, note_id: str) -> list[dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM edges WHERE source_id = ? OR target_id = ?",
                (note_id, note_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_outgoing_edges(self, note_id: str) -> None:
        with self._lock:
            self._con.execute("DELETE FROM edges WHERE source_id = ?", (note_id,))
            self._con.commit()

    # ── Bulk ops ──────────────────────────────────────────────────────────────

    def clear_index(self) -> None:
        with self._lock:
            self._con.execute("DELETE FROM edges")
            self._con.execute("DELETE FROM tags")
            self._con.execute("DELETE FROM notes")
            self._con.commit()

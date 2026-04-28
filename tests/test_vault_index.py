"""Unit tests for VaultIndex (Phase 23 — T-I05)."""

from __future__ import annotations

from pathlib import Path

import pytest

from echos.core.vault_index import VaultIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_index(tmp_path: Path) -> VaultIndex:
    return VaultIndex(tmp_path)


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

class TestSchemaCreation:
    def test_creates_echoes_directory(self, tmp_path: Path):
        VaultIndex(tmp_path)
        assert (tmp_path / ".echoes").is_dir()

    def test_creates_db_file(self, tmp_path: Path):
        VaultIndex(tmp_path)
        assert (tmp_path / ".echoes" / "vault.index.db").is_file()

    def test_tables_exist(self, tmp_path: Path):
        import sqlite3
        VaultIndex(tmp_path)
        con = sqlite3.connect(str(tmp_path / ".echoes" / "vault.index.db"))
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        con.close()
        assert {"notes", "edges", "tags"} <= tables

    def test_reinit_same_path_does_not_raise(self, tmp_path: Path):
        VaultIndex(tmp_path)
        VaultIndex(tmp_path)  # second open should not error


# ---------------------------------------------------------------------------
# upsert_note / get_dirty_notes / get_all_nodes
# ---------------------------------------------------------------------------

class TestNoteOps:
    def test_upsert_and_get_dirty(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("note1.md", "/vault/note1.md", 1234567890.0, dirty=1)
        dirty = vi.get_dirty_notes()
        assert len(dirty) == 1
        assert dirty[0]["id"] == "note1.md"
        assert dirty[0]["dirty"] == 1

    def test_clean_note_not_in_dirty(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("note1.md", "/vault/note1.md", 0.0, dirty=0)
        assert vi.get_dirty_notes() == []

    def test_upsert_updates_existing(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("note1.md", "/v/note1.md", 100.0, fingerprint_text="old", dirty=0)
        vi.upsert_note("note1.md", "/v/note1.md", 200.0, fingerprint_text="new", dirty=1)
        nodes = vi.get_all_nodes()
        assert len(nodes) == 1
        assert nodes[0]["fingerprint_text"] == "new"
        assert nodes[0]["modified_at"] == 200.0

    def test_get_all_nodes_returns_all(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("a.md", "/v/a.md", 0.0, dirty=1)
        vi.upsert_note("b.md", "/v/b.md", 0.0, dirty=0)
        nodes = vi.get_all_nodes()
        ids = {n["id"] for n in nodes}
        assert ids == {"a.md", "b.md"}

    def test_set_dirty_by_path(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("note1.md", "/v/note1.md", 0.0, dirty=0)
        vi.set_dirty("/v/note1.md")
        dirty = vi.get_dirty_notes()
        assert len(dirty) == 1
        assert dirty[0]["id"] == "note1.md"

    def test_set_dirty_by_rel_id(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("sub/note.md", str(tmp_path / "sub" / "note.md"), 0.0, dirty=0)
        vi.set_dirty(str(tmp_path / "sub" / "note.md"))
        assert len(vi.get_dirty_notes()) == 1

    def test_delete_note_removes_row(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("n.md", "/v/n.md", 0.0, dirty=1)
        vi.delete_note("/v/n.md")
        assert vi.get_all_nodes() == []

    def test_delete_note_removes_edges(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("a.md", "/v/a.md", 0.0, dirty=0)
        vi.upsert_note("b.md", "/v/b.md", 0.0, dirty=0)
        vi.upsert_edge("a.md", "b.md", 1.0, "wikilink", "wikilink")
        vi.delete_note("/v/a.md")
        assert vi.get_all_edges() == []

    def test_vector_blob_round_trip(self, tmp_path: Path):
        import numpy as np
        vi = make_index(tmp_path)
        vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        vi.upsert_note("n.md", "/v/n.md", 0.0, vector_blob=vec.tobytes(), dirty=0)
        nodes = vi.get_all_nodes()
        restored = np.frombuffer(nodes[0]["vector_blob"], dtype=np.float32)
        assert list(restored) == pytest.approx([0.1, 0.2, 0.3], abs=1e-6)


# ---------------------------------------------------------------------------
# upsert_edge / get_all_edges / delete_outgoing_edges / get_edges
# ---------------------------------------------------------------------------

class TestEdgeOps:
    def test_upsert_and_get_all_edges(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("a.md", "/v/a.md", 0.0, dirty=0)
        vi.upsert_note("b.md", "/v/b.md", 0.0, dirty=0)
        vi.upsert_edge("a.md", "b.md", 0.75, "shared concept", "concept")
        edges = vi.get_all_edges()
        assert len(edges) == 1
        assert edges[0]["source_id"] == "a.md"
        assert edges[0]["target_id"] == "b.md"
        assert edges[0]["strength"] == pytest.approx(0.75)
        assert edges[0]["edge_type"] == "concept"

    def test_upsert_edge_updates_on_conflict(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("a.md", "/v/a.md", 0.0, dirty=0)
        vi.upsert_note("b.md", "/v/b.md", 0.0, dirty=0)
        vi.upsert_edge("a.md", "b.md", 0.5, "old reason", "concept")
        vi.upsert_edge("a.md", "b.md", 1.0, "wikilink", "wikilink")
        edges = vi.get_all_edges()
        assert len(edges) == 1
        assert edges[0]["strength"] == pytest.approx(1.0)
        assert edges[0]["edge_type"] == "wikilink"

    def test_get_edges_returns_both_directions(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("a.md", "/v/a.md", 0.0, dirty=0)
        vi.upsert_note("b.md", "/v/b.md", 0.0, dirty=0)
        vi.upsert_note("c.md", "/v/c.md", 0.0, dirty=0)
        vi.upsert_edge("a.md", "b.md", 1.0, "wikilink", "wikilink")
        vi.upsert_edge("c.md", "a.md", 0.8, "concept", "concept")
        edges = vi.get_edges("a.md")
        types = {(e["source_id"], e["target_id"]) for e in edges}
        assert ("a.md", "b.md") in types
        assert ("c.md", "a.md") in types

    def test_delete_outgoing_edges(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("a.md", "/v/a.md", 0.0, dirty=0)
        vi.upsert_note("b.md", "/v/b.md", 0.0, dirty=0)
        vi.upsert_note("c.md", "/v/c.md", 0.0, dirty=0)
        vi.upsert_edge("a.md", "b.md", 1.0, "wikilink", "wikilink")
        vi.upsert_edge("c.md", "a.md", 0.8, "concept", "concept")
        vi.delete_outgoing_edges("a.md")
        edges = vi.get_all_edges()
        # Only the incoming edge (c→a) should remain
        assert len(edges) == 1
        assert edges[0]["source_id"] == "c.md"

    def test_delete_outgoing_noop_for_unknown_note(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.delete_outgoing_edges("nonexistent.md")  # should not raise


# ---------------------------------------------------------------------------
# clear_index
# ---------------------------------------------------------------------------

class TestClearIndex:
    def test_clears_all_tables(self, tmp_path: Path):
        vi = make_index(tmp_path)
        vi.upsert_note("a.md", "/v/a.md", 0.0, dirty=1)
        vi.upsert_note("b.md", "/v/b.md", 0.0, dirty=0)
        vi.upsert_edge("a.md", "b.md", 1.0, "link", "wikilink")
        vi.clear_index()
        assert vi.get_all_nodes() == []
        assert vi.get_all_edges() == []


# ---------------------------------------------------------------------------
# Transaction / constraint robustness
# ---------------------------------------------------------------------------

class TestConstraints:
    def test_upsert_idempotent_same_data(self, tmp_path: Path):
        vi = make_index(tmp_path)
        for _ in range(3):
            vi.upsert_note("n.md", "/v/n.md", 0.0, dirty=1)
        assert len(vi.get_all_nodes()) == 1

    def test_invalid_tag_source_raises(self, tmp_path: Path):
        import sqlite3
        vi = make_index(tmp_path)
        vi.upsert_note("n.md", "/v/n.md", 0.0, dirty=0)
        with pytest.raises(sqlite3.IntegrityError):
            with vi._lock:
                vi._con.execute(
                    "INSERT INTO tags (note_id, tag, source) VALUES (?, ?, ?)",
                    ("n.md", "test-tag", "invalid_source"),
                )
                vi._con.commit()

    def test_after_constraint_error_db_still_functional(self, tmp_path: Path):
        import sqlite3
        vi = make_index(tmp_path)
        vi.upsert_note("n.md", "/v/n.md", 0.0, dirty=0)
        # Intentionally violate constraint
        try:
            with vi._lock:
                vi._con.execute(
                    "INSERT INTO tags (note_id, tag, source) VALUES (?, ?, ?)",
                    ("n.md", "t", "bad"),
                )
                vi._con.commit()
        except sqlite3.IntegrityError:
            with vi._lock:
                vi._con.rollback()
        # DB should still work after the error
        vi.upsert_note("n2.md", "/v/n2.md", 1.0, dirty=1)
        assert len(vi.get_all_nodes()) == 2

"""Unit tests for IndexWorker (Phase 23 — T-I06).

Calls worker.run() directly (not worker.start()) to avoid needing a Qt event
loop; Qt signals emitted from run() fire synchronously in the same thread.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from echos.core.fingerprint import Fingerprint
from echos.core.index_worker import IndexWorker
from echos.core.vault_index import VaultIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dummy_vec() -> np.ndarray:
    return np.zeros(384, dtype=np.float32)


def _make_embed_engine(vec=None):
    m = MagicMock()
    m.embed.return_value = vec if vec is not None else _dummy_vec()
    return m


def _make_fp_engine(concepts=None, domains=None):
    m = MagicMock()
    m.generate.return_value = Fingerprint(
        concepts=concepts or ["concept"],
        domains=domains or ["domain"],
        content_hash="ab3f",
    )
    return m


def _create_md_files(directory: Path, count: int) -> list[Path]:
    paths = []
    for i in range(count):
        p = directory / f"note{i}.md"
        p.write_text(f"# Note {i}\n\nContent for note {i}.")
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# T-I06-1: batch processing marks notes clean
# ---------------------------------------------------------------------------

class TestBatchProcessing:
    def test_processing_marks_notes_clean(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        _create_md_files(tmp_path, 3)

        for i in range(3):
            md = tmp_path / f"note{i}.md"
            vi.upsert_note(f"note{i}.md", str(md), md.stat().st_mtime, dirty=1)

        worker = IndexWorker(vi, _make_embed_engine(), _make_fp_engine())
        worker.run()

        assert vi.get_dirty_notes() == []

    def test_processing_stores_fingerprint(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        md = tmp_path / "note.md"
        md.write_text("# Test")
        vi.upsert_note("note.md", str(md), md.stat().st_mtime, dirty=1)

        fp_engine = _make_fp_engine(concepts=["alpha", "beta"])
        worker = IndexWorker(vi, _make_embed_engine(), fp_engine, api_key="k", model_id="m")
        worker.run()

        nodes = vi.get_all_nodes()
        assert len(nodes) == 1
        assert "alpha" in nodes[0]["fingerprint_text"]

    def test_processing_stores_vector_blob(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        md = tmp_path / "note.md"
        md.write_text("# Test")
        vi.upsert_note("note.md", str(md), md.stat().st_mtime, dirty=1)

        vec = np.ones(384, dtype=np.float32)
        worker = IndexWorker(vi, _make_embed_engine(vec=vec), _make_fp_engine())
        worker.run()

        nodes = vi.get_all_nodes()
        blob = nodes[0]["vector_blob"]
        assert blob is not None
        restored = np.frombuffer(blob, dtype=np.float32)
        assert restored.shape == (384,)

    def test_emits_note_indexed_signal(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        md = tmp_path / "note.md"
        md.write_text("# Test")
        vi.upsert_note("note.md", str(md), md.stat().st_mtime, dirty=1)

        indexed_paths: list[str] = []
        worker = IndexWorker(vi, _make_embed_engine(), _make_fp_engine())
        worker.note_indexed.connect(indexed_paths.append)
        worker.run()

        assert str(md) in indexed_paths

    def test_emits_progress_signal(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        for i in range(3):
            md = tmp_path / f"n{i}.md"
            md.write_text("content")
            vi.upsert_note(f"n{i}.md", str(md), md.stat().st_mtime, dirty=1)

        progress_calls: list[tuple[int, int]] = []
        worker = IndexWorker(vi, _make_embed_engine(), _make_fp_engine())
        worker.progress.connect(lambda d, t: progress_calls.append((d, t)))
        worker.run()

        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)

    def test_emits_finished_signal(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        md = tmp_path / "n.md"
        md.write_text("content")
        vi.upsert_note("n.md", str(md), md.stat().st_mtime, dirty=1)

        finished = []
        worker = IndexWorker(vi, _make_embed_engine(), _make_fp_engine())
        worker.indexing_finished.connect(lambda: finished.append(True))
        worker.run()

        assert finished == [True]

    def test_no_dirty_notes_emits_finished_immediately(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        finished = []
        worker = IndexWorker(vi, _make_embed_engine(), _make_fp_engine())
        worker.indexing_finished.connect(lambda: finished.append(True))
        worker.run()
        assert finished == [True]


# ---------------------------------------------------------------------------
# T-I06-2: stop() exits cleanly mid-batch
# ---------------------------------------------------------------------------

class TestStopBehaviour:
    def test_stop_before_run_skips_all(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        for i in range(10):
            md = tmp_path / f"n{i}.md"
            md.write_text(f"Content {i}")
            vi.upsert_note(f"n{i}.md", str(md), md.stat().st_mtime, dirty=1)

        worker = IndexWorker(vi, _make_embed_engine(), _make_fp_engine())
        worker.stop()
        worker.run()

        # No notes should have been processed
        assert len(vi.get_dirty_notes()) == 10

    def test_stop_mid_run_exits_after_current_note(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        mds = _create_md_files(tmp_path, 5)
        for md in mds:
            vi.upsert_note(md.name, str(md), md.stat().st_mtime, dirty=1)

        stop_event_set = False

        original_embed = _make_embed_engine().embed

        call_count = 0

        def embed_with_stop(text):
            nonlocal call_count, stop_event_set
            call_count += 1
            if call_count == 2:
                worker.stop()
                stop_event_set = True
            return _dummy_vec()

        mock_emb = MagicMock()
        mock_emb.embed.side_effect = embed_with_stop

        worker = IndexWorker(vi, mock_emb, _make_fp_engine())
        worker.run()

        # stop was set at note 2, so processing stopped before all 5
        assert stop_event_set
        remaining_dirty = len(vi.get_dirty_notes())
        assert remaining_dirty > 0  # some notes still dirty


# ---------------------------------------------------------------------------
# T-I06-3: error in one note does not abort the batch
# ---------------------------------------------------------------------------

class TestErrorIsolation:
    def test_error_in_one_note_continues_rest(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        for i in range(4):
            md = tmp_path / f"n{i}.md"
            md.write_text(f"Content {i}")
            vi.upsert_note(f"n{i}.md", str(md), md.stat().st_mtime, dirty=1)

        call_count = 0

        def embed_sometimes_fails(text):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Embedding failed for note 2")
            return _dummy_vec()

        mock_emb = MagicMock()
        mock_emb.embed.side_effect = embed_sometimes_fails

        errors: list[str] = []
        worker = IndexWorker(vi, mock_emb, _make_fp_engine())
        worker.error.connect(errors.append)
        worker.run()

        # Exactly one error was reported
        assert len(errors) == 1

        # The failed note should still be dirty; the others should be clean
        dirty = vi.get_dirty_notes()
        assert len(dirty) == 1

    def test_missing_file_reports_error_continues(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        # One real file, one phantom path
        real_md = tmp_path / "real.md"
        real_md.write_text("Real content")
        vi.upsert_note("real.md", str(real_md), real_md.stat().st_mtime, dirty=1)
        vi.upsert_note(
            "ghost.md", str(tmp_path / "ghost.md"), 0.0, dirty=1
        )

        errors: list[str] = []
        worker = IndexWorker(vi, _make_embed_engine(), _make_fp_engine())
        worker.error.connect(errors.append)
        worker.run()

        # Ghost file error reported, real file processed
        assert len(errors) == 1
        dirty = vi.get_dirty_notes()
        assert len(dirty) == 1
        assert dirty[0]["id"] == "ghost.md"


# ---------------------------------------------------------------------------
# Wikilink edge indexing
# ---------------------------------------------------------------------------

class TestWikilinkIndexing:
    def test_wikilinks_stored_as_edges(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        note_a = tmp_path / "topic.md"
        note_b = tmp_path / "related.md"
        note_a.write_text("# Topic\n\nSee also [[related]].")
        note_b.write_text("# Related\n\nContent.")

        vi.upsert_note("topic.md", str(note_a), note_a.stat().st_mtime, dirty=1)
        vi.upsert_note("related.md", str(note_b), note_b.stat().st_mtime, dirty=0)

        worker = IndexWorker(vi, _make_embed_engine(), _make_fp_engine())
        worker.run()

        edges = vi.get_all_edges()
        edge_pairs = {(e["source_id"], e["target_id"]) for e in edges}
        assert ("topic.md", "related.md") in edge_pairs

    def test_no_wikilinks_no_edges(self, tmp_path: Path, qtbot):
        vi = VaultIndex(tmp_path)
        md = tmp_path / "standalone.md"
        md.write_text("# Standalone\n\nNo links here.")
        vi.upsert_note("standalone.md", str(md), md.stat().st_mtime, dirty=1)

        worker = IndexWorker(vi, _make_embed_engine(), _make_fp_engine())
        worker.run()

        assert vi.get_all_edges() == []

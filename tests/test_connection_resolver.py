"""Unit tests for ConnectionResolver (Phase 24 — T-R05)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from echos.core.connection_resolver import ConnectionResolver, EdgeData, NodeData, _cosine
from echos.core.vault_index import VaultIndex
from echos.utils.theme import DOMAIN_PALETTE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vi(tmp_path: Path) -> VaultIndex:
    return VaultIndex(tmp_path)


def _unit_vec(dim: int, hot: int) -> np.ndarray:
    """One-hot unit vector in dimension *dim* with index *hot* set to 1."""
    v = np.zeros(dim, dtype=np.float32)
    v[hot] = 1.0
    return v


def _similar_vec(base: np.ndarray, noise: float = 0.05) -> np.ndarray:
    """Return a vector close to *base* (cosine > 0.8)."""
    v = base + np.random.default_rng(42).uniform(-noise, noise, base.shape).astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


# ---------------------------------------------------------------------------
# Empty vault
# ---------------------------------------------------------------------------

class TestEmptyVault:
    def test_empty_vault_returns_empty_nodes_and_edges(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        nodes, edges = ConnectionResolver.resolve(vi)
        assert nodes == []
        assert edges == []

    def test_vault_with_no_indexed_notes_returns_empty(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        # Insert a note but with no content (not yet indexed)
        vi.upsert_note("note.md", str(tmp_path / "note.md"), 0.0, dirty=1)
        nodes, edges = ConnectionResolver.resolve(vi)
        # Should have one file node, no edges
        file_nodes = [n for n in nodes if n.kind == "file"]
        assert len(file_nodes) == 1
        assert edges == []


# ---------------------------------------------------------------------------
# NodeData fields
# ---------------------------------------------------------------------------

class TestNodeDataFields:
    def test_file_node_label_is_stem(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note("lecture-01.md", str(tmp_path / "lecture-01.md"), 0.0, dirty=0)
        nodes, _ = ConnectionResolver.resolve(vi)
        file_nodes = [n for n in nodes if n.kind == "file"]
        assert file_nodes[0].label == "lecture-01"

    def test_file_node_domain_from_fingerprint(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        fp = "concepts:[ml,backprop] | domain:[ai,ml] | hash:aaaa"
        vi.upsert_note("n.md", str(tmp_path / "n.md"), 0.0, fingerprint_text=fp, dirty=0)
        nodes, _ = ConnectionResolver.resolve(vi)
        file_node = next(n for n in nodes if n.kind == "file")
        assert file_node.domain == "ai"

    def test_file_node_color_in_domain_palette(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        fp = "concepts:[ml] | domain:[science] | hash:aaaa"
        vi.upsert_note("n.md", str(tmp_path / "n.md"), 0.0, fingerprint_text=fp, dirty=0)
        nodes, _ = ConnectionResolver.resolve(vi)
        file_node = next(n for n in nodes if n.kind == "file")
        assert file_node.color in DOMAIN_PALETTE

    def test_file_node_without_fingerprint_gets_default_color(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note("n.md", str(tmp_path / "n.md"), 0.0, dirty=0)
        nodes, _ = ConnectionResolver.resolve(vi)
        file_node = next(n for n in nodes if n.kind == "file")
        assert file_node.color == "#b0ae9e"   # CANVAS_NODE_DEFAULT

    def test_dir_node_created_for_subdirectory(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note(
            "CS446/note.md", str(tmp_path / "CS446" / "note.md"), 0.0, dirty=0
        )
        nodes, _ = ConnectionResolver.resolve(vi)
        dir_nodes = [n for n in nodes if n.kind == "dir"]
        assert len(dir_nodes) == 1
        assert dir_nodes[0].id == "CS446"
        assert dir_nodes[0].label == "CS446"

    def test_file_node_dir_id_matches_parent_dir(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note(
            "CS446/note.md", str(tmp_path / "CS446" / "note.md"), 0.0, dirty=0
        )
        nodes, _ = ConnectionResolver.resolve(vi)
        file_node = next(n for n in nodes if n.kind == "file")
        assert file_node.dir_id == "CS446"

    def test_root_level_file_has_no_dir_id(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note("root.md", str(tmp_path / "root.md"), 0.0, dirty=0)
        nodes, _ = ConnectionResolver.resolve(vi)
        file_node = next(n for n in nodes if n.kind == "file")
        assert file_node.dir_id is None

    def test_nested_dirs_all_created(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note(
            "A/B/note.md", str(tmp_path / "A" / "B" / "note.md"), 0.0, dirty=0
        )
        nodes, _ = ConnectionResolver.resolve(vi)
        dir_ids = {n.id for n in nodes if n.kind == "dir"}
        assert "A" in dir_ids
        assert "A/B" in dir_ids

    def test_fingerprint_string_included_in_node(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        fp = "concepts:[ml,backprop] | domain:[ai] | hash:ab3f"
        vi.upsert_note("n.md", str(tmp_path / "n.md"), 0.0, fingerprint_text=fp, dirty=0)
        nodes, _ = ConnectionResolver.resolve(vi)
        file_node = next(n for n in nodes if n.kind == "file")
        assert file_node.fingerprint == fp


# ---------------------------------------------------------------------------
# Wikilink edges
# ---------------------------------------------------------------------------

class TestWikilinkEdges:
    def test_wikilink_edge_detected(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, dirty=0)
        vi.upsert_edge("a.md", "b.md", 1.0, "wikilink", "wikilink")

        _, edges = ConnectionResolver.resolve(vi)

        wiki = [e for e in edges if e.edge_type == "wikilink"]
        assert len(wiki) == 1
        assert wiki[0].strength == 1.0

    def test_wikilink_pairs_are_preserved(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, dirty=0)
        vi.upsert_note("c.md", str(tmp_path / "c.md"), 0.0, dirty=0)
        vi.upsert_edge("a.md", "b.md", 1.0, "wikilink", "wikilink")
        vi.upsert_edge("b.md", "c.md", 1.0, "wikilink", "wikilink")

        _, edges = ConnectionResolver.resolve(vi)
        wiki = [e for e in edges if e.edge_type == "wikilink"]
        assert len(wiki) == 2

    def test_non_wikilink_db_edges_excluded(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, dirty=0)
        # Store a concept edge directly in DB (simulating old data)
        vi.upsert_edge("a.md", "b.md", 0.5, "concept overlap", "concept")

        _, edges = ConnectionResolver.resolve(vi)
        wiki = [e for e in edges if e.edge_type == "wikilink"]
        assert len(wiki) == 0


# ---------------------------------------------------------------------------
# Concept overlap edges
# ---------------------------------------------------------------------------

class TestConceptEdges:
    def test_shared_concept_produces_edge(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        fp_a = "concepts:[ml,backprop,loss] | domain:[ai] | hash:aaaa"
        fp_b = "concepts:[ml,stats,prob] | domain:[math] | hash:bbbb"
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, fingerprint_text=fp_a, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, fingerprint_text=fp_b, dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        concept_edges = [e for e in edges if e.edge_type == "concept"]
        assert len(concept_edges) == 1
        assert concept_edges[0].strength == pytest.approx(1 / 3)  # 1 shared / max(3, 3)

    def test_strength_formula_shared_over_max(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        # a: 4 concepts, b: 4 concepts, 2 shared → 2/4 = 0.5
        fp_a = "concepts:[ml,backprop,cnn,rnn] | domain:[ai] | hash:aaaa"
        fp_b = "concepts:[ml,backprop,stats,prob] | domain:[math] | hash:bbbb"
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, fingerprint_text=fp_a, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, fingerprint_text=fp_b, dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        concept_edges = [e for e in edges if e.edge_type == "concept"]
        assert len(concept_edges) == 1
        assert concept_edges[0].strength == pytest.approx(0.5)

    def test_strength_uses_max_of_both_lengths(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        # a: 2 concepts, b: 6 concepts, 1 shared → 1/6 ≈ 0.167
        fp_a = "concepts:[ml,ai] | domain:[tech] | hash:aaaa"
        fp_b = "concepts:[ml,stats,prob,calc,lin,alg] | domain:[math] | hash:bbbb"
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, fingerprint_text=fp_a, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, fingerprint_text=fp_b, dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        concept_edges = [e for e in edges if e.edge_type == "concept"]
        assert len(concept_edges) == 1
        assert concept_edges[0].strength == pytest.approx(1 / 6, rel=1e-4)

    def test_no_shared_concepts_no_edge(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        fp_a = "concepts:[chemistry,bonds] | domain:[science] | hash:aaaa"
        fp_b = "concepts:[history,war] | domain:[humanities] | hash:bbbb"
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, fingerprint_text=fp_a, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, fingerprint_text=fp_b, dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        assert edges == []

    def test_notes_without_fingerprints_no_concept_edges(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        assert edges == []


# ---------------------------------------------------------------------------
# Vector similarity edges
# ---------------------------------------------------------------------------

class TestVectorEdges:
    def test_identical_vectors_produce_edge(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vec = _unit_vec(384, 0)
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, vector_blob=vec.tobytes(), dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, vector_blob=vec.tobytes(), dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        vector_edges = [e for e in edges if e.edge_type == "vector"]
        assert len(vector_edges) == 1
        assert vector_edges[0].strength == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_vectors_no_edge(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        va = _unit_vec(384, 0)
        vb = _unit_vec(384, 1)   # cos(va, vb) = 0.0 < 0.8
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, vector_blob=va.tobytes(), dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, vector_blob=vb.tobytes(), dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        vector_edges = [e for e in edges if e.edge_type == "vector"]
        assert len(vector_edges) == 0

    def test_high_similarity_above_threshold(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        base = _unit_vec(384, 0)
        similar = _similar_vec(base, noise=0.01)   # very close → cosine > 0.99
        assert _cosine(base, similar) >= 0.8

        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, vector_blob=base.tobytes(), dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, vector_blob=similar.tobytes(), dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        vector_edges = [e for e in edges if e.edge_type == "vector"]
        assert len(vector_edges) == 1

    def test_similarity_below_threshold_no_edge(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        va = _unit_vec(384, 0)
        # Build a vector with cosine ~0.5 (45 degrees away)
        vb = np.zeros(384, dtype=np.float32)
        vb[0] = 1.0 / np.sqrt(2)
        vb[1] = 1.0 / np.sqrt(2)
        assert _cosine(va, vb) == pytest.approx(1.0 / np.sqrt(2), abs=1e-5)  # ~0.707 < 0.8
        assert _cosine(va, vb) < 0.8

        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, vector_blob=va.tobytes(), dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, vector_blob=vb.tobytes(), dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        vector_edges = [e for e in edges if e.edge_type == "vector"]
        assert len(vector_edges) == 0

    def test_vector_edge_strength_is_cosine_value(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        va = _unit_vec(384, 0)
        similar = _similar_vec(va, noise=0.01)
        expected_cosine = _cosine(va, similar)

        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, vector_blob=va.tobytes(), dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, vector_blob=similar.tobytes(), dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        vector_edges = [e for e in edges if e.edge_type == "vector"]
        assert len(vector_edges) == 1
        assert vector_edges[0].strength == pytest.approx(expected_cosine, abs=1e-4)


# ---------------------------------------------------------------------------
# Multi-type deduplication (wikilink > concept > vector)
# ---------------------------------------------------------------------------

class TestEdgeDeduplication:
    def test_wikilink_wins_over_concept(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        fp_a = "concepts:[ml,backprop] | domain:[ai] | hash:aaaa"
        fp_b = "concepts:[ml,stats] | domain:[math] | hash:bbbb"
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, fingerprint_text=fp_a, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, fingerprint_text=fp_b, dirty=0)
        # Both share "ml" (concept) and have a wikilink (stored in DB)
        vi.upsert_edge("a.md", "b.md", 1.0, "wikilink", "wikilink")

        _, edges = ConnectionResolver.resolve(vi)
        # All edges for the a↔b pair
        pair_edges = [e for e in edges
                      if {e.source, e.target} == {"a.md", "b.md"}]
        assert len(pair_edges) == 1
        assert pair_edges[0].edge_type == "wikilink"

    def test_concept_wins_over_vector(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vec = _unit_vec(384, 0)
        fp_a = "concepts:[ml,backprop] | domain:[ai] | hash:aaaa"
        fp_b = "concepts:[ml,stats] | domain:[math] | hash:bbbb"
        vi.upsert_note(
            "a.md", str(tmp_path / "a.md"), 0.0,
            fingerprint_text=fp_a, vector_blob=vec.tobytes(), dirty=0,
        )
        vi.upsert_note(
            "b.md", str(tmp_path / "b.md"), 0.0,
            fingerprint_text=fp_b, vector_blob=vec.tobytes(), dirty=0,
        )
        # Both share "ml" (concept) and have identical vectors (cosine=1.0)

        _, edges = ConnectionResolver.resolve(vi)
        pair_edges = [e for e in edges
                      if {e.source, e.target} == {"a.md", "b.md"}]
        assert len(pair_edges) == 1
        assert pair_edges[0].edge_type == "concept"

    def test_wikilink_wins_over_both_concept_and_vector(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        vec = _unit_vec(384, 0)
        fp_a = "concepts:[ml,backprop] | domain:[ai] | hash:aaaa"
        fp_b = "concepts:[ml,stats] | domain:[math] | hash:bbbb"
        vi.upsert_note(
            "a.md", str(tmp_path / "a.md"), 0.0,
            fingerprint_text=fp_a, vector_blob=vec.tobytes(), dirty=0,
        )
        vi.upsert_note(
            "b.md", str(tmp_path / "b.md"), 0.0,
            fingerprint_text=fp_b, vector_blob=vec.tobytes(), dirty=0,
        )
        vi.upsert_edge("a.md", "b.md", 1.0, "wikilink", "wikilink")

        _, edges = ConnectionResolver.resolve(vi)
        pair_edges = [e for e in edges
                      if {e.source, e.target} == {"a.md", "b.md"}]
        assert len(pair_edges) == 1
        assert pair_edges[0].edge_type == "wikilink"

    def test_each_unrelated_pair_gets_own_edge(self, tmp_path: Path):
        vi = _make_vi(tmp_path)
        fp_a = "concepts:[ml] | domain:[ai] | hash:aaaa"
        fp_b = "concepts:[ml] | domain:[ai] | hash:bbbb"
        fp_c = "concepts:[ml] | domain:[ai] | hash:cccc"
        vi.upsert_note("a.md", str(tmp_path / "a.md"), 0.0, fingerprint_text=fp_a, dirty=0)
        vi.upsert_note("b.md", str(tmp_path / "b.md"), 0.0, fingerprint_text=fp_b, dirty=0)
        vi.upsert_note("c.md", str(tmp_path / "c.md"), 0.0, fingerprint_text=fp_c, dirty=0)

        _, edges = ConnectionResolver.resolve(vi)
        # 3 notes all sharing "ml" → 3 pairs, 3 concept edges
        assert len(edges) == 3
        assert all(e.edge_type == "concept" for e in edges)

    def test_vector_edge_skipped_when_concept_exists(self, tmp_path: Path):
        """Vector edge not added when concept edge already exists for same pair."""
        vi = _make_vi(tmp_path)
        vec = _unit_vec(384, 0)
        fp_a = "concepts:[ml,backprop] | domain:[ai] | hash:aaaa"
        fp_b = "concepts:[ml,stats] | domain:[math] | hash:bbbb"
        vi.upsert_note(
            "a.md", str(tmp_path / "a.md"), 0.0,
            fingerprint_text=fp_a, vector_blob=vec.tobytes(), dirty=0,
        )
        vi.upsert_note(
            "b.md", str(tmp_path / "b.md"), 0.0,
            fingerprint_text=fp_b, vector_blob=vec.tobytes(), dirty=0,
        )

        _, edges = ConnectionResolver.resolve(vi)
        # Only 1 edge — concept wins, vector is skipped
        assert len(edges) == 1
        assert edges[0].edge_type == "concept"

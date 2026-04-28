"""Unit tests for Fingerprint dataclass and FingerprintEngine (Phase 22)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from echos.core.fingerprint import (
    Fingerprint,
    FingerprintEngine,
    _collect_unique_concepts,
    _sha256_short,
)


# ---------------------------------------------------------------------------
# Fingerprint.to_string / from_string
# ---------------------------------------------------------------------------

class TestFingerprintRoundtrip:
    def test_roundtrip_short_concepts(self):
        fp = Fingerprint(
            concepts=["ml", "backprop", "loss"],
            domains=["ai", "ml"],
            content_hash="ab3f",
        )
        s = fp.to_string()
        fp2 = Fingerprint.from_string(s)
        assert fp2.concepts == fp.concepts
        assert fp2.domains == fp.domains
        assert fp2.content_hash == fp.content_hash

    def test_roundtrip_multi_word_concepts(self):
        fp = Fingerprint(
            concepts=["neural net", "gradient descent", "batch norm"],
            domains=["deep learning"],
            content_hash="cafe",
        )
        s = fp.to_string()
        fp2 = Fingerprint.from_string(s)
        assert fp2.concepts == fp.concepts
        assert fp2.domains == fp.domains

    def test_compact_string_at_most_100_chars(self):
        # Worst case: 8 long concepts
        fp = Fingerprint(
            concepts=["very long concept alpha", "very long concept beta",
                      "very long concept gamma", "very long concept delta",
                      "very long concept epsilon", "very long concept zeta",
                      "very long concept eta", "very long concept theta"],
            domains=["domain one", "domain two"],
            content_hash="ab3f",
        )
        s = fp.to_string()
        assert len(s) <= 100

    def test_compact_string_short_fits_exactly(self):
        fp = Fingerprint(concepts=["a", "b"], domains=["x"], content_hash="0000")
        s = fp.to_string()
        assert len(s) <= 100
        assert "concepts:[a,b]" in s
        assert "domain:[x]" in s
        assert "hash:0000" in s

    def test_from_string_empty_fields(self):
        fp = Fingerprint.from_string("concepts:[] | domain:[] | hash:0000")
        assert fp.concepts == []
        assert fp.domains == []
        assert fp.content_hash == "0000"

    def test_from_string_partial_truncation(self):
        # Even a partially truncated string should not crash
        fp = Fingerprint.from_string("concepts:[a,b] | domain:[x")
        assert "a" in fp.concepts
        # Domains may be empty if closing bracket is missing
        assert isinstance(fp.domains, list)

    def test_sha256_short_is_4_hex_chars(self):
        h = _sha256_short("hello")
        assert len(h) == 4
        assert all(c in "0123456789abcdef" for c in h)

    def test_content_hash_derived_from_body(self):
        fp = Fingerprint(concepts=[], domains=[], content_hash=_sha256_short("my note"))
        s = fp.to_string()
        fp2 = Fingerprint.from_string(s)
        assert fp2.content_hash == fp.content_hash


# ---------------------------------------------------------------------------
# _collect_unique_concepts
# ---------------------------------------------------------------------------

class TestCollectUniqueConcepts:
    def test_empty_list(self):
        assert _collect_unique_concepts([]) == set()

    def test_collects_across_fingerprints(self):
        fps = [
            Fingerprint(["a", "b"], ["x"], "aaaa").to_string(),
            Fingerprint(["b", "c"], ["y"], "bbbb").to_string(),
        ]
        concepts = _collect_unique_concepts(fps)
        assert concepts == {"a", "b", "c"}

    def test_lowercases_concepts(self):
        fp_str = Fingerprint(["Machine Learning", "AI"], ["Tech"], "cccc").to_string()
        concepts = _collect_unique_concepts([fp_str])
        assert "machine learning" in concepts
        assert "ai" in concepts


# ---------------------------------------------------------------------------
# FingerprintEngine.generate — pre-filter behaviour
# ---------------------------------------------------------------------------

class TestFingerprintEnginePreFilter:
    def _make_fps(self, n: int) -> list[str]:
        return [Fingerprint([f"c{i}"], ["d"], "aaaa").to_string() for i in range(n)]

    def test_prefilter_skipped_for_30_notes(self):
        engine = FingerprintEngine()
        mock_emb = MagicMock()
        engine._embedding_engine = mock_emb

        fps = self._make_fps(30)

        with patch.object(engine, "_call_llm", return_value={"concepts": ["t"], "domains": ["d"]}):
            engine.generate("body", fps, "key", "model")

        mock_emb.top_k_similar.assert_not_called()

    def test_prefilter_skipped_for_fewer_than_30_notes(self):
        engine = FingerprintEngine()
        mock_emb = MagicMock()
        engine._embedding_engine = mock_emb

        fps = self._make_fps(15)

        with patch.object(engine, "_call_llm", return_value={"concepts": ["t"], "domains": ["d"]}):
            engine.generate("body", fps, "key", "model")

        mock_emb.top_k_similar.assert_not_called()

    def test_prefilter_called_for_31_notes_with_vault_index(self):
        engine = FingerprintEngine()
        mock_emb = MagicMock()
        mock_vi = MagicMock()
        mock_emb._vault_index = mock_vi
        mock_emb.top_k_similar.return_value = []
        mock_vi.get_all_nodes.return_value = []
        engine._embedding_engine = mock_emb

        fps = self._make_fps(31)

        with patch.object(engine, "_call_llm", return_value={"concepts": ["t"], "domains": ["d"]}):
            engine.generate("body", fps, "key", "model")

        mock_emb.top_k_similar.assert_called_once()

    def test_no_embedding_engine_passes_all(self):
        engine = FingerprintEngine(embedding_engine=None)
        fps = self._make_fps(50)

        captured_fps: list[list[str]] = []

        def _fake_call_llm(body, fp_list, api_key, model_id):
            captured_fps.append(fp_list)
            return {"concepts": ["t"], "domains": ["d"]}

        with patch.object(engine, "_call_llm", side_effect=_fake_call_llm):
            engine.generate("body", fps, "key", "model")

        assert captured_fps[0] == fps


# ---------------------------------------------------------------------------
# FingerprintEngine.generate — vocabulary guard
# ---------------------------------------------------------------------------

class TestFingerprintEngineVocabularyGuard:
    def _make_200_concept_fps(self) -> list[str]:
        fps: list[str] = []
        for i in range(40):
            # 5 unique concepts each × 40 = 200 unique concepts total
            fp = Fingerprint(
                concepts=[f"concept{i * 5 + j}" for j in range(5)],
                domains=["domain"],
                content_hash="aaaa",
            )
            fps.append(fp.to_string())
        return fps

    def test_consolidation_triggered_at_201_concepts(self):
        engine = FingerprintEngine()
        fps = self._make_200_concept_fps()  # 200 unique concepts

        with patch.object(
            engine,
            "_call_llm",
            return_value={"concepts": ["brand_new_concept_201"], "domains": ["domain"]},
        ), patch.object(
            engine,
            "_consolidate_concepts",
            return_value=["merged1", "merged2"],
        ) as mock_consolidate:
            result = engine.generate("note body", fps, "key", "model")
            mock_consolidate.assert_called_once()
            # Consolidated concepts should be in result
            assert result.concepts == ["merged1", "merged2"]

    def test_consolidation_not_triggered_below_201_concepts(self):
        engine = FingerprintEngine()
        # Only 5 existing concepts + 1 new = 6 total — well below 200
        fps = [Fingerprint(["a", "b", "c", "d", "e"], ["domain"], "aaaa").to_string()]

        with patch.object(
            engine,
            "_call_llm",
            return_value={"concepts": ["f"], "domains": ["domain"]},
        ), patch.object(
            engine, "_consolidate_concepts"
        ) as mock_consolidate:
            engine.generate("note body", fps, "key", "model")
            mock_consolidate.assert_not_called()

    def test_generate_returns_fingerprint_dataclass(self):
        engine = FingerprintEngine()

        with patch.object(
            engine,
            "_call_llm",
            return_value={"concepts": ["foo", "bar"], "domains": ["science"]},
        ):
            result = engine.generate("some note text", [], "key", "model")

        assert isinstance(result, Fingerprint)
        assert result.concepts == ["foo", "bar"]
        assert result.domains == ["science"]
        assert len(result.content_hash) == 4

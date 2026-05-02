"""EmbeddingEngine — local sentence-transformers wrapper + cosine top-k."""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_DIM = 384


class EmbeddingEngine:
    """Wraps all-MiniLM-L6-v2 for note embeddings and nearest-neighbour lookup."""

    def __init__(self, vault_index=None) -> None:
        self._vault_index = vault_index
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(_MODEL_NAME)
        except Exception as exc:
            logger.warning("EmbeddingEngine: model load failed: %s", exc)

    def embed(self, text: str) -> np.ndarray:
        """Return a 384-dim float32 embedding for *text*."""
        self._ensure_model()
        if self._model is None:
            return np.zeros(_DIM, dtype=np.float32)
        vec = self._model.encode(text, convert_to_numpy=True)
        return np.asarray(vec, dtype=np.float32)

    def top_k_similar(self, text: str, k: int = 20) -> list[str]:
        """Return note IDs of the *k* most similar notes to *text*."""
        if self._vault_index is None:
            return []

        query = self.embed(text)
        nodes = self._vault_index.get_all_nodes()
        candidates: list[tuple[str, np.ndarray]] = []
        for node in nodes:
            blob = node.get("vector_blob")
            if not blob:
                continue
            vec = np.frombuffer(blob, dtype=np.float32)
            if vec.shape == query.shape:
                candidates.append((node["id"], vec))

        if not candidates:
            return []

        from sklearn.metrics.pairwise import cosine_similarity
        vecs = np.stack([c[1] for c in candidates])
        scores = cosine_similarity(query.reshape(1, -1), vecs)[0]
        order = np.argsort(scores)[::-1][:k]
        return [candidates[i][0] for i in order]

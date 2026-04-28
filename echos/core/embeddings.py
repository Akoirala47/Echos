"""EmbeddingEngine — thin wrapper around sentence-transformers/all-MiniLM-L6-v2.

Provides:
  embed(text)               → 384-dim float32 vector (lazy model load)
  top_k_similar(text, k)    → top-k note IDs by cosine similarity (uses VaultIndex)

Handles ImportError gracefully: falls back to returning [] from top_k_similar
so callers can treat it as "pass all" without crashing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from echos.core.vault_index import VaultIndex

logger = logging.getLogger(__name__)

_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class EmbeddingEngine:
    """Wraps all-MiniLM-L6-v2 with lazy loading and optional VaultIndex integration."""

    MODEL_ID = _MODEL_ID

    def __init__(self, vault_index: "VaultIndex | None" = None) -> None:
        self._vault_index = vault_index
        self._model = None  # lazy-loaded on first embed() call

    # ── Public API ──────────────────────────────────────────────────────────

    def set_vault_index(self, vault_index: "VaultIndex") -> None:
        self._vault_index = vault_index

    def embed(self, text: str) -> np.ndarray | None:
        """Return a 384-dim float32 embedding, or None if sentence-transformers unavailable."""
        try:
            model = self._load_model()
            if model is None:
                return None
            vec = model.encode(text, normalize_embeddings=True)
            return np.asarray(vec, dtype=np.float32)
        except Exception as exc:
            logger.warning("EmbeddingEngine.embed failed: %s", exc)
            return None

    def top_k_similar(self, query_text: str, k: int) -> list[str]:
        """Return top-k note IDs by cosine similarity against VaultIndex stored vectors.

        Returns [] if VaultIndex is not set or sentence-transformers is unavailable.
        """
        if self._vault_index is None:
            return []

        query_vec = self.embed(query_text)
        if query_vec is None:
            return []

        try:
            nodes = self._vault_index.get_all_nodes()
        except Exception as exc:
            logger.warning("EmbeddingEngine: could not read VaultIndex: %s", exc)
            return []

        scored: list[tuple[float, str]] = []
        for row in nodes:
            blob = row.get("vector_blob")
            if not blob:
                continue
            try:
                vec = np.frombuffer(blob, dtype=np.float32)
                scored.append((_cosine(query_vec, vec), row["id"]))
            except Exception:
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        return [nid for _, nid in scored[:k]]

    def is_available(self) -> bool:
        """Return True if sentence-transformers can be imported."""
        return self._load_model() is not None

    # ── Internal ─────────────────────────────────────────────────────────────

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.MODEL_ID)
            logger.info("EmbeddingEngine: loaded %s", self.MODEL_ID)
            return self._model
        except ImportError:
            logger.warning(
                "sentence-transformers not installed; embedding pre-filter disabled. "
                "Install with: pip install sentence-transformers"
            )
            return None
        except Exception as exc:
            logger.warning("EmbeddingEngine: model load failed: %s", exc)
            return None

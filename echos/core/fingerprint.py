"""FingerprintEngine — generates compact concept fingerprints for vault notes.

Each Fingerprint encodes 5–8 key concepts, 2–3 domain clusters, and a 4-char
SHA-256 hash of the note body, all in a single ≤100-char string for fast
diffing and concept-reuse across notes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_MAX_UNIQUE_CONCEPTS = 200


# ---------------------------------------------------------------------------
# Fingerprint dataclass
# ---------------------------------------------------------------------------

@dataclass
class Fingerprint:
    concepts: list[str]
    domains: list[str]
    content_hash: str  # first 4 hex chars of SHA-256 of note body

    def to_string(self) -> str:
        """Encode as 'concepts:[a,b,c] | domain:[x,y] | hash:ab3f' (≤100 chars)."""
        h = self.content_hash[:4]
        domains_str = ",".join(self.domains)
        # Try progressively fewer concepts until it fits in 100 chars
        for n in range(len(self.concepts), 0, -1):
            concepts_str = ",".join(self.concepts[:n])
            s = f"concepts:[{concepts_str}] | domain:[{domains_str}] | hash:{h}"
            if len(s) <= 100:
                return s
        # Absolute fallback — truncate hard
        return f"concepts:[] | domain:[{domains_str}] | hash:{h}"[:100]

    @classmethod
    def from_string(cls, s: str) -> "Fingerprint":
        """Parse a compact fingerprint string back into a Fingerprint."""
        concepts_m = re.search(r'concepts:\[([^\]]*)\]', s)
        domain_m = re.search(r'domain:\[([^\]]*)\]', s)
        hash_m = re.search(r'hash:([0-9a-f]{4})', s)

        concepts = (
            [c.strip() for c in concepts_m.group(1).split(",") if c.strip()]
            if concepts_m else []
        )
        domains = (
            [d.strip() for d in domain_m.group(1).split(",") if d.strip()]
            if domain_m else []
        )
        content_hash = hash_m.group(1) if hash_m else ""
        return cls(concepts=concepts, domains=domains, content_hash=content_hash)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:4]


def _collect_unique_concepts(fingerprint_strings: list[str]) -> set[str]:
    """Collect all unique concept terms across a list of fingerprint strings."""
    concepts: set[str] = set()
    for fp_str in fingerprint_strings:
        fp = Fingerprint.from_string(fp_str)
        concepts.update(c.lower() for c in fp.concepts if c)
    return concepts


_SYSTEM_PROMPT = (
    "You are a concept fingerprinting assistant. "
    "Given a note and existing concept vocabulary, extract a fingerprint.\n\n"
    "Return ONLY a JSON object — no preamble, no explanation:\n"
    '{"concepts": ["term1", ...], "domains": ["broad1", ...]}\n\n'
    "Rules:\n"
    "- concepts: 5–8 short terms (≤3 words), lowercase, key ideas\n"
    "- domains: 2–3 broad subject clusters (e.g. 'machine learning', 'biology')\n"
    "- PREFER reusing existing concept terms before coining new ones"
)

_CONSOLIDATION_PROMPT = """\
Some of these concept terms are near-synonyms. Merge them into a reduced set.

Existing concepts:
{concepts}

Return ONLY a JSON array (no preamble):
["merged1", "merged2", ...]
"""


# ---------------------------------------------------------------------------
# FingerprintEngine
# ---------------------------------------------------------------------------

class FingerprintEngine:
    """Generates concept fingerprints via LLM with optional embedding pre-filter."""

    def __init__(self, embedding_engine=None) -> None:
        # EmbeddingEngine reference (optional); used for pre-filter on large vaults
        self._embedding_engine = embedding_engine

    def generate(
        self,
        note_body: str,
        existing_fingerprints: list[str],
        api_key: str,
        model_id: str,
    ) -> Fingerprint:
        """Generate a Fingerprint for note_body.

        existing_fingerprints — list of to_string() outputs from already-indexed notes.
        """
        content_hash = _sha256_short(note_body)

        # ── Pre-filter ──────────────────────────────────────────────────────
        # Skip if ≤30 notes (cheap) or no embedding engine configured
        if len(existing_fingerprints) <= 30 or self._embedding_engine is None:
            fingerprints_for_llm = existing_fingerprints
        else:
            vault_index = getattr(self._embedding_engine, "_vault_index", None)
            if vault_index is not None:
                top_k_ids = self._embedding_engine.top_k_similar(note_body, k=20)
                if top_k_ids:
                    fp_map = {
                        row["id"]: row.get("fingerprint_text", "")
                        for row in vault_index.get_all_nodes()
                    }
                    fingerprints_for_llm = [
                        fp_map[nid]
                        for nid in top_k_ids
                        if nid in fp_map and fp_map[nid]
                    ]
                else:
                    fingerprints_for_llm = existing_fingerprints
            else:
                fingerprints_for_llm = existing_fingerprints

        # ── Vocabulary guard (count before LLM call) ────────────────────────
        existing_concepts = _collect_unique_concepts(existing_fingerprints)

        # ── LLM call ────────────────────────────────────────────────────────
        raw = self._call_llm(note_body, fingerprints_for_llm, api_key, model_id)

        new_concepts = [c.lower() for c in raw.get("concepts", []) if c]
        new_unique = existing_concepts | set(new_concepts)

        if len(new_unique) > _MAX_UNIQUE_CONCEPTS:
            # Second LLM pass to consolidate near-synonyms
            consolidated = self._consolidate_concepts(
                list(new_unique), api_key, model_id
            )
            raw["concepts"] = consolidated

        return Fingerprint(
            concepts=[c.lower() for c in raw.get("concepts", [])[:8] if c],
            domains=[d.lower() for d in raw.get("domains", [])[:3] if d],
            content_hash=content_hash,
        )

    # ── LLM helpers ─────────────────────────────────────────────────────────

    def _call_llm(
        self,
        note_body: str,
        existing_fingerprints: list[str],
        api_key: str,
        model_id: str,
    ) -> dict:
        try:
            import google.generativeai as genai
        except ImportError:
            logger.warning("google-generativeai not installed; skipping fingerprint LLM call")
            return {"concepts": [], "domains": []}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id, system_instruction=_SYSTEM_PROMPT)

        existing_str = (
            "\n".join(existing_fingerprints[:50]) if existing_fingerprints else "(none)"
        )
        prompt = (
            f"Existing concept vocabulary:\n{existing_str}\n\n"
            f"Note body:\n{note_body[:3000]}"
        )
        try:
            response = model.generate_content(prompt)
            text = re.sub(
                r"^```(?:json)?\s*|\s*```$", "", response.text.strip(), flags=re.MULTILINE
            ).strip()
            return json.loads(text)
        except Exception as exc:
            logger.warning("FingerprintEngine LLM call failed: %s", exc)
            return {"concepts": [], "domains": []}

    def _consolidate_concepts(
        self, concepts: list[str], api_key: str, model_id: str
    ) -> list[str]:
        try:
            import google.generativeai as genai
        except ImportError:
            return concepts[:_MAX_UNIQUE_CONCEPTS]

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)
        prompt = _CONSOLIDATION_PROMPT.format(concepts=json.dumps(concepts))
        try:
            response = model.generate_content(prompt)
            text = re.sub(
                r"^```(?:json)?\s*|\s*```$", "", response.text.strip(), flags=re.MULTILINE
            ).strip()
            result = json.loads(text)
            if isinstance(result, list):
                return [str(c) for c in result]
        except Exception as exc:
            logger.warning("FingerprintEngine consolidation failed: %s", exc)
        return concepts[:_MAX_UNIQUE_CONCEPTS]

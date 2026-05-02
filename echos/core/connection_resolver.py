"""ConnectionResolver — builds graph NodeData/EdgeData from VaultIndex."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from echos.core.fingerprint import Fingerprint
from echos.utils.theme import CANVAS_NODE_DEFAULT, DOMAIN_PALETTE

_VECTOR_THRESHOLD = 0.8


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _domain_color(domain: str | None) -> str:
    if domain is None:
        return CANVAS_NODE_DEFAULT
    idx = sum(ord(c) for c in domain) % len(DOMAIN_PALETTE)
    return DOMAIN_PALETTE[idx]


@dataclass
class NodeData:
    id: str
    kind: str          # "file" | "dir"
    label: str
    color: str
    domain: str | None = None
    dir_id: str | None = None
    fingerprint: str | None = None
    path: str | None = None


@dataclass
class EdgeData:
    source: str
    target: str
    edge_type: str
    strength: float


class ConnectionResolver:
    """Derives graph nodes and edges from a VaultIndex snapshot."""

    @staticmethod
    def resolve(vault_index) -> tuple[list[NodeData], list[EdgeData]]:
        raw_notes = vault_index.get_all_nodes()
        if not raw_notes:
            return [], []

        # ── Build file nodes ──────────────────────────────────────────────────
        file_nodes: dict[str, NodeData] = {}
        dir_nodes: dict[str, NodeData] = {}

        for row in raw_notes:
            note_id: str = row["id"]
            fp_text: str | None = row.get("fingerprint_text")

            fp = Fingerprint.from_string(fp_text) if fp_text else None
            domain = fp.domains[0] if (fp and fp.domains) else None
            color = _domain_color(domain)

            # Derive dir_id from note_id path
            parts = note_id.replace("\\", "/").split("/")
            stem = Path(parts[-1]).stem
            dir_id = "/".join(parts[:-1]) if len(parts) > 1 else None

            file_nodes[note_id] = NodeData(
                id=note_id,
                kind="file",
                label=stem,
                color=color,
                domain=domain,
                dir_id=dir_id,
                fingerprint=fp_text,
                path=row.get("path"),
            )

            # Create all ancestor dir nodes
            for depth in range(len(parts) - 1):
                did = "/".join(parts[: depth + 1])
                if did not in dir_nodes:
                    dir_nodes[did] = NodeData(
                        id=did,
                        kind="dir",
                        label=parts[depth],
                        color=CANVAS_NODE_DEFAULT,
                    )

        nodes: list[NodeData] = list(dir_nodes.values()) + list(file_nodes.values())

        # ── Build edges ───────────────────────────────────────────────────────
        db_edges = vault_index.get_all_edges()
        edges: list[EdgeData] = []
        covered: set[frozenset] = set()  # frozenset of {source_id, target_id}

        # Priority 1: wikilink edges from DB
        for e in db_edges:
            if e["edge_type"] != "wikilink":
                continue
            s, t = e["source_id"], e["target_id"]
            pair = frozenset({s, t})
            if pair not in covered:
                covered.add(pair)
                edges.append(EdgeData(source=s, target=t, edge_type="wikilink", strength=e["strength"]))

        # Priority 2: concept edges (derived from fingerprint overlap)
        note_ids = list(file_nodes.keys())
        for i in range(len(note_ids)):
            for j in range(i + 1, len(note_ids)):
                a_id, b_id = note_ids[i], note_ids[j]
                pair = frozenset({a_id, b_id})
                if pair in covered:
                    continue
                fp_a_text = file_nodes[a_id].fingerprint
                fp_b_text = file_nodes[b_id].fingerprint
                if not fp_a_text or not fp_b_text:
                    continue
                fp_a = Fingerprint.from_string(fp_a_text)
                fp_b = Fingerprint.from_string(fp_b_text)
                shared = set(fp_a.concepts) & set(fp_b.concepts)
                if not shared:
                    continue
                denom = max(len(fp_a.concepts), len(fp_b.concepts), 1)
                strength = len(shared) / denom
                covered.add(pair)
                edges.append(EdgeData(source=a_id, target=b_id, edge_type="concept", strength=strength))

        # Priority 3: vector similarity edges
        vecs: dict[str, np.ndarray] = {}
        for row in raw_notes:
            blob = row.get("vector_blob")
            if blob:
                vecs[row["id"]] = np.frombuffer(blob, dtype=np.float32)

        vec_ids = list(vecs.keys())
        for i in range(len(vec_ids)):
            for j in range(i + 1, len(vec_ids)):
                a_id, b_id = vec_ids[i], vec_ids[j]
                pair = frozenset({a_id, b_id})
                if pair in covered:
                    continue
                sim = _cosine(vecs[a_id], vecs[b_id])
                if sim >= _VECTOR_THRESHOLD:
                    covered.add(pair)
                    edges.append(EdgeData(source=a_id, target=b_id, edge_type="vector", strength=sim))

        return nodes, edges

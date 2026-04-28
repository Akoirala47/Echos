"""ConnectionResolver — computes display-ready graph nodes and edges from VaultIndex.

Reads the SQLite index and produces:
  - NodeData for every indexed note + a virtual dir-node for every parent directory
  - EdgeData from three sources, deduplicated by priority (wikilink > concept > vector)

Edge-type rules
  wikilink — stored in DB by IndexWorker (edge_type='wikilink')
  concept  — two notes share ≥1 concept label in their fingerprints
  vector   — cosine similarity of stored 384-dim vectors ≥ 0.8,
              only when no wikilink or concept edge already exists for that pair

Strength
  wikilink : 1.0
  concept  : shared_concept_count / max(total_concepts_a, total_concepts_b)
  vector   : cosine similarity value (0.8–1.0)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from echos.core.fingerprint import Fingerprint
from echos.core.vault_index import VaultIndex
from echos.utils.theme import DOMAIN_PALETTE

logger = logging.getLogger(__name__)

_NODE_DEFAULT_COLOR = "#b0ae9e"   # CANVAS_NODE_DEFAULT


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class NodeData:
    id: str
    path: str
    label: str
    domain: str
    color: str
    dir_id: str | None = None
    kind: str = "file"       # "file" | "dir"
    fingerprint: str = ""    # compact fingerprint string — shown in tooltip


@dataclass
class EdgeData:
    source: str
    target: str
    strength: float
    edge_type: str           # "concept" | "vector" | "wikilink"
    reason: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _domain_color(domain: str) -> str:
    """Map a domain name to a consistent DOMAIN_PALETTE colour."""
    if not domain:
        return _NODE_DEFAULT_COLOR
    return DOMAIN_PALETTE[abs(hash(domain)) % len(DOMAIN_PALETTE)]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _concept_set(fp_text: str) -> set[str]:
    if not fp_text:
        return set()
    fp = Fingerprint.from_string(fp_text)
    return {c.lower() for c in fp.concepts if c}


def _primary_domain(fp_text: str) -> str:
    if not fp_text:
        return ""
    fp = Fingerprint.from_string(fp_text)
    return fp.domains[0].lower() if fp.domains else ""


def _build_dir_nodes(dir_ids: set[str], vault_root: Path) -> list[NodeData]:
    """Build virtual dir NodeData for every unique parent-directory path."""
    all_dirs: set[str] = set()
    for rel in dir_ids:
        parts = Path(rel).parts
        for depth in range(1, len(parts) + 1):
            all_dirs.add(str(Path(*parts[:depth])))

    dir_nodes: list[NodeData] = []
    for rel_dir in sorted(all_dirs):
        p = Path(rel_dir)
        parent_str = str(p.parent)
        parent_id = None if parent_str == "." else parent_str
        color = DOMAIN_PALETTE[abs(hash(p.name)) % len(DOMAIN_PALETTE)]
        dir_nodes.append(NodeData(
            id=rel_dir,
            path=str(vault_root / rel_dir),
            label=p.name,
            domain="",
            color=color,
            dir_id=parent_id,
            kind="dir",
        ))
    return dir_nodes


# ── Edge computation ──────────────────────────────────────────────────────────

_PRIORITY = {"wikilink": 3, "concept": 2, "vector": 1}


def _compute_edges(
    file_node_ids: list[str],
    fp_by_id: dict[str, str],
    vec_by_id: dict[str, np.ndarray],
    db_edges: list[dict],
) -> list[EdgeData]:
    best: dict[tuple[str, str], EdgeData] = {}

    def _key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a < b else (b, a)

    def _try_add(edge: EdgeData) -> None:
        k = _key(edge.source, edge.target)
        ex = best.get(k)
        if ex is None or _PRIORITY.get(edge.edge_type, 0) > _PRIORITY.get(ex.edge_type, 0):
            best[k] = edge

    # ── 1. Wikilink edges from the DB ─────────────────────────────────────────
    for e in db_edges:
        if e.get("edge_type") == "wikilink":
            _try_add(EdgeData(
                source=e["source_id"],
                target=e["target_id"],
                strength=1.0,
                edge_type="wikilink",
                reason="wikilink",
            ))

    # ── 2. Concept-overlap edges ──────────────────────────────────────────────
    concepts: dict[str, set[str]] = {
        nid: _concept_set(fp_by_id.get(nid, ""))
        for nid in file_node_ids
    }
    n = len(file_node_ids)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = file_node_ids[i], file_node_ids[j]
            ca, cb = concepts[a], concepts[b]
            if not ca or not cb:
                continue
            shared = ca & cb
            if shared:
                strength = len(shared) / max(len(ca), len(cb))
                _try_add(EdgeData(
                    source=a,
                    target=b,
                    strength=strength,
                    edge_type="concept",
                    reason=", ".join(sorted(shared)[:3]),
                ))

    # ── 3. Vector-similarity edges (only where no higher-priority edge exists) ─
    if vec_by_id:
        vec_ids = [nid for nid in file_node_ids if nid in vec_by_id]
        m = len(vec_ids)
        for i in range(m):
            for j in range(i + 1, m):
                a, b = vec_ids[i], vec_ids[j]
                k = _key(a, b)
                ex = best.get(k)
                if ex and ex.edge_type in ("wikilink", "concept"):
                    continue  # already covered by higher-priority edge
                sim = _cosine(vec_by_id[a], vec_by_id[b])
                if sim >= 0.8:
                    _try_add(EdgeData(
                        source=a,
                        target=b,
                        strength=float(sim),
                        edge_type="vector",
                        reason=f"cosine={sim:.2f}",
                    ))

    return list(best.values())


# ── ConnectionResolver ────────────────────────────────────────────────────────

class ConnectionResolver:
    """Reads a VaultIndex and produces display-ready NodeData + EdgeData lists."""

    @staticmethod
    def resolve(vault_index: VaultIndex) -> tuple[list[NodeData], list[EdgeData]]:
        """Return (nodes, edges) derived from the indexed vault.

        Notes not yet indexed (no fingerprint / vector) are still shown as nodes
        with default colour — they just won't generate concept or vector edges.
        """
        try:
            db_nodes = vault_index.get_all_nodes()
            db_edges = vault_index.get_all_edges()
        except Exception as exc:
            logger.warning("ConnectionResolver: could not read VaultIndex: %s", exc)
            return [], []

        if not db_nodes:
            return [], []

        vault_root = vault_index.root

        # ── Build per-note lookup tables ──────────────────────────────────────
        fp_by_id: dict[str, str] = {
            row["id"]: (row.get("fingerprint_text") or "")
            for row in db_nodes
        }
        vec_by_id: dict[str, np.ndarray] = {}
        for row in db_nodes:
            blob = row.get("vector_blob")
            if blob:
                try:
                    vec = np.frombuffer(blob, dtype=np.float32)
                    if vec.size > 0:
                        vec_by_id[row["id"]] = vec
                except Exception:
                    pass

        # ── Build file NodeData ───────────────────────────────────────────────
        file_nodes: list[NodeData] = []
        dir_ids_seen: set[str] = set()

        for row in db_nodes:
            nid = row["id"]
            fp_text = fp_by_id[nid]
            domain = _primary_domain(fp_text)
            color = _domain_color(domain)

            note_path = Path(row["path"])
            try:
                parent_rel = str(note_path.parent.relative_to(vault_root))
                if parent_rel == ".":
                    parent_rel = ""
            except ValueError:
                parent_rel = ""

            file_nodes.append(NodeData(
                id=nid,
                path=row["path"],
                label=note_path.stem,
                domain=domain,
                color=color,
                dir_id=parent_rel if parent_rel else None,
                kind="file",
                fingerprint=fp_text,
            ))
            if parent_rel:
                dir_ids_seen.add(parent_rel)

        # ── Build directory NodeData ──────────────────────────────────────────
        dir_nodes = _build_dir_nodes(dir_ids_seen, vault_root)

        all_nodes = dir_nodes + file_nodes

        # ── Compute edges ─────────────────────────────────────────────────────
        file_ids = [n.id for n in file_nodes]
        edges = _compute_edges(file_ids, fp_by_id, vec_by_id, db_edges)

        return all_nodes, edges

"""Persistence: CSV <-> Edge, JSON graph emit, node synthesis, fingerprinting."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .schema import (
    Edge,
    Node,
    infer_node_kind,
    node_id_for,
    node_layer_for,
)

CSV_COLUMNS = [
    "edge_id", "chain", "hop", "layer", "kind",
    "src_module", "src_offset", "src_name", "src_insn",
    "dst_module", "dst_offset", "dst_name",
    "resolved_by", "confidence", "evidence", "source", "note",
]


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------

def load_csv(path: str | Path) -> List[Edge]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [Edge.from_dict(dict(r)) for r in csv.DictReader(fh)]


def save_csv(edges: List[Edge], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for e in edges:
            w.writerow(e.to_csv_row())


# --------------------------------------------------------------------------
# Node synthesis (deterministic; every edge endpoint gets exactly one node)
# --------------------------------------------------------------------------

def synthesize_nodes(edges: List[Edge]) -> List[Node]:
    seen: Dict[str, Node] = {}
    for e in edges:
        for side, module, name, off in (
            ("src", e.src_module, e.src_name, e.src_offset),
            ("dst", e.dst_module, e.dst_name, e.dst_offset),
        ):
            nid = node_id_for(module, name, off)
            if nid in seen:
                continue
            seen[nid] = Node(
                id=nid,
                layer=node_layer_for(module, e.layer),
                module=module,
                kind=infer_node_kind(module, name, off, e.layer, e.kind, side),
                name=name if not off or module in ("kernel", "android-runtime") and False else name,
                offset=off,
            )
    # Node.name for instruction nodes: keep the human name (may be empty).
    return [seen[k] for k in sorted(seen)]


# --------------------------------------------------------------------------
# JSON graph emit
# --------------------------------------------------------------------------

def save_json(
    edges: List[Edge],
    nodes: List[Node],
    chains: List[Dict[str, Any]],
    checks: List[Dict[str, Any]],
    dart_hot_targets: List[Dict[str, Any]],
    meta: Dict[str, Any],
    path: str | Path,
) -> None:
    doc = {
        "meta": meta,
        "chains": chains,
        "nodes": [n.to_dict() for n in nodes],
        "edges": [e.to_dict() for e in edges],
        "checks": checks,
        "dart_hot_targets": dart_hot_targets,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Bundle fingerprint (self-consistency across rebuilds)
# --------------------------------------------------------------------------

def fingerprint(bundle: str | Path) -> Tuple[str, int]:
    """sha256 (truncated to 32 hex) over sorted ``relpath + NUL + bytes``."""
    bundle = Path(bundle)
    files = sorted(p for p in bundle.rglob("*") if p.is_file())
    h = hashlib.sha256()
    for p in files:
        h.update(str(p.relative_to(bundle)).encode("utf-8"))
        h.update(b"\x00")
        h.update(p.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()[:32], len(files)

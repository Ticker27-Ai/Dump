"""In-memory call graph: indexes + queries (trace / paths / fan-in / search)."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Dict, Iterable, List, Optional, Tuple

from .schema import Edge, Node, node_id_for, norm_offset


class CallGraph:
    """Query layer over a built edge list.

    Nodes are synthesised deterministically (see ``store.synthesize_nodes``)
    so the graph can be constructed from edges alone::

        g = CallGraph(edges)
        g.trace("libengine.so", "0xf3a08", depth=2)
        g.top_targets(layer="L5", top=12)
    """

    def __init__(self, edges: List[Edge], nodes: Optional[List[Node]] = None):
        from .store import synthesize_nodes  # deferred: store imports schema only

        self.edges: List[Edge] = list(edges)
        self.nodes: Dict[str, Node] = {n.id: n for n in (nodes if nodes is not None else synthesize_nodes(edges))}
        self.by_id: Dict[str, Edge] = {e.edge_id: e for e in self.edges if e.edge_id}
        self.by_src: Dict[str, List[Edge]] = defaultdict(list)
        self.by_dst: Dict[str, List[Edge]] = defaultdict(list)
        self.by_kind: Dict[str, List[Edge]] = defaultdict(list)
        self.by_layer: Dict[str, List[Edge]] = defaultdict(list)
        self.by_chain: Dict[str, List[Edge]] = defaultdict(list)
        for e in self.edges:
            self.by_src[node_id_for(e.src_module, e.src_name, e.src_offset)].append(e)
            self.by_dst[node_id_for(e.dst_module, e.dst_name, e.dst_offset)].append(e)
            self.by_kind[e.kind].append(e)
            self.by_layer[e.layer].append(e)
            if e.chain:
                self.by_chain[e.chain].append(e)

    # -- basic lookups ----------------------------------------------------

    def find_edges(
        self,
        layer: str = "",
        kind: str = "",
        src_module: str = "",
        src_offset: str = "",
        dst_module: str = "",
        dst_offset: str = "",
        chain: str = "",
    ) -> List[Edge]:
        out = self.edges
        if layer:
            out = [e for e in out if e.layer == layer]
        if kind:
            out = [e for e in out if e.kind == kind]
        if src_module:
            out = [e for e in out if e.src_module == src_module]
        if src_offset:
            want = norm_offset(src_offset)
            out = [e for e in out if e.src_offset == want]
        if dst_module:
            out = [e for e in out if e.dst_module == dst_module]
        if dst_offset:
            want = norm_offset(dst_offset)
            out = [e for e in out if e.dst_offset == want]
        if chain:
            out = [e for e in out if e.chain == chain]
        return out

    def search(self, text: str, fields: Iterable[str] = ("src_name", "dst_name", "src_insn")) -> List[Edge]:
        needle = text.lower()
        hits = []
        for e in self.edges:
            for f in fields:
                if needle in str(getattr(e, f, "")).lower():
                    hits.append(e)
                    break
        return hits

    # -- neighbourhood / trace --------------------------------------------

    def neighbours(self, node_id: str, direction: str = "both") -> List[Tuple[Edge, str]]:
        """Edges touching ``node_id``; each paired with ``"out"``/``"in"``."""
        out: List[Tuple[Edge, str]] = []
        if direction in ("both", "out"):
            out.extend((e, "out") for e in self.by_src.get(node_id, []))
        if direction in ("both", "in"):
            out.extend((e, "in") for e in self.by_dst.get(node_id, []))
        return out

    def trace(
        self,
        module: str,
        offset: str = "",
        name: str = "",
        depth: int = 2,
        direction: str = "both",
        max_nodes: int = 400,
    ) -> Dict[str, object]:
        """BFS walk from one endpoint; returns ``{"nodes": [...], "edges": [...]}``.

        ``direction`` is ``"out"`` (callees), ``"in"`` (callers) or ``"both"``.
        """
        start = node_id_for(module, name, offset)
        seen_nodes = {start: 0}
        seen_edges: Dict[str, Edge] = {}
        queue: deque[Tuple[str, int]] = deque([(start, 0)])
        while queue and len(seen_nodes) < max_nodes:
            nid, dist = queue.popleft()
            if dist >= depth:
                continue
            for edge, rel in self.neighbours(nid, direction):
                if edge.edge_id and edge.edge_id not in seen_edges:
                    seen_edges[edge.edge_id] = edge
                nxt = (
                    node_id_for(edge.dst_module, edge.dst_name, edge.dst_offset)
                    if rel == "out"
                    else node_id_for(edge.src_module, edge.src_name, edge.src_offset)
                )
                if nxt not in seen_nodes:
                    seen_nodes[nxt] = dist + 1
                    queue.append((nxt, dist + 1))
        nodes = [self.nodes[n] for n in seen_nodes if n in self.nodes]
        nodes += [Node(id=n, module=n.split("!")[0].split("#")[0]) for n in seen_nodes if n not in self.nodes]
        return {"nodes": nodes, "edges": list(seen_edges.values())}

    def find_paths(
        self,
        src: Tuple[str, str, str],
        dst: Tuple[str, str, str],
        max_depth: int = 6,
        limit: int = 10,
    ) -> List[List[Edge]]:
        """All simple paths (BFS, capped) between two endpoints.

        Each endpoint is ``(module, name, offset)``.
        """
        start = node_id_for(*src)
        goal = node_id_for(*dst)
        paths: List[List[Edge]] = []
        queue: deque[Tuple[str, List[Edge]]] = deque([(start, [])])
        while queue and len(paths) < limit:
            nid, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for edge in self.by_src.get(nid, []):
                nxt = node_id_for(edge.dst_module, edge.dst_name, edge.dst_offset)
                if any(node_id_for(e.src_module, e.src_name, e.src_offset) == nxt for e in path):
                    continue  # simple paths only
                new_path = path + [edge]
                if nxt == goal:
                    paths.append(new_path)
                else:
                    queue.append((nxt, new_path))
        return paths

    # -- fan-in / fan-out --------------------------------------------------

    def fan_in(self, module: str, offset: str = "", name: str = "") -> int:
        return len(self.by_dst.get(node_id_for(module, name, offset), []))

    def fan_out(self, module: str, offset: str = "", name: str = "") -> int:
        return len(self.by_src.get(node_id_for(module, name, offset), []))

    def top_targets(self, layer: str = "", top: int = 25) -> List[Dict[str, object]]:
        """Hottest dst nodes by fan-in: ``(-fan_in, offset)`` deterministic."""
        counts: Counter = Counter()
        sample: Dict[str, Edge] = {}
        for e in self.edges:
            if layer and e.layer != layer:
                continue
            nid = node_id_for(e.dst_module, e.dst_name, e.dst_offset)
            counts[nid] += 1
            if nid not in sample:
                sample[nid] = e
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        out = []
        for nid, fan in ranked[:top]:
            e = sample[nid]
            out.append({
                "node": nid, "fan_in": fan,
                "module": e.dst_module, "offset": e.dst_offset, "name": e.dst_name,
            })
        return out

    # -- stats --------------------------------------------------------------

    def stats(self) -> Dict[str, object]:
        return {
            "edges": len(self.edges),
            "nodes": len(self.nodes),
            "by_layer": {k: len(v) for k, v in sorted(self.by_layer.items())},
            "by_kind": {k: len(v) for k, v in sorted(self.by_kind.items())},
            "by_confidence": dict(Counter(e.confidence or "?" for e in self.edges)),
            "chains": sorted(self.by_chain),
        }

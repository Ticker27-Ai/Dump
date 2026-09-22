#!/usr/bin/env python3
"""Query a built call-linkage graph.

Usage:
    python3 tools/query_linkage.py build/call_linkage.json stats
    python3 tools/query_linkage.py build/call_linkage.json trace --module libengine.so --offset 0xf3a08
    python3 tools/query_linkage.py build/call_linkage.json fan-in --layer L5 --top 12
    python3 tools/query_linkage.py build/call_linkage.json search pjowqpxe
    python3 tools/query_linkage.py build/call_linkage.json chain CH-04
    python3 tools/query_linkage.py build/call_linkage.json paths --from libengine.so+0xf3a08 --to classes.dex

A CSV file (baseline or rebuilt) is accepted too: it is loaded directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.call_linkage.graph import CallGraph
from tools.call_linkage.schema import Edge, node_id_for
from tools.call_linkage.store import load_csv


def load_graph(path: str) -> CallGraph:
    p = Path(path)
    if p.suffix == ".json":
        doc = json.loads(p.read_text(encoding="utf-8"))
        return CallGraph([Edge.from_dict(e) for e in doc["edges"]])
    return CallGraph(load_csv(p))


def fmt_edge(e: Edge) -> str:
    src = f"{e.src_module}{'+' + e.src_offset if e.src_offset else ''}"
    dst = f"{e.dst_module}{'+' + e.dst_offset if e.dst_offset else ''}"
    return f"{e.edge_id or '?'} [{e.layer}/{e.kind}] {src} --({e.src_insn[:60]})--> {dst} [{e.confidence}]"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Query a call-linkage graph.")
    ap.add_argument("graph", help="call_linkage.json or call_linkage.csv")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats", help="edge/node/layer/kind counts")

    t = sub.add_parser("trace", help="BFS neighbourhood of one endpoint")
    t.add_argument("--module", required=True)
    t.add_argument("--offset", default="")
    t.add_argument("--name", default="")
    t.add_argument("--depth", type=int, default=2)
    t.add_argument("--direction", default="both", choices=["in", "out", "both"])

    f = sub.add_parser("fan-in", help="hottest dst nodes")
    f.add_argument("--layer", default="")
    f.add_argument("--top", type=int, default=25)

    s = sub.add_parser("search", help="substring search over names/instructions")
    s.add_argument("text")

    c = sub.add_parser("chain", help="list one chain's hops")
    c.add_argument("chain_id")

    p = sub.add_parser("paths", help="paths between two endpoints (mod[+off][#name])")
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--to", dest="dst", required=True)
    p.add_argument("--max-depth", type=int, default=6)

    n = sub.add_parser("node", help="show one node + its edges")
    n.add_argument("node_id")
    args = ap.parse_args(argv)

    g = load_graph(args.graph)
    if args.cmd == "stats":
        st = g.stats()
        print(f"edges={st['edges']} nodes={st['nodes']}")
        print("by_layer:", st["by_layer"])
        print("by_confidence:", st["by_confidence"])
        print("chains:", st["chains"])
    elif args.cmd == "trace":
        res = g.trace(args.module, args.offset, args.name, args.depth, args.direction)
        print(f"nodes={len(res['nodes'])} edges={len(res['edges'])}")
        for e in sorted(res["edges"], key=lambda e: e.edge_id):
            print(" ", fmt_edge(e))
    elif args.cmd == "fan-in":
        for t in g.top_targets(layer=args.layer, top=args.top):
            print(f"{t['fan_in']:4d}  {t['module']}+{t['offset']}  {t['name'][:80]}")
    elif args.cmd == "search":
        for e in g.search(args.text):
            print(" ", fmt_edge(e))
    elif args.cmd == "chain":
        edges = sorted(g.find_edges(chain=args.chain_id), key=lambda e: e.hop)
        if not edges:
            print(f"no edges with chain={args.chain_id}")
            return 1
        for e in edges:
            print(f"  hop {e.hop:3d} " + fmt_edge(e))
    elif args.cmd == "paths":
        def split(s: str):
            mod, off, name = s, "", ""
            if "#" in mod:
                mod, name = mod.split("#", 1)
            if "+" in mod:
                mod, off = mod.split("+", 1)
            return (mod, name, off)
        paths = g.find_paths(split(args.src), split(args.dst), args.max_depth)
        print(f"{len(paths)} path(s)")
        for path in paths:
            print("  " + " -> ".join(
                node_id_for(e.src_module, e.src_name, e.src_offset) for e in path)
                + " -> " + node_id_for(path[-1].dst_module, path[-1].dst_name, path[-1].dst_offset))
    elif args.cmd == "node":
        node = g.nodes.get(args.node_id)
        print(node if node else "unknown node (showing touching edges anyway)")
        for e, rel in g.neighbours(args.node_id):
            print(f"  [{rel}] " + fmt_edge(e))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

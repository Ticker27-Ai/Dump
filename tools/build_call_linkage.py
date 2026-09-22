#!/usr/bin/env python3
"""Rebuild the call-linkage (สายการเรียก) graph from the evidence bundle.

Usage:
    python3 tools/build_call_linkage.py [--bundle Codes/SnakeLogic] [--out build]
    python3 tools/build_call_linkage.py --out build --compare        # semantic diff vs baseline
    python3 tools/build_call_linkage.py --out build --extra my_hops.json

Outputs (in --out): call_linkage.csv, call_linkage.json, CALL_LINKAGE.md,
CALL_LINKAGE_OVERVIEW.mmd.

``--extra`` accepts a JSON list of annotation dicts (same keys as
tools/call_linkage/annotations.py entries) so new instruction/offset hops can
be added without editing the package.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.call_linkage import build as B
from tools.call_linkage import chains as C
from tools.call_linkage import render as R
from tools.call_linkage import store as S
from tools.call_linkage import verify as V
from tools.call_linkage.graph import CallGraph
from tools.call_linkage.schema import KINDS, LAYERS


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rebuild the call-linkage graph.")
    ap.add_argument("--bundle", default="Codes/SnakeLogic")
    ap.add_argument("--baseline", default=None, help="trusted call_linkage.csv for L5 import + parity (default: <bundle>/call_linkage.csv)")
    ap.add_argument("--out", default="build")
    ap.add_argument("--no-l5", action="store_true", help="skip the L5 baseline import")
    ap.add_argument("--extra", default=None, help="JSON file with extra annotation dicts")
    ap.add_argument("--compare", action="store_true", help="semantic diff rebuilt-vs-baseline")
    args = ap.parse_args(argv)

    bundle = Path(args.bundle)
    baseline = Path(args.baseline) if args.baseline else bundle / "call_linkage.csv"
    extra = json.loads(Path(args.extra).read_text(encoding="utf-8")) if args.extra else []

    edges, diag = B.build_from_fragments(bundle, baseline_csv=baseline,
                                        extra_annotations=extra,
                                        with_l5_import=not args.no_l5)
    graph = CallGraph(edges)
    resolved, missing = C.resolve_all(graph, bundle=str(bundle))
    checks = V.run_all(graph, bundle, baseline_csv=baseline if not args.no_l5 else None,
                       chains=resolved)
    hot = graph.top_targets(layer="L5", top=25)
    fp, nfiles = S.fingerprint(bundle)
    meta = {
        "title": "SNAKE.apk - call linkage (rebuilt)",
        "generated_by": "tools/build_call_linkage.py",
        "bundle": str(bundle),
        "bundle_fingerprint": fp,
        "bundle_files": nfiles,
        "baseline": str(baseline) if not args.no_l5 else None,
        "provenance": {"derived": "L1 declares/invokes, L2 init_array, L6 engine symbols",
                       "curated": "L3/L4 instruction hops + fixed L1/L2/L6 edges (annotations.py)",
                       "imported": "L5 Dart edges (verbatim from baseline; asm/*.dart not in bundle)"},
        "layers": [{"id": k, **v} for k, v in LAYERS.items()],
        "kinds": KINDS,
        "diagnostics": diag,
    }

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    S.save_csv(edges, outdir / "call_linkage.csv")
    S.save_json(edges, list(graph.nodes.values()),
                [{"id": c.id, "layer_path": c.layer_path, "title": c.title,
                  "title_th": c.title_th, "goal": c.goal,
                  "hops": [{"n": h.n, "edge": h.edge_id, "text": h.text,
                            "match": h.match, "ok": bool(h.edge_id)} for h in c.hops]}
                 for c in resolved],
                checks, hot, meta, outdir / "call_linkage.json")
    (outdir / "CALL_LINKAGE.md").write_text(
        R.markdown_report(graph, resolved, checks, meta, hot), encoding="utf-8")
    (outdir / "CALL_LINKAGE_OVERVIEW.mmd").write_text(R.OVERVIEW_MERMAID, encoding="utf-8")

    # -- console summary ----------------------------------------------------
    print(f"edges={diag['total']}  derived(L1/L2/L6)="
          f"{diag['derived_l1_declares'] + diag['derived_l1_invokes'] + diag['derived_l2_init'] + diag['derived_l6_binds']}"
          f"  curated={diag['curated']}  imported_L5={diag['imported_l5']}")
    print(f"chains: {len(resolved)}, hops: {sum(len(c.hops) for c in resolved)},"
          f" unresolved: {len(missing)}")
    for m in missing[:10]:
        print(f"  MISSING {m['chain']} hop {m['n']}: {m['match']}")
    fails = [c for c in checks if c["status"] == "FAIL"]
    for c in checks:
        print(f"  [{c['status']}] {c['name']}")
    if args.compare and not args.no_l5:
        diff = R.compare_edges(edges, S.load_csv(baseline))
        print(f"compare vs {baseline}: only_in_new={len(diff['only_in_new'])}"
              f" only_in_old={len(diff['only_in_old'])}")
        for d in diff["only_in_new"][:10] + diff["only_in_old"][:10]:
            print(f"  {d}")
    print(f"wrote {outdir}/call_linkage.csv, call_linkage.json, CALL_LINKAGE.md, CALL_LINKAGE_OVERVIEW.mmd")
    return 1 if (fails or missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())

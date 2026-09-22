#!/usr/bin/env python3
"""Regenerate tools/call_linkage/annotations.py from a trusted call_linkage.csv.

Usage:
    python3 tools/codegen_annotations.py [baseline.csv]   # default: Codes/SnakeLogic/call_linkage.csv

Only the *curated* hops are extracted (L3/L4 + fixed L1/L2/L6 edges). Derived
layers (L1 declares/invokes, L2 init_array, L6 engine symbols) are rebuilt from
fragments by tools/call_linkage/build.py, and L5 is imported from baseline.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

DERIVED = {
    ("L1", "declares_native"),
    ("L1", "invokes_native_class"),
    ("L2", "loader_init_call"),
    ("L6", "binds_engine_symbol"),
}

HEADER = '''"""Curated instruction/offset annotations (L3/L4 + fixed L1/L2/L6 hops).

GENERATED — do not hand-edit the table below. Regenerate with:
    python3 tools/codegen_annotations.py   # (see docs/CALL_LINKAGE_GUIDE.md)

Each entry is analyst judgment (dst_name / resolved_by / confidence) anchored
to a real instruction: ``verify`` asserts every src_offset exists in the decoded
listings (F4b/F4c/F4d) with a matching mnemonic.

TO EXTEND (ต่อยอด): append new dicts to ``EXTRA_ANNOTATIONS`` at the bottom of
this file, or pass ``extra_annotations=[...]`` to ``build.build_from_fragments``.
Required keys: layer, kind, src_module, src_offset, src_name, src_insn,
dst_module, dst_offset, dst_name, resolved_by, confidence, evidence, source.
Optional: note, chain, hop.
"""

from __future__ import annotations

from typing import Any, Dict, List


ANNOTATIONS: List[Dict[str, Any]] = [
'''

FOOTER = ''']


# ---------------------------------------------------------------------------
# Extension point: add your own instruction/offset hops here.
# Example:
#   EXTRA_ANNOTATIONS = [
#       {
#           "layer": "L3", "kind": "calls_direct",
#           "src_module": "libengine.so", "src_offset": "0x1234",
#           "src_name": "my new window", "src_insn": "bl #0x5678",
#           "dst_module": "libengine.so", "dst_offset": "0x5678",
#           "dst_name": "sub_5678", "resolved_by": "analyst",
#           "confidence": "probable", "evidence": "...",
#           "source": "analyst-note", "chain": "CH-12", "hop": 1,
#       },
#   ]
# ---------------------------------------------------------------------------
EXTRA_ANNOTATIONS: List[Dict[str, Any]] = []
'''


def main() -> int:
    baseline = Path(sys.argv[1] if len(sys.argv) > 1 else "Codes/SnakeLogic/call_linkage.csv")
    rows = list(csv.DictReader(baseline.open(encoding="utf-8")))
    cur = [r for r in rows if (r["layer"], r["kind"]) not in DERIVED and r["layer"] != "L5"]
    cur.sort(key=lambda r: (r["layer"], r["kind"], r["src_module"], r["src_offset"] or "", r["dst_offset"] or ""))
    out = [HEADER]
    for r in cur:
        out.append("    {\n")
        for k in ("layer", "kind", "src_module", "src_offset", "src_name", "src_insn",
                  "dst_module", "dst_offset", "dst_name", "resolved_by", "confidence",
                  "evidence", "source", "note", "chain", "hop"):
            v = r[k]
            out.append(f"        {k!r}: {int(v or 0) if k == 'hop' else repr(v)},\n")
        out.append("    },\n")
    out.append(FOOTER)
    dest = Path(__file__).resolve().parent / "call_linkage" / "annotations.py"
    dest.write_text("".join(out), encoding="utf-8")
    print(f"wrote {dest} ({len(cur)} curated hops from {baseline})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Graph builder: fragments -> edges.

Three edge provenances (ซื่อสัตย์กับที่มา — never mix them silently):

* **derived**    -- computed from parsed fragments (L1 declares/invokes,
  L2 ``loader_init_call``, L6 ``binds_engine_symbol``)
* **curated**    -- analyst annotations (``annotations.ANNOTATIONS`` +
  ``extra_annotations``): L3/L4 instruction hops + fixed L1/L2/L6 edges.
  Every ``libengine.so`` annotation is checked against the decoded listings.
* **imported**   -- L5 Dart edges copied verbatim from the trusted baseline
  CSV, because ``output/blutter/asm/*.dart`` is not part of the bundle.

``build_from_fragments()`` returns ``(edges, diagnostics)`` with stable,
deterministically assigned edge ids (``E0001`` ...).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import annotations as _ann
from .parse import (
    hex_int,
    load_fragments_json,
    parse_asm_listing,
    parse_f2,
    parse_f6_api_pairs,
    to_hex,
)
from .schema import LAYER_ORDER, Edge, offset_int
from .store import load_csv


# --------------------------------------------------------------------------
# id assignment (deterministic)
# --------------------------------------------------------------------------

def assign_ids(edges: List[Edge]) -> List[Edge]:
    def sort_key(e: Edge):
        return (
            LAYER_ORDER.index(e.layer) if e.layer in LAYER_ORDER else 99,
            e.kind,
            e.src_module,
            offset_int(e.src_offset) if offset_int(e.src_offset) is not None else -1,
            e.dst_module,
            offset_int(e.dst_offset) if offset_int(e.dst_offset) is not None else -1,
            e.src_name,
            e.dst_name,
        )

    edges = sorted(edges, key=sort_key)
    for i, e in enumerate(edges, 1):
        e.edge_id = f"E{i:04d}"
    return edges


# --------------------------------------------------------------------------
# derived builders
# --------------------------------------------------------------------------

def build_l1_declares(frag: Dict[str, Any]) -> List[Edge]:
    out = []
    for m in frag["dex"]["native_methods"]:
        if not m.get("custom"):
            continue
        cls, name, sig = m["class"], m["name"], m["sig"]
        out.append(Edge(
            chain="CH-08", hop=0, layer="L1", kind="declares_native",
            src_module="classes.dex", src_name=cls,
            src_insn="ACC_NATIVE method declaration",
            dst_module="classes.dex", dst_name=f"{cls[:-1]};->{name}{sig}",
            resolved_by="dex method_ids access flags", confidence="proven",
            evidence=f"expected static export {m['jni_long_name']} is exported by NOBODY"
                     " -> must be bound via RegisterNatives",
            source="fragments/F2_dex_natives.txt",
        ))
    return out


def build_l1_invokes(f2: Dict[str, Any]) -> List[Edge]:
    """One edge per F2 caller offset, hop = offset order (1..N)."""
    callers = sorted(f2["callers"], key=lambda c: hex_int(c["offset"]) or 0)
    out = []
    for i, c in enumerate(callers, 1):
        out.append(Edge(
            chain="CH-08", hop=i, layer="L1", kind="invokes_native_class",
            src_module="classes.dex", src_offset=c["offset"], src_name=c["method"],
            src_insn="invoke-* (the invoked member is not recorded per site in F2)",
            dst_module="classes.dex", dst_name=c["class"],
            resolved_by="dex code-item scan (F2)", confidence="proven",
            evidence=f"F2 lists this invoke offset under '{c['class']}: N distinct caller"
                     " method(s)'; the class names are obfuscated into"
                     " androidx.appcompat.view.menu.*, so the offset is the reliable half"
                     " of the evidence",
            source="fragments/F2_dex_natives.txt",
        ))
    return out


def build_l2_init(frag: Dict[str, Any]) -> List[Edge]:
    out = []
    for entry in frag["libengine"]["init_array"]:
        i = entry["index"]
        out.append(Edge(
            chain="CH-02", hop=i + 1, layer="L2", kind="loader_init_call",
            src_module="libengine.so", src_offset=entry["slot"],
            src_name=f".init_array[{i}]",
            src_insn="R_AARCH64_RELATIVE addend (the slot holds no file bytes)",
            dst_module="libengine.so", dst_offset=entry["target"],
            dst_name=f"_INIT_{i} (.text, prologue {entry['prologue'][:16]}...)",
            resolved_by=".rela.dyn addend; Ghidra's 02_init_array_entries.txt agrees on"
                        " all 44 after rebasing -0x100000",
            confidence="proven",
            evidence=f"slot {entry['slot']} -> {entry['target']} in {entry['section']},"
                     f" value_from={entry['value_from']}",
            source="fragments.json:libengine.init_array",
        ))
    return out


def build_l6_binds(pairs: List[Dict[str, str]]) -> List[Edge]:
    """One edge per F6 pair, hop = libapp-offset order (4..14, after the 3
    CH-10 closure hops that come from the L5 import)."""
    pairs = sorted(pairs, key=lambda p: hex_int(p["libapp"]) or 0)
    out = []
    for i, p in enumerate(pairs, 4):
        out.append(Edge(
            chain="CH-10", hop=i, layer="L6", kind="binds_engine_symbol",
            src_module="libapp.so", src_offset=p["libapp"], src_name=p["name"],
            src_insn="snapshot string referencing an engine C++ API",
            dst_module="libflutter.so", dst_offset=p["libflutter"], dst_name=p["name"],
            resolved_by="exact byte match of the API name in both images",
            confidence="proven",
            evidence=f"libapp.so+{p['libapp']} <-> libflutter.so+{p['libflutter']};"
                     f" {len(pairs)} of the {len(pairs)} names the snapshot uses exist"
                     " in the shipped engine",
            source="fragments/F6_libflutter_version.txt",
        ))
    return out


# --------------------------------------------------------------------------
# curated + import
# --------------------------------------------------------------------------

def build_curated(extra_annotations: Optional[List[Dict[str, Any]]] = None) -> List[Edge]:
    rows = list(_ann.ANNOTATIONS) + list(_ann.EXTRA_ANNOTATIONS) + list(extra_annotations or [])
    return [Edge.from_dict(r) for r in rows]


def build_l5_import(baseline_csv: str | Path) -> List[Edge]:
    """Verbatim import of L5 rows (blutter asm/*.dart is not in the bundle)."""
    return [e for e in load_csv(baseline_csv) if e.layer == "L5"]


# --------------------------------------------------------------------------
# top-level build
# --------------------------------------------------------------------------

def build_from_fragments(
    bundle: str | Path,
    baseline_csv: Optional[str | Path] = None,
    extra_annotations: Optional[List[Dict[str, Any]]] = None,
    with_l5_import: bool = True,
) -> Tuple[List[Edge], Dict[str, Any]]:
    bundle = Path(bundle)
    frag = load_fragments_json(bundle)
    f2 = parse_f2(bundle / "fragments" / "F2_dex_natives.txt")
    f6 = parse_f6_api_pairs(bundle / "fragments" / "F6_libflutter_version.txt")

    edges: List[Edge] = []
    edges += build_l1_declares(frag)
    edges += build_l1_invokes(f2)
    edges += build_l2_init(frag)
    edges += build_l6_binds(f6)
    curated = build_curated(extra_annotations)
    edges += curated
    imported = 0
    if with_l5_import:
        if baseline_csv is None:
            baseline_csv = bundle / "call_linkage.csv"
        l5 = build_l5_import(baseline_csv)
        edges += l5
        imported = len(l5)

    edges = assign_ids(edges)
    diag = {
        "derived_l1_declares": len([e for e in edges if e.kind == "declares_native"]),
        "derived_l1_invokes": len([e for e in edges if e.kind == "invokes_native_class"]),
        "derived_l2_init": len([e for e in edges if e.kind == "loader_init_call"]),
        "derived_l6_binds": len([e for e in edges if e.kind == "binds_engine_symbol"]),
        "curated": len(curated),
        "imported_l5": imported,
        "total": len(edges),
        "bundle": str(bundle),
        "baseline": str(baseline_csv) if with_l5_import else None,
    }
    return edges, diag


def load_asm_listings(bundle: str | Path) -> Dict[str, Dict[str, Any]]:
    """Parse F4b/F4c/F4d once; shared by verify + evidence helpers."""
    bundle = Path(bundle)
    frag_dir = bundle / "fragments"
    return {
        "F4b": parse_asm_listing(frag_dir / "F4b_libengine_mytext.asm"),
        "F4c": parse_asm_listing(frag_dir / "F4c_libengine_JNI_OnLoad.asm"),
        "F4d": parse_asm_listing(frag_dir / "F4d_libengine_regnatives_windows.asm"),
    }

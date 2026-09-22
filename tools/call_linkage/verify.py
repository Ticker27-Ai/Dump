"""Verification suite: every load-bearing claim re-checked against the bundle.

Each check returns ``{"name","status","detail"}`` with status PASS/FAIL/SKIP.
Checks that need files outside the bundle (blutter ``asm/*.dart``,
``addNames.py``, Ghidra artifacts) are reported as SKIP with the reason —
they are covered indirectly by the L5-baseline parity check instead.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .build import load_asm_listings
from .graph import CallGraph
from .parse import (
    hex_int,
    load_fragments_json,
    norm_insn,
    parse_f1_lib_sizes,
    parse_f2,
    parse_f4_exports,
    parse_f5_sections,
    parse_f6_api_pairs,
)
from .schema import offset_int
from .store import load_csv


def _parse_dex_size(bundle: Path) -> Optional[int]:
    text = (bundle / "fragments" / "F1_apk_inventory.txt").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"classes\.dex[^\n]*?size[=:]\s*(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"classes\.dex[^\n]*?(\d{5,})\s*bytes", text)
    return int(m.group(1)) if m else None


_PSEUDO_PREFIXES = (
    "nmethods =", "stp/str", "r_aarch64", "fill-array", "invoke-", "acc_native",
    "dlopen", "call ", "ldr x8", "adrp ",
)


def _is_pseudo(insn: str) -> bool:
    return norm_insn(insn).startswith(_PSEUDO_PREFIXES)


def run_all(
    graph: CallGraph,
    bundle: str | Path,
    baseline_csv: Optional[str | Path] = None,
    chains: Optional[List[Any]] = None,
) -> List[Dict[str, str]]:
    bundle = Path(bundle)
    results: List[Dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        results.append({"name": name, "status": status, "detail": detail})

    frag = load_fragments_json(bundle)
    f2 = parse_f2(bundle / "fragments" / "F2_dex_natives.txt")
    listings = load_asm_listings(bundle)
    merged: Dict[str, Dict[str, Any]] = {}
    for tag, lst in listings.items():
        for off, rec in lst["insns"].items():
            merged.setdefault(off, dict(rec, listing=tag))

    # -- 1. fragment census -------------------------------------------------
    customs = [m for m in frag["dex"]["native_methods"] if m.get("custom")]
    n_callers = len(f2["callers"])
    n_init = len(frag["libengine"]["init_array"])
    n_sites = len(frag["libengine"]["register_natives_sites"])
    n_pairs = len(parse_f6_api_pairs(bundle / "fragments" / "F6_libflutter_version.txt"))
    ok = (len(customs), n_callers, n_init, n_sites, n_pairs) == (13, 20, 44, 3, 11)
    add("fragment census matches the analysed build",
        "PASS" if ok else "FAIL",
        f"custom natives={len(customs)} callers={n_callers} init_array={n_init}"
        f" reg_sites={n_sites} engine_pairs={n_pairs} (want 13/20/44/3/11)")

    # -- 2. every F2 caller offset became an edge ----------------------------
    caller_offs = {c["offset"] for c in f2["callers"]}
    edge_offs = {e.src_offset for e in graph.find_edges(layer="L1", kind="invokes_native_class")}
    missing = sorted(caller_offs - edge_offs)
    add("every F2 caller offset became an edge",
        "PASS" if not missing else "FAIL",
        f"{len(edge_offs)}/{len(caller_offs)} offsets covered"
        + (f"; missing={missing}" if missing else ""))

    # -- 3. curated annotations point at real instructions -------------------
    bad: List[str] = []
    skipped: List[str] = []
    checked = 0
    for e in graph.edges:
        if e.src_module != "libengine.so" or not e.src_offset:
            continue
        if e.kind in ("rejected_slot_load",):
            continue  # audit-trail rows, deliberately outside decoded windows
        rec = merged.get(e.src_offset)
        if rec is None:
            if _is_pseudo(e.src_insn):
                # pseudo-insns anchor to site headers, not instruction rows
                site_vas = {s["va"].lower() for s in frag["libengine"]["register_natives_sites"]}
                if e.src_offset in site_vas:
                    checked += 1
                    continue
            skipped.append(f"{e.src_offset} ({e.kind})")
            continue
        checked += 1
        if not _is_pseudo(e.src_insn):
            want_mnem = norm_insn(e.src_insn).split(" ")[0]
            if rec["mnemonic"].lower() != want_mnem:
                bad.append(f"{e.src_offset}: listing has {rec['mnemonic']!r}, edge says {e.src_insn!r}")
    add("every curated annotation points at a real instruction",
        "FAIL" if bad else "PASS",
        f"{checked} libengine.so hops checked against F4b/F4c/F4d"
        + (f"; mnemonic mismatches={bad}" if bad else "")
        + (f"; outside decoded windows (kept, not checked)={len(skipped)}" if skipped else ""))

    # -- 4. RegisterNatives total == declarations ----------------------------
    total = sum(s["count"] for s in frag["libengine"]["register_natives_sites"])
    n_decl = len(graph.find_edges(kind="declares_native"))
    add("RegisterNatives nMethods total == custom native declarations",
        "PASS" if total == n_decl == 13 else "FAIL",
        f"{total} registered across {n_sites} sites vs {n_decl} declared in the dex")

    # -- 5. fnPtr inside .mytext ---------------------------------------------
    mytext = frag["libengine"]["mytext"]
    base = hex_int(mytext["addr"]) or 0
    size = int(mytext["size"])
    fn_edges = graph.find_edges(kind="stages_fnptr")
    ptrs = [offset_int(e.dst_offset) for e in fn_edges]
    inside = all(p is not None and base <= p < base + size for p in ptrs) and bool(ptrs)
    add("the recovered fnPtr lies inside .mytext",
        "PASS" if inside else "FAIL",
        f"{[e.dst_offset for e in fn_edges]} in {mytext['addr']}..{hex(base + size)}")

    # -- 6. JNI_OnLoad entry --------------------------------------------------
    f4_exports = parse_f4_exports(bundle / "fragments" / "F4_libengine_jni.txt")
    onload = f4_exports.get("JNI_OnLoad")
    entry = graph.find_edges(layer="L2", kind="calls_entry_point",
                             dst_module="libengine.so", dst_offset=str(onload or ""))
    add("JNI_OnLoad edges start at the exported entry point",
        "PASS" if onload and entry else "FAIL",
        f"F4 exports {len(f4_exports)} defined symbols; JNI_OnLoad={onload}; entry edges={len(entry)}")

    # -- 7. one slot-215 blr per site -----------------------------------------
    reg = [e for e in graph.find_edges(kind="registers_natives") if e.dst_offset == "0x6b8"]
    sites = sorted((hex_int(s["va"]) or 0) for s in frag["libengine"]["register_natives_sites"])
    # each blr must sit just after a distinct ldr site (same window, < 0x20 bytes on)
    unused = set(sites)
    orphan = []
    for e in reg:
        v = hex_int(e.src_offset) or -1
        host = next((s for s in sorted(unused) if 0 < v - s < 0x20), None)
        if host is None:
            orphan.append(e.src_offset)
        else:
            unused.discard(host)
    ok = len(reg) == len(sites) and not orphan and not unused
    add("every RegisterNatives site produced exactly one slot-215 blr edge",
        "PASS" if ok else "FAIL",
        f"blr @ {sorted(e.src_offset for e in reg)} for ldr sites"
        f" {[hex(s) for s in sites]}"
        + ("" if ok else f"; orphan={orphan} uncovered={[hex(s) for s in unused]}"))

    # -- 8. address-space bounds ----------------------------------------------
    sizes = parse_f1_lib_sizes(bundle / "fragments" / "F1_apk_inventory.txt")
    bounds = {
        "libengine.so": sizes.get("lib/arm64-v8a/libengine.so"),
        "libapp.so": sizes.get("lib/arm64-v8a/libapp.so"),
        "libflutter.so": sizes.get("lib/arm64-v8a/libflutter.so"),
        "classes.dex": _parse_dex_size(bundle),
    }
    bad_bounds: List[str] = []
    for e in graph.edges:
        for module, off in ((e.src_module, e.src_offset), (e.dst_module, e.dst_offset)):
            if module == "libapp.so!pp" or not off:
                continue  # pool slots are not file offsets
            if module in ("android-runtime", "kernel"):
                continue  # slots / syscall numbers, not addresses
            bound = bounds.get(module)
            v = offset_int(off)
            if bound and v is not None and v >= bound:
                bad_bounds.append(f"{e.edge_id}:{module}+{off} >= {bound}")
    add("no edge points outside its module's address space",
        "PASS" if not bad_bounds else "FAIL",
        f"bounds={bounds}" + (f"; violations={bad_bounds[:5]}" if bad_bounds else ""))

    # -- 9. Dart targets inside .text ------------------------------------------
    sections = parse_f5_sections(bundle / "fragments" / "F5_libapp_dart.txt")
    text = sections.get(".text", {})
    tbase, tsize = hex_int(text.get("addr")), int(text.get("size", 0))
    bad_dart: List[str] = []
    n_dart = 0
    for e in graph.find_edges(layer="L5"):
        for off in (e.src_offset, e.dst_offset):
            if e.src_module == "libapp.so!pp" and off == e.src_offset:
                continue
            v = offset_int(off)
            if v is None:
                continue
            n_dart += 1
            if tbase is None or not (tbase <= v < tbase + tsize):
                bad_dart.append(f"{e.edge_id}:{off}")
    add("every Dart call endpoint lands inside libapp.so .text",
        "PASS" if not bad_dart else "FAIL",
        f".text {text.get('addr')}+{tsize}; {n_dart} endpoints checked"
        + (f"; outside={bad_dart[:5]}" if bad_dart else ""))

    # -- 10. no duplicate semantic key -----------------------------------------
    seen: Dict[Tuple[str, ...], str] = {}
    dupes: List[str] = []
    for e in graph.edges:
        if e.dedup_key() in seen:
            dupes.append(f"{e.edge_id} duplicates {seen[e.dedup_key()]} @ {e.dedup_key()}")
        else:
            seen[e.dedup_key()] = e.edge_id
    add("no hop is published twice",
        "PASS" if not dupes else "FAIL",
        f"{len(graph.edges)} edges, {len(seen)} distinct dedup keys (names included)"
        + (f"; dupes={dupes[:3]}" if dupes else ""))

    # -- 11. no dangling node ---------------------------------------------------
    from .schema import node_id_for as _nid

    dangling = [eid for eid, n in graph.nodes.items()
                if eid not in graph.by_src and eid not in graph.by_dst]
    _ = _nid  # (node ids are built by the same helper in graph/store)
    add("no dangling node reference",
        "PASS" if not dangling else "FAIL",
        f"{len(graph.edges)} edges, {len(graph.nodes)} nodes"
        + (f"; dangling={dangling[:5]}" if dangling else ""))

    # -- 12. chain hops resolve -------------------------------------------------
    if chains is None:
        add("chain hops all exist in the edge set", "SKIP", "no chains supplied to verify")
    else:
        total_hops = sum(len(c.hops) for c in chains)
        unresolved = [(c.id, h.n) for c in chains for h in c.hops if not h.edge_id]
        add("chain hops all exist in the edge set",
            "PASS" if not unresolved else "FAIL",
            f"{total_hops - len(unresolved)}/{total_hops} hops resolved"
            + (f"; unresolved={unresolved[:5]}" if unresolved else ""))

    # -- 13/14. baseline parity (when a trusted CSV is supplied) ----------------
    if baseline_csv is None:
        add("L5 import parity with the trusted baseline", "SKIP", "no baseline supplied")
        add("layer/kind totals match the trusted baseline", "SKIP", "no baseline supplied")
    else:
        base = load_csv(baseline_csv)
        base_l5 = {e.key() for e in base if e.layer == "L5"}
        got_l5 = {e.key() for e in graph.edges if e.layer == "L5"}
        add("L5 import parity with the trusted baseline",
            "PASS" if base_l5 == got_l5 else "FAIL",
            f"baseline L5={len(base_l5)} imported={len(got_l5)}"
            + (f"; missing={len(base_l5 - got_l5)} extra={len(got_l5 - base_l5)}"
               if base_l5 != got_l5 else ""))
        from collections import Counter as _C

        want_c = _C((e.layer, e.kind) for e in base)
        got_c = _C((e.layer, e.kind) for e in graph.edges)
        add("layer/kind totals match the trusted baseline",
            "PASS" if want_c == got_c else "FAIL",
            f"baseline={len(base)} rebuilt={len(graph.edges)}"
            + ("" if want_c == got_c else f"; diff={dict((set(want_c.items()) ^ set(got_c.items())))}"))

    # -- 15. schema validation ---------------------------------------------------
    invalid: List[str] = []
    for e in graph.edges:
        problems = e.validate()
        if problems:
            invalid.append(f"{e.edge_id}: {problems}")
    add("every edge validates against the schema",
        "PASS" if not invalid else "FAIL",
        f"{len(graph.edges) - len(invalid)}/{len(graph.edges)} valid"
        + (f"; e.g. {invalid[:3]}" if invalid else ""))

    return results

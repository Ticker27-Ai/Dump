"""Chain registry (CH-01 .. CH-11): declarativeสายการเรียก + resolver.

A chain is an ordered list of hops; each hop matches ONE edge by semantic key
(``layer/kind/src_module/src_offset/dst_module/dst_offset``) — never by the
volatile ``edge_id``. ``resolve_all(graph)`` binds hops to the rebuilt edges.

TO EXTEND (ต่อยอด): append a ``ChainDef`` to ``CHAIN_DEFS`` (e.g. ``CH-12``),
optionally with hops pointing at your ``EXTRA_ANNOTATIONS`` edges, then::

    resolved, missing = chains.resolve_all(graph)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .graph import CallGraph
from .parse import hex_int, load_fragments_json
from .schema import Chain, Hop, norm_offset


@dataclass
class ChainDef:
    id: str
    layer_path: str
    title: str
    title_th: str = ""
    goal: str = ""
    hops: List[Hop] = field(default_factory=list)          # static hops
    generator: str = ""                                     # or computed: CH-02/08/10b/11


def _hop(layer: str, kind: str, src_module: str, src_offset: str,
         text: str, dst_module: str = "", dst_offset: str = "") -> Hop:
    match: Dict[str, str] = {"layer": layer, "kind": kind,
                             "src_module": src_module, "src_offset": norm_offset(src_offset)}
    if dst_module:
        match["dst_module"] = dst_module
    if dst_offset:
        match["dst_offset"] = norm_offset(dst_offset)
    return Hop(match=match, text=text)


_L = "libengine.so"

CHAIN_DEFS: List[ChainDef] = [
    ChainDef(
        id="CH-01", layer_path="L1 -> L2 -> L3",
        title="application start -> libengine.so is loaded",
        title_th="เริ่มแอป -> libengine.so ถูกโหลด",
        goal="Show how the sample reaches its protected native code at all: the name"
             " 'engine' never appears in the dex string pool, it is built byte by byte.",
        hops=[
            _hop("L1", "invokes_loader", "classes.dex", "0x2b6c2e",
                 "Lcom/snake/App;-><clinit>()V invokes System.loadLibrary"),
            _hop("L1", "invokes_loader", "classes.dex", "0x2b6c40",
                 "the library name is built by fill-array-data, 6 payload bytes = 'engine'"),
            _hop("L2", "loads_library", "android-runtime", "",
                 "the loader maps lib/arm64-v8a/libengine.so", dst_module="libengine.so"),
            _hop("L2", "loader_init_call", _L, "0x825c78",
                 "the loader then calls the 44 .init_array constructors before JNI_OnLoad"),
            _hop("L2", "calls_entry_point", "android-runtime", "",
                 "and finally hands control to the exported JNI_OnLoad",
                 dst_module="libengine.so", dst_offset="0xf3fa0"),
        ],
    ),
    ChainDef(
        id="CH-02", layer_path="L2 -> L3",
        title="dynamic loader -> 44 staged constructors",
        title_th="dynamic loader -> constructor ที่วางไว้ 44 ตัว",
        goal="Every constructor the loader will call, with the slot that holds it and"
             " the target offset it points at. Ghidra's independent list agrees on 44/44.",
        generator="init_array",
    ),
    ChainDef(
        id="CH-03", layer_path="L3",
        title="JNI_OnLoad: two RWX pages, a synthesised branch opcode, two jumps out",
        title_th="JNI_OnLoad: หน้า RWX 2 หน้า, opcode branch ที่สังเคราะห์เอง, และทางออก 2 ครั้ง",
        goal="JNI_OnLoad registers nothing itself (0 JNIEnv slot loads in 12,280 bytes"
             " of Ghidra decompilation). What it does instead is build code: this is the"
             " hop sequence that explains why the registration sites live elsewhere.",
        hops=[
            _hop("L3", "calls_plt", _L, "0xf3fd8", "sysconf - page size for the coming mmap"),
            _hop("L3", "calls_syscall", _L, "0xf4018",
                 "svc #222 mmap(NULL, len, PROT_RWX, MAP_PRIVATE|ANON) - the first writable+exec page"),
            _hop("L3", "computes_branch", _L, "0xf4054", "br through a 4-entry relative-offset table"),
            _hop("L3", "calls_plt", _L, "0xf406c", "rand - entropy mixed into the synthesised opcode"),
            _hop("L3", "writes_generated_code", _L, "0xf4078",
                 "the B opcode is written word by word into the fresh page"),
            _hop("L3", "writes_generated_code", _L, "0xf40a0", "page n-1 is patched to branch to page n"),
            _hop("L3", "calls_plt", _L, "0xf40ac", "FUN_0091ad58 (Ghidra) over the written range"),
            _hop("L3", "jumps_into_generated", _L, "0xf40e0",
                 "blr into the generated page - control leaves the static image"),
            _hop("L3", "calls_syscall", _L, "0xf411c", "second RWX mmap"),
            _hop("L3", "jumps_into_generated", _L, "0xf43f4",
                 "blr into the second generated table; the return value selects the path"),
            _hop("L3", "calls_syscall", _L, "0xf4428", "svc #53 fchmodat on a value taken from the generated page"),
            _hop("L3", "calls_plt", _L, "0xf446c",
                 "strlen - the two length checks (11 and 10) that gate the byte-decode loops"),
        ],
    ),
    ChainDef(
        id="CH-04", layer_path="L3 -> L4 -> L1",
        title="registration site 0xf3a08 -> com/snake/helper/Native",
        title_th="registration site 0xf3a08 -> com/snake/helper/Native",
        goal="The full instruction walk from the first call in the window to the"
             " RegisterNatives blr, ending at the dex class it is attributed to.",
        hops=[
            _hop("L3", "calls_plt", _L, "0xf3944", "FUN_0091ad58 (Ghidra)"),
            _hop("L3", "calls_syscall_stub", _L, "0xf3968",
                 "indirect syscall stub: mmap(0, 0x18, PROT_RWX, MAP_PRIVATE|ANON)"),
            _hop("L3", "calls_direct", _L, "0xf3988", "0x7778a8 - returns the decoder object"),
            _hop("L3", "calls_direct", _L, "0xf3994", "0x81f140 - a 12-byte record is allocated"),
            _hop("L3", "calls_vtable0", _L, "0xf39c4", "the decode loop calls *obj once per byte (23 iterations)"),
            _hop("L4", "finds_class", _L, "0xf39e8", "FindClass on the 23 decoded bytes -> 'com/snake/helper/Native'"),
            _hop("L4", "registers_natives", _L, "0xf3a0c", "RegisterNatives(env, jclass, 0x828ee8, 10)"),
        ],
    ),
    ChainDef(
        id="CH-05", layer_path="L3 -> L4 -> L1",
        title="registration site 0xb40a8 -> com/snake/helper/flagger",
        title_th="registration site 0xb40a8 -> com/snake/helper/flagger",
        goal="The full instruction walk from the first call in the window to the"
             " RegisterNatives blr, ending at the dex class it is attributed to.",
        hops=[
            _hop("L3", "calls_syscall", _L, "0xb3fe4", "svc #53 fchmodat before anything else"),
            _hop("L3", "calls_plt", _L, "0xb4018", "FUN_0091ad58 (Ghidra)"),
            _hop("L3", "calls_syscall_stub", _L, "0xb403c",
                 "indirect syscall stub: mmap(0, 4, PROT_RWX, MAP_PRIVATE|ANON)"),
            _hop("L3", "calls_direct", _L, "0xb4050", "0x777fb0 - returns the decoder object"),
            _hop("L3", "calls_direct", _L, "0xb405c", "0x81f140 - a 12-byte record is allocated"),
            _hop("L3", "calls_vtable0", _L, "0xb407c", "the decode loop calls *obj once per byte (3 iterations)"),
            _hop("L4", "stages_fnptr", _L, "0xb40b0",
                 "stp x21, x9, [sp, #0x40] - the fnPtr written into the table is 0x81eeb0"),
            _hop("L4", "registers_natives", _L, "0xb40b4", "RegisterNatives(env, jclass, sp+0x20, 2)"),
        ],
    ),
    ChainDef(
        id="CH-07", layer_path="L3 -> L4 -> L1",
        title="registration site 0xb0140 -> com/snake/helper/Native",
        title_th="registration site 0xb0140 -> com/snake/helper/Native",
        goal="The full instruction walk from the first call in the window to the"
             " RegisterNatives blr, ending at the dex class it is attributed to.",
        hops=[
            _hop("L3", "calls_syscall_stub", _L, "0xb0068",
                 "indirect syscall stub with 6 staged arguments (mmap-shaped)"),
            _hop("L3", "calls_direct", _L, "0xb0088", "0x7775d8 - returns the decoder object"),
            _hop("L3", "calls_direct", _L, "0xb0094", "0x81f140 - a 12-byte record is allocated"),
            _hop("L3", "calls_vtable0", _L, "0xb00c4", "the decode loop calls *obj once per byte (8 iterations)"),
            _hop("L3", "calls_direct", _L, "0xb00e4",
                 "0x81f250 - memcmp-shaped (ptr, ptr, 8) -> int, gates the registration"),
            _hop("L4", "registers_natives", _L, "0xb0144", "RegisterNatives(env, jclass, sp+0x38, 1)"),
            _hop("L4", "calls_jni_slot", _L, "0xb018c", "ExceptionClear on the failure path"),
        ],
    ),
    ChainDef(
        id="CH-06", layer_path="L4 -> L3",
        title="the one statically recoverable native handler (.mytext)",
        title_th="native handler ตัวเดียวที่กู้คืนได้จาก static (.mytext)",
        goal="Follow the single fnPtr that survives static analysis: registered by site"
             " 0xb40a8, living in the hand-named .mytext section, calling"
             " FromReflectedMethod and then forwarding into .text at 0xb01c4.",
        hops=[
            _hop("L4", "stages_fnptr", _L, "0xb40b0",
                 "window 2 stages the pointer: adrp 0x81e000 + add #0xeb0 -> 0x81eeb0,"
                 " stored into JNINativeMethod[1].fnPtr"),
            _hop("L2", "calls_entry_point", "android-runtime", "",
                 "ART later calls that fnPtr - 0x81eeb0 decodes as `ret`, the real body opens at 0x81eeb4",
                 dst_module="libengine.so", dst_offset="0x81eeb0"),
            _hop("L4", "calls_jni_slot", _L, "0x81eed4",
                 "the body converts its 4th argument: FromReflectedMethod(env, x3)"),
            _hop("L3", "calls_direct", _L, "0x81eee4",
                 "and forwards (env, saved x2, reflected Method) into .text at 0xb01c4"),
        ],
    ),
    ChainDef(
        id="CH-08", layer_path="L1 -> L4",
        title="20 Java invoke sites -> the 13 registered natives",
        title_th="invoke site ฝั่ง Java 20 จุด -> native 13 ตัวที่ถูก register",
        goal="The Java side of the bridge: every dex offset that invokes a class whose"
             " methods are bound by RegisterNatives. Sorted by offset, so the obfuscated"
             " androidx.appcompat.view.menu.* callers can be walked in file order.",
        generator="dex_invokes",
    ),
    ChainDef(
        id="CH-09", layer_path="L1 -> L2 -> L6",
        title="the Flutter half of the same mechanism",
        title_th="ฝั่ง Flutter ใช้กลไกเดียวกัน",
        goal="libflutter.so exports no Java_* symbol either, yet the dex declares 41"
             " FlutterJNI natives - so the engine uses RegisterNatives too. Same shape,"
             " different library, which is why the 13 custom natives are not special.",
        hops=[
            _hop("L1", "invokes_loader", "classes.dex", "0x2bafda",
                 "FlutterJNI.loadLibrary() invokes System.loadLibrary('flutter')"),
            _hop("L2", "loads_library", "android-runtime", "",
                 "the loader maps lib/arm64-v8a/libflutter.so", dst_module="libflutter.so"),
            _hop("L6", "calls_entry_point", "android-runtime", "",
                 "the engine's own JNI_OnLoad binds FlutterJNI's 41 natives the same way",
                 dst_module="libflutter.so"),
        ],
    ),
    ChainDef(
        id="CH-10", layer_path="L5 -> L6",
        title="Dart platform-channel handlers and the engine symbols they run on",
        title_th="handler ของ Dart platform channel และสัญลักษณ์ engine ที่มันวิ่งอยู่",
        goal="The Dart end of the bridge: the 3 MethodCall closures blutter found in the"
             " C2 library, each with a code offset and an object-pool slot, plus the 11"
             " PlatformConfigurationNativeApi names the snapshot resolves against"
             " libflutter.so (both offsets given).",
        generator="dart_handlers",
    ),
    ChainDef(
        id="CH-11", layer_path="L5",
        title="Dart instruction-level call edges (fan-in ranking)",
        title_th="call edge ระดับ instruction ของ Dart (จัดอันดับตาม fan-in)",
        goal="blutter's disassembly yields real instruction offsets for the Dart half."
             " The 12 hottest call targets are listed here; the complete edge set lives"
             " in call_linkage.csv (layer L5).",
        generator="dart_hot12",
    ),
]


# --------------------------------------------------------------------------
# generators for computed chains
# --------------------------------------------------------------------------

_CH08_TEXT = ("มี 11 declaration: 10 ตัวถูกผูกโดย site ที่ 0xf3a08 (ความยาวชื่อจาก FindClass = 23)"
              " และ 1 ตัวโดย site ที่ 0xb0140 (ขอบเขต decode loop = 8 -> pjowqpxe)")

_CH10_HANDLERS = [
    ("0x3910", "0x504300", "_pfc", "_dX"),
    ("0x2cd8", "0x50e170", "_cec", "_hX"),
    ("0x2ce8", "0x50dad8", "_eec", "_hX"),
]


def _gen_init_array(graph: CallGraph, bundle: Optional[str]) -> List[Hop]:
    edges = sorted(graph.find_edges(layer="L2", kind="loader_init_call"),
                   key=lambda e: e.hop)
    shared: Optional[str] = None
    if bundle:
        try:
            frag = load_fragments_json(bundle)
            inits = frag["libengine"]["init_array"]
            shared = inits[0]["prologue"] if inits else None
            prologues = {e["slot"].lower(): e["prologue"] for e in inits}
        except Exception:
            prologues = {}
    else:
        prologues = {}
    hops = []
    for e in edges:
        same = (prologues.get(e.src_offset, shared) == shared) if shared else e.hop <= 37
        text = (f"ลำดับที่ {e.hop - 1}: ใช้ prologue 16 ไบต์ร่วมกับอีก 36 ตัว" if same
                else f"ลำดับที่ {e.hop - 1}: prologue ของตัวเอง ไม่อยู่ในกลุ่ม 37 ตัว")
        hops.append(Hop(match={"layer": "L2", "kind": "loader_init_call",
                               "src_module": "libengine.so", "src_offset": e.src_offset}, text=text))
    return hops


def _gen_dex_invokes(graph: CallGraph, bundle: Optional[str]) -> List[Hop]:
    edges = sorted(graph.find_edges(layer="L1", kind="invokes_native_class"),
                   key=lambda e: hex_int(e.src_offset) or 0)
    return [Hop(match={"layer": "L1", "kind": "invokes_native_class",
                       "src_module": "classes.dex", "src_offset": e.src_offset},
                text=_CH08_TEXT) for e in edges]


def _gen_dart_handlers(graph: CallGraph, bundle: Optional[str]) -> List[Hop]:
    hops = []
    for slot, addr, name, cls in _CH10_HANDLERS:
        hops.append(Hop(
            match={"layer": "L5", "kind": "dart_instantiates_closure",
                   "src_module": "libapp.so!pp", "src_offset": slot},
            text=f"MethodCall handler {name} ({cls}) @ {addr} - pool slot {slot}"))
    binds = sorted(graph.find_edges(layer="L6", kind="binds_engine_symbol"),
                   key=lambda e: hex_int(e.src_offset) or 0)
    for e in binds:
        hops.append(Hop(
            match={"layer": "L6", "kind": "binds_engine_symbol",
                   "src_module": "libapp.so", "src_offset": e.src_offset},
            text=f"{e.src_name}: libapp.so+{e.src_offset} <-> libflutter.so+{e.dst_offset}"))
    return hops


def _gen_dart_hot12(graph: CallGraph, bundle: Optional[str]) -> List[Hop]:
    from .schema import offset_int  # local: avoid circulars in docs builds

    counts: Dict[Tuple[str, str, str], List[Any]] = {}
    for e in graph.find_edges(layer="L5"):
        if e.kind not in ("dart_call", "dart_tail_call"):
            continue
        key = (e.dst_module, e.dst_offset, e.dst_name)
        counts.setdefault(key, []).append(e)
    ranked = sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0][1] or "", kv[0][0]))
    hops = []
    for (mod, off, _name), callers in ranked[:12]:
        rep = min(callers, key=lambda e: offset_int(e.src_offset)
                  if offset_int(e.src_offset) is not None else 10**18)
        hops.append(Hop(
            match={"layer": "L5", "kind": rep.kind,
                   "src_module": rep.src_module, "src_offset": rep.src_offset},
            text=f"fan-in {len(callers)} - one of its call sites is shown at the left"))
    return hops


_GENERATORS = {
    "init_array": _gen_init_array,
    "dex_invokes": _gen_dex_invokes,
    "dart_handlers": _gen_dart_handlers,
    "dart_hot12": _gen_dart_hot12,
}


# --------------------------------------------------------------------------
# resolver
# --------------------------------------------------------------------------

def _matches(edge: Any, match: Dict[str, str]) -> bool:
    for field, want in match.items():
        got = getattr(edge, field, "")
        if field in ("src_offset", "dst_offset"):
            got, want = norm_offset(got), norm_offset(want)
        if got != want:
            return False
    return True


def resolve_all(
    graph: CallGraph,
    bundle: Optional[str] = None,
    chain_defs: Optional[List[ChainDef]] = None,
) -> Tuple[List[Chain], List[Dict[str, Any]]]:
    """Bind every hop to an edge id. Returns ``(chains, missing)``."""
    out: List[Chain] = []
    missing: List[Dict[str, Any]] = []
    for cdef in (chain_defs if chain_defs is not None else CHAIN_DEFS):
        hops = list(cdef.hops)
        if cdef.generator:
            hops = _GENERATORS[cdef.generator](graph, bundle)
        resolved: List[Hop] = []
        for n, hop in enumerate(hops, 1):
            cands = [e for e in graph.edges if _matches(e, hop.match)]
            h = Hop(match=dict(hop.match), text=hop.text, n=n)
            if len(cands) == 1:
                h.edge_id = cands[0].edge_id
            else:
                missing.append({"chain": cdef.id, "n": n, "match": hop.match,
                                "candidates": len(cands), "text": hop.text})
            resolved.append(h)
        out.append(Chain(id=cdef.id, layer_path=cdef.layer_path, title=cdef.title,
                         title_th=cdef.title_th, goal=cdef.goal, hops=resolved))
    return out, missing

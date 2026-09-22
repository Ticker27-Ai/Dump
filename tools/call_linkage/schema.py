"""Core schema: layers, edge kinds, nodes, edges, chains.

Every hop reads ``caller instruction -> callee`` and is addressed by
``module+offset`` of the *calling* instruction. Offsets are file virtual
addresses (Ghidra's +0x100000 image base is already rebased in fragments).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------
# Layers
# --------------------------------------------------------------------------

LAYERS: Dict[str, Dict[str, str]] = {
    "L1": {"name": "dex", "description": "Dalvik bytecode - classes.dex invoke/loader offsets"},
    "L2": {"name": "loader", "description": "ELF loader - .init_array slots and exported entry points"},
    "L3": {"name": "native", "description": "libengine.so machine code - decoded AArch64 instructions"},
    "L4": {"name": "jni", "description": "JNI boundary - JNIEnv function-table slots, RegisterNatives"},
    "L5": {"name": "dart", "description": "Dart AOT snapshot - libapp.so instruction-level call edges"},
    "L6": {"name": "engine", "description": "Flutter engine - libflutter.so symbols the snapshot binds to"},
}
LAYER_ORDER = ["L1", "L2", "L3", "L4", "L5", "L6"]

# --------------------------------------------------------------------------
# Edge kinds (24)
# --------------------------------------------------------------------------

KINDS: Dict[str, str] = {
    "invokes_loader": "dex invoke-static of java.lang.System.loadLibrary",
    "loads_library": "the loader maps a .so named by that invoke",
    "calls_entry_point": "dlopen hands control to an exported entry point",
    "invokes_native_class": "dex invoke-* into a class that declares ACC_NATIVE methods",
    "declares_native": "the class declares a native method (no Java body)",
    "loader_init_call": "the dynamic loader calls a .init_array constructor",
    "calls_direct": "bl to a fixed offset inside the same module",
    "calls_plt": "bl to a PLT stub, i.e. an imported function",
    "calls_jni_slot": "blr through a JNIEnv function-table slot",
    "calls_vtable0": "blr through *obj, i.e. a virtual entry resolved at run time",
    "calls_syscall_stub": "blr to an indirect-syscall stub (syscall args staged in x0-x5, nr in w6)",
    "calls_syscall": "svc #0 - a direct syscall, number staged in w8/x8",
    "jumps_into_generated": "blr/br into code that the function itself wrote at run time",
    "computes_branch": "br to a target computed from a relative-offset table",
    "writes_generated_code": "store of a synthesised AArch64 opcode into a fresh RWX page",
    "stages_fnptr": "store of a function pointer into a JNINativeMethod[] entry",
    "registers_natives": "the RegisterNatives call itself (nMethods known, fnPtrs runtime)",
    "finds_class": "the FindClass call that produces the jclass argument",
    "binds_fnptr_to_dex": "a recovered fnPtr attributed to a declared dex native",
    "rejected_slot_load": "a 0x6b8-pattern load that is NOT a JNIEnv call (audit trail)",
    "dart_call": "bl inside the Dart AOT snapshot",
    "dart_tail_call": "b (tail branch) to a Dart runtime stub",
    "dart_instantiates_closure": "ldr xN,[PP,#slot] of an AnonymousClosure - allocates a handler",
    "binds_engine_symbol": "a snapshot name that libflutter.so must export/hold",
}

# --------------------------------------------------------------------------
# Confidence levels
# --------------------------------------------------------------------------

CONFIDENCE = ("proven", "strong", "probable", "candidate")
CONFIDENCE_ORDER = {c: i for i, c in enumerate(CONFIDENCE)}


# --------------------------------------------------------------------------
# Offset helpers
# --------------------------------------------------------------------------

def norm_offset(off: Any) -> str:
    """Normalise an offset to lowercase ``0x...`` (no leading zeros) or ``""``."""
    if off is None:
        return ""
    s = str(off).strip().lower()
    if s in ("", "-", "none", "null"):
        return ""
    try:
        return hex(int(s, 0))
    except ValueError:
        return s


def offset_int(off: Any) -> Optional[int]:
    """Parse an offset to int, or None when absent/unparseable."""
    s = norm_offset(off)
    if not s:
        return None
    try:
        return int(s, 16)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Nodes / edges
# --------------------------------------------------------------------------

@dataclass
class Node:
    id: str
    layer: str = ""
    module: str = ""
    kind: str = ""
    name: str = ""
    offset: str = ""
    section: str = ""
    attrs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "layer": self.layer,
            "module": self.module,
            "kind": self.kind,
            "name": self.name,
            "offset": self.offset or None,
            "section": self.section,
            "attrs": self.attrs,
        }


@dataclass
class Edge:
    edge_id: str = ""
    chain: str = ""
    hop: int = 0
    layer: str = ""
    kind: str = ""
    src_module: str = ""
    src_offset: str = ""
    src_name: str = ""
    src_insn: str = ""
    dst_module: str = ""
    dst_offset: str = ""
    dst_name: str = ""
    resolved_by: str = ""
    confidence: str = ""
    evidence: str = ""
    source: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        self.src_offset = norm_offset(self.src_offset)
        self.dst_offset = norm_offset(self.dst_offset)
        if isinstance(self.hop, str):
            self.hop = int(self.hop or 0)

    def key(self) -> Tuple[str, str, str, str, str, str]:
        """Semantic identity (stable across rebuilds, unlike edge_id)."""
        return (
            self.layer,
            self.kind,
            self.src_module,
            self.src_offset,
            self.dst_module,
            self.dst_offset,
        )

    def dedup_key(self) -> Tuple[str, ...]:
        """Identity for duplicate detection: names included, because offset-less
        declaration edges (e.g. 13x ``declares_native``) legitimately share one
        ``key()`` and differ only by method name."""
        return self.key() + (self.src_name, self.dst_name)

    def validate(self) -> List[str]:
        problems: List[str] = []
        if self.layer not in LAYERS:
            problems.append(f"unknown layer {self.layer!r}")
        if self.kind not in KINDS:
            problems.append(f"unknown kind {self.kind!r}")
        if self.confidence and self.confidence not in CONFIDENCE:
            problems.append(f"unknown confidence {self.confidence!r}")
        if not self.src_module:
            problems.append("empty src_module")
        if not self.dst_module:
            problems.append("empty dst_module")
        return problems

    def to_csv_row(self) -> Dict[str, str]:
        return {
            "edge_id": self.edge_id,
            "chain": self.chain,
            "hop": str(self.hop),
            "layer": self.layer,
            "kind": self.kind,
            "src_module": self.src_module,
            "src_offset": self.src_offset,
            "src_name": self.src_name,
            "src_insn": self.src_insn,
            "dst_module": self.dst_module,
            "dst_offset": self.dst_offset,
            "dst_name": self.dst_name,
            "resolved_by": self.resolved_by,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source": self.source,
            "note": self.note,
        }

    def to_dict(self) -> Dict[str, Any]:
        d = self.to_csv_row()
        d["hop"] = self.hop
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Edge":
        return cls(
            edge_id=str(d.get("edge_id", "")),
            chain=str(d.get("chain", "")),
            hop=int(str(d.get("hop", "0") or "0")),
            layer=str(d.get("layer", "")),
            kind=str(d.get("kind", "")),
            src_module=str(d.get("src_module", "")),
            src_offset=str(d.get("src_offset", "")),
            src_name=str(d.get("src_name", "")),
            src_insn=str(d.get("src_insn", "")),
            dst_module=str(d.get("dst_module", "")),
            dst_offset=str(d.get("dst_offset", "")),
            dst_name=str(d.get("dst_name", "")),
            resolved_by=str(d.get("resolved_by", "")),
            confidence=str(d.get("confidence", "")),
            evidence=str(d.get("evidence", "")),
            source=str(d.get("source", "")),
            note=str(d.get("note", "")),
        )


@dataclass
class Hop:
    """One step of a chain: which edge (by semantic key) + narrative text."""

    match: Dict[str, str]
    text: str = ""
    n: int = 0
    edge_id: str = ""  # filled by chains.resolve_all()


@dataclass
class Chain:
    id: str
    layer_path: str = ""
    title: str = ""
    title_th: str = ""
    goal: str = ""
    hops: List[Hop] = field(default_factory=list)


# --------------------------------------------------------------------------
# Node synthesis (deterministic ids shared by store/graph/render)
# --------------------------------------------------------------------------

def node_id_for(module: str, name: str, offset: str) -> str:
    """Endpoint -> node id.

    * ``libapp.so!pp`` + slot  -> ``libapp.so!pp!0x...`` (pool slot)
    * offset present           -> ``module!0x...``         (instruction/slot)
    * otherwise                -> ``module#name``           (named entity)
    """
    module = (module or "").strip()
    name = (name or "").strip()
    off = norm_offset(offset)
    if module == "libapp.so!pp" and off:
        return f"libapp.so!pp!{off}"
    if off:
        return f"{module}!{off}"
    return f"{module}#{name}"


def infer_node_kind(
    module: str,
    name: str,
    offset: str,
    edge_layer: str = "",
    edge_kind: str = "",
    side: str = "src",
) -> str:
    """Best-effort node kind mirroring the committed graph vocabulary."""
    off = norm_offset(offset)
    name = (name or "").strip()
    if module == "libapp.so!pp":
        return "pool_slot"
    if module == "kernel":
        return "syscall"
    if module == "android-runtime":
        return "jni_slot" if off else "runtime"
    if edge_kind == "binds_engine_symbol" and side == "src":
        return "string"
    if edge_kind in ("writes_generated_code", "jumps_into_generated", "computes_branch") and side == "dst":
        return "page"
    if edge_kind == "loads_library" and side == "dst":
        return "module"
    if module == "classes.dex":
        if off:
            return "instruction"
        if name.startswith("L") and ";-" in name or ";->" in name:
            return "dex_method"
        if name.startswith("L") and name.endswith(";"):
            return "class"
        return "function"
    if off and side == "src":
        return "instruction"
    if off and side == "dst":
        # named code target (sub_*, JNI_OnLoad, _INIT_*) vs bare address
        if name and not name.startswith("0x"):
            return "function"
        return "instruction"
    return "function"


def node_layer_for(module: str, edge_layer: str) -> str:
    if module == "classes.dex":
        return "L1"
    if module in ("android-runtime", "kernel"):
        return edge_layer or "L2"
    if module == "libengine.so":
        return edge_layer or "L3"
    if module in ("libapp.so", "libapp.so!pp"):
        return "L5"
    if module == "libflutter.so":
        return "L6"
    return edge_layer or ""

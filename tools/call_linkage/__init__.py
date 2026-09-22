"""Call-linkage (สายการเรียก) graph toolkit.

Links instruction/offset -> callee across layers:

    L1 dex    : classes.dex invoke / loader offsets
    L2 loader : ELF loader (.init_array, entry points)
    L3 native : libengine.so decoded AArch64 instructions
    L4 jni    : JNIEnv slots, RegisterNatives boundary
    L5 dart   : libapp.so Dart AOT call edges
    L6 engine : libflutter.so symbols the snapshot binds to

Typical flows::

    from tools.call_linkage import build, chains, verify, render, graph as gmod

    edges, diag = build.build_from_fragments("Codes/SnakeLogic")
    g = gmod.CallGraph(edges)
    resolved, missing = chains.resolve_all(g)
    results = verify.run_all(g, "Codes/SnakeLogic")

Extension points (ต่อยอด)::

* ``annotations.EXTRA_ANNOTATIONS`` -- append a new instruction/offset hop
* ``chains.CHAIN_DEFS`` -- append a new ``ChainDef`` (CH-12, ...)
* ``build.build_from_fragments(..., extra_annotations=[...])``
"""

from .schema import (  # noqa: F401
    LAYERS,
    LAYER_ORDER,
    KINDS,
    CONFIDENCE,
    CONFIDENCE_ORDER,
    Node,
    Edge,
    Hop,
    Chain,
    norm_offset,
    offset_int,
    node_id_for,
    infer_node_kind,
)
from .graph import CallGraph  # noqa: F401

__all__ = [
    "LAYERS",
    "LAYER_ORDER",
    "KINDS",
    "CONFIDENCE",
    "CONFIDENCE_ORDER",
    "Node",
    "Edge",
    "Hop",
    "Chain",
    "norm_offset",
    "offset_int",
    "node_id_for",
    "infer_node_kind",
    "CallGraph",
]

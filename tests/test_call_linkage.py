#!/usr/bin/env python3
"""Unit tests for tools/call_linkage (stdlib unittest, no dependencies).

Run (from repo root):
    python3 -m unittest tests.test_call_linkage -v
    # or directly:
    python3 tests/test_call_linkage.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.call_linkage import build as B
from tools.call_linkage import chains as C
from tools.call_linkage import verify as V
from tools.call_linkage.graph import CallGraph
from tools.call_linkage.parse import (
    load_fragments_json,
    parse_asm_listing,
    parse_f2,
    parse_f6_api_pairs,
)

BUNDLE = ROOT / "Codes" / "SnakeLogic"
BASELINE = BUNDLE / "call_linkage.csv"

EXPECTED_LAYER_TOTALS = {"L1": 37, "L2": 48, "L3": 35, "L4": 13, "L5": 546, "L6": 12}


class ParseTests(unittest.TestCase):
    def test_f2_counts(self):
        f2 = parse_f2(BUNDLE / "fragments" / "F2_dex_natives.txt")
        self.assertEqual(len(f2["natives"]), 13)
        self.assertEqual(len(f2["callers"]), 20)
        self.assertEqual(len(f2["loaders"]), 2)
        offs = {c["offset"] for c in f2["callers"]}
        self.assertIn("0xed930", offs)
        self.assertIn("0x38e7ec", offs)

    def test_f6_pairs(self):
        pairs = parse_f6_api_pairs(BUNDLE / "fragments" / "F6_libflutter_version.txt")
        self.assertEqual(len(pairs), 11)
        names = {p["name"] for p in pairs}
        self.assertIn("PlatformConfigurationNativeApi::SendPlatformMessage", names)

    def test_asm_listings_cover_registration_windows(self):
        f4d = parse_asm_listing(BUNDLE / "fragments" / "F4d_libengine_regnatives_windows.asm")
        self.assertEqual(set(f4d["sites"]), {"0xb0140", "0xb40a8", "0xf3a08"})
        self.assertEqual(f4d["insns"]["0xb0144"]["mnemonic"], "blr")
        self.assertEqual(f4d["insns"]["0xf3a0c"]["text"], "blr x8")
        f4c = parse_asm_listing(BUNDLE / "fragments" / "F4c_libengine_JNI_OnLoad.asm")
        self.assertIn("0xf3fa0", f4c["insns"])
        self.assertIn("0xf4018", f4c["insns"])
        f4b = parse_asm_listing(BUNDLE / "fragments" / "F4b_libengine_mytext.asm")
        self.assertEqual(f4b["insns"]["0x81eed4"]["text"], "blr x8")

    def test_fragments_json_census(self):
        frag = load_fragments_json(BUNDLE)
        customs = [m for m in frag["dex"]["native_methods"] if m.get("custom")]
        self.assertEqual(len(customs), 13)
        self.assertEqual(len(frag["libengine"]["init_array"]), 44)
        self.assertEqual(len(frag["libengine"]["register_natives_sites"]), 3)
        self.assertEqual(sum(s["count"] for s in frag["libengine"]["register_natives_sites"]), 13)


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.edges, cls.diag = B.build_from_fragments(BUNDLE, baseline_csv=BASELINE)
        cls.graph = CallGraph(cls.edges)

    def test_total_edges(self):
        self.assertEqual(len(self.edges), 691)

    def test_layer_totals(self):
        self.assertEqual(self.graph.stats()["by_layer"], EXPECTED_LAYER_TOTALS)

    def test_provenance_split(self):
        self.assertEqual(self.diag["curated"], 57)
        self.assertEqual(self.diag["imported_l5"], 546)
        self.assertEqual(
            self.diag["derived_l1_declares"] + self.diag["derived_l1_invokes"]
            + self.diag["derived_l2_init"] + self.diag["derived_l6_binds"], 88)

    def test_ids_deterministic(self):
        edges2, _ = B.build_from_fragments(BUNDLE, baseline_csv=BASELINE)
        self.assertEqual([e.edge_id for e in self.edges], [e.edge_id for e in edges2])
        self.assertEqual([e.key() for e in self.edges], [e.key() for e in edges2])

    def test_nodes_match_committed_count(self):
        self.assertEqual(len(self.graph.nodes), 1048)


class ChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        edges, _ = B.build_from_fragments(BUNDLE, baseline_csv=BASELINE)
        cls.graph = CallGraph(edges)
        cls.resolved, cls.missing = C.resolve_all(cls.graph, bundle=str(BUNDLE))

    def test_all_chains_resolve(self):
        self.assertEqual(len(self.resolved), 11)
        self.assertEqual(self.missing, [])
        self.assertEqual(sum(len(c.hops) for c in self.resolved), 136)

    def test_ch11_hot_target(self):
        ch11 = next(c for c in self.resolved if c.id == "CH-11")
        first = self.graph.by_id[ch11.hops[0].edge_id]
        self.assertEqual(first.dst_offset, "0x554734")
        self.assertIn("fan-in 80", ch11.hops[0].text)


class QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        edges, _ = B.build_from_fragments(BUNDLE, baseline_csv=BASELINE)
        cls.graph = CallGraph(edges)

    def test_fan_in_top(self):
        top = self.graph.top_targets(layer="L5", top=3)
        self.assertEqual(top[0]["offset"], "0x554734")
        self.assertEqual(top[0]["fan_in"], 80)

    def test_trace_finds_registration(self):
        res = self.graph.trace("libengine.so", "0xf3a08", depth=1)
        kinds = {e.kind for e in res["edges"]}
        self.assertIn("binds_fnptr_to_dex", kinds)

    def test_search(self):
        hits = self.graph.search("pjowqpxe")
        self.assertGreaterEqual(len(hits), 2)


class VerifyTests(unittest.TestCase):
    def test_no_failures(self):
        edges, _ = B.build_from_fragments(BUNDLE, baseline_csv=BASELINE)
        graph = CallGraph(edges)
        resolved, _ = C.resolve_all(graph, bundle=str(BUNDLE))
        results = V.run_all(graph, BUNDLE, baseline_csv=BASELINE, chains=resolved)
        fails = [r for r in results if r["status"] == "FAIL"]
        self.assertEqual(fails, [])
        self.assertGreaterEqual(len(results), 14)


class ExtensionTests(unittest.TestCase):
    def test_add_annotation_and_chain(self):
        extra = [{
            "layer": "L3", "kind": "calls_direct",
            "src_module": "libengine.so", "src_offset": "0xf446c",
            "src_name": "test demo", "src_insn": "bl #0x81f0e0",
            "dst_module": "libengine.so", "dst_offset": "0x81f0e0",
            "dst_name": "strlen-test", "resolved_by": "unit test",
            "confidence": "candidate", "evidence": "test", "source": "test",
            "chain": "CH-99", "hop": 1,
        }]
        edges, diag = B.build_from_fragments(BUNDLE, baseline_csv=BASELINE,
                                             extra_annotations=extra)
        self.assertEqual(diag["total"], 692)
        graph = CallGraph(edges)
        demo = C.ChainDef(
            id="CH-99", layer_path="L3", title="demo",
            hops=[C._hop("L3", "calls_direct", "libengine.so", "0xf446c", "demo")])
        resolved, missing = C.resolve_all(graph, bundle=str(BUNDLE),
                                          chain_defs=C.CHAIN_DEFS + [demo])
        self.assertEqual(len(resolved), 12)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()

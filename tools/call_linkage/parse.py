"""Fragment parsers: fragments/*.txt + decoded *.asm listings + fragments.json.

Only stdlib is used. Every parser returns plain dicts/lists so builders and
checks can consume them without depending on file layout details.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schema import norm_offset

HEX = r"0x[0-9a-fA-F]+"


# --------------------------------------------------------------------------
# Decoded AArch64 listings (F4b / F4c / F4d)
# --------------------------------------------------------------------------

_INSN_RE = re.compile(rf"^\s*({HEX})\s*:\s*([A-Za-z][\w.]*)\s*(.*?)\s*$")
_SITE_RE = re.compile(rf"^#####\s*site\s*@({HEX})\s+nMethods=(\d+)\s+table=(\S+)")


def parse_asm_listing(path: str | Path) -> Dict[str, Any]:
    """Parse ``0x....: mnemonic operands`` lines.

    Returns ``{"insns": {off: {"text","mnemonic","line"}}, "order": [off...],
    "sites": {site_off: {"nmethods": int, "table": str, "members": [off...]}}}``
    """
    path = Path(path)
    insns: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    sites: Dict[str, Dict[str, Any]] = {}
    current_site: Optional[str] = None
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        m_site = _SITE_RE.match(raw)
        if m_site:
            current_site = norm_offset(m_site.group(1))
            sites[current_site] = {
                "nmethods": int(m_site.group(2)),
                "table": m_site.group(3),
                "members": [],
            }
            continue
        m = _INSN_RE.match(raw)
        if not m:
            continue
        off = norm_offset(m.group(1))
        mnemonic = m.group(2)
        operands = re.sub(r"\s+", " ", m.group(3)).strip()
        text = mnemonic if not operands else f"{mnemonic} {operands}"
        insns[off] = {"text": text, "mnemonic": mnemonic, "line": lineno, "raw": raw.strip()}
        order.append(off)
        if current_site is not None:
            sites[current_site]["members"].append(off)
    return {"insns": insns, "order": order, "sites": sites, "file": str(path)}


def norm_insn(text: str) -> str:
    """Normalise an instruction for comparison (spacing/case/hex)."""
    text = re.sub(r"\s+", " ", (text or "").strip()).lower()
    text = re.sub(r"0x([0-9a-f]+)", lambda m: hex(int(m.group(1), 16)), text)
    text = re.sub(r"#\s*", "#", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    return text


# --------------------------------------------------------------------------
# F2: dex natives / loaders / callers (text form; offsets live here)
# --------------------------------------------------------------------------

_F2_CLASS_RE = re.compile(r"^\s*CLASS\s+(\S+)\s+JNI name:\s*(\S+)\s+(\d+)\s+native method")
_F2_NATIVE_RE = re.compile(r"^\s*native\s+(\S+)\s+(\S+)\s*$")
_F2_LOADER_RE = re.compile(r"^\s*@classes\.dex\+(0x[0-9a-fA-F]+)\s+(\S+->\S+)\s*$")
_F2_CALLER_RE = re.compile(r"^\s*<-\s*(\S+)\s+@(0x[0-9a-fA-F]+)\s*$")
_F2_CALLER_CLASS_RE = re.compile(r"^\s*(\S+);\s*:\s*(\d+)\s+distinct caller")


def parse_f2(path: str | Path) -> Dict[str, Any]:
    """Parse F2_dex_natives.txt -> natives, loaders (with offsets), callers."""
    natives: List[Dict[str, str]] = []
    loaders: List[Dict[str, str]] = []
    callers: List[Dict[str, str]] = []
    current_class = ""
    caller_class = ""
    enclosing = ""
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = _F2_CLASS_RE.match(raw)
        if m:
            current_class = m.group(1)
            continue
        m = _F2_NATIVE_RE.match(raw)
        if m and current_class:
            natives.append({"class": current_class, "sig": m.group(1), "name": m.group(2)})
            continue
        m = _F2_LOADER_RE.match(raw)
        if m:
            loaders.append({"offset": norm_offset(m.group(1)), "target": m.group(2),
                            "enclosing": "", "lib": "", "how": ""})
            continue
        if "enclosing method :" in raw and loaders and not loaders[-1]["enclosing"]:
            loaders[-1]["enclosing"] = raw.split(":", 1)[1].strip()
            continue
        if "library name" in raw and loaders and not loaders[-1]["lib"]:
            mm = re.search(r"'([^']+)'", raw)
            loaders[-1]["lib"] = mm.group(1) if mm else ""
            mm2 = re.search(r"\(([^)]+)\)\s*$", raw)
            loaders[-1]["how"] = mm2.group(1) if mm2 else ""
            continue
        m = _F2_CALLER_CLASS_RE.match(raw)
        if m:
            caller_class = m.group(1) + ";"
            continue
        m = _F2_CALLER_RE.match(raw)
        if m and caller_class:
            callers.append({"class": caller_class, "method": m.group(1),
                            "offset": norm_offset(m.group(2))})
    return {"natives": natives, "loaders": loaders, "callers": callers}


# --------------------------------------------------------------------------
# F1: APK inventory (module sizes for address-space checks)
# --------------------------------------------------------------------------

_F1_LIB_RE = re.compile(r"^\s*(lib/\S+\.so)\s+size=(\d+)\s+sha256=([0-9a-f]+)")


def parse_f1_lib_sizes(path: str | Path) -> Dict[str, int]:
    sizes: Dict[str, int] = {}
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = _F1_LIB_RE.match(raw)
        if m:
            sizes[m.group(1)] = int(m.group(2))
    return sizes


# --------------------------------------------------------------------------
# F5: libapp sections (.text range for Dart checks)
# --------------------------------------------------------------------------

_F5_SECTION_RE = re.compile(r"^\s*(\.\w+)\s+addr=(0x[0-9a-fA-F]+)\s+size=(\d+)")


def parse_f5_sections(path: str | Path) -> Dict[str, Dict[str, Any]]:
    sections: Dict[str, Dict[str, Any]] = {}
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = _F5_SECTION_RE.match(raw)
        if m:
            sections[m.group(1)] = {"addr": norm_offset(m.group(2)), "size": int(m.group(3))}
    return sections


# --------------------------------------------------------------------------
# F6: engine API pairs (libapp@off libflutter@off)
# --------------------------------------------------------------------------

_F6_PAIR_RE = re.compile(
    r"^\s*both\s+(\S+)\s+libapp@(0x[0-9a-fA-F]+)\s+libflutter@(0x[0-9a-fA-F]+)"
)


def parse_f6_api_pairs(path: str | Path) -> List[Dict[str, str]]:
    pairs: List[Dict[str, str]] = []
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = _F6_PAIR_RE.match(raw)
        if m:
            pairs.append({"name": m.group(1), "libapp": norm_offset(m.group(2)),
                          "libflutter": norm_offset(m.group(3))})
    return pairs


# --------------------------------------------------------------------------
# F4: defined dynamic exports (name -> addr)
# --------------------------------------------------------------------------

_F4_EXPORT_RE = re.compile(rf"^\s*({HEX})\s+STT_\w+\s+(\S+)\s*$")


def parse_f4_exports(path: str | Path) -> Dict[str, str]:
    exports: Dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = _F4_EXPORT_RE.match(raw)
        if m:
            exports[m.group(2)] = norm_offset(m.group(1))
    return exports


# --------------------------------------------------------------------------
# fragments.json + small helpers
# --------------------------------------------------------------------------

def load_fragments_json(bundle: str | Path) -> Dict[str, Any]:
    return json.loads((Path(bundle) / "fragments" / "fragments.json").read_text(encoding="utf-8"))


def hex_int(value: Any) -> Optional[int]:
    """int from hex str / decimal str / int."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip().lower()
    try:
        return int(s, 0)
    except ValueError:
        return None


def to_hex(value: Any) -> str:
    v = hex_int(value)
    return hex(v) if v is not None else ""

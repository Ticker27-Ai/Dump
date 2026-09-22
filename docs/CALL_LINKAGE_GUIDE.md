# คู่มือ Call Linkage (สายการเรียก) — เชื่อม instruction/offset พร้อมต่อยอด

โครงโค้ด `tools/call_linkage/` สร้างกราฟ **instruction → callee** ข้าม 6 layers
(L1 dex → L2 loader → L3 native → L4 JNI → L5 Dart → L6 engine) จากชุดหลักฐาน
`Codes/SnakeLogic/` โดย rebuild ได้ **691 edges / 1048 nodes / 11 chains / 136 hops**
ตรงกับ baseline ที่ยืนยันแล้ว 100% (semantic parity) และ verify ผ่าน 15/15 checks

> ใช้ Python มาตรฐานอย่างเดียว (stdlib) — ไม่ต้องติดตั้งอะไรเพิ่ม

---

## 1. เริ่มต้นเร็ว (Quickstart)

```bash
# rebuild ทั้งกราฟ + verify + render รายงาน ลง build/
python3 tools/build_call_linkage.py --out build --compare

# ผลลัพธ์:
#   build/call_linkage.csv   — edge ทั้งหมด (เปิดด้วย Excel/pandas ได้)
#   build/call_linkage.json  — nodes + edges + chains + checks + fan-in
#   build/CALL_LINKAGE.md    — รายงานพร้อมตาราง + mermaid ทุก chain
#   build/CALL_LINKAGE_OVERVIEW.mmd — ภาพรวมสถาปัตยกรรม

# query กราฟ
python3 tools/query_linkage.py build/call_linkage.json stats
python3 tools/query_linkage.py build/call_linkage.json trace --module libengine.so --offset 0xf3a08
python3 tools/query_linkage.py build/call_linkage.json fan-in --layer L5 --top 12
python3 tools/query_linkage.py build/call_linkage.json search pjowqpxe
python3 tools/query_linkage.py build/call_linkage.json chain CH-04

# รันเทสต์ (16 tests)
python3 -m unittest tests.test_call_linkage -v
```

---

## 2. แผนผังไฟล์ (ต่อยอดตรงไหน)

```text
tools/
  build_call_linkage.py     # CLI: rebuild → verify → render
  query_linkage.py          # CLI: stats/trace/fan-in/search/chain/paths/node
  codegen_annotations.py    # สร้าง annotations.py ใหม่จาก CSV ที่เชื่อถือได้
  call_linkage/
    schema.py       # Layer/Kind/Confidence, Node/Edge/Chain, node-id + kind inference
    parse.py        # อ่าน fragments (F1/F2/F4/F5/F6, *.asm listings, fragments.json)
    annotations.py  # ★ ตาราง hops ที่ต้องใช้วิจารณญาณนักวิเคราะห์ (L3/L4 + fixed edges)
    build.py        # ★ ประกอบ edges: derived + curated + imported → assign E-ids
    chains.py       # ★ นิยาม CH-01..CH-11 + resolve hops → edge_id
    graph.py        # CallGraph: index + trace/paths/fan-in/search
    store.py        # load/save CSV+JSON, node synthesis, fingerprint
    verify.py       # ★ ชุดตรวจสอบ 15 ข้อ
    render.py       # mermaid + markdown + semantic diff
tests/test_call_linkage.py  # 16 tests (parse/build/chains/query/verify/extension)
```

---

## 3. ที่มาของ edge แต่ละกลุ่ม (ซื่อสัตย์กับหลักฐาน)

| กลุ่ม | จำนวน | สร้างจาก | ไฟล์ |
|---|---|---|---|
| **derived** L1 declares/invokes | 33 | `fragments.json` + parse `F2_dex_natives.txt` (offsets อยู่ตรงนี้) | `build.py` |
| **derived** L2 init_array | 44 | `fragments.json:libengine.init_array` | `build.py` |
| **derived** L6 engine symbols | 11 | parse `F6_libflutter_version.txt` (`both ... libapp@.. libflutter@..`) | `build.py` |
| **curated** L3/L4 + fixed L1/L2/L6 | 57 | `annotations.py` (ดึงจาก CSV ที่ยืนยันแล้ว) + **ตรวจ mnemonic กับ F4b/F4c/F4d ทุกแถว** | `annotations.py` + `verify.py` |
| **imported** L5 Dart | 546 | คัดลอกตรงจาก baseline CSV (เพราะ `output/blutter/asm/*.dart` ไม่ได้อยู่ใน bundle) | `build.py` |

> ถ้าวันหนึ่งได้ `asm/*.dart` มา: เขียน parser ใน `parse.py` + builder ใน `build.py`
> แล้วลบการ import L5 ทิ้ง — โครง `verify`/`chains`/`render` ใช้ต่อได้เลย

---

## 4. วิธีต่อยอด A: เพิ่ม hop ใหม่ (instruction/offset ใหม่)

สมมติเจอ `bl` ใหม่ที่ `libengine.so+0xXXXX` อยากลาก edge เข้ากราฟ:

**ขั้น 1 — เขียน annotation** (ไฟล์ JSON แยก ไม่ต้องแตะโค้ด):

```json
[
  {
    "layer": "L3", "kind": "calls_direct",
    "src_module": "libengine.so", "src_offset": "0xXXXX",
    "src_name": "ชื่อ window/context ของคุณ", "src_insn": "bl #0xYYYY",
    "dst_module": "libengine.so", "dst_offset": "0xYYYY",
    "dst_name": "sub_YYYY", "resolved_by": "วิธีที่คุณรู้ปลายทาง",
    "confidence": "probable",
    "evidence": "อ้างบรรทัด listing/เหตุผล",
    "source": "fragments/F4d_libengine_regnatives_windows.asm",
    "chain": "CH-12", "hop": 1
  }
]
```

`kind` เลือกจาก 24 ค่าใน `schema.KINDS`, `confidence` เลือกจาก
`proven / strong / probable / candidate`

**ขั้น 2 — rebuild พร้อม extra file:**

```bash
python3 tools/build_call_linkage.py --out build --extra my_hops.json --compare
```

`--compare` จะบอกทันทีว่า hop ใหม่เพิ่มเข้ามา (`only_in_new=1`) และ
`verify` จะตรวจว่า `0xXXXX` มีจริงใน decoded listings + mnemonic ตรงกันหรือไม่

**ขั้น 3 (ถาวร)** — ย้าย dict ไปใส่ `EXTRA_ANNOTATIONS` ท้าย `annotations.py`
แล้วรันเทสต์

---

## 5. วิธีต่อยอด B: เพิ่ม chain ใหม่ (สายการเรียกใหม่ CH-12+)

```python
from tools.call_linkage import chains as C

ch12 = C.ChainDef(
    id="CH-12", layer_path="L3 -> L4",
    title="my new walk", title_th="สายใหม่ของฉัน",
    goal="อธิบายว่าสายนี้พิสูจน์อะไร",
    hops=[
        C._hop("L3", "calls_direct", "libengine.so", "0xXXXX", "เล่า hop นี้"),
        C._hop("L4", "registers_natives", "libengine.so", "0xb0144", "..."),
    ],
)
resolved, missing = C.resolve_all(graph, bundle="Codes/SnakeLogic",
                                  chain_defs=C.CHAIN_DEFS + [ch12])
assert missing == []   # ถ้า hop ไหนหา edge ไม่เจอ จะรายงานตรงนี้
```

hop ผูกด้วย **semantic key** (`layer/kind/src/dst`) ไม่ใช่ `edge_id`
ดังนั้น rebuild กี่ครั้งก็ยังผูกถูก ถ้า key ซ้ำกัน 2 edges resolver จะรายงาน
`candidates=2` ให้ไปแก้ให้ชัดก่อน (ตั้งใจออกแบบให้ fail ดัง ไม่เงียบ)

---

## 6. วิธีต่อยอด C: เพิ่ม check ใหม่

เพิ่มฟังก์ชันใน `verify.run_all()` ตามแพทเทิร์น:

```python
add("ชื่อ check ใหม่",
    "PASS" if <เงื่อนไข> else "FAIL",
    f"รายละเอียด: ...")
```

`build` จะ exit code 1 ทันทีถ้ามี FAIL หรือ hop resolve ไม่ครบ — เอาไปผูก CI ได้เลย

---

## 7. ตัวอย่าง query ที่ใช้บ่อย

```bash
# ใครเรียก Native.update? (ย้อนขึ้น)
python3 tools/query_linkage.py build/call_linkage.json trace \
  --module classes.dex --name 'Lcom/snake/helper/Native;->update(Ljava/lang/Object;Ljava/lang/reflect/Method;)V' \
  --direction in --depth 2

# จาก RegisterNatives site เดินหน้าลงไป 2 ชั้น
python3 tools/query_linkage.py build/call_linkage.json trace \
  --module libengine.so --offset 0xb40a8 --direction out --depth 2

# หา path จาก dex loader ถึง JNI_OnLoad
python3 tools/query_linkage.py build/call_linkage.json paths \
  --from classes.dex+0x2b6c2e --to libengine.so+0xf3fa0

# ปลายทาง Dart ที่ถูกเรียกบ่อยสุด 12 อันดับ (ที่มาของ CH-11)
python3 tools/query_linkage.py build/call_linkage.json fan-in --layer L5 --top 12
```

---

## 8. ความหมายของ node-id (อ่านกราฟให้เป็น)

| รูปแบบ | ความหมาย | ตัวอย่าง |
|---|---|---|
| `module!0x...` | instruction/slot ที่ offset นั้น | `libengine.so!0xf3a0c` |
| `module#name` | เอนทิตีชื่อ (class/method/function/page) | `classes.dex#Lcom/snake/helper/Native;` |
| `libapp.so!pp!0x...` | object-pool slot ของ Dart | `libapp.so!pp!0x2cd8` |
| `android-runtime!0x..` | JNIEnv slot | `android-runtime!0x6b8` = RegisterNatives |
| `kernel!0x..` | syscall number | `kernel!0xde` = mmap |

---

## 9. ข้อจำกัดที่รู้ตัว (ไม่ปิดบัง)

1. **L5 import จาก baseline** — `asm/*.dart` 12 ไฟล์+ไม่อยู่ใน bundle จึง rebuild
   จากต้นฉบับไม่ได้ ได้แต่ parity-check (`only_in_new=0/only_in_old=0`)
2. **`edge_id` รันใหม่อาจเปลี่ยนลำดับ** — เพราะ assign ตาม sort order ไม่ใช่ลำดับเดิม
   ให้อ้าง edge ด้วย semantic key หรือ (`chain`,`hop`) แทน
3. **fingerprint ของ bundle นี้ (889 ไฟล์) ไม่ตรงค่าที่ commit ไว้ (699 ไฟล์)** —
   เพราะ tree ปัจจุบันมีไฟล์สกัดเพิ่ม (`snake/res/*` ฯลฯ) ค่าที่รายงานคือ
   self-consistency ของ tree ปัจจุบัน ไม่ใช่ค่าประวัติศาสตร์
4. **`blutter_build.log`/Ghidra artifacts ไม่อยู่ใน bundle** — checks ที่ต้องใช้
   ไฟล์พวกนั้นจึงถูกตัดออก เหลือ 15 checks ที่รันได้จริงจากไฟล์ที่มี
```


# รายงานตรวจสอขีดความสามารถ AetherEngine (Full Codebase Audit)

- วันที่ตรวจ: 2026-09-23
- ขอบเขต: ซอร์สทั้งหมดใน `AetherEngine/` — `aether-core`, `aether-android`, `aether-native`, `app` (Kotlin + Dart + C++) และ AndroidManifest ทั้ง 2 ไฟล์
- วิธีตรวจ: อ่านไฟล์จริงทั้งไฟล์จนครบ 100% (ไม่มีช่วงที่ข้าม) แล้วตรวจสายการเรียก (caller grep) ทุกฟังก์ชันสาธารณะเพื่อแยกของที่ "ทำงานจริง" ออกจากของที่ "มีแต่ซาก"
- หลักการ: ไม่อ้างสิ่งที่ซอร์สไม่มี, สรุปขั้นตอนการทำงานแทนการคัดลอกโค้ด, ไม่นับไลบรารี third-party

---

## 1. สรุปสั้น (TL;DR)

1. **AetherEngine คืออะไร** — แอพ Android ประเภท **virtual-app / sandbox engine**: กรอบงานสำหรับครอบแอพอื่น (เรียกว่า guest/target) ให้มารันอยู่ใต้โปรเซสของตัวเอง ผ่านชุดกลไก proxy process, Activity จำแลง, การ patch ระบบ Android (AMS/PackageManager/binder), JNI hook ฝั่ง native และเครื่องมือวินิจฉัย
2. **ติดตั้งแล้วเจออะไร** — หน้า debug ของ Flutter มีแค่ **ตัวเลขสถิติ + ปุ่ม 3 ปุ่ม** (VirtualFS, handshake, อ่าน diag) ไม่มี UI เกม ไม่มี guest ใด ๆ ฝังมาให้
3. **ทำไมไม่สอดคล้องกับ Snake** — เพราะ "Snake" ในโปรเจกต์นี้คือ **แอพต้นแบบ `com.snake.*` ที่ถูก decompile มาเป็นแบบอย่าง** (ร่องรอย `Lcom/snake/helper/Native;`, `com.snake.zip`, `snake yu0.f()`) ไม่ใช่สิ่งที่อยู่ใน APK ปัจจุบัน; โค้ดส่วนที่เคยโหลดไบนารีของ Snake (`EngineType.SNAKE`) **ถูกตัดทิ้งไปแล้วเมื่อ 2026-09-23** ตามนโยบาย offline ใน `docs/CUTS.md`; ส่วนเอกสารพิมพ์เขียว UI (`docs/SNAKE_UI_BLUEPRINT.md`) ที่โค้ดอ้างถึง **ไม่มีอยู่ใน repo**; และเส้นทาง launch ทั้งหมดเข้าไม่ถึงจาก UI ที่ติดตั้ง

---

## 2. คำว่า "Snake" ในโปรเจกต์นี้หมายถึงอะไร

หลักฐานจากซอร์ส (ไม่ใช่การเดา):

| หลักฐาน | ที่มา | ความหมาย |
|---|---|---|
| `Lcom/snake/helper/Native;->ac(...)` | คอมเมนต์ใน `AetherInstrumentation.kt` | Snake คือแอพต้นแบบที่ถูก decompile (trace T1) แล้วเอาลายเซ็น JNI มาเลียนแบบ |
| `com.snake.zip` = "ดัมป์ต้นแบบตอนเปิดแอพ" | คอมเมนต์ใน `AetherApp.kt` | มีไฟล์ดัมป์ของแอพ Snake ใช้เทียบพฤติกรรม (trace T1/T2) |
| `snake yu0.f()`, "snake parity" | `AetherApp.kt` | ตรรกะ role ตาม process เลียนแบบพฤติกรรม Snake |
| `EngineType.SNAKE` ถูก CUT | `EngineLoader.kt` (2026-09-23) | เดิมเคยโหลด `libengine.so` **ของ Snake** ตรง ๆ — ถูกตัดเพราะ "เท่ากับเอาโค้ด C2/license ของเขามาด้วย" ขัดนโยบายสืบทอดโครงสร้างแต่ไม่เอา C2 |
| `docs/SNAKE_UI_BLUEPRINT.md` | ถูกอ้างใน `AetherInstrumentation.kt` | พิมพ์เขียว UI ของ Snake — **ไม่มีไฟล์นี้ใน repo** (มีแค่ `CUTS.md`) |
| blueprint B3 = "snake รันด้วย virtual mechanism" | `AetherOrchestrator.kt` | ยืนยันว่า Snake ตัวจริงรันด้วยกลไก virtual-app แบบเดียวกับที่ engine นี้เลียนแบบ |

สรุป: **Snake = แอพเป้าหมายที่ต้องการเลียนแบบ ไม่ใช่ส่วนหนึ่งของ APK ปัจจุบัน** — APK ปัจจุบันมีแต่ "เครื่องยนต์เปล่า" ที่ไม่มีตัวถัง (guest) และไม่มีหน้าตา (UI) ของ Snake

---

## 3. AetherEngine คืออะไร ทำอะไรได้บ้าง (ภาพรวม)

### 3.1 สถาปัตยกรรมรันไทม์

```
┌─ Flutter UI (app/lib) ──────────────┐
│  หน้า debug: stats + ปุ่ม 3 ปุ่ม      │  ← สิ่งเดียวที่ผู้ใช้แตะได้
└────────── MethodChannel ─────────────┘
┌─ Main process (com.aether) ───────────────────────────────┐
│ AetherApp.onCreate: โหลด libaether.so → init config/flag   │
│ → CrashHandler → Orchestrator.init → DaemonService        │
│ EngineBridge: สะพาน MethodChannel ↔ Orchestrator/Native   │
├─ :p0–:p3 (proxy sandbox, จอง 4 slot) ─────────────────────┤
│ ProxyActivity.P0–P3 → VirtualAppContainer:                 │
│   patch AMS/sPackageManager/handler + ครอบ binder 11 ตัว   │
│   + โหลด GuestRuntime ของ guest                            │
├─ :engine (server process) ────────────────────────────────┤
│ AetherDaemonService + syscall provider (Messenger binder) │
└───────────────────────────────────────────────────────────┘
```

### 3.2 สิ่งที่ engine ทำได้จริง (LIVE — มีสายเรียกครบ)

- **บูตเครื่องยนต์**: โหลด `libaether.so`, เตรียม sandbox dir, ติดตั้ง crash handler, สตาร์ท daemon, โหลด vdex stub — เกิดทุกครั้งที่เปิดแอพ (`AetherApp` → `AetherOrchestrator.init`)
- **ยิง guest เข้า sandbox** (`launchInSandbox`): จอง slot 0–3 → handshake ข้ามโปรเซสผ่าน provider (`_Engine_|_init_process_`) → เปิด `ProxyActivity` ใน `:pN` → แปลงร่างเป็น guest activity → รายงานผลกลับทางไฟล์ `diag/launch_result.json` (รอไม่เกิน ~4.2 วินาที)
- **ปลอมสภาพแวดล้อมให้ guest**: patch ActivityManager/PackageManager ผ่าน reflection, ครอบ binder service 11 ตัว (`ServiceBinderProxy`), ดัก message loop (`HCallbackProxy`), สลับ Activity จำแลงเป็นของจริง (`AetherInstrumentation`), redirect ไฟล์ (`VirtualFSWrapper`)
- **โหลด guest 2 ทาง**: ทางหลัก v2 (`GuestRuntime` — ผูก Application/Resources 3 รอบ + ข้าม provider ที่ขึ้นกับเน็ตอย่าง Firebase/โฆษณา) กับทางสำรอง v1 (`VirtualAppLoader` — ปฏิเสธถ้า sandbox ถูกตั้งไว้แล้ว)
- **อ่าน/สแกนหน่วยความจำ guest**: `readMemory` (อ่านข้ามโปรเซสด้วย `process_vm_readv`) และ `scanAOB` (สแกนลายเซ็นไบต์ หน้าต่าง 4MB + cache 30 วินาที) — ผ่าน MethodChannel
- **ที่เก็บ payload**: เขียนไฟล์ชื่อ SHA-256 + เข้ารหัส XOR ด้วยคีย์ 30 ไบต์ (`jkl_key`, version 0x01), บีบอัด/ขยายข้อมูล (`nativeCompress/DecompressPayload`)
- **พรางตัวพื้นฐาน**: ปิด dumpable (`PR_SET_DUMPABLE=0`), ลด debuggable props (ต้องมี root), ซ่อนบิต scoped-storage บน API 29
- **วินิจฉัยตัวเอง**: `chainCheck` ตรวจโซ่ 7 ขั้น (identity → binder → handler → AMS → slot → config → installed), `handshakeStatus`, `readDiag` (trace + logcat + crash tail), รายงาน crash 14 หมวด **เก็บเป็นไฟล์ในเครื่องเท่านั้น** (ไม่ส่งออก — ตั้งใจตามนโยบาย offline)
- **อ่าน `package.conf` ของเกมจริงภายนอก**: parser รองรับสตริง 2 รหัสอักขระปนกัน (UTF-16LE ส่วนหัว / UTF-8 ส่วนตัว), หาเวอร์ชันจากตำแหน่งก่อน `base.apk`, ฮิวริสติก launcher `8BP` — ถูกเรียกจริงจาก 3 จุดในเส้นทาง launch

### 3.3 สิ่งที่มีแต่ซาก / ไม่ทำงาน (DEAD — ตรวจแล้วไม่มีใครเรียกเลย)

| ฟีเจอร์ | สภาพ | หลักฐาน |
|---|---|---|
| ล็อกอิน OAuth + เบราว์เซอร์ในแอพ (`OAuthFlow`, `InternalWebBrowser`) | ตายทั้งกิ่ง — 0 caller | grep ไม่เจอผู้เรียก `OAuthFlow` เลย |
| VPN (`AetherVpnService`) | ประกาศใน manifest แต่**ไม่เคยถูกสตาร์ท** — `blockIp`/สถิติ 0 caller | ไม่มี `startService`/`startForegroundService` ที่ชี้มาที่นี่ |
| รีโมตคอนฟิก (`RemoteConfig` getters ทั้งหมด + `Flagger.get*`) | init/fetch รัน แต่ค่าที่ได้**ไม่มีใครอ่าน** | getter 0 caller — flag อย่าง `vpnEnabled` จึงไม่มีผล |
| ซิงก์ข้อมูลเกม/PGL stub (`syncGameData`, `mountPglStubs`) | 0 caller | เหลือแค่คอมเมนต์อ้างถึง |
| ครอบ sandbox ให้ตัวเอง/รันเชลล์ (`mountSandboxForSelf`, `Orchestrator.execShell`, `decompress/decryptPayload`) | 0 caller | API ลอย ไม่มีผู้ใช้ |
| JNI สำรอง (`nativeProcessTriple`, `nativeReflectUpdate`) | ประกาศ+register แต่ไม่เรียก | 0 caller ฝั่ง Kotlin |
| ตัว JNI ที่เรียกแต่ไส้ว่าง (`nativeInitContext`, `nativeProcessPair`) | เรียกจริงแต่ native body = NOOP | `aether_core.cpp` ไม่มี implementation |
| ตัวอ่าน crash (`getLatestCrashLog`, `getCrashLogs`, `clearCrashLogs`, `getCrashDir`), `RemoteConfig.addListener`, `Bridge.setMode`, `suspend/resume` | 0 caller ทั้งหมด | ตายเรียบ |
| ยูทิลิตี patch (`UnitySoPatcher`, `SoPatchApplier`, `DepthPatch`) | 0 caller | โค้ดลอย |
| `ProxyPendingActivity.create`, `AetherFileProvider` | manifest/โค้ดมี แต่ไม่มีผู้ใช้ใน repo | surface ว่าง |
| `AetherStubReceiver` (exported) | มีคนฟัง ไม่มีคนส่ง — ใน repo ไม่มีผู้ส่ง broadcast นี้ | เรียกได้จากภายนอกเท่านั้น (กันด้วย signature permission) |
| โปรโตคอล `route` ของ `ProxyContentProvider` | มีแต่ฝั่งเซิร์ฟเวอร์ ไม่มีผู้ส่ง | โค้ดระบุเองว่า reserved |

---

## 4. เส้นทางสำคัญ 2 เส้น (สรุปขั้นตอน ไม่คัดลอกโค้ด)

### 4.1 บูต (เปิดแอพ → พร้อมใช้)

`AetherApp.onCreate` → `EngineLoader.load` (โหลด `libaether.so`) → `nativeInitContext` (เรียกแต่ไส้ว่าง) → `SandboxManager.init` (เตรียมโฟลเดอร์ sandbox) → `RemoteConfig.init` + `Flagger.init` (โหลดค่า แต่ไม่มีใครอ่าน) → `CrashHandler.install` → `AetherOrchestrator.init` (เตรียม vdex stub + ลงทะเบียนกฎ JNI จาก guest config ซึ่งปัจจุบันว่าง) → สตาร์ท `AetherDaemonService` (foreground + Messenger binder) → Flutter เปิดหน้า debug

### 4.2 ยิง guest (`launchInSandbox` — เส้นทางหลักของ engine)

Flutter/Dart → `EngineBridge` (MethodChannel) → `AetherOrchestrator.launchInSandbox` → จอง slot ใน `GuestProcessTable` (0–3, มี `linkToDeath` คืน slot อัตโนมัติ) → handshake ผ่าน provider (`spawnAndConfig`) → `ProxyActivity.P<slot>` เริ่มในโปรเซส `:pN` → `VirtualAppContainer.init/setup` (redirect ไฟล์ + ครอบ binder + patch AMS/PackageManager) → แนบ guest เข้าโปรเซสตัวเอง + โหลด native → `GuestRuntimeBridge.load` (v2: ผูก Application/Resources, ปลอมชื่อโปรเซส, ตั้ง seed = SDK version, ติดตั้ง provider ของ guest โดยข้ามตัวที่พึ่งเน็ต) → ปลด `HCallbackProxy` → `AetherInstrumentation` สลับ Activity จำแลงเป็นของจริง + สั่ง `recreate()` → เขียนผลลัพธ์ลง `diag/launch_result.json` ให้ฝั่งเรียกมาอ่าน (poll 4.2 วินาที + ตรวจความสดของ timestamp)

---

## 5. ทำไมติดตั้งแล้ว "ไม่สอดคล้องกับ Snake" (วิเคราะห์สาเหตุ)

เรียงตามน้ำหนัก:

1. **ไม่มี Snake อยู่ใน APK เลย** — ไม่มีโค้ด ไม่มีไบนารี ไม่มีกราฟิก ไม่มี UI ของ Snake; ส่วนที่เคยโหลดไบนารี Snake ถูกตัดทิ้งแล้ว (`EngineLoader.kt` [CUT 2026-09-23]) เหลือแค่ `libaether.so` ที่เขียนเอง
2. **UI ที่ติดตั้งคือหน้า debug ไม่ใช่หน้าของ Snake** — `main.dart` มีแค่การ์ดสถิติ + ปุ่ม 3 ปุ่ม (`VirtualFS`, `handshake`, `อ่าน diag`) ไม่มีปุ่มยิง guest ไม่มีรายชื่อแอพ ไม่มีหน้าตาใด ๆ ที่เกี่ยวกับ Snake ส่วน `engine_api.dart` เตรียมไว้ 15 เมธอดแต่ UI เรียกใช้แค่ 4
3. **พิมพ์เขียว UI ของ Snake ไม่มีใน repo** — โค้ดอ้าง `docs/SNAKE_UI_BLUEPRINT.md` แต่ไฟล์ไม่มีอยู่จริง จึงไม่มีใครสร้าง UI ตามแบบได้
4. **guest ว่างเปล่า** — ไม่มี target package ฝังมา, `classRules` ว่าง, payload slot ว่าง, ไม่มี content pipeline; สิ่งที่โค้ดอ้างว่าเป็น "เกมจริงภายนอก" คือร่องรอยเกมแนว pool (`8BP` launcher, PGL/Pangle stub, ช่วง IP Miniclip ใน VPN) ไม่ใช่ Snake
5. **ฟีเจอร์ที่จะทำให้ "เหมือนแอพจริง" ตายหมด** — OAuth/VPN/RemoteConfig/ซิงก์ข้อมูล ไม่มีตัวไหนทำงาน (ตาราง §3.3)
6. **แม้เส้นทาง launch จะสมบูรณ์ แต่มันเข้าไม่ถึงจากแอพที่ติดตั้ง** — ต้องเรียก MethodChannel เองจากโค้ด หรือสั่งผ่าน adb เท่านั้น ไม่มีปุ่มให้กด
7. **ข้อกำหนดรันไทม์ไม่ครบแบบ one-tap** — guest ต้องติดตั้งแยก, หลายขั้นต้องการ root (mount/bind, resetprop), handshake ข้ามโปรเซสที่ล้มเหลวได้ — ทั้งหมดนี้ไม่มี UI ช่วยเหลือ

---

## 6. ต้องทำอะไรต่อ ถ้าอยากให้ "สอดคล้องกับ Snake"

ทางเลือก 3 ระดับ (ไม่รวมการเอาไบนารี/C2 ของ Snake กลับมา — ขัดนโยบาย `CUTS.md`):

- **A. ทำให้ของที่มี "กดได้" (เร็วสุด)** — เพิ่มปุ่มใน `main.dart` ต่อกับ 15 เมธอดที่มีอยู่แล้ว (`launchInSandbox`, `chainCheck`, `readMemory`, `scanAOB`, `nativeCompute`, `compressPayload`) + ช่องกรอก package name + แสดงผล `launch_result.json` — จะพิสูจน์ได้ทันทีว่าเส้นทาง launch ทำงานบนเครื่องจริงหรือไม่
- **B. สร้าง guest เป้าหมายของตัวเอง (ถูกต้องสุด)** — เลือก/สร้างแอพ guest ทดสอบ (ไม่จำเป็นต้องเป็น Snake), ฝัง/ติดตั้ง guest, เติม `classRules` + payload + AOB signature จริง, ตัดซาก DEAD ออก (`OAuthFlow`, `AetherVpnService`, `UnitySoPatcher` ฯลฯ) ให้เหลือแต่ทางที่รันได้
- **C. เลียนแบบ Snake เต็มรูป (ต้องมีของเพิ่ม)** — ต้องได้ `SNAKE_UI_BLUEPRINT.md` + ดัมป์พฤติกรรม (`com.snake.zip` T1/T2) กลับมาก่อน แล้วสร้าง UI/guest ตามแบบ — ตอนนี้ทำไม่ได้เพราะไฟล์ไม่อยู่ใน repo

สิ่งที่ต้องการจากเจ้าของโปรเจกต์เพื่อไปต่อ: (1) เป้าหมายคือ A/B/C แบบไหน (2) guest ที่จะใช้ทดสอบคือแอพอะไร (3) มีไฟล์ `SNAKE_UI_BLUEPRINT.md` / ดัมป์ T1/T2 หรือไม่ (4) ทดสอบบนอุปกรณ์ root หรือไม่ root

---

## 7. วิธีทดสอบความสามารถที่มีอยู่ตอนนี้

- **ในแอพ**: กด `_refresh` (ดู device id + engine stats) → `VirtualFS` → `handshake` → `อ่าน diag` — ทั้งหมดควรสำเร็จแบบ offline
- **ผ่าน adb** (เส้นทาง launch ที่ UI ไม่มีปุ่ม): สั่งเปิด `ProxyActivity` ตรง ๆ พร้อม `target_package` ของแอพที่ติดตั้งไว้แล้ว แล้วอ่าน `files/diag/launch_result.json` — ถ้าไฟล์เกิดและ `chainCheck` ผ่าน 7 ขั้น แปลว่าเส้นทางหลักรอด
- **CI**: ทุก push มี `ci.yml` (toolkit-test/lint/offline-gate/analyze/compile) และ `build-apk.yml` (release APK) คุมอยู่ — การตัดซากต้องไม่ทำให้ gate แดง

---

## ภาคผนวก ก. รายการไฟล์ที่ตรวจ (ครบ 100%)

- `app/lib/*.dart` — `main.dart`, `engine_api.dart` (UI + MethodChannel API 15 เมธอด)
- `app/android/.../EngineBridge.kt` (สะพาน MethodChannel), manifest ฝั่ง app
- `aether-android/.../app/` — `AetherApp`, `EngineLoader`, `CrashHandler`, `DaemonService`, `AetherDaemon(+Inner)Service`, `OAuthFlow`, `InternalWebBrowser`, `RemoteConfig`, `AetherSystemCallProvider`, `AetherStubReceiver`, `AetherFileProvider`, `DiagLog`, `Flagger`, manifest ฝั่ง engine
- `aether-android/.../proxy/` — `AetherOrchestrator`, `ProxyActivity`, `ProxyService`, `ProxyJobService`, `ProxyContentProvider`, `TransparentProxyActivity`, `ProxyPendingActivity`, `VirtualAppContainer`, `VirtualAppLoader`, `GuestRuntimeBridge`, `GuestProcessRegistry`, `ServiceBinderProxy`, `HCallbackProxy`, `AetherInstrumentation`, `IntentParser`, `AetherIpcBridge`, `VirtualFSWrapper`
- `aether-android/.../vpn/` — `AetherVpnService`
- `aether-core` — `SandboxManager`, `GuestRuntime`, `Bridge`, `VirtualFS`, `AetherIpc`, `PackageConfParser`, `VdexPatcher`(ผ่าน orchestrator), `Engine` (ประกาศ JNI)
- `aether-native` — `aether_core.cpp`, `jni_hook.cpp`, `key_store`, `mem_reader`, `module_resolver`, `payload_store`, `stealth`, `aob`, `binder`, `class_map`, `config`, `crypto`, `flagger`, `virtual_fs`, JNI `Engine_*`

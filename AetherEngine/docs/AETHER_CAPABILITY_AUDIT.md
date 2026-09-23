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
| ยูทิลิตี patch (`UnitySoPatcher`, `SoPatchApplier`, `DepthPatch`) | **PHANTOM — ไม่มีใน repo** (ดู §9: รายงานรอบแรกอ้างผิด ไม่มีไฟล์/สัญลักษณ์นี้เลย) |
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
- `aether-core` — มีแค่ 5 ไฟล์: `SandboxManager` (มี `provisionVdexStubs()` + `mountSandbox` + `generatePackageConf`), `GuestRuntime` (มี `suspend/resume` ที่ dead), `PackageConfParser`, `RemoteConfig`, `Engine` (ประกาศ JNI) — ชื่อ `Bridge`/`VirtualFS`/`AetherIpc`/`VdexPatcher` ในรายงานรอบแรกเรียกเพี้ยน (ของจริง: `GuestRuntimeBridge.RuntimeMode`, `VirtualFSWrapper`, `AetherIpcBridge` ใน `ProxyContentProvider.kt`, ฟังก์ชัน `provisionVdexStubs`) — ดู §9
- `aether-android/.../proxy/MethodUtils.kt` — **รอบแรกตกหล่น**: มีจริง 7 เมธอด mirror ของ Snake ครบ แต่ **0 caller (DEAD)** — ต้อง wire ในงาน P2/P3 ไม่ใช่สร้างใหม่
- `aether-native` — `aether_core.cpp`, `jni_hook.cpp`, `key_store`, `mem_reader`, `module_resolver`, `payload_store`, `stealth`, `aob`, `binder`, `class_map`, `config`, `crypto`, `flagger`, `virtual_fs`, JNI `Engine_*`

---

## 8. Deep dive: หลักการทำงานแบบทะลุปรุโปร่ง (2026-09-23 รอบ 2)

### 8.1 EngineBridge คืออะไรกันแน่ (515 บรรทัด — อ่านครบแล้ว)

`EngineBridge` (`app/android/.../com/aether/EngineBridge.kt`) เป็น `object : MethodCallHandler` ช่อง `com.aether/engine_bridge` รับ 15 เมธอดจาก Dart — แต่หน้าที่จริงมี **2 ครึ่ง**:

1. **เจ้าของ channel คนเดียว** — ไม่มีมัน Dart ทั้ง 15 เมธอดพังทันที (`MissingPluginException`) หน้าแอพที่ติดตั้งกลายเป็นจอตาย
2. **fast-path ของบูตครึ่งหลัง** — `init()` (ถูกเรียกจาก `AetherHostActivity.configureFlutterEngine` เพียงที่เดียว) ทำ `orchestrator.init` (ถ้ายัง) → `attachToProcess(ownPid, "", "com.aether")` → `startEngine()` ในโปรเซส main แบบ synchronous ตั้งแต่เปิด activity
3. **ทางเข้าเดียวของ 15 ปฏิบัติการ** — ทุกเมธอดเป็น `private fun` ที่ส่งต่อไป Orchestrator/Native (ตาราง §8.2) ไม่มี entry อื่นใน repo

### 8.2 แผนที่ 15 เมธอด → ปลายทาง

| เมธอด Dart | EngineBridge ส่งต่อไปที่ | เงื่อนไขก่อนทำงาน |
|---|---|---|
| `isTargetInstalled` / `getInstalledGameInfo` | `PackageManager` ตรง ๆ | มี context |
| `getDeviceId` | `ANDROID_ID` → fallback fingerprint (offline) | มี context |
| `getEngineStats` | `Orchestrator.getStats()` | — (อ่านค่าเฉย ๆ) |
| `getVirtualAppStatus` | `VirtualAppContainer` + `Engine.classRuleCount()` | — |
| `testVirtualFS` | `VirtualAppContainer.testVirtualFSResolve()` | — |
| `readMemory` | `nativeFindModuleBase` + `Orchestrator.readMemory` (≤4096B, คืน hex+ascii) | **ต้อง attached** |
| `scanAOB` | `nativeFindModuleBase` + `nativeScanAOB` (256KB จาก base) | **ต้อง attached** |
| `nativeCompute` | `Engine.nativeCompute` (คืน hex 8 ไบต์) | lib โหลดแล้ว |
| `compressPayload` | `Engine.nativeCompressPayload` (hex↔hex) | lib โหลดแล้ว |
| `launchApp` | `getLaunchIntentForPackage` + `startActivity` (opt-in เปิดแอพนอก) | แอพมีอยู่จริง |
| `launchInSandbox` | `Orchestrator.launchInSandbox` + `launchResultAwait` (poll ไฟล์ 4.2s) | **orchestrator initialized** |
| `readDiag` | อ่านไฟล์ `diag/trace.log` + `logcat_*` (400 บรรทัดท้าย) + `crash_*.log` (80 บรรทัดท้าย) | — |
| `chainCheck` | ตรวจ 7 ขั้นในโปรเซส main เอง (identity/sCache/HCallback/AMS/slot/childConfig/installed) | — |
| `handshakeStatus` | `ContentResolver.call` เมธอด `_Engine_|_init_process_` จริงด้วย DIAG slot สุดท้าย | provider `:pN` ตอบ |

### 8.3 บูตแยก 3 ทาง (split boot) — ทำไมตัดชิ้นใดชิ้นหนึ่งแล้วไม่ตายทั้งระบบ

| เส้นทาง | ใครทำ | เมื่อไร | ได้อะไร |
|---|---|---|---|
| **A. `AetherApp.onCreate`** (ทุกโปรเซส) | exempt hidden-API → `DiagLog.init` → `nativeInitContext` (main/child เท่านั้น, ไส้ว่าง) → `Flagger/RemoteConfig.init` + `fetchAsync` → `nativeHydratePayloads` (สแกน `root/files/`) → `CrashHandler.install` → `Orchestrator.init` → สตาร์ท `AetherDaemonService` | เปิดแอพ/โปรเซสเกิด | lib + โฟลเดอร์ + crash + orchestrator(initialized) + daemon |
| **B. `EngineBridge.init`** (main เท่านั้น) | `orchestrator.init` (ถ้ายัง) → `attachToProcess` → `startEngine` + ลงทะเบียน channel | Flutter activity เปิด (`configureFlutterEngine`) | attached + running + UI ใช้ได้ — **เร็วสุด (synchronous)** |
| **C. watchdog ใน `AetherDaemonService`** (main — ไม่มี `android:process` ใน manifest จึงไม่ใช่ `:engine`) | ลูปทุก 3 วินาที 5 เคส: ยังไม่ init→init+attach / init แล้วไม่ attach→`doSelfAttach` / attach แล้วไม่ running→`startEngine` / running แต่ native เสีย 3 ครั้ง→re-attach / ครบ→healthy | หลัง daemon สตาร์ท (~วินาที) | **ตาข่ายนิรภัย**: ไม่มี B ก็ attach+start ได้เองภายใน ~9 วินาที |

### 8.4 "ถ้าไม่มี EngineBridge จะเกิดอะไร" (ตอบด้วยหลักฐาน ไม่ใช่เดา)

| ส่วน | ผล | เหตุผล |
|---|---|---|
| หน้า Flutter ที่ติดตั้ง | **ตายสนิท** — ทุกปุ่มพัง | ไม่มี handler ให้ channel (มีที่เดียวคือ `EngineBridge.init` จาก `AetherHostActivity`) |
| บูต engine (lib/sandbox/crash/init/daemon) | **รอดทั้งหมด** | อยู่ใน `AetherApp` ไม่ได้อ้าง EngineBridge (มีแค่คอมเมนต์เอ่ยชื่อ) |
| attached/running ใน main | **รอดช้าลง** (~3–9 วินาทีแทนทันที) | watchdog เคส 5→1→2 ทำแทน (`doSelfAttach` + `startEngine`) |
| `readMemory`/`scanAOB`/`chainCheck`/diag | **เรียกไม่ได้** (ไม่ใช่พัง — คือไม่มีทางเรียก) | caller เดียวใน repo คือเมธอด private ของ EngineBridge |
| `launchInSandbox` | **โค้ดพร้อม แต่ไม่มีใครกด** — ต้องการแค่ initialized (ไม่ต้องการ attached) และเรียก `startEngine()` เองข้างใน; เหลือทางเดียวคือ adb ยิง `ProxyActivity` (exported=true) ตรง ๆ ซึ่ง**ข้าม** slot/handshake/bootstrap — `ProxyActivity` จะ seed slot จาก extra + ใช้ `target_package` จาก intent (default `com.aether` = ไม่ virtual = แค่ self-attach แล้วจบ) = โหมดพิการ |
| `:pN` / `:engine` | **ไม่กระทบ** | `ProxyActivity` self-attach เอง, daemon ไม่แตะ EngineBridge |

สรุปประโยคเดียว: **EngineBridge ไม่ใช่แค่สะพาน UI — มันคือรีโมตกดปุ่มทั้ง 15 ปุ่ม + สตาร์ทเครื่องทางลัด; ถอดมันออกเครื่องยนต์ยังติด (บูต+watchdog) แต่ไม่มีพวงมาลัย ไม่มีคันเร่ง ไม่มีหน้าปัด — เหลือแต่ adb เจาะผ่านประตู exported ที่เปิดอ้าอยู่**

### 8.5 โซ่เต็มเส้น — กดปุ่ม launch 1 ครั้งเกิดอะไรบ้าง (6 ด่าน)

1. **Dart** `launchInSandbox(pkg)` → channel → `EngineBridge.launchInSandbox` (ตรวจ context/pkg ว่าง)
2. **`Orchestrator.launchInSandbox`**: ต้องการ initialized → เคลียร์ container ถ้า target เปลี่ยน → `VirtualAppContainer.init+setup` (ปลอม package) → `bootstrapGameData+mountSandbox` → `startEngine()` → `GuestProcessTable.allocate` (slot 0–3, เต็ม = ปฏิเสธแบบ a7:317) → `spawnAndConfig` handshake ผ่าน provider (ปลุก `:pN` + ส่ง config + `linkToDeath`) → ยิง `ProxyActivity$P<slot>` พร้อม `target_package`/`target_sandbox`/`EXTRA_SLOT`
3. **`:pN` `ProxyActivity.onCreate`**: `DiagLog.init` → ตัดสิน identity (p3-config ชนะ intent ยกเว้นของ diag) → seed slot (ถ้าไม่มี handshake) → `VirtualAppContainer.init+setup` รอบโปรเซสลูก → self-attach + `startEngine` ของตัวเอง
4. **โหลด guest** (`GuestRuntimeBridge.load`): v2 `GuestRuntime` ผูก Application/Resources 3 รอบ + ปลอมชื่อโปรเซส + `nativeSetSeed(SDK)` + ติดตั้ง provider ของ guest ข้าม Firebase/โฆษณา → ปลด `HCallbackProxy`
5. **สลับร่าง** (`AetherInstrumentation`): `newActivity` สร้าง stub แล้วสลับเป็น guest class + `FORCE-GUEST Resources` → `recreate()` รีสตาร์ทเป็น guest เต็มตัว
6. **รายงานผลข้ามโปรเซส**: `:pN` เขียน `diag/launch_result.json` → `launchResultAwait` ใน main poll ทุก 400ms × 10 (4.2s) + ตรวจ `ts` ใหม่กว่าเวลากด (กันผลค้าง) → คืน Map ให้ Dart; ถ้าเงียบ = `pending` ให้กด Diag ดู trace

### 8.6 สิ่งที่รอบแรกพูดไม่คม (แก้ไขตามคำท้วง)

- รอบแรกระบุ EngineBridge ว่า "สะพาน MethodChannel" เฉย ๆ — **จริง ๆ มีบทบาทบูต (attach+start fast-path)** และเป็น single entry ของ 15 ปฏิบัติการ (เพิ่ม §8.1–8.2)
- รอบแรกบอก daemon อยู่ `:engine` — **จริง ๆ `AetherDaemonService` ไม่มี `android:process` ใน manifest จึงรันใน main** (มีแค่ `InnerService` ที่อยู่ `:engine`) ทำให้ watchdog เป็นตาข่ายของ main ไม่ใช่ของ `:engine` (แก้ §8.3)
- รอบแรกบอก "launch เข้าถึงได้ผ่าน adb" ลอย ๆ — **จริง ๆ ทาง adb ข้าม 3 ด่าน (slot/handshake/bootstrap) และ default ไม่ virtual** (เพิ่ม §8.4)

---

## 9. สแกน repo ให้ครบจริง (2026-09-23 รอบ 3 — ปิดช่องที่รอบแรกพลาด)

รอบแรกอ้าง "100%" แต่สแกนแค่ซอร์สหลัก — รอบนี้เดินทุกไฟล์ใน repo (143 ไฟล์ ไม่นับ build) แล้ว ผล:

### 9.1 ไฟล์ที่ตกหล่น (อ่านครบแล้ว)

| ไฟล์ | สิ่งที่พบ |
|---|---|
| `proxy/MethodUtils.kt` | มีจริง 7 เมธอด (mirror Snake 6 + ctor overload) แต่ **0 caller = DEAD** — แก้ `SNAKE_EVIDENCE_AUDIT §2.3`: ไม่ใช่ "ขาด" แต่เป็น "มีแต่ไม่ต่อ" |
| `res/values/strings.xml` | แค่ label/description ของ permission IPC (ไม่มี `engine_service_name` แบบ Snake — Aether hardcode `:engine` ใน manifest) |
| `res/xml/file_paths.xml` | FileProvider paths: `sandbox/`, `config/`, cache, external |
| `docs/AETHER_RESTRUCTURE.md` | รายงานตัด C2 (NET-1..4/BIN-1/REN-1): เคยมี `CONFIG_ENDPOINT=rest.snakeseller.com` + `fetchRemotePglMap/Version` + `EngineType.SNAKE` — ตัดหมดแล้วตาม `CUTS.md` |
| `docs/CALL_LINKAGE_GUIDE.md` + `tools/call_linkage/` (3,485 บรรทัด) + `tests/` | toolkit สร้างกราฟ instruction→callee 6 layers (691 edges/1048 nodes/11 chains) จาก `Codes/SnakeLogic` — stdlib ล้วน, CI รันเทสต์ 16 ข้อผ่าน |
| `app/build.gradle` | `com.aether`, minSdk 28, **arm64-only**, R8 OFF (กัน JNI/reflection พัง), CI debug-keystore signing; คอมเมนต์ล็อก **"GAME version 56.23.2 fixed at build time"** |
| `aether-native/.../CMakeLists.txt` | `libaether.so` จาก 13 core TU + `virtual_fs.cpp` + lz4; เคยตัด `manifest_snapshot` (C++ duplicate ไม่มี caller) + `hide_module` (ต้อง root) |
| `app/assets/` (SVG โซเชียล 5 + ฟอนต์ 4) | **ของ Snake** (ชื่อไฟล์ตรง F1 เป๊ะ) เพิ่มมาตั้งแต่ restructure (`ab3b5df`) ประกาศใน pubspec (`flutter_svg`) แต่ **Dart ไม่เรียกใช้เลย** — ของ stage ไว้งาน C |

### 9.2 รายงานรอบแรกที่ต้องแก้ (phantom + ชื่อเพี้ยน)

| ข้อ | ความจริง |
|---|---|
| `UnitySoPatcher`/`SoPatchApplier`/`DepthPatch` "0 caller" | **PHANTOM** — ไม่มีไฟล์/สัญลักษณ์นี้ใน repo เลย (§3.3 แก้แล้ว) |
| `object Bridge` + `Bridge.setMode` + "DUAL default" | ของจริงคือ `GuestRuntimeBridge.RuntimeMode` (enum) + `setMode` (0 caller ✓ dead ถูก) + **default คือ AUTO ไม่ใช่ DUAL** |
| `VirtualFS` / `AetherIpc` / `VdexPatcher` (ภาคผนวก) | ชื่อจริง: `VirtualFSWrapper` / `AetherIpcBridge` (ใน `ProxyContentProvider.kt`) / ฟังก์ชัน `provisionVdexStubs()` |
| `suspend/resume` "0 caller" | ยืนยันถูก — มีจริง (`GuestRuntime.kt:179/185`) ไม่มี caller |
| `reference/NATIVE_CALLSITE_MAP.md`, `scripts/native_chain_parity.py` (คอมเมนต์ใน `GuestProcessRegistry.kt` อ้าง) | **ไม่มีใน repo** — dangling reference (หนี้เอกสาร — P1 ควรแก้คอมเมนต์ให้ชี้ `AetherEngine/docs/` แทน) |
| README ว่า daemon อยู่ `:engine` | เพี้ยน (มีแค่ InnerService ที่ `:engine` — ดู §8.3) |

### 9.3 สถานะการสแกนหลังรอบ 3

อ่านแล้ว: Kotlin 37 + Dart 3 + C/C++ 30 + manifests + res/xml + build/config + docs 6 + tools/tests (survey หัวไฟล์+สถาปัตยกรรม) + โฟลเดอร์ assets — **ครบ 143 ไฟล์ ไม่เหลือ blind spot ระดับไฟล์** (เหลือแค่ body พฤติกรรมฝั่ง Snake ที่ต้อง runtime — งาน P4)

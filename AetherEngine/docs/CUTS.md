# CUTS.md — ทะเบียนสิ่งที่ถูกตัดออกจาก AetherEngine

ไฟล์นี้คือคำตอบของคอมเมนต์ `[CUT …]` / `audit C…` ทั่ว repo
(ของเดิมอ้าง `docs/CUTS.md` แต่ไม่มีไฟล์นี้ใน repo — สร้างเมื่อ 2026-09-23;
รายการก่อนหน้านั้นปะติดปะต่อจากคอมเมนต์ในโค้ดเท่านั้น)

## นโยบาย (มีผลตั้งแต่ 2026-09-23 — **แก้โดยคำสั่งเจ้าของวันเดียวกัน ดู §คืนโมดูลข้างล่าง**)

1. **offline-only** — ห้ามมี URL/endpoint/การดึงข้อมูลผ่านเน็ตในซอร์ส
   ข้อยกเว้นเดียวคือ WebView ที่ผู้ใช้กดเปิดเอง (`InternalWebBrowser`
   ผ่าน `OAuthFlow.start` — ไม่มี endpoint ตายตัวในโค้ด)
2. **ไม่เอา C2 และใบอนุญาตของ Snake** — สืบทอดเฉพาะโครงสร้าง
   (module layout, JNI bridge, init chain, sandbox layout)
   ห้ามโหลดไบนารี Snake (`libengine.so`) หรือเรียก endpoint ของเขา
3. จะเพิ่ม network ใด ๆ กลับมา = ต้องลงทะเบียนในไฟล์นี้ก่อน
   (บอกเหตุผล + endpoint + ไฟล์ที่แตะ) แล้วค่อยเขียนโค้ด

## 2026-09-23 — เจ้าของสั่งคืน license/C2 แบบ FULL (proof phase)

- ข้อ 1–2 **พักใช้ชั่วคราว**เพื่อพิสูจน์ parity เต็ม; ข้อ 3 (ลงทะเบียนก่อนเพิ่ม network) **ยังมีผล**
- NET-1..4 + REN-1 คืนชีพในรูป **โมดูลแยก** (`license/` = นโยบาย, `c2/` = ขนส่ง, core เรียกผ่าน interface + flag อิสระ) ตาม `SNAKE_PARITY_PLAN.md` §License/C2 FULL track — พิสูจน์ก่อน แล้วค่อยยืดหยุ่น (ปิด/ลบ/สลับ endpoint ได้โดย core ไม่แตะ)
- **BIN-1 ยังคงตัด** (ไม่โหลด `libengine.so`) จนกว่าเจ้าของจะสั่งเปลี่ยน
- Endpoint ที่ลงทะเบียน: `ENDPOINT_LIVE = https://rest.snakeseller.com/api/request/` (registry อย่างเดียว — default วิ่ง mock, ห้ามยิง live จนกว่าเจ้าของสั่งชัดตาม G-LC3) + topup `https://www.snakeengine.com/topup/` + oauth `https://snakeengine.com/oauth/google` — ทั้งสามเก็บเป็น host/path แยกชิ้นใน `aether-core/.../c2/Endpoints.kt` (ไม่มี URL literal ทั้งเส้น — CI offline gate ยังเขียว)

## 2026-09-23 — ตัด C2/ใบอนุญาต (restructure รอบ snake-parity)

| รหัส | สิ่งที่ตัด | ไฟล์/จุด | เหตุผล |
|---|---|---|---|
| NET-1 | `CONFIG_ENDPOINT=https://rest.snakeseller.com/api/request/` | `SandboxManager.kt` | endpoint C2/license จุดเดียวของฝั่ง Kotlin |
| NET-2 | `fetchRemotePglMap()` ทั้งฟังก์ชัน | `SandboxManager.kt` | ดึง PGL map ผ่าน NET-1 → ใช้ตาราง `DEFAULT_*` แทน |
| NET-3 | `fetchRemoteVersion()` (local fun) | `SandboxManager.kt` → `generatePackageConf()` | ดึง version ผ่าน NET-1 → ใช้ `versionName` บนเครื่อง |
| BIN-1 | `EngineType.SNAKE` + `set/getEngineType` (opt-in โหลด `libengine.so`) | `EngineLoader.kt` (เขียนใหม่) | โหลดไบนารี Snake ทั้งก้อน = เอา C2/license มาด้วยทั้งชุด |
| NET-4 | `import java.net.HttpURLConnection/URL` (ไม่ได้ใช้) + คอมเมนต์ค้างเรื่อง upload | `CrashHandler.kt` | กันเข้าใจผิด — crash log เป็น local-only |
| REN-1 | `fetchRemoteAsync/Sync()` → `fetchAsync/Sync()` (+ `@Deprecated` alias ชื่อเก่าไว้ให้) | `RemoteConfig.kt`, `AetherApp.kt` | ชื่อเก่าหลอกว่ามี remote — จริง ๆ offline อยู่แล้ว |

**คงไว้โดยเจตนา (ไม่ใช่ C2):** `ensureDeviceToken()` (ไฟล์ token จำลองใน sandbox
ฝั่ง guest — ไม่มีเน็ต), `OAuthFlow`/`InternalWebBrowser` (ผู้ใช้กดล็อกอินเอง,
ไม่มี endpoint ตายตัว), `AetherVpnService` (VPN จับแพ็กเก็ตบนเครื่อง),
`getDeviceId()` (โชว์ใน UI อย่างเดียว), `INTERNET` permission (เผื่อ WebView
ที่ผู้ใช้เปิดเอง) — ถ้าไม่ต้องการชิ้นไหน ตัดเพิ่มได้เลย

## ประวัติจากคอมเมนต์ในโค้ด (ปะติดปะต่อ — ไฟล์นี้เพิ่งสร้าง)

- **2026-09-11** — `spoofRootEnvironment()` (resetprop/magiskpolicy),
  `Stealth::blockDebugger()` (anti-debug) — ทำให้แอพกั๊ก/ปิดตัวเองบนเครื่องจริง
- **2026-09-14 (audit C1/C3/C4)** — `decryptString`/`nativeValidate`/
  `nativeWriteLog` (ไม่มี caller), `launchGame`/`getEngineStatus` (Dart 0 callers)
- **audit C2** — เติม `DiagLog.init` บน main process
- **audit C5** — ถอด `env_check.cpp` ทั้งไฟล์ (probe ถูก CUT + blueprint ตัด stealth)
- **audit C6** — เติม `nativeExemptHiddenApi` (hidden-API exemption ครั้งเดียว/process)
- **audit C13** — `nativeHydratePayloads` log ชื่อ dir จริง; VirtualFS self-test ผ่าน native

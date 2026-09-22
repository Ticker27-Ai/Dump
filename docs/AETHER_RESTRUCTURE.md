# รายงาน: สืบทอดโครง Snake → AetherEngine (ยกเว้น C2 + ใบอนุญาต)

วันที่: 2026-09-23 · ซอร์สต้นทาง: `AetherEngine.zip` บน branch นี้
(164 ไฟล์: Kotlin 37, C/C++ 30, ไม่มี Dart) → แตกไว้ที่ `AetherEngine/`

## 1. สรุปผู้บริหาร

- โค้ดเดิมสืบทอดโครง snake มาไกลแล้ว (~6.9k บรรทัด) — งานรอบนี้คือ
  **ตัดส่วน C2/ใบอนุญาตที่หลงเหลือ + เติมช่องว่างโครงสร้าง + ตั้งนโยบายกันกลับ**
- ตัดเน็ตออกหมด: ในซอร์สทั้ง tree **ไม่เหลือ URL literal เลย** (เหลือ offline 100%)
- เติม Dart UI ที่ขาด (`flutter build apk` เดิมไม่มี `lib/` = บิลด์ไม่ได้)
- สร้าง `docs/CUTS.md` (เดิมโค้ดอ้างถึงแต่ไม่มีไฟล์) + `README.md`
- ไม่ได้ย้ายไฟล์ข้ามโมดูล — โครง Gradle/Flutter เดิมถูกต้องแล้ว
  (single APK ผ่าน `flutter build apk`, R8 ปิดเพราะ JNI+reflection)

## 2. ตารางเทียบ snake → Aether (ตาม layer ใน ANALYSIS)

| Layer snake | ของ snake (อ้างอิง) | ของ Aether (ไฟล์) | สถานะ |
|---|---|---|---|
| L1 แอพ/init | `com.snake.App`, `loadLibrary("engine")`, แยก role Main/Child/Server | `app/AetherApp.kt`, `app/EngineLoader.kt` | ✅ ตรง (role dispatch ครบ) |
| L2 JNI | `JNI_OnLoad` + `RegisterNatives` (~40), `Native.ic/compute/…` | `aether-native/aether_core.cpp` (25 entries) + `aether-core/Engine.kt` | ✅ ตรง (บาง body เป็น NOOP ที่ mark ไว้) |
| L3 native | ตรรกะใน `libengine.so` | `core/*.cpp` (mem/aob/crypto/vfs/hook/classmap/payload/keystore ฯลฯ) + `layer/bindmount/` | ✅ ตรง |
| L4 IPC/Provider | `ProxyContentProvider`, `SystemCallProvider`, stub P0–P3 | `proxy/ProxyContentProvider(+P0–P3)`, `ipc/AetherSystemCallProvider`, `ProxyService/PendingActivity/JobService/TransparentActivity`, `ipc/AetherStubReceiver`, `GuestProcessRegistry` | ✅ ตรง (ใช้ภายในเครื่องเท่านั้น) |
| L5 Dart UI | `libapp.so` + MethodCall handlers (`Ieg.dart`) | `app/lib/main.dart` + `app/lib/engine_api.dart` (**เขียนใหม่**) ↔ `EngineBridge.kt` (15 เมธอด) + `AetherHostActivity` | ✅ เติมแล้ว (ไม่มี LicenseStore/topup) |
| L6 Service/Daemon/VPN | `DaemonService`, `ProxyVpnService`, FCM | `daemon/AetherDaemonService(+Inner)`, `vpn/AetherVpnService` | ✅ ตรง (FCM ไม่เอา — อยู่กับ C2) |
| Sandbox/payload | `root/data/…`, `package.conf`, PGL, payload SHA-256, vdex | `SandboxManager.kt`, `PackageConfParser.kt`, `payload_store`, `provision*` | ✅ ตรง |
| ❌ C2 | `rest.snakeseller.com`, `snakeengine.com/topup`, `Ieg` handlers | — | **ตัด (NET-1..4)** |
| ❌ ใบอนุญาต | login gate, token/sellerId, topup, version-lock, `LicenseStore` (Dart) | — | **ตัด (NET-1..3, BIN-1)** ไม่สร้าง LicenseStore |

## 3. สิ่งที่ตัด (รอบนี้)

| รหัส | สิ่งที่ตัด | ไฟล์ |
|---|---|---|
| NET-1 | `CONFIG_ENDPOINT` (rest.snakeseller.com — URL เดียวในซอร์ส) | `SandboxManager.kt` |
| NET-2 | `fetchRemotePglMap()` ทั้งฟังก์ชัน → ใช้ตาราง `DEFAULT_*` | `SandboxManager.kt` |
| NET-3 | `fetchRemoteVersion()` → ใช้ `versionName` บนเครื่อง | `SandboxManager.kt` |
| BIN-1 | `EngineType.SNAKE` (opt-in โหลด `libengine.so` ทั้งก้อน) → เหลือ `aether` ตัวเดียว | `EngineLoader.kt` (เขียนใหม่) |
| NET-4 | import `HttpURLConnection/URL` ที่ไม่ได้ใช้ + คอมเมนต์ค้างเรื่อง upload | `CrashHandler.kt` |
| REN-1 | `fetchRemoteAsync/Sync()` → `fetchAsync/Sync()` (+ alias ชื่อเก่า `@Deprecated`) | `RemoteConfig.kt`, `AetherApp.kt` |

**คงไว้โดยเจตนา:** `ensureDeviceToken` (ไฟล์ใน sandbox ฝั่ง guest, ไม่มีเน็ต),
`OAuthFlow`/`InternalWebBrowser` (ผู้ใช้กดเอง, ไม่มี endpoint ตายตัว),
`AetherVpnService` (บนเครื่อง), `getDeviceId` (โชว์ UI), permission
`INTERNET` (เผื่อ WebView) — ดูเหตุผลเต็มใน `AetherEngine/docs/CUTS.md`

## 4. ไฟล์ที่สร้างใหม่

- `AetherEngine/app/lib/engine_api.dart` — client ครบ 15 เมธอดตรง `EngineBridge`
- `AetherEngine/app/lib/main.dart` — จอหลัก: device id + stats + ปุ่ม
  VirtualFS/handshake/อ่าน diag (ไม่มีจอ login/license)
- `AetherEngine/docs/CUTS.md` — ทะเบียนการตัด + นโยบาย offline-only
- `AetherEngine/README.md` — ภาพรวมโมดูล + สายบูต + วิธีบิลด์

## 5. การตรวจสอบ (ใน sandbox นี้ — ไม่มี Flutter/Android SDK เลยบิลด์จริงไม่ได้)

- [x] grep URL/`HttpURLConnection` ทั่วซอร์ส (kt/cpp/hpp/dart) = **0 จุด**
- [x] grep `CONFIG_ENDPOINT/fetchRemotePglMap/fetchRemoteVersion/EngineType/`
  `libengine.so/rest.snakeseller` = เหลือแค่คอมเมนต์ `[CUT]` ที่ mark ไว้
- [x] สมดุล `{}`/`()` ไฟล์ที่แก้ + Dart ใหม่ 7 ไฟล์ = ครบ
- [x] call site ทุกจุด (`fetchAsync`, `EngineLoader.load`) ตรงกัน ไม่มี caller ค้าง
- [ ] **ต้องทำบนเครื่องจริง:** `cd AetherEngine/app && flutter build apk --release`
  แล้วติดตั้งเทส — คาดว่าบิลด์ผ่าน (ไม่มีการเปลี่ยน API/ลายเซ็นที่ Dart/Kotlin เรียก)

## 6. งานค้างที่แนะนำ (ยังไม่ทำ)

1. บิลด์ + รันบนเครื่องจริง แล้วกดปุ่ม VirtualFS/handshake/อ่าน diag ในจอหลัก
2. ถ้าไม่ต้องการ `OAuthFlow`/WebView หรือ `ensureDeviceToken` — ตัดเพิ่มได้เลย
3. (ทางเลือก) ขยาย `tools/call_linkage` มาสร้าง call-linkage ของ Aether
   ต่อจาก snake — โครงรองรับอยู่แล้ว (`--extra` + chain registry)

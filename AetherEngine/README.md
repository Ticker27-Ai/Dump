# AetherEngine

Virtual-app + memory engine บน Android — สืบทอด **โครงสร้าง** มาจาก Snake
Engine 2.2.6 (module layout, JNI bridge, init chain, sandbox layout)
แต่**ไม่เอา C2 และระบบใบอนุญาต** (ดู `docs/CUTS.md`) — ทำงาน offline 100%

## โมดูล

| โมดูล | อะไรอยู่ข้างใน |
|---|---|
| `app/` | Flutter shell (UI) — `lib/main.dart`, `lib/engine_api.dart` (MethodChannel `com.aether/engine_bridge`) + Android host (`app/android`) |
| `aether-android/aether-app/` (`:aether-android`, library) | โค้ด engine ฝั่ง JVM: `app/` (Application+โหลด .so), `daemon/`, `ipc/`, `proxy/` (virtual-app/binder/WebView/OAuth), `vpn/` |
| `aether-core/` (`:aether-core`) | `Engine` (JNI facade), `GuestRuntime`, `SandboxManager`, `RemoteConfig` (offline), `PackageConfParser` |
| `aether-native/` (`:aether-native`) | `libaether.so`: `aether_core.cpp` (JNI_OnLoad + RegisterNatives) + `core/` (mem/aob/crypto/vfs/hook ฯลฯ) |

APK ประกอบผ่าน Flutter เท่านั้น (`app/android` ดึง 3 โมดูลมาเป็น subproject)

## สายการบูต (ย่อ)

```
AetherHostActivity → EngineBridge.init → AetherOrchestrator.init
AetherApp.onCreate → EngineLoader.load (libaether.so) → nativeExemptHiddenApi
  → nativeInitContext (main/child) → Flagger/RemoteConfig/CrashHandler
  → AetherOrchestrator → DaemonService(:engine) → Flutter UI (main.dart)
```

## บิลด์

```sh
cd app && flutter build apk --release   # ต้องมี Flutter SDK + Android SDK บนเครื่อง
```

ไม่มี toolchain พวกนี้ใน repo — CI ดู `.github/workflows/`

## กฎเหล็ก

- **offline-only / ไม่มี C2/ใบอนุญาต** — รายละเอียดและทะเบียนการตัดใน `docs/CUTS.md`
- `minSdk 28`, arm64 อย่างเดียว, ปิด R8 (`app/android/app/build.gradle` — กัน JNI+reflection พัง)
- JNI ลงทะเบียนทาง `RegisterNatives` ที่เดียวใน `aether_core.cpp`

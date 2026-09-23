# แผนยืดหยุ่นสู่ Snake Parity (Flexible Plan)

- วันที่: 2026-09-23 — เขียนหลังหลักฐานครบ (Codes.zip + snake.zip + dex-structural ตรวจเอง)
- เป้าหมาย: Aether รัน guest ได้ด้วยกลไกเดียวกับ Snake 2.2.6 โดยไม่แตะ C2/license (นโยบาย `CUTS.md` คงเดิม)
- วิธีอ่าน: แต่ละ phase มี **gate** (ผ่านจึงไปต่อ) + **ทางเลี่ยง** (flex) ถ้าหลักฐาน/เครื่องมือไม่พร้อม

## 0. กฎยืดหยุ่น 5 ข้อ (ห้ามแหก)

1. **Role+shape ไม่ใช่ชื่อ**: ชื่อ obf เปลี่ยนทุกบิลด์ (2.1.3↔2.2.6 พิสูจน์แล้ว) — อ้างอิง component ด้วยบทบาท+ลายเซ็นเท่านั้น (เช่น "PM-proxy: คืน *Info ครบ + `k(Context,AppInfo)→Resources`" ไม่ใช่ "zg0")
2. **Static ก่อน Runtime**: อะไรพิสูจน์ด้วย static ได้ → ทำเลย; อะไรต้อง runtime (body native, provider vocabulary เต็ม, Dart handler bodies) → เขียน probe ก่อนอ้าง
3. **Guest แยก Core**: ของเฉพาะ guest (eightballpool/PGL/package-profile) อยู่ชั้น guest-spec นอก core engine — ห้ามปน (บทเรียน §17/contamination)
4. **เลิกอ้าง parity ลอย**: ของ clean-room (mem/AOB/IO-rules/JNI ชุดขยาย) เก็บได้แต่ต้องถอดคำว่า "snake parity" ออกจนกว่าจะมีหลักฐาน
5. **Gate ทุก phase**: ไม่ผ่าน gate = หยุดที่ phase นั้น + ใช้ทางเลี่ยงที่ระบุ ไม่เดาต่อ

## Phase 0 — Baseline หลักฐาน (static ล้วน, ทำได้ทันที)

- ล็อก fingerprint ชุดอ้างอิง (APK `f84760…`, dex `e2b1fb…`, libengine `f5d751…`, libapp `2d3577…`) + เมทริกซ์ drift 2.1.3↔2.2.6 (ชื่อคลาส/ลายเซ็นที่เปลี่ยน)
- สร้าง role-map: Snake role → ไฟล์ Aether ปัจจุบัน → สถานะ (ตรง/ต่าง/ขาด) — ใช้ตาราง §2 ของ `SNAKE_EVIDENCE_AUDIT.md` + §6 เป็นต้นฉบับ
- **Gate G0**: role-map ครบทุก role ใน chain 24-hop — **Flex**: role ไหนไม่มีหลักฐาน → ติดป้าย `UNMAPPED` แล้วข้ามไปก่อน ไม่บล็อก phase 1

## Phase 1 — แก้ให้ตรงแบบไม่รื้อโครง (static-safe)

1. Authority → `"%s.proxy_content_provider_%d"`; keys → `_S_|_target_/_P_target_/_user_id_*` (+bundle `SnakeEngine_client_config`); คง `:engine` ไว้ (ถูกแล้ว)
2. ใช้ p3-map จาก jadx (`m/n/o/p/q/r/s`) แทนการเดา; แก้คอมเมนต์ `a7.w/u` → `r1.w/a7.u` + ถอดเลขบรรทัดที่พิสูจน์ไม่ได้
3. Stub-name builder ตาม format strings (`%s.helper.ProxyActivity$P%d%s` + 3 แบบ + provider)
4. Sandbox layout + conf 7 ไฟล์ตาม kv0; binder wrappers ขยาย 11 → 15 ตามหลักฐาน (activity_task + connectivity + packageinstaller + alarm — ดู audit §8 ว่า "26 Stub$Proxy" ไม่ใช่รายชื่อ services)

**P1 ปิดแล้ว 2026-09-23** (batch 1–5 + fix เขียว CI run 35808705857): handshake UID-check + p3 map ยืนยันตาม CALLSITE_MAP · G1 PM-identity fallback · LC0 license/c2 skeleton · G2 provider allow-list + flags · binders 11→15 · kv0 layout + SystemConf + installGuest(H) + UI ติดตั้ง/เปิดเกม — คงค้างเฉพาะ gates ที่ต้องใช้เครื่องจริง (G-NR, G-GMS experiment, G-LC3)
5. `package.conf`: ทิ้ง dual-parser → รองรับ Java-serialized profile (หรือ opaque + serialize ของตัวเอง)
6. ถอด `8BP`/Miniclip-game ออกจาก core (ย้ายไป guest-spec ถ้ายังต้องการ)
- **Gate G1**: `chainCheck` ผ่าน + CI เขียว + grep ไม่เหลือคำอ้าง parity ผิด ๆ — **Flex**: ข้อไหนกระทบรันไทม์ → แยก flag `parityXX` เปิด/ปิดได้

## Phase 2 — จัดสถาปัตยกรรมให้เหมือนต้นแบบ (รื้อปานกลาง)

1. **ทำ `ProxyActivity` ให้บาง** (shell ตามต้นแบบ) + ย้าย bootstrap ไป coordinator บทบาท jv0 (bind/bindApplication/O2-shape) ที่ถูกขับด้วย provider-handshake + H-callback ไม่ใช่ `onCreate`
2. **Entry channels**: MethodChannel `"A"` + เมธอด `A–J` (`G`=launch `(pkg,userId)`, `H`=install, …) แทน `engine_bridge` ชุดปัจจุบัน (เก็บของเดิมไว้หลัง flag จนกว่า UI ใหม่เสร็จ)
3. Daemon: alarm-restart (`onDestroy 1.5s`/`onTaskRemoved 1s`) + channel names จริง; Browser/OAuth ชุบตาม extras/broadcasts จริง; VPN กลับเป็น stub บาง
4. ProxyService/JobService/Pending/BroadcastReceiver เติม lifecycle ตาม dex
- **Gate G2**: ลำดับบูต `:pN` ตรง 24-hop (ตรวจด้วย trace) — **Flex**: ถ้าไม่มีเครื่องรัน → ตรวจด้วย unit/widget + `chainCheck`/`handshakeStatus` แทน แล้วค้าง G2 ไว้ (ไม่แก้ต่อแบบตาบอด)

## Phase 3 — ชั้น Guest-spec (แยก repo-dir ชัดเจน)

- Guest profile = `guest/<pkg>/`: conf layout, PGL loader hooks, UID map, version-check strings — eightballpool เป็น profile ตัวอย่างตัวแรก (หลักฐาน runtime มีครบสุด)
- `Native` Java helpers 8 ตัว (`a/b/gcuid/getApplicationInfo/il×2/logIn×2`) + `MethodUtils` 6 ตัว สร้างตามลายเซ็น dex (body เขียนเอง clean-room — ไม่คัดลอก)
- **Gate G3**: guest ตัวอย่างติดตั้ง (H) + เปิด (G) + รายงานผลผ่านไฟล์ได้ — **Flex**: ยังไม่มี guest จริง → ใช้แอพระบบ (เช่น เครื่องคิดเลข) เป็น guest ทดสอบตามที่เคยเสนอ

## Phase 4 — Runtime proof (ต้องมีเครื่อง/ฝั่งรัน)

- Frida probes ตาม `ANALYSIS §8` + `EVIDENCE_CHAIN §5` (RegisterNatives dump, `Provider.call` log, `MethodChannel` payload, HTTP capture ใน lab)
- ปิด NOT ESTABLISHED: provider vocabulary เต็ม, `update/pjowqpxe` callers, Dart handler bodies, `a7:317`-semantics จริง
- **Gate G4**: ทุกข้ออ้างพฤติกรรมใหม่มี trace รองรับ — **Flex**: ไม่มีเครื่อง → phase นี้พักทั้งก้อน งาน 0–3 ไม่ขึ้นกับ phase นี้

## Phase 5 — Dart UI (งาน C เต็มรูป)

- สร้าง UI ใหม่จาก pool strings (seller/orders/topup/i18n 5 ภาษา + social links) + ต่อ 3 MethodCall handlers — หน้า debug ปัจจุบันทิ้งได้เมื่อ phase นี้จบ
- **Gate G5**: เทียบ flow กับ `ANALYSIS §4.4` state machine ได้ครบ — **Flex**: ทำแค่ G/H (launch/install) ก่อนก็ได้ ที่เหลือตามหลัง

## สิ่งที่เจ้าของยืนยันแล้ว (2026-09-23 — ล็อก)

1. **เครื่องทดสอบ: NO-ROOT** — เส้นทาง root ทั้งหมด (mount --bind, resetprop, magiskpolicy) ใช้ไม่ได้ → ดู "No-root track" ข้างล่าง
2. **Guest = eightballpool ใช่** — ล็อกเวอร์ชัน **56.23.2** (มี split APK `split_config.arm64_v8a.apk` — installer ต้องรองรับ splits)
3. **`com.snake.zip` ได้แล้ว** — ตรวจแล้วตรง 56.23.2 (audit §7) — `jadx_out`/`com.snake_1.zip` ยังไม่มี (คงค้าง)
4. **`libengine_strings.txt`** ยังไม่มี (ลิงก์ minis:// เปิดไม่ได้) — คงค้าง
5. นโยบายไม่แตะ C2/license — **กลับคำสั่ง 2026-09-23**: เอา license/C2 กลับมาแบบ **FULL** (พิสูจน์ก่อน–ยืดหยุ่นทีหลัง แยกโมดูลกัน) → ดู "License/C2 FULL track" ข้างล่าง

## License/C2 FULL track (พิสูจน์ก่อน–ยืดหยุ่นทีหลัง — เจ้าของสั่ง 2026-09-23)

### หลักการแยกโมดูล (ไม่ต่อรอง)

```
core (offline ได้เสมอ — ต้องรันโดยปิดทุก flag)
  ↑ เรียกผ่าน interface เท่านั้น (DI ประกอบร่าง)
License module (นโยบาย)              C2 module (ขนส่ง)
- LicenseManager: VALID/GRACE/       - C2Transport + endpoint registry
  EXPIRED/OFFLINE                      (request builder/auth/retry/poll)
- token store (Access Token,         - OAuth/WebView login flow
  Seller ID ตาม Dart pool)             - mock server + record/replay
- cache+expiry+grace บนเครื่อง         fixtures สำหรับพิสูจน์
- tamper/env signals (ทรง su-fake×9)
```

- Core ห้าม import impl ของ license/c2 — รู้จักแค่ `LicenseProvider`/`C2Provider` interface (+ `NoOp` ตอนปิด)
- Flag อิสระ: `license.enabled`, `c2.enabled`, `c2.endpoint` (default = mock), `c2.mode = mock|replay|live`
- ยืดหยุ่นทีหลัง = ปิด flag / ลบโมดูล / สลับ endpoint ได้โดย core ไม่แตะ
- **BIN-1 ยังคงตัด**: ไม่โหลด `libengine.so` ของ Snake (เอาพฤติกรรม parity ด้วยโค้ดเรา ไม่ใช่ reuse ไบนารีเขา) — ถ้าเจ้าของจะสั่งคืนค่อยว่ากัน

### งาน

| ID | งาน | หลักฐานรองรับ |
|---|---|---|
| LC0 (P1) | โครง `license/` + `c2/` packages, interfaces, NoOp impls, flags — core พฤติกรรมเดิม 100% | — (โครงสร้าง) |
| L1 (P2) | `LicenseManager`: token store, state machine, cache+expiry+grace, env-signal inputs (ทรง su-fake×9; no-root = absent คือ clean) | Dart pool (Access Token/Seller ID), su-fake×9 |
| C1 (P2) | `C2Transport`: endpoint registry (`ENDPOINT_LIVE` = `rest.snakeseller.com/api/request/` — ลงทะเบียนอย่างเดียว, default วิ่ง mock), request/response envelope เริ่มต้น, retry/backoff | URLs pool-exact; header ที่เดาไว้ถูกพิสูจน์ผิดแล้ว → shape จริงรอ P4 |
| C2 (P2/P3) | ชุบ OAuth login: `InternalWebBrowser` + `_oauth_redirect_prefix` + broadcasts `INTERNAL_OAUTH_RESULT/CANCELLED` → ต่อเข้า token store; topup WebView (`snakeengine.com/topup/`) | dex (browser+redirect+2 broadcasts), native (oauth URL+client-id), pool (topup URL) |
| LC-proof (P3/P4) | พิสูจน์บน mock: login→token→orders→topup ครบสาย + fixtures เช็คอิน; ปิดหลักฐาน JSON shape จริงด้วย jadx_out/traffic capture | ต้องได้ jadx_out หรือ capture (ยกระดับคำสั่งซื้อเดิม) |

### Gate + กติกา live endpoint

- **G-LC1**: build+tests ผ่านทั้ง flags OFF (offline parity เดิม) และ ON-against-mock
- **G-LC2**: โฟลว์ login→entitlement→orders เขียวบน mock + ไม่มี live endpoint hardcode ใน code path (อยู่ใน registry เท่านั้น)
- **G-LC3 (ต้องเจ้าของสั่งชัด)**: default = **ห้ามยิง live** (`rest.snakeseller.com` ของจริง) — ถ้าสั่งพิสูจน์ live ต้องเป็นเครื่อง lab + account แยก + rate-limit + จดบันทึก (server เขาจะ reject client แปลกหน้าอยู่แล้ว + เลี่ยงพฤติกรรม abusive)

## No-root track (ผลจากการล็อกข้อ 1)

| งาน | เดิม (มี root) | No-root (ที่ต้องทำ) |
|---|---|---|
| `mountSandbox` | `mount --bind` พาธเกมจริง | **copy APK+splits เข้า sandbox** (Java/Kotlin file copy) + `VirtualFS` redirect — P1 ต้องพิสูจน์ fallback นี้ก่อน |
| PGL stubs | bind ทับ `…/arm64-v8a/*.so` | copy stub ลง sandbox + redirect path — ห้ามแตะไฟล์เกมจริง |
| `resetprop`/magiskpolicy/stealth-root | ปรับ props ระบบ | **ตัดออก** — คงแค่ `PR_SET_DUMPABLE` + non-root checks |
| ติดตั้ง guest (H) | ผ่าน PMS เสมือน + mount | copy จาก `uri` (`lr.c`-shape) + `getPackageArchiveInfo` ตรวจ valid + แตก splits ตาม ABI (ไม่ต้อง root) |
| VPN (ถ้าชุบ) | ตั้งค่าเน็ต | ต้องมี consent dialog + `BIND_VPN_SERVICE` (no-root ทำได้ แต่ Snake ต้นแบบเป็น stub — ตามต้นแบบไปก่อน) |
| P4 Frida probes | ตรงไปตรงมา | ต้องใช้ `frida-gadget` ฝังใน APK (no-root) หรือ emulator-root ชั่วคราวเฉพาะ lab — ตัดสินใจตอนถึง P4 |

**Gate เพิ่ม G-NR**: `bootstrapGameData + mountSandbox + launchInSandbox` ต้องรอดบนเครื่อง no-root (ตรวจด้วย `chainCheck` + `launch_result.json`) ก่อนปิด P1

## GMS track (หลักสำคัญ — เจ้าของสั่งโฟกัส)

### หลักฐาน (ย่อ — เต็มอยู่ใน turn log 2026-09-23)

- **Guest 56.23.2 ต้องการ GMS ทั้งชุด** (package.conf 65 hits): Firebase ครบ (InitProvider/Messaging/Crashlytics+NDK/Sessions/Installations/datatransport), **PlayGames** (`PlayGamesInitProvider` + `games.APP_ID` + v2 activities), **Google Sign-In** (`SignInHubActivity` + `RevocationBoundService`), **MobileAds** (+`DELAY_APP_MEASUREMENT_INIT`), Analytics legacy, Measurement, **Billing V1+V2** (`ProxyBillingActivity`×2 + PlayCore dialog), c2dm, install-referrer — **ไม่มี Integrity/SafetyNet** ✓ (ตัดความเสี่ยงนี้ออก)
- **Snake พิสูจน์แล้วว่า pass-through รอด**: guest ใต้ Snake มี Firebase installation ของตัวเอง (`PersistedInstallation…697261581904…` + heartbeat), `gms.appid`, `measurement.prefs`, `crashlytics.xml`, measurement DB — คือ guest คุย GMS core จริงสำเร็จ
- **Snake dex ไม่มี skip-list ฝั่ง guest-GMS** (`SignInHubActivity`/`ProxyBillingActivity`/`games.APP_ID` = 0 hits) — engine ปล่อยผ่าน + ความสอดคล้อง identity (p3) ทำงานแทน
- **Aether วันนี้ทำตรงข้าม**: skip `FirebaseInitProvider` + `gms.ads/measurement` + ads ทั้งหมด; firewall กลืน GMS SE; PM-proxy ส่ง DATA query ตรง (`getPackageInfo(guest)` คืนของจริง/host) = **ไม่มี guest-identity spoof** — นี่คือสาเหตุที่ GMS จะ reject (`Unknown calling package name` บน main looper → process ตายเงียบ ตามที่คอมเมนต์ `0955c54/P4` บันทึกไว้)

### งาน (no-root ทำได้ทั้งหมด)

| ID | งาน | หลักฐานรองรับ |
|---|---|---|
| G1 | **PM-proxy guest-identity**: `getPackageInfo/getApplicationInfo/signatures` ของ guest ต้องคืนข้อมูล guest (อ่านจาก APK ที่ติดตั้งผ่าน `getPackageArchiveInfo` — ไม่ต้อง root) + p3-map coherence (guest UID/userId/token) | Snake pass-through + p3 jadx-map |
| G2 | **Provider allow-list** แทน blanket-skip: นโยบายรายตัว + log เหตุผล; ลำดับเปิด: `FirebaseInitProvider` → `PlayGamesInitProvider` → MobileAds (เคารพ `DELAY_APP_MEASUREMENT_INIT`) → measurement; ติดตั้งแบบ gated (try/catch + นอก main dispatch ถ้าจำเป็น) | guest InitProviders ใน conf + SE หลักฐาน P4 |
| G2-impl (P1 batch 3 ✅) | `ProviderPolicy` + `ProviderFlags` (core): default = พฤติกรรมเดิมทุกประการ (SKIP ชุดเดิม); เปิดทดลองทีละ flag ตามลำดับ PlayGames → Firebase-retest → gms.ads → ads; logcat telemetry `SKIP/GATED-TRY/GATED-OK/FAIL` + สรุป `installProviders → ok/total`; V1/V2 ใช้ policy เดียวกัน; ตัด prefix `gms.measurement` ที่ตาย (ไม่มี provider นี้ใน manifest จริง) | package.conf 13 providers + device proof 0955c54 |
| G3 | **Intent routing กิจกรรม GMS ของ guest**: `SignInHub/GamesResolution/AdActivity/ProxyBilling×2/PlayCoreDialog/GoogleApiActivity` ต้อง resolve + swap ผ่าน stub ได้ (อยู่ใน guest manifest แล้ว — verify ทีละตัว) + account-manager proxy รองรับ Sign-In flow | package.conf component list |
| G4 | **Billing/FCM end-to-end**: `ProxyBillingActivity` flow + `FirebaseMessagingService` routing ของ guest — หมายเหตุ: นี่คือ billing ของ guest เอง ไม่ใช่ license ของเรา (ไม่ขัด CUTS.md — รอเจ้าของยืนยันอีกครั้ง) | Billing V1+V2 + MESSAGING_EVENT ใน conf |
| G5 (ถ้าจำเป็น) | virtual-broker/worker-layer ทรง ninja D5 (กัน SE ลง main) — ทำก็ต่อเมื่อ G2 gated แล้ว main ยังตาย | คอมเมนต์ P5 ในโค้ด |

### Gate + ความต้องการ

- **Gate G-GMS**: guest เปิดได้ + `gms.appid` + measurement prefs + Firebase installation ของ guest เกิดขึ้น (เทียบ dump จริง) + Play Games sign-in สำเร็จ — โดยไม่มี SE ค้างใน firewall log
- เครื่องทดสอบต้องมี: GMS core (Play Services) + Google account + guest 56.23.2 ติดตั้งอยู่
- ความเสี่ยงหลัก: Firebase API-key ตรวจ package+SHA-1 (mitigation: G1 signature spoof + เทสจริง); measurement dynamite (mitigation: DELAY + gated install)

## ตาราง role-map ตั้งต้น (ย่อ — ฉบับเต็มอยู่ใน audit §2+§6)

| Snake role (shape) | Aether ปัจจุบัน | สถานะ |
|---|---|---|
| Entry (launcher + channels A–J) | `AetherHostActivity` (Flutter เปล่า) | ขาด → P2 |
| Facade yu0/xu0 (role+singleton) | `AetherApp` + `Orchestrator` (ปนกัน) | ต่าง → P2 |
| Core jv0/iv0 (bind/O2-shape) | `GuestRuntime`+`Bridge`+`Loader` | ต่าง → P2 |
| PM-proxy zg0/pv0 | `ServiceBinderProxy` (11/26) | ขาด 15 → P1 |
| AM-slot r1/a7 + p3 map | `GuestProcessTable/Holder` (keys ผิด) | แก้ → P1 |
| il0/kl0 (pack/stub-name) | ชื่อ stub hardcode | แก้ → P1 |
| Instrumentation b8/zh | `AetherInstrumentation` | ใกล้ → P2 |
| H-callback my | `HCallbackProxy` | ใกล้ → P2 |
| Providers + handshake | `ProxyContentProvider` (authority/keys ผิด) | แก้ → P1 |
| DaemonService + alarms | watchdog อย่างเดียว | เติม → P2 |
| Browser/OAuth/VPN | DEAD ทั้งสาม | ชุบ → P2 |
| Native bridge (11+2) + helpers | JNI ประดิษฐ์ + ไม่มี helpers | แยก → P1+P3 |
| Dart UI seller/orders | หน้า debug | สร้างใหม่ → P5 |

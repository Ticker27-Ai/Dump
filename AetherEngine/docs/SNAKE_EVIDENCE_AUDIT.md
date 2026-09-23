# รายงานหลักฐาน Snake ต้นแบบ + ผลเทียบกับ Aether (Snake Evidence Audit)

- วันที่ตรวจ: 2026-09-23
- วิธีตรวจ: อ่าน fragments F1–F8 + VERIFICATION + C2 report + IOC + LINKAGE/CALL_LINKAGE + ANALYSIS ทั้งหมด; เขียน DEX parser (stdlib ล้วน) ดึงรายชื่อเมธอด/ฟิลด์ของทุกคลาสที่ Aether อ้างถึงจาก `classes.dex` จริง; grep สตริง cross-check ทุกชื่อที่ Aether อ้างว่า "snake parity"
- วินัยหลักฐาน: CONFIRMED = เห็นจากไบต์/offset, STRUCTURAL = มีเมธอด/ฟิลด์รูปร่างตรงแต่ body พิสูจน์ไม่ได้, NOT ESTABLISHED = ไม่มีหลักฐาน, CONTAMINATED = หลักฐานปนเปื้อน

## 0. สถานะไฟล์หลักฐาน (สำคัญ — อ่านก่อน)

| ไฟล์ | สถานะ |
|---|---|
| `snake.zip` ที่ระบุ | **ไม่มีใน repo** — ค้นทั้ง `origin/main` และ `origin/arena` แล้วไม่พบชื่อนี้ |
| `Codes.zip` (บน main, commit `ab17769`) | **มี** — ข้างในคือ `Codes/SnakeLogic/` = ชุดวิเคราะห์ SNAKE.apk 2.2.6 (fragments + linkage + manifest/dex/res ที่ถอดแล้ว) — รายงานฉบับนี้ใช้ชุดนี้เป็นหลัก |
| `com.snake.zip` (runtime dump ที่คอมเมนต์ Aether อ้าง T1/T2) | **ไม่อยู่ใน Codes.zip** — อ้างถึงใน C2 report §17 เท่านั้น (พร้อมคำเตือนปนเปื้อน) |
| `libengine.so` / `libapp.so` ตัวจริง | **ไม่อยู่ใน Codes.zip** — มีแค่ผลวิเคราะห์ (F4–F8, blutter outputs) + fingerprints |
| `docs/SNAKE_UI_BLUEPRINT.md` | **ไม่มี** (ยืนยันซ้ำ) |
| `ANALYSIS_Snake_Engine_2.2.6.md` (ราก repo) | มี — รายงาน static 519 บรรทัด ลงวันที่ 2026-09-22 ใช้อ้างอิงร่วม |

Fingerprints (ยืนยันตรงกันทั้ง F1/VERIFICATION/C2 report): APK `f84760…`, dex `e2b1fb…`, libengine `f5d751…`, libapp `2d3577…`, libflutter `0baa71…`

## 1. Snake ตัวจริงคืออะไร (สรุปจากหลักฐาน)

- **แอพ**: `com.snake` v2.2.6 (minSdk 28 / target 35) ป้ายชื่อ "Snake Engine" — **Flutter (Dart 3.5.4 AOT) + Android bridge + native**
- **ประเภทธุรกิจ**: แอพ **seller/order** (SnakeSeller) — seller login, Access Token, Seller ID, Recent/All Orders, Order Details, Topup ผ่าน WebView, Google OAuth, ลิงก์โซเชียล (facebook/telegram/whatsapp/discord) — **ไม่ใช่เกม** และ UI เป็น Dart AOT (กู้ได้แค่สตริง + ชื่อ handler)
- **Entry**: launcher คือ `com.Entry` (activity ธรรมดา + dispatcher `C(id0,kd0$d)` + callback `onActivityResult/onRequestPermissionsResult`) — ไม่ใช่ FlutterActivity
- **Native**: `libengine.so` 8.5MB — packer/protector (mmap RWX + เขียน B-opcode + jump), `JNI_OnLoad` ไม่ register อะไร, RegisterNatives 3 จุด (n=10 หา `com/snake/helper/Native` ยาว 23 ตัวอักษร / n=2 หา `na/nb` / n=1 หาชื่อยาว 8 = `pjowqpxe`) รวม 13 = 13 declarations พอดี, `.mytext` ทำ `FromReflectedMethod` ให้ `update(Object,Method)` ตัวเดียวที่รับ `Method`
- **Endpoints จริงใน libapp.so (pool-exact)**: `https://rest.snakeseller.com/api/request/` (REST หลัก) + `https://www.snakeengine.com/topup/` (topup web) — ส่วน header ที่เคยเดา (`clientAuth/apiToken/clientVersion/signature`) ถูกพิสูจน์แล้วว่า **ไม่ใช่** (pool hits = 0)
- **IPC**: provider authority ฟอร์แมต `"%s.proxy_content_provider_%d"` → `com.snake.proxy_content_provider_0..3`, handshake method `_Engine_|_init_process_` + keys `_S_|_*` 12 ตัว (ดู §3), โปรเซส `:p0–:p3` (ใน manifest มีแค่นี้ — **ไม่มี `:engine**)

## 2. ผลเทียบ Snake ↔ Aether (ตารางหลัก)

### 2.1 ตรงกัน (Aether ทำถูก — มีหลักฐานรองรับ)

| ข้ออ้าง Aether | หลักฐาน Snake | สถานะ |
|---|---|---|
| โครง helper `Proxy*/DaemonService/FileProvider/InternalWebBrowser/flagger/Native` | คลาส `com/snake/helper/*` ใน dex ครบชุดเดียวกัน + manifest components 51 ตรงกัน | CONFIRMED |
| โปรเซส `:p0–:p3` + proxy `P0–P3` (+`_L` landscape) | สตริง `:p0…:p3` ใน manifest + dex/manifest มี `P0–P3`/`P0_L–P3_L` ครบ | CONFIRMED |
| handshake `_Engine_|_init_process_` + `_S_|_*` | ใน dex มี method นี้ + keys 12 ตัว (`_target_`, `_P_target_`, `_user_id_`, `_P_user_id_`, `_UserId`, `_server_`, `_server_name_`, `_token_`, `_activity_info_`, `_activity_token_v_`, `_service_info_`, `_start_id_`) | CONFIRMED (keys) |
| `jv0.O2/P2/D2/E2` | `jv0` มี `O2(String,String)`, `P2(p3)`, `D2()→p3`, `E2()→String`, `C2(IBinder)→Activity`, `A2→Service`, `B2()→jv0` ฯลฯ (~40 เมธอด) | STRUCTURAL |
| `zg0.k` = ตัวทำ guest Resources | `zg0.k(Context,ApplicationInfo)→Resources` มีจริง; `zg0` ทั้งคลาสคือ PM-proxy (คืน ActivityInfo/PackageInfo/ProviderInfo/ServiceInfo/…) | STRUCTURAL (แรง) |
| `tz.i` = proxy handler ของ AMS | `tz.i(Object,Object)` มีจริง + `tz.l/n(Object,Method,Object[])` = ทรง `InvocationHandler.invoke` | STRUCTURAL (แรง) |
| `b8` = Instrumentation delegate | `b8` มี `callActivityOn*`/`newActivity` ครบ + ฟิลด์ `l:Instrumentation`; F2 ยืนยัน `b8.callActivityOnResume` invoke `Native` | STRUCTURAL |
| `p3` = config parcelable มี int `p/q/r` | `p3` เป็น Parcelable มีฟิลด์ `m,n:String`, `o,p,q,r,s:int`, `t:IBinder` | STRUCTURAL (รูปร่าง) |
| `yu0.f(Context,wb)` | มีจริง | STRUCTURAL |
| `ic(Context)`/`ac(O,O)`/`update(O,Method)`/`pjowqpxe(O,O,O)` | 11 natives + `flagger.na/nb` ตรง F2 ทุกตัวอักษร | CONFIRMED |
| `SystemCallProvider.a():boolean` + `b(Bundle)` | มีจริงทั้งคู่ | STRUCTURAL |
| VPN มีช่องทาง always-on | manifest มี `ProxyVpnService` + `SUPPORTS_ALWAYS_ON=true` | CONFIRMED (surface) |
| OAuth/browser เป็นของจริง | `InternalWebBrowser` (WebView+ProgressBar+validate) + Google OAuth URL + โซเชียลใน Dart pool | CONFIRMED |

### 2.2 ไม่ตรง / ผิด (ข้อมูลไม่ตรงตามที่ท้วง — เรียงตามความร้ายแรง)

| # | ข้ออ้าง/ของใน Aether | ความจริงจากหลักฐาน | หลักฐาน |
|---|---|---|---|
| 1 | `ProxyActivity.onCreate` หนา = bootstrap ทั้งหมด (container+attach+guest+swap+recreate) | **`ProxyActivity` ของ Snake มีแค่ `init`+`onNewIntent`, `P0` มีแค่ `init` — ไม่มี `onCreate` เลย** — ตรรกะบูต guest ของ Snake ไม่ได้อยู่ใน activity นี้ (แคนดิเดต: `Native.a/b(Activity,String,IJZ)`, `vx.f` ทรงเดียวกัน, `jv0.*`, provider dispatch) | dex method list |
| 2 | `r1.w()` ("base stub ยิงเมื่อไม่ใช้ slot") | **`r1` ไม่มีเมธอด `w`** (มีแค่ `a–t` ตัวเดียว) — อ้างผิด (แต่ `r1.k(Intent,I,il0,ActivityInfo)→Intent` มีจริง รับ `il0` ตรงข้ออ้าง stub) | dex method list |
| 3 | `a7.w` ("ขั้น ② a7.w/u:292") | **`a7` ไม่มีเมธอด `w`** (มี `a–u`, `m(yj0)→boolean` กับ `u(…5 args)→yj0` มีจริง) — ครึ่งหนึ่งผิด; เลขบรรทัด `:292/:171/:317` พิสูจน์ไม่ได้จาก static | dex method list |
| 4 | miniclip = เกมเป้าหมาย (VPN log ช่วง IP, สมมติฐาน guest) | สตริง `miniclip` ใน dex = **`com.miniclip.madsandroidsdk` (โฆษณา MADS SDK) เท่านั้น** — ไม่ใช่เกม | dex strings (2 hits, context ads SDK) |
| 5 | `8BP`/`PGL`/`pangle` (launcher heuristic + stub) | **0 hits ทั้ง dex** — ไม่มีใน Snake static เลย | dex strings |
| 6 | `_S_|_guest_pkg_` + `target_package` + `EXTRA_SLOT` + `DIAG_PKG` | **0 hits ทั้งหมด** — Snake ใช้ `_S_|_target_`, `_S_|_P_target_*`, `_user_id_*` — ชุดคีย์ Aether ตั้งชื่อเอง | dex strings |
| 7 | โปรเซส `:engine` (Aether daemon/inner) | manifest Snake มีแค่ `:p0–:p3` — **ไม่มีสตริง `:engine`** | manifest strings |
| 8 | authority `com.aether.proxy.content.N` | Snake ใช้ `"%s.proxy_content_provider_%d"` (`com.snake.proxy_content_provider_0..3`) — Aether รู้แล้วแต่คงของตัวเองไว้ (มีคอมเมนต์ P2) | dex format string + manifest |
| 9 | JNI ชุดขยาย (`nativeFindModuleBase/scanAOB/attach/setSeed/compute/watchdog/exempt/hydrate/IO规则/classRule/compress/reflect/triple/pair/initContext`…) | **0 hits ทั้ง dex** (ยกเว้น `nativeAttach` 1 = ของ Flutter ไม่ใช่ Aether) — ทั้งชุด Aether ประดิษฐ์เอง ไม่มีใน Snake | dex strings |
| 10 | `b8.callActivityOnResume → Native.ac` (ระบุตัว) | F2 บันทึกแค่ "20 callers ระดับคลาส" **ไม่ระบุว่าเรียก native ตัวไหน** — `→ac` เป็น INFERRED ไม่ใช่ proven | F2 + ANALYSIS E4 |
| 11 | `a5: newInstance()` ("SNAKE-proven fix") | `a5` **ไม่มีเมธอดเลย** (มีแค่ 3 ฟิลด์ `go0*`) — พฤติกรรม "a5 fix" พิสูจน์ไม่ได้จาก static | dex method list |
| 12 | `p3.p/q` = uid, `p3.r` = user id | ฟิลด์ `p,q,r:int` มีจริง (รูปร่างผ่าน) แต่ **ความหมายแต่ละฟิลด์พิสูจน์ไม่ได้** — ต้องอ่าน body/decompile | dex fields |
| 13 | `il0` แพ็ค `_S_|_target_` / `kl0` = slot→component | `il0` ถือ (int,ActivityInfo,Intent,String) + `r1.k` รับ `il0` ✓ / `kl0` เป็น int→String ทั้งคลาส ✓ — รูปร่างผ่าน แต่ mapping จริง NOT ESTABLISHED | dex method list |
| 14 | `AetherVpnService` (TUN เต็มรูปแบบใน Kotlin) | `ProxyVpnService` ของ Snake **มีแค่ `init`** — ตรรกะ VPN ไม่ได้อยู่ใน Java (น่าจะ native/อื่น) — Aether เขียน TUN เองโดยไม่มีต้นแบบ Java | dex method list |
| 15 | `package.conf` parser (dual-encoding + semver-before-base.apk) | dex มีสตริงเปล่า `"package.conf"` แค่ 1 hit (ไม่มี path ไม่มี format) — parser ทั้งตัวของ Aether ไม่มีหลักฐานรองรับ (น่าจะมาจาก dump ปนเปื้อน §4) | dex strings |
| 16 | `IPC_ACCESS` signature permission | dex ไม่มี custom permission ของ `com.snake` เลย (manifest มีแค่ `DYNAMIC_RECEIVER_NOT_EXPORTED`) | dex + F3 |

### 2.3 ของจริงที่ Aether ขาด (ต้องสร้างเพิ่มเพื่องาน C)

| ของใน Snake | สถานะ Aether |
|---|---|
| `com.Entry` (launcher + dispatcher + callback) | ไม่มี — Aether ใช้ `AetherHostActivity` (FlutterActivity เปล่า) |
| `Native.a/b/gcuid/getApplicationInfo/il/logIn` (8 Java helpers) | ไม่มีเลย |
| `MethodUtils` (getMethodName/getDesc/…) | ไม่มีเลย |
| `InternalWebBrowser` + OAuth flow ที่ต่อจริง | มีไฟล์แต่ DEAD (0 callers) — ต้องชุบชีวิต |
| `ProxyVpnService` ที่ต่อจริง | มีไฟล์แต่ DEAD (ไม่เคยสตาร์ท) — และทรงไม่ตรงต้นแบบ (ต้นแบบ Java ว่าง) |
| `ProxyService/ProxyJobService` lifecycle เต็ม (`onStartCommand/onStartJob/onStopJob/…`) | Aether เป็น stub (`onBind null`/finish ทันที) |
| `ProxyPendingActivity.onCreate` + `ProxyBroadcastReceiver.onReceive` | Aether มีไฟล์แต่ไม่มี caller |
| `loadLibrary("engine")` แบบซ่อนชื่อ (fill-array-data) | Aether โหลด `libaether` ตรง ๆ |
| Dart UI (seller/orders/topup/i18n 5 ภาษา) + 3 MethodCall handlers | Aether มีแค่หน้า debug — ไม่มีอะไรตรงนี้เลย |

## 3. คำตอบเรื่อง "ข้อมูลอาจไม่ตรง" — ตรงเผง และสาเหตุใหญ่อยู่ที่ §17

C2 report §17 (Evidence Contamination Warning) ระบุชัด: **`com.snake.zip` (runtime dump) ปนเปื้อน** — มี `com.snake/root/data/user/0/com.miniclip.eightballpool/` (8 Ball Pool!) + `root/proc/0/cmdline` = eightballpool ฝังอยู่ รายงานสั่ง **ห้าม attribute ของ eightballpool ให้ Snake** — แต่ร่องรอยใน Aether (`8BP` heuristic, PGL stub, Miniclip IP, `package.conf` parser, `bootstrapGameData` จาก "เกมจริง") ไม่มีใน Snake static เลยแม้แต่ hit เดียว → **สรุปได้ว่า Aether ส่วน "game-data" สร้างจากส่วนปนเปื้อนของ dump ไม่ใช่จาก Snake** นี่คือรากของความไม่สอดคล้อง

## 4. สิ่งที่ต้องแก้ใน Aether เพื่องาน C (เรียงลำดับ)

1. **ย้าย guest-bootstrap ออกจาก `ProxyActivity.onCreate`** — ของจริง activity ว่าง; ย้ายตรรกะไปชั้น coordinator ทรง `jv0` + bridge ทรง `Native.a/b` แล้วให้ proxy เป็น shell ตามต้นแบบ
2. **แก้ชื่อ/เลขที่อ้างผิด**: ลบ `r1.w`/`a7.w` (ไม่มีจริง), ถอดเลขบรรทัด decompile (`:292/:171/:317/:58`) ที่พิสูจน์ไม่ได้, เปลี่ยน `→ac` เป็น candidate
3. **เปลี่ยน authority + keys + process ให้ตรง**: `"%s.proxy_content_provider_%d"`, ใช้ `_S_|_target_/_P_target_/_user_id_` แทน `guest_pkg`/`target_package`/`EXTRA_SLOT`, ตัด `:engine` (หรือพิสูจน์ว่า Snake daemon อยู่ process ไหนก่อน)
4. **สร้างของที่ขาด**: `Entry` launcher, `Native` Java helpers 8 ตัว, `MethodUtils`, ชุบ `InternalWebBrowser`+OAuth (Google OAuth + topup URL จริง), ชุบ VPN ตามทรงต้นแบบ (Java บาง + native), lifecycle เต็มให้ ProxyService/JobService/Pending/BroadcastReceiver
5. **ตัดของปนเปื้อน**: `8BP`/PGL/Miniclip-game/`package.conf`-dual ทั้งหมด (หรือย้ายไป guest-spec ภายนอก ไม่ใช่ core)
6. **Dart UI ใหม่**: seller/orders/topup ตามสตริง pool (มีครบใน pp.txt + i18n) — หน้า debug ปัจจุบันทิ้งได้เมื่องาน C เริ่ม
7. **อย่าแตะ**: อย่าเอา `libengine.so`/endpoints/credentials ของ Snake กลับมา (นโยบาย CUTS.md) — สร้าง `libaether` ต่อแต่ตัด JNI ที่อ้าง parity ผิด ๆ ให้เหลือแค่ที่ออกแบบเองจริง

## 5. หลักฐานที่ยังขาด (ต้องการเพื่อปิด NOT ESTABLISHED)

1. `com.snake.zip` ตัวจริง (runtime dump — ตอนนี้มีแค่คำอ้าง) 2. `libengine.so`/`libapp.so` ไบนารี (มีแค่ผลวิเคราะห์) 3. decompile `com.snake.helper.*` + `androidx…menu/{jv0,a7,r1,p3,il0,kl0,tz,zg0,b8,yu0,vx,z10}` (body ทั้งหมด) 4. runtime traces ตาม ANALYSIS §8 (Frida RegisterNatives dump, Provider.call log, HTTP capture) 5. `SNAKE_UI_BLUEPRINT.md`

## ภาคผนวก ก. ลายเซ็นที่ตรวจจาก dex (STRUCTURAL ทั้งหมด — body ไม่รู้)

- `jv0`: `O2(String,String)`, `P2(p3)`, `D2()→p3`, `E2()→String`, `C2(IBinder)→Activity`, `A2(ServiceInfo,IBinder)→Service`, `B2()→jv0`, `y2(ServiceInfo)→JobService`, `z2(ApplicationInfo)→Context` (+ ~30)
- `a7`: `a–u` ตัวเดียว (`m(yj0)→boolean`, `u(String,String,I,I,I)→yj0`, **ไม่มี `w`**)
- `r1`: `a–t` ตัวเดียว (`k(Intent,I,il0,ActivityInfo)→Intent`, `m(…ActivityInfo,IBinder,I)→p1`, **ไม่มี `w`**)
- `p3`: Parcelable `m,n:String`, `o,p,q,r,s:int`, `t:IBinder`
- `il0`: `(int,ActivityInfo,Intent,String)`, `a(Intent)→il0`, `b(Intent,Intent,ActivityInfo,String,int)`
- `kl0`: `a–i(int)→String`, `j(String)→boolean`
- `tz`: `i(Object,Object)`, `l/n(Object,Method,Object[])→Object` (= invoke-shape), `m(Object)→long`, `o(Object[])→int`
- `zg0`: `a–k` (คืน *Info ทุกชนิด), `k(Context,ApplicationInfo)→Resources`
- `b8`: Instrumentation delegate เต็ม + ฟิลด์ `l:Instrumentation`
- `Native`: 11 natives (`ac/aior/awl/chl/djp/eio/i/ic/ilil/pjowqpxe/update`) + 8 Java (`a/b/gcuid/getApplicationInfo/il×2/logIn×2`)
- Provider authority: `"%s.proxy_content_provider_%d"`; handshake `_Engine_|_init_process_` (+`_Engine_|_client_`); keys `_S_|_*` 12 ตัว (§2.1); processes `:p0–:p3` เท่านั้น

---

## 6. รอบแก้ 2 — สิ่งที่ snake.zip (2026-09-23) เปลี่ยนคำตัดสิน (อ่านทับ §2–§4)

หลักฐานใหม่: `EVIDENCE_CHAIN.md` (chain ติดตั้ง/เปิดเกมจาก jadx 3,084 ไฟล์), `NATIVE_CALLSITE_MAP.md` (24-hop "G"→เกมรัน + call-site ราย native), `file_read` (MASTER_INDEX decompile 2026-09-09), `libapp/libengine_analysis.md`, `libengine_dump.txt`, สรุป dex/manifest **2.1.3** (อีกเวอร์ชัน — เทียบ drift กับ 2.2.6 ได้), `patch.md` (diff เต็มของ SnakeLogic + blutter asm + res)

### 6.1 คำตัดสินที่ถูกพลิก (ของเดิมผิด — ยอมรับตรงนี้)

| ข้อ | เดิม (§2.2) | ใหม่ (หลักฐาน) |
|---|---|---|
| #2 `r1.w` | "ไม่มี — อ้างผิด" | **ผิดที่ผมเอง**: `head` ตัด output parser — รันใหม่เต็มแล้ว `r1` มี `u,v,w,x,y,z` ครบ, `w(I,Intent,ActivityInfo,p1)→Intent` **มีจริง** + jadx ยืนยัน `r1.java:578 w()` (จอง stub) — ข้ออ้าง Aether ถูกต้อง |
| #7 `:engine` | "ไม่มี — Aether ประดิษฐ์" | **พลิก**: ค่า `:engine` อยู่ใน `resources.arsc` (`engine_service_name`, manifest อ้าง `@0x7f100041`) + EVIDENCE_CHAIN ยืนยัน Server role — `:engine` ของ Aether **ถูกต้อง** |
| #10 `b8→ac` | "INFERRED ไม่ใช่ proven" | **พลิก**: jadx ยืนยัน `b8.java:79 Native.ac(activity, getDeclaredMethod("pjowqpxe"))` — ข้ออ้าง Aether ถูกต้อง |
| #12 ความหมายฟิลด์ `p3` | "NOT ESTABLISHED" | **พลิก**: jadx ยืนยัน map `m`=guest pkg, `n`=processName, `o`=slot, `p`=guest UID, `q`=server myUid, `r`=userId, `s`=caller token — Aether ถูก 2.5/3 (p=guest UID ✓, r=userId ✓, q=server myUid ≈) |
| #13 `il0/kl0` mapping | "NOT ESTABLISHED" | **ยืนยัน**: `il0.b` ใส่ extras `_S_|_*` (hop 15), `kl0.a/d` สร้างชื่อ stub (hop 14, EVIDENCE_CHAIN ขั้น D) |

### 6.2 คำตัดสินที่คงเดิม แต่ได้ความคมเพิ่ม

| ข้อ | สถานะใหม่ |
|---|---|
| #1 ProxyActivity ว่าง | **คง** (P0 = init-only, ไม่มี onCreate — ตรวจครบแล้ว) + กลไกชัด: Snake ขับ `:pN` ด้วย provider-handshake + H-callback (`my.h→O2`) ไม่ใช่ activity — Aether ที่ยัด bootstrap ไว้ใน `onCreate` คือจุดต่างเชิงสถาปัตยกรรมที่ใหญ่สุด |
| #3 `a7.w` | **คง** (`a7` = `a–u` ตรวจครบ ไม่มี `w`) + คู่ที่ถูกคือ **`r1.w` (r1.java:578) + `a7.u` (a7.java:292) + `a7.m` (a7.java:171)** — คอมเมนต์ Aether "a7.w/u" เขียนปน ต้องแก้เป็น "r1.w/a7.u" |
| #4 miniclip | **คง** (dex = MAds ads SDK เท่านั้น; เอกสาร 2.1.3 เตือนเองว่า "ไม่มีชื่อเกมเต็มใน DEX") + eightballpool-as-guest มาจาก **runtime dump** (channel G/H + package.conf + cmdline) ไม่ใช่ static — สองอย่างนี้จริงพร้อมกันได้ |
| #5 `8BP`/PGL | **คงสำหรับ static** (0 hits) + PGL payload (`libpgarmor/libbuffer_pgl/libgame-Module`) เป็นของจริงฝั่ง **runtime** (dump §3 + libengine มี `ElfReader::Load` ปลด PGL) — ที่อยู่ของมันคือชั้น guest-config ไม่ใช่ core; `8BP` ยังไม่มีที่มา → ทิ้ง/ทำเครื่องหมายสมมติฐาน |
| #6 keys ประดิษฐ์ | **คง** (0 hits) + ได้ชื่อ bundle จริง `SnakeEngine_client_config` (dex 1 hit) |
| #8 authority | **คง** (Aether ใช้ของตัวเองโดยรู้ตัว) → งาน C ต้องเปลี่ยนเป็น `%s.proxy_content_provider_%d` |
| #9 JNI ชุดขยาย | **คง** (0 hits) + ของจริงที่คู่กันอยู่ใน **native** (FS redirect ผ่าน hooks + `Native.il→d20` ฝั่ง Java) — ของ Aether เป็น clean-room addition: เก็บได้แต่เลิกอ้าง parity |
| #11 `a5` | **คงโครงสร้าง** (ไม่มีเมธอด) + field handles จริงอยู่ `t1.java` (t1.f/b/e/g) ไม่ใช่ a5 — "SNAKE-proven fix" ต้องอ้าง t1/go0 |
| #14 VPN Java ว่าง | **คง** (init-only ตรวจครบ; file_read: "stub 5 บรรทัด รอใช้") |
| #15 `package.conf` | **แก้ความหมาย**: ไฟล์มีจริงแต่เป็น **Java-serialized BPackage/y6 (173,904B)** ไม่ใช่ dual-encoding — parser Aether ต้องเขียนใหม่ (หรือทำ opaque + serialize ของตัวเอง) |
| #16 permission | **คง** |
| §3 contamination | **แก้ความหมาย**: eightballpool = **หลักฐาน guest-runtime ที่ถูกต้อง** (guest ของ virtual engine) ไม่ใช่ของปลอม — §17 เตือนแค่ "อย่า attribute ไฟล์ guest ให้โค้ด engine" — ความผิด Aether คือเอา guest-specific ไปไว้ใน core ไม่ใช่ตัวข้อมูล |

### 6.3 ของใหม่จาก snake.zip (เข้าแผน C โดยตรง)

- **Entry channels**: MethodChannel ชื่อ `"A"` + เมธอดตัวเดียว `A–J` (`G`=เปิดเกม `(pkg,userId)`, `H`=install, `F`=FCM token, `B/D`=prefs, …) — Aether ใช้ `com.aether/engine_bridge` + 15 ชื่อยาว = โปรโตคอลคนละโลก ต้องเปลี่ยนเพื่องาน C
- **Daemon**: `onDestroy→alarm restart 1.5s`, `onTaskRemoved→1s`, channel `"Snake Engine"`/`com.snake.snake_engine(.inner)`/`SnakeEngine_Core` (dex ยืนยันสตริง) — Aether มีแค่ watchdog
- **InternalWebBrowser**: extra `"url"`, `_oauth_redirect_prefix` (dex 1 hit), non-http → `yu0.j().C()` deeplink, broadcasts `INTERNAL_OAUTH_RESULT/CANCELLED` (dex มีทั้งคู่)
- **Binder**: 26 `$Stub$Proxy` interfaces (2.2.6 นับได้ 26 ตรง 2.1.3) — Aether มี 11 → ขาด 15
- **Sandbox layout (kv0)**: `root`, `data/app/`, `data/user/%d/%s`, `data/user_de/%d/%s`, `Android/data/%s`, `databases` + conf 7 ไฟล์ (`uid/package/shared-user/user/accounts/fake-location.conf`)
- **Version drift 2.1.3↔2.2.6** (สำคัญสุดต่อแผน): ชื่อ obfuscated เปลี่ยนทุกบิลด์ (`xu0→yu0`, `iv0→jv0`, `c8→b8`, …), ลายเซ็น drift (`ilil(String)→String` กลายเป็น `ilil(int)→String`) — **ห้าม hardcode ชื่อ obf เป็น API ระยะยาว** ต้อง map ด้วย role+shape
- **Native**: XOR keystream `off+0xA4` ถอดได้ ~2,480 สตริง (ไฟล์ผลไม่ได้แนบมา), OAuth `snakeengine.com/oauth/google` + client-id อยู่ native, `ElfReader::Load` = ตัวปลด PGL payload, `.mytext` = JNIEnv flag helper (ไม่ใช่โค้ดซ่อน)
- ยังไม่ยืนยัน: stub action `UUID.randomUUID` (0 hits ใน dex — น่าจะ drift หรือ doc พูดเกิน), `stub_receiver` action ใน 2.2.6 (มีใน 2.1.3)

---

## 7. ยืนยัน `com.snake.zip` = dump ตรงเวอร์ชันเกมเก่า 56.23.2 (2026-09-23)

ไฟล์อยู่ราก `origin/main` (3,177,815 B → แตก 7.8 MB / 341 ไฟล์) โครงตรง `EVIDENCE_CHAIN §3` ทุกจุด:

| หลักฐาน | ค่าที่ตรวจได้ | สถานะ |
|---|---|---|
| `root/proc/0/cmdline` | `com.miniclip.eightballpool` | CONFIRMED |
| `root/data/app/.../package.conf` | **173,904 B** (ตรงที่อ้าง), sha256 `34afdbbe…` (ต่างจาก `8ce5af64…` ที่ §3.6 อ้าง — คนละสแนปช็อต) | CONFIRMED |
| versionName ใน package.conf | **`56.23.2` (UTF-16LE, offset 173372)** + พาธจริง `/data/app/~~9tOh…/…-1A0k…/base.apk` + `split_config.arm64_v8a.apk` (guest เป็น split APK) | CONFIRMED — dump ตรงเวอร์ชันที่เจ้าของระบุ |
| versionCode `562310023` | **ไม่พบ** (ค้นทั้ง UTF-8/16 + int32 LE/BE) — ตัวเลขนี้ยังไม่มีที่มาในไฟล์ | NOT ESTABLISHED |
| ฟอร์แมต package.conf | **custom binary** (`u32=31` + เรคคอร์ด UTF-16LE มี length-prefix + tag คลาส `u6/o50/z6` + tail versionName/base.apk) — **ไม่ใช่** Java serialization ตามที่ EVIDENCE_CHAIN ขั้น B เขียนไว้ | CONFIRMED (แก้ §6.2 #15: ทั้ง "Java-ser" และ "dual-encoding" ผิดทั้งคู่ — ต้อง parse ฟอร์แมตนี้จริงในงาน P3) |
| int ในไฟล์ | พบ 28, 35 (SDK), **3965** (= `Module-3965` ในชื่อ .so) | CONFIRMED |
| `root/system/*.conf` | `uid.conf` 8B (`01 00…`), `user.conf` 28B, `shared-user.conf` 4B NUL — binary ทั้งหมด | CONFIRMED (ค่า hex บันทึกใน turn log) |
| PGL `.so` 3 ไฟล์ | 86 / 67,904 / 220 B ตรงที่อ้าง; **ไม่มี ELF magic — entropy สูง = เข้ารหัสทั้งสาม** | CONFIRMED |
| `files/` blobs | **92 ไฟล์** (ชื่อ SHA-256) | CONFIRMED |
| `oat/arm64/` | `Anonymous-DexFile@*.vdex` × 5 (hidden-dex verifier records) | CONFIRMED |
| `shared_prefs/com.snake.xml` | `cip_pub` ว่าง | CONFIRMED |
| guest components ใน conf | AppLovin, **Pangle** (`bytedance.openadsdk` ครบชุด activity), Fyber/Inneractive, SuperAwesome — guest หนักโฆษณา | CONFIRMED |

นัยต่อแผน: guest = eightballpool **56.23.2 ล็อกแล้ว** (มี split APK — installer P3 ต้องรองรับ splits); parser package.conf ต้องเขียนตามฟอร์แมต custom นี้ (u16len+UTF-16 + tag คลาส); PGL = encrypted payload (ห้ามแกะ — ใช้แบบ opaque ตามนโยบาย)

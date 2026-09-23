package com.aether.license

/**
 * License entitlement states (LC0 skeleton — P1 batch 1).
 *
 * โมดูล license = นโยบายล้วน (ไม่รู้จักเน็ต — ขนส่งอยู่ใน c2/) core เรียกผ่าน
 * [LicenseProvider] อย่างเดียว; ปิด flag = [DISABLED] = พฤติกรรม offline เดิม
 */
enum class LicenseState {
    /** module disabled (flags OFF) — core runs offline as today */
    DISABLED,
    /** entitled, verified */
    VALID,
    /** expired but inside grace window */
    GRACE,
    /** expired, no grace left */
    EXPIRED,
    /** verifier unreachable (offline) — caller decides fallback policy */
    UNREACHABLE,
}

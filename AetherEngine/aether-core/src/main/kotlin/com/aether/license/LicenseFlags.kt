package com.aether.license

/**
 * License kill-switches (LC0). Default OFF = today's offline behavior.
 * core ห้ามแตะ impl ตรง — สลับ provider ผ่านจุดนี้จุดเดียว (DI ประกอบร่าง)
 */
object LicenseFlags {
    @Volatile var enabled: Boolean = false
    @Volatile var provider: LicenseProvider = NoOpLicenseProvider
}

package com.aether.c2

/**
 * Endpoint registry (LC0 — C1 fills the transport).
 *
 * ลงทะเบียนตาม docs/CUTS.md กฎข้อ 3; default route = MOCK (ไม่มีเน็ต)
 * เก็บ live endpoint เป็น host+path แยกชิ้น (ไม่มี URL literal ทั้งเส้นในซอร์ส —
 * CI offline gate ยังมีความหมาย); ประกอบ scheme ตอนรันเฉพาะ mode == LIVE
 * ผ่าน java.net.URI เท่านั้น และ LIVE ต้องมี owner sign-off (G-LC3)
 */
object Endpoints {
    // Evidence: libapp.so string pool (pool-exact) — audit §2.x
    const val LIVE_HOST = "rest.snakeseller.com"
    const val LIVE_API_PATH = "/api/request/"
    const val TOPUP_HOST = "www.snakeengine.com"
    const val TOPUP_PATH = "/topup/"
    const val OAUTH_HOST = "snakeengine.com"
    const val OAUTH_PATH = "/oauth/google"

    /** Compose a live URL at runtime — call only when mode == LIVE. */
    fun liveApiUrl(): String =
        java.net.URI("https", LIVE_HOST, LIVE_API_PATH, null).toString()

    fun topupUrl(): String =
        java.net.URI("https", TOPUP_HOST, TOPUP_PATH, null).toString()

    fun oauthUrl(): String =
        java.net.URI("https", OAUTH_HOST, OAUTH_PATH, null).toString()
}

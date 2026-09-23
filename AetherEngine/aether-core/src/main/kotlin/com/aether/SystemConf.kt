package com.aether

import java.io.File

/**
 * P1 batch 5 (close): system conf bootstrap records (kv0 layout).
 *
 * Evidence-exact bytes from com.snake.zip (root/system/: uid, user,
 * shared-user confs + root/proc/0/cmdline):
 *   uid.conf          8 B: 01 00 00 00 00 00 00 00
 *   user.conf        28 B: 01 00 00 00 | 01 00 00 00 | 00*8 | FF FF FF FF | 00*8
 *   shared-user.conf  4 B: 00 00 00 00
 *   proc/0/cmdline       : raw guest package bytes, NO trailing NUL (26 B for 8BP)
 *
 * Semantics are OPAQUE (unknown — do not invent meaning): the writer creates
 * missing files only (never overwrites live state), the verifier checks shape
 * (presence + exact size). Real consumer: chainCheck hop [7] (sandbox
 * integrity telemetry) + installGuest report.
 *
 * Pure JVM (no Android deps).
 */
object SystemConf {
    val UID_CONF: ByteArray = byteArrayOf(0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)
    val USER_CONF: ByteArray = byteArrayOf(
        0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte(),
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    )
    val SHARED_USER_CONF: ByteArray = byteArrayOf(0x00, 0x00, 0x00, 0x00)

    /** Write missing files only. Returns name -> size present afterwards. */
    fun writeDefaults(systemDir: File): Map<String, Int> {
        systemDir.mkdirs()
        val defs = mapOf(
            "uid.conf" to UID_CONF,
            "user.conf" to USER_CONF,
            "shared-user.conf" to SHARED_USER_CONF,
        )
        val out = LinkedHashMap<String, Int>()
        for ((name, bytes) in defs) {
            val f = File(systemDir, name)
            if (!f.exists()) {
                runCatching { f.writeBytes(bytes) }
            }
            if (f.exists()) out[name] = f.length().toInt()
        }
        return out
    }

    /** Shape check: presence + exact size. Content opaque. */
    fun verify(systemDir: File): Map<String, String> {
        fun one(name: String, want: Int): String {
            val f = File(systemDir, name)
            if (!f.exists()) return "MISSING"
            return if (f.length().toInt() == want) "ok(${f.length()}B)" else "SIZE!(${f.length()}B)"
        }
        return mapOf(
            "uid.conf" to one("uid.conf", 8),
            "user.conf" to one("user.conf", 28),
            "shared-user.conf" to one("shared-user.conf", 4),
        )
    }

    /** proc/0/cmdline = raw package bytes (dump has no trailing NUL). Overwrites. */
    fun writeCmdline(procZeroDir: File, guestPkg: String): Boolean {
        return runCatching {
            procZeroDir.mkdirs()
            File(procZeroDir, "cmdline").writeBytes(guestPkg.toByteArray(Charsets.UTF_8))
            true
        }.getOrDefault(false)
    }

    fun readCmdline(procZeroDir: File): String? {
        val f = File(procZeroDir, "cmdline")
        return if (f.exists()) runCatching { f.readBytes().toString(Charsets.UTF_8) }.getOrNull()
        else null
    }
}

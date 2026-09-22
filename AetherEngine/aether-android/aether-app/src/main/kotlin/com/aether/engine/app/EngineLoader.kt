package com.aether.engine.app

import android.content.Context
import android.util.Log

/**
 * EngineLoader — โหลด native engine (offline, ตัวเดียว)
 *
 * [CUT 2026-09-23] ตัด EngineType.SNAKE (libengine.so ของ Snake) ทิ้ง —
 * การโหลดไบนารี Snake ทั้งก้อนเท่ากับเอาโค้ด C2/license ของเขามาด้วยทั้งชุด
 * ขัดกับนโยบาย "สืบทอดโครงสร้าง แต่ไม่เอา C2 และใบอนุญาต" (ดู docs/CUTS.md)
 * ตอนนี้เหลือ libaether.so ตัวเดียวที่มากับ APK (ซอร์สใน aether-native/)
 */
object EngineLoader {
    private const val TAG = "EngineLoader"
    private const val LIBRARY_NAME = "aether"

    /**
     * โหลด libaether.so — เรียกครั้งเดียวจาก AetherApp.onCreate()
     * @throws UnsatisfiedLinkError ถ้าไม่มี .so ใน APK
     */
    fun load(context: Context) {
        try {
            System.loadLibrary(LIBRARY_NAME)
            Log.i(TAG, "✓ Aether Engine loaded (lib$LIBRARY_NAME.so)")
        } catch (e: UnsatisfiedLinkError) {
            Log.e(TAG, "CRITICAL: lib$LIBRARY_NAME.so not found: ${e.message}")
            throw e
        }
    }
}

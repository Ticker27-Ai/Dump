// engine_api.dart — ฝั่ง Dart ของช่อง com.aether/engine_bridge
//
// [SCAFFOLD 2026-09-23] เขียนใหม่ทั้งไฟล์ (ของเดิมใน repo มีแค่ pubspec —
// ไม่มีโค้ด Dart เลย) — client ตรงกับ 15 เมธอดของ EngineBridge.kt ฝั่ง host
// ไม่มี license/topup/network ใด ๆ (นโยบาย offline ดู docs/CUTS.md)
//
// ใช้: import 'engine_api.dart'; → await EngineApi.getEngineStats();

import 'package:flutter/services.dart';

/// เรียก engine ฝั่ง host ผ่าน MethodChannel (in-process, ไม่ผ่านเน็ต)
class EngineApi {
  EngineApi._();

  static const MethodChannel _ch = MethodChannel('com.aether/engine_bridge');

  /// มีแพ็กเกจเป้าหมายติดตั้งอยู่ไหม (เช็กก่อน virtualize)
  static Future<bool> isTargetInstalled(String packageName) async {
    try {
      return await _ch.invokeMethod<bool>(
            'isTargetInstalled', {'packageName': packageName}) ??
          false;
    } on PlatformException {
      return false;
    }
  }

  /// ข้อมูลเกมที่ติดตั้ง (versionName/Code ฯลฯ) — null ถ้าไม่มี/อ่านไม่ได้
  static Future<Map<String, dynamic>?> getInstalledGameInfo(
      String packageName) async {
    try {
      final m = await _ch.invokeMapMethod<String, dynamic>(
          'getInstalledGameInfo', {'packageName': packageName});
      return m == null ? null : Map<String, dynamic>.from(m);
    } on PlatformException {
      return null;
    }
  }

  /// ติดตั้ง guest เข้า sandbox (H): verify PMS + bootstrap (dirs + confs)
  /// คืน Map{ok, versionName, versionCode, confBytes, systemConfs, cmdline, reason}
  static Future<Map<String, dynamic>> installGuest(String packageName) async {
    try {
      final m = await _ch.invokeMapMethod<String, dynamic>(
          'installGuest', {'packageName': packageName});
      return m == null ? {'ok': false} : Map<String, dynamic>.from(m);
    } on PlatformException {
      return {'ok': false};
    }
  }

  /// รหัสเครื่อง (ANDROID_ID — แสดงผลใน UI อย่างเดียว, ไม่ส่งออก)
  static Future<String> getDeviceId() async {
    try {
      return await _ch.invokeMethod<String>('getDeviceId') ?? 'unknown';
    } on PlatformException {
      return 'unknown';
    }
  }

  /// สถิติ engine (readCount/scanCount/uptime ฯลฯ)
  static Future<Map<String, dynamic>> getEngineStats() async {
    try {
      final m = await _ch.invokeMapMethod<String, dynamic>('getEngineStats');
      return m == null ? {} : Map<String, dynamic>.from(m);
    } on PlatformException {
      return {};
    }
  }

  /// สถานะ virtual app (container/proxy พร้อมไหม)
  static Future<Map<String, dynamic>> getVirtualAppStatus() async {
    try {
      final m =
          await _ch.invokeMapMethod<String, dynamic>('getVirtualAppStatus');
      return m == null ? {} : Map<String, dynamic>.from(m);
    } on PlatformException {
      return {};
    }
  }

  /// self-test VirtualFS ผ่าน native จริง (คืนข้อความผลลัพธ์)
  static Future<String> testVirtualFS() async {
    try {
      return await _ch.invokeMethod<String>('testVirtualFS') ?? '';
    } on PlatformException {
      return '';
    }
  }

  /// อ่านหน่วยความจำ N ไบต์จาก address (demo: libaether.so .text)
  static Future<Map<String, dynamic>?> readMemory(int address, int size) async {
    try {
      final m = await _ch.invokeMapMethod<String, dynamic>(
          'readMemory', {'address': address, 'size': size});
      return m == null ? null : Map<String, dynamic>.from(m);
    } on PlatformException {
      return null;
    }
  }

  /// สแกนลายเซ็น AOB (hex + mask) — คืน address ที่เจอ (0 = ไม่เจอ)
  static Future<int> scanAOB(String hex, String mask) async {
    try {
      return await _ch
              .invokeMethod<int>('scanAOB', {'hex': hex, 'mask': mask}) ??
          0;
    } on PlatformException {
      return 0;
    }
  }

  /// รัน Engine.nativeCompute — คืนผล 8 ไบต์เป็น hex
  static Future<String> nativeCompute(int input) async {
    try {
      return await _ch.invokeMethod<String>('nativeCompute', {'input': input}) ??
          '';
    } on PlatformException {
      return '';
    }
  }

  /// บีบอัด payload (native zlib deflate) — รับ/ส่งเป็น hex
  static Future<String> compressPayload(String hex) async {
    try {
      return await _ch.invokeMethod<String>('compressPayload', {'hex': hex}) ??
          '';
    } on PlatformException {
      return '';
    }
  }

  /// เปิดแอปที่ติดตั้งแล้วตาม package name (ผู้ใช้กดเองเท่านั้น)
  static Future<bool> launchApp(String packageName) async {
    try {
      return await _ch
              .invokeMethod<bool>('launchApp', {'packageName': packageName}) ??
          false;
    } on PlatformException {
      return false;
    }
  }

  /// virtualize เป้าหมายแบบ in-process (ไม่ยิง Intent ออกนอก)
  static Future<dynamic> launchInSandbox(String packageName) async {
    try {
      return await _ch
          .invokeMethod('launchInSandbox', {'packageName': packageName});
    } on PlatformException {
      return null;
    }
  }

  /// อ่านไฟล์ diag ล่าสุด (EngineBridge.readDiag)
  static Future<String> readDiag() async {
    try {
      return await _ch.invokeMethod<String>('readDiag') ?? '';
    } on PlatformException {
      return '';
    }
  }

  /// ตรวจ boot chain ของเป้าหมาย (คืนข้อความรายงาน)
  static Future<String> chainCheck(String packageName) async {
    try {
      return await _ch.invokeMethod<String>(
            'chainCheck', {'packageName': packageName}) ??
          '';
    } on PlatformException {
      return '';
    }
  }

  /// สถานะ handshake ฝั่ง engine (in-process)
  static Future<String> handshakeStatus() async {
    try {
      return await _ch.invokeMethod<String>('handshakeStatus') ?? '';
    } on PlatformException {
      return '';
    }
  }
}

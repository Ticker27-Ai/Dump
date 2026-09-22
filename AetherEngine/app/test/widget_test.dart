// widget_test.dart — smoke test จอหลัก (mock ฝั่ง host ผ่าน MethodChannel)
//
// [SCAFFOLD 2026-09-23] เขียนใหม่ — ของเดิมไม่มี app/test/ เลย
// รันใน CI: flutter test (ไม่ต้องมีเครื่อง/ emulator)

import 'package:aether/main.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const ch = MethodChannel('com.aether/engine_bridge');

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(ch, (call) async {
      switch (call.method) {
        case 'getDeviceId':
          return 'test-device-1';
        case 'getEngineStats':
          return <String, dynamic>{'uptime': 42, 'readCount': 7};
        case 'testVirtualFS':
          return 'vfs-ok';
        case 'handshakeStatus':
          return 'hs-ok';
        case 'readDiag':
          return 'diag-line-1';
        default:
          return null;
      }
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(ch, null);
  });

  testWidgets('โชว์ device id + stats จาก engine', (tester) async {
    await tester.pumpWidget(const AetherApp());
    await tester.pumpAndSettle();
    expect(find.text('test-device-1'), findsOneWidget);
    expect(find.text('uptime'), findsOneWidget);
    expect(find.text('42'), findsOneWidget);
  });

  testWidgets('ปุ่ม VirtualFS โชว์รายงาน', (tester) async {
    await tester.pumpWidget(const AetherApp());
    await tester.pumpAndSettle();
    await tester.tap(find.text('VirtualFS'));
    await tester.pumpAndSettle();
    expect(find.textContaining('vfs-ok'), findsOneWidget);
  });
}

// main.dart — จอหลัก AetherEngine (Flutter shell)
//
// [SCAFFOLD 2026-09-23] เขียนใหม่ทั้งไฟล์ — UI เริ่มต้นแบบ offline:
// แสดง device id + สถิติ engine + ปุ่ม self-test (VirtualFS/handshake)
// + ตัวอ่าน diag — ไม่มีจอ login/license/topup (ดู docs/CUTS.md)

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'engine_api.dart';

void main() => runApp(const AetherApp());

class AetherApp extends StatelessWidget {
  const AetherApp({super.key});

  @override
Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AetherEngine',
      theme: ThemeData(colorSchemeSeed: Colors.teal, useMaterial3: true),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String _deviceId = '…';
  Map<String, dynamic> _stats = {};
  String _report = '';
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  /// ดึง device id + stats ใหม่ (in-process ผ่าน MethodChannel)
  Future<void> _refresh() async {
    setState(() => _busy = true);
    try {
      final id = await EngineApi.getDeviceId();
      final stats = await EngineApi.getEngineStats();
      if (!mounted) return;
      setState(() {
        _deviceId = id;
        _stats = stats;
      });
    } catch (e) {
      debugPrint('refresh failed: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// รันคำสั่งแล้วเอาข้อความมาโชว์ในแผงรายงาน
  Future<void> _run(String label, Future<String> Function() fn) async {
    setState(() => _busy = true);
    try {
      final out = await fn();
      if (!mounted) return;
      setState(() => _report = '── $label ──\n$out');
    } catch (e) {
      debugPrint('$label failed: $e');
      if (!mounted) return;
      setState(() => _report = '── $label ──\nล้มเหลว: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final rows = _stats.entries.toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text('AetherEngine'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'รีเฟรช',
            onPressed: _busy ? null : _refresh,
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.smartphone),
              title: const Text('อุปกรณ์ (แสดงผลอย่างเดียว)'),
              subtitle: Text(_deviceId),
            ),
          ),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('สถิติ engine',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  if (rows.isEmpty)
                    const Text('— ยังไม่มีข้อมูล —')
                  else
                    for (final e in rows)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Row(
                          children: [
                            Expanded(child: Text(e.key)),
                            Text('${e.value}',
                                style: const TextStyle(
                                    fontFeatures: [FontFeature.tabularFigures()])),
                          ],
                        ),
                      ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              ElevatedButton(
                onPressed: _busy
                    ? null
                    : () => _run('VirtualFS self-test', EngineApi.testVirtualFS),
                child: const Text('VirtualFS'),
              ),
              ElevatedButton(
                onPressed: _busy
                    ? null
                    : () => _run('handshake', EngineApi.handshakeStatus),
                child: const Text('handshake'),
              ),
              ElevatedButton(
                onPressed: _busy
                    ? null
                    : () => _run('diag ล่าสุด', EngineApi.readDiag),
                child: const Text('อ่าน diag'),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (_report.isNotEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: SelectableText(
                  _report,
                  style: const TextStyle(
                      fontFamily: 'monospace', fontSize: 12),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

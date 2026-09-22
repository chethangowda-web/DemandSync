import 'package:flutter/foundation.dart';

const String _configuredBase = String.fromEnvironment('API_BASE');

/// Where the DemandSYNC API lives.
///  * `--dart-define=API_BASE=https://...` always wins.
///  * On the web the app is served by the API itself, so the page origin is the API.
///  * On an Android emulator the host machine is 10.0.2.2.
String apiBaseUrl() {
  if (_configuredBase.isNotEmpty) return _configuredBase;
  if (kIsWeb) return Uri.base.origin;
  return 'http://10.0.2.2:8000';
}

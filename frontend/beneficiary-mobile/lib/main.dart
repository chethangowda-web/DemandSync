import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app.dart';
import 'core/api_client.dart';
import 'core/config.dart';
import 'core/session.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting();
  // Screen readers (and browser accessibility tooling) get the semantic tree on the web from the first frame.
  if (kIsWeb) SemanticsBinding.instance.ensureSemantics();
  final session = await SessionController.load();
  final api = HttpApiClient(baseUrl: apiBaseUrl(), token: () => session.token, onUnauthorized: session.expire);
  runApp(DemandSyncApp(api: api, session: session));
}

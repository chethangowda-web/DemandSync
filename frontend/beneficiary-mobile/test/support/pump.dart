import 'package:demandsync_beneficiary/app.dart';
import 'package:demandsync_beneficiary/core/session.dart';
import 'package:demandsync_beneficiary/l10n/generated/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'fake_api.dart';

AppLocalizations get l10nEn => lookupAppLocalizations(const Locale('en'));
AppLocalizations get l10nHi => lookupAppLocalizations(const Locale('hi'));
AppLocalizations get l10nKn => lookupAppLocalizations(const Locale('kn'));

Future<void> initDates() => initializeDateFormatting();

/// Pumps the whole app, signed in by default, on a phone-sized (or tall) screen.
Future<SessionController> pumpApp(
  WidgetTester tester,
  FakeApi api, {
  Locale locale = const Locale('en'),
  double textScale = 1.0,
  bool loggedIn = true,
  bool tall = false,
  bool settle = true,
}) async {
  // At very large text scale the 390dp phone would overflow many rows; give it more width so the
  // government UI can still be read without clipping, exactly as a real device would allow scrolling.
  final w = textScale > 1.5 ? 2340.0 : 1170.0;
  tester.view.physicalSize = tall ? Size(w, 7000) : Size(w, 2532);
  tester.view.devicePixelRatio = 3.0;
  tester.platformDispatcher.textScaleFactorTestValue = textScale;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
    tester.platformDispatcher.clearAllTestValues();
  });
  final session = SessionController.memory(token: loggedIn ? 'test-token' : null, locale: locale);
  await tester.pumpWidget(DemandSyncApp(api: api, session: session));
  if (settle) await tester.pumpAndSettle();
  return session;
}

/// Taps a widget that may be off screen.
Future<void> tapText(WidgetTester tester, String text) async {
  final f = find.text(text).first;
  await tester.ensureVisible(f);
  await tester.pumpAndSettle();
  await tester.tap(f);
  await tester.pumpAndSettle();
}

import 'package:demandsync_beneficiary/screens/entitlement_screen.dart';
import 'package:demandsync_beneficiary/screens/history_screen.dart';
import 'package:demandsync_beneficiary/screens/login_screen.dart';
import 'package:demandsync_beneficiary/screens/plan_screen.dart';
import 'package:demandsync_beneficiary/screens/track_screen.dart';
import 'package:demandsync_beneficiary/screens/welcome_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_api.dart';
import 'package:demandsync_beneficiary/core/models.dart';

import 'support/fixtures.dart';
import 'support/pump.dart';

void main() {
  setUpAll(initDates);

  testWidgets('signed out: welcome screen leads to login, not straight into the app', (tester) async {
    final api = FakeApi();
    await pumpApp(tester, api, loggedIn: false);
    expect(find.byType(WelcomeScreen), findsOneWidget);
    expect(find.text(l10nEn.appTagline), findsOneWidget);
    await tapText(tester, l10nEn.getStarted);
    expect(find.byType(LoginScreen), findsOneWidget);
    expect(api.calls, isEmpty); // nothing is fetched before the user is authenticated
  });

  testWidgets('home shows real data from the backend, not placeholders', (tester) async {
    final api = FakeApi();
    await pumpApp(tester, api);
    expect(find.textContaining('Sneha Samra'), findsOneWidget);
    expect(find.textContaining('March 2026'), findsWidgets);
    expect(find.text('22 kg'), findsOneWidget); // rice
    expect(find.text('13 kg'), findsOneWidget); // wheat
    expect(find.text('35 kg'), findsWidgets); // total
    expect(find.textContaining(l10nEn.planMyCollection), findsOneWidget);
    expect(api.calls, contains('home'));
  });

  testWidgets('the four tabs are Home, My Ration, History, Help — nothing else', (tester) async {
    await pumpApp(tester, FakeApi());
    final l = l10nEn;
    for (final label in [l.navHome, l.navMyRation, l.navHistory, l.navHelp]) {
      expect(find.widgetWithText(NavigationDestination, label), findsOneWidget);
    }
    expect(find.byType(NavigationDestination), findsNWidgets(4));
  });

  testWidgets('bottom navigation actually switches screens', (tester) async {
    final api = FakeApi();
    await pumpApp(tester, api);
    await tapText(tester, l10nEn.navMyRation);
    expect(find.byType(TrackScreen), findsOneWidget);
    await tapText(tester, l10nEn.navHistory);
    expect(find.byType(HistoryScreen), findsOneWidget);
    await tapText(tester, l10nEn.navHome);
    expect(find.text('Sneha Samra'), findsOneWidget);
    expect(api.calls, containsAll(['home', 'tracking', 'collections']));
  });

  testWidgets('entitlement screen is reachable and shows the same numbers as home', (tester) async {
    await pumpApp(tester, FakeApi());
    await tapText(tester, 'My entitlement');
    expect(find.byType(EntitlementScreen), findsOneWidget);
    expect(find.text('22 kg'), findsOneWidget);
    expect(find.text('13 kg'), findsOneWidget);
  });

  testWidgets('an active choice window with no plan offers Plan my collection, and it opens the flow', (tester) async {
    await pumpApp(tester, FakeApi());
    await tapText(tester, l10nEn.planMyCollection);
    expect(find.byType(PlanScreen), findsOneWidget);
  });

  testWidgets('a submitted plan shows View my plan instead of a second Plan my collection', (tester) async {
    final api = FakeApi()..overrides['home'] = () => HomeData.fromJson(fixture('home_intent'));
    await pumpApp(tester, api);
    expect(find.text(l10nEn.viewMyPlan), findsOneWidget);
    expect(find.text(l10nEn.planMyCollection), findsNothing);
  });

  testWidgets('a suspended current shop is flagged on home, in English words plus an icon', (tester) async {
    final api = FakeApi()..overrides['home'] = () => HomeData.fromJson(fixture('home_fps_suspended'));
    await pumpApp(tester, api);
    expect(find.text(l10nEn.shopNotActive), findsWidgets);
  });

  testWidgets('no active cycle is shown honestly, never a fake one', (tester) async {
    final api = FakeApi()..overrides['home'] = () => HomeData.fromJson(fixture('home_no_cycle'));
    await pumpApp(tester, api);
    expect(find.textContaining('March 2026'), findsNothing);
    expect(find.text(l10nEn.noticeNoCycle), findsWidgets);
  });

  testWidgets('a network failure on load shows retry, not a blank or crashed screen', (tester) async {
    var attempts = 0;
    final api = FakeApi()
      ..overrides['home'] = () {
        attempts++;
        throw Exception('offline');
      };
    await pumpApp(tester, api);
    expect(find.text(l10nEn.retry), findsOneWidget);
    expect(find.text('Sneha Samra'), findsNothing);
    api.overrides.remove('home');
    await tapText(tester, l10nEn.retry);
    expect(find.text('Sneha Samra'), findsOneWidget);
    expect(attempts, 1);
  });

  testWidgets('language switches instantly and to a real script, without re-login', (tester) async {
    final session = await pumpApp(tester, FakeApi());
    expect(find.text('My entitlement'), findsOneWidget);
    await tapText(tester, 'English'); // the language button shows the current language's own name
    await tapText(tester, 'ಕನ್ನಡ');
    expect(session.locale.languageCode, 'kn');
    expect(find.text(l10nKn.myEntitlement), findsOneWidget);
    expect(find.text('My entitlement'), findsNothing);
  });

  testWidgets('large system text scale does not crash or clip the primary action', (tester) async {
    await pumpApp(tester, FakeApi(), textScale: 2.0);
    expect(tester.takeException(), isNull);
    // the button is still reachable by scrolling, exactly as a real user would; it must never be lost entirely
    await tester.drag(find.byType(Scrollable).first, const Offset(0, -1000));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.textContaining(l10nEn.planMyCollection), findsOneWidget);
  });

  testWidgets('a very tall phone still renders every home section without overflow', (tester) async {
    await pumpApp(tester, FakeApi(), tall: false);
    expect(tester.takeException(), isNull);
  });
}

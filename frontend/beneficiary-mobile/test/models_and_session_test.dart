import 'package:demandsync_beneficiary/core/format.dart';
import 'package:demandsync_beneficiary/core/models.dart';
import 'package:demandsync_beneficiary/core/session.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fixtures.dart';

void main() {
  setUpAll(() => initializeDateFormatting());

  group('models parse what the backend really sends', () {
    test('home (open window, no plan)', () {
      final h = HomeData.fromJson(fixture('home_open'));
      expect(h.beneficiary.name, 'Sneha Samra');
      expect(h.beneficiary.scheme, 'AAY');
      expect(h.beneficiary.householdSize, 7);
      expect((h.statutory.rice, h.statutory.wheat, h.statutory.total), (22, 13, 35));
      expect(h.cycle!.cycle, '2026-03');
      expect(h.cycle!.windowOpen, isTrue);
      expect(h.intent, isNull);
      expect(h.statusKey, 'CHOICE_WINDOW_OPEN');
      expect(h.notice!.code, 'PLAN_NOW');
      // remaining entitlement is statutory minus recorded collections, computed by the server
      expect(h.entitlement!.collectedTotalKg, 24);
      expect(h.entitlement!.remainingTotalKg, h.statutory.total - h.entitlement!.collectedTotalKg);
    });

    test('home with a plan, with a suspended shop, and with no active cycle', () {
      final planned = HomeData.fromJson(fixture('home_intent'));
      expect(planned.intent!.reference, matches(RegExp(r'^INT-2026-\d{6}$')));
      expect(planned.statusKey, 'INTENT_SUBMITTED');
      expect(HomeData.fromJson(fixture('home_fps_suspended')).fps.isActive, isFalse);
      final none = HomeData.fromJson(fixture('home_no_cycle'));
      expect(none.cycle, isNull);
      expect(none.entitlement, isNull);
      expect(none.notice!.code, 'NO_CYCLE');
    });

    test('journeys: nothing invented when data is missing', () {
      final open = Journey.fromJson(fixture('tracking_open'));
      expect(open.steps.map((s) => s.key), [
        'INTENT_SUBMITTED', 'DEMAND_PLANNED', 'ALLOCATED', 'DISPATCHED', 'IN_TRANSIT', 'RECEIVED_AT_FPS', 'AVAILABLE_FOR_COLLECTION', 'COLLECTED'
      ]);
      expect(open.telemetry, isNull);
      final noGps = Journey.fromJson(fixture('tracking_in_transit_no_gps'));
      expect(noGps.telemetry, isNull);
      expect(noGps.telemetryNote, 'LIVE_LOCATION_UNAVAILABLE');
      final gps = Journey.fromJson(fixture('tracking_in_transit_gps'));
      expect(gps.telemetry!.vehicleNumber, isNotEmpty);
      expect(gps.telemetry!.latitude, inInclusiveRange(-90, 90));
      expect(gps.telemetryNote, isNull);
      final delivered = Journey.fromJson(fixture('tracking_delivered'));
      expect(delivered.steps.where((s) => s.status == 'DONE').length, greaterThanOrEqualTo(7));
    });

    test('history, receipts, assistant, grievances', () {
      expect(CollectionRecord.fromJson((fixture('history_collections')['items'] as List).first as Map<String, dynamic>).totalKg, 24);
      final tx = (fixture('history_transactions')['items'] as List).map((j) => TransactionRecord.fromJson(j as Map<String, dynamic>)).toList();
      expect(tx, isNotEmpty);
      expect(tx.every((t) => t.isSuccess), isTrue);
      final r = DigitalReceipt.fromJson(fixture('digital_receipt'));
      expect(r.verificationRef, matches(RegExp(r'^[0-9A-F]{16}$')));
      expect(r.qrPayload, 'DSYNC|${r.transactionId}|${r.verificationRef}');
      final a = AssistantAnswer.fromJson(fixture('assistant_entitlement_hi'));
      expect(a.generative, isFalse);
      expect(a.answer, contains('किग्रा'));
      final s = GrievanceSuggestion.fromJson(fixture('grievance_suggest'));
      expect(s.category, 'TRANSACTION_FAILURE');
      expect(s.related, isNotEmpty);
      expect(Grievance.fromJson(fixture('grievance_created')).status, 'OPEN');
      expect(OtpRequestResult.fromJson(fixture('otp_request')).devOtp, isNotNull);
    });

    test('recorded errors keep their code and parameters', () {
      final e = recordedError('error_exceeds', 422);
      expect(e.code, 'EXCEEDS_REMAINING');
      expect((e.params['rice'] as Map)['remaining_kg'], 4);
      expect(recordedError('error_duplicate', 409).params['reference'], matches(RegExp(r'^INT-')));
    });
  });

  group('formatting', () {
    test('kg values', () {
      expect(kgText(35), '35');
      expect(kgText(35.0), '35');
      expect(kgText(3.5), '3.5');
    });

    test('cycle labels follow the language', () {
      expect(cycleLabel('2026-03', 'en'), 'March 2026');
      expect(cycleLabel('2026-03', 'hi'), contains('2026'));
      expect(cycleLabel('2026-03', 'kn'), contains('2026'));
      expect(cycleLabel('2026-03', 'hi'), isNot(cycleLabel('2026-03', 'en')));
    });

    test('ration cards are masked', () {
      expect(maskedCard('RC2023100000'), '••••0000');
      expect(maskedCard('RC1'), 'RC1');
    });
  });

  group('session', () {
    test('sign in, expire, sign out', () async {
      final s = SessionController.memory();
      var notified = 0;
      s.addListener(() => notified++);
      expect(s.loggedIn, isFalse);
      await s.signIn('abc');
      expect((s.loggedIn, s.token, s.expired), (true, 'abc', false));
      s.expire();
      expect((s.loggedIn, s.token, s.expired), (false, null, true));
      await s.signIn('def');
      expect(s.expired, isFalse);
      await s.signOut();
      expect((s.loggedIn, s.expired), (false, false));
      expect(notified, greaterThanOrEqualTo(4));
    });

    test('expire does nothing when nobody is signed in', () {
      final s = SessionController.memory();
      s.expire();
      expect(s.expired, isFalse);
    });

    test('refresh tick and language', () async {
      final s = SessionController.memory();
      final before = s.refreshTick;
      s.bump();
      expect(s.refreshTick, before + 1);
      await s.setLocale(const Locale('kn'));
      expect(s.locale.languageCode, 'kn');
    });

    test('token and language survive a restart', () async {
      SharedPreferences.setMockInitialValues({});
      final first = await SessionController.load();
      await first.signIn('persisted-token');
      await first.setLocale(const Locale('hi'));
      final second = await SessionController.load();
      expect(second.token, 'persisted-token');
      expect(second.locale.languageCode, 'hi');
      await second.signOut();
      expect((await SessionController.load()).token, isNull);
    });

    test('an unknown stored language falls back to English', () async {
      SharedPreferences.setMockInitialValues({'demandsync.lang': 'xx'});
      expect((await SessionController.load()).locale.languageCode, 'en');
    });
  });
}

import 'dart:convert';
import 'dart:io';

import 'package:demandsync_beneficiary/core/api_client.dart';
import 'package:demandsync_beneficiary/core/api_exception.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'support/fixtures.dart';

http.Response json(Object body, [int status = 200]) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json; charset=utf-8'});

HttpApiClient clientFor(MockClient m, {String? Function()? token, void Function()? onUnauthorized, Duration? timeout}) => HttpApiClient(
      baseUrl: 'https://api.example.test',
      token: token ?? () => 'secret-token',
      onUnauthorized: onUnauthorized,
      client: m,
      timeout: timeout ?? const Duration(seconds: 2),
    );

void main() {
  group('requests', () {
    test('the session token is sent on authenticated calls and read fresh each time', () async {
      final seen = <String?>[];
      var current = 'first';
      final api = clientFor(MockClient((r) async {
        seen.add(r.headers['Authorization']);
        return json(fixture('home_open'));
      }), token: () => current);
      await api.home();
      current = 'second';
      await api.home();
      expect(seen, ['Bearer first', 'Bearer second']);
    });

    test('login calls carry no token', () async {
      final seen = <Map<String, String>>[];
      final api = clientFor(MockClient((r) async {
        seen.add(r.headers);
        return json(fixture('otp_request'));
      }));
      await api.requestOtp('RC1', '9000');
      expect(seen.single.containsKey('Authorization'), isFalse);
    });

    test('no request ever carries a beneficiary id: identity comes from the token only', () async {
      final requests = <http.Request>[];
      final api = clientFor(MockClient((r) async {
        requests.add(r);
        final p = r.url.path;
        if (p.endsWith('/home')) return json(fixture('home_open'));
        if (p.endsWith('/entitlement')) return json(fixture('entitlement'));
        if (p.endsWith('/fps/eligible')) return json(fixture('fps_eligible'));
        if (p.endsWith('/preferences')) return json(fixture('receipt_recorded'), 201);
        if (p.contains('/preferences/')) return json(fixture('receipt_recorded'));
        if (p.endsWith('/tracking/me')) return json(fixture('tracking_open'));
        if (p.endsWith('/history/me')) return json(fixture('history_${r.url.queryParameters['kind']}'));
        if (p.endsWith('/receipt')) return json(fixture('digital_receipt'));
        if (p.endsWith('/ai/assistant')) return json(fixture('assistant_entitlement_en'));
        if (p.endsWith('/grievance-suggest')) return json(fixture('grievance_suggest'));
        if (p.endsWith('/grievances/me')) return json(fixture('grievances'));
        if (p.endsWith('/grievances')) return json(fixture('grievance_created'), 201);
        return json({});
      }));
      await api.home();
      await api.entitlement();
      await api.eligibleFps();
      await api.submitIntent(fpsId: 'FPS-0244', riceKg: 1, wheatKg: 1, mode: 'SELF');
      await api.intentReceipt('INT-2026-000001');
      await api.cancelIntent('INT-2026-000001');
      await api.tracking();
      await api.collections();
      await api.transactions();
      await api.intents();
      await api.digitalReceipt('EPOS-00000001');
      await api.ask(intent: 'ENTITLEMENT', language: 'en');
      await api.suggestGrievance('machine failed');
      await api.submitGrievance(category: 'OTHER', description: 'something happened here');
      await api.myGrievances();
      expect(requests.length, greaterThan(14));
      for (final r in requests) {
        final haystack = '${r.url}${r.body}'.toLowerCase();
        expect(haystack.contains('beneficiary_id'), isFalse, reason: r.url.toString());
        expect(haystack.contains('ben-0'), isFalse, reason: r.url.toString());
      }
    });

    test('submit sends exactly what the user chose', () async {
      late Map<String, dynamic> body;
      final api = clientFor(MockClient((r) async {
        body = jsonDecode(r.body) as Map<String, dynamic>;
        return json(fixture('receipt_recorded'), 201);
      }));
      await api.submitIntent(fpsId: 'FPS-0519', riceKg: 3, wheatKg: 2, mode: 'AUTHORIZED_PERSON');
      expect(body, {'fps_id': 'FPS-0519', 'rice_quantity_kg': 3, 'wheat_quantity_kg': 2, 'collection_mode': 'AUTHORIZED_PERSON'});
    });

    test('references are URL-encoded', () async {
      late Uri seen;
      final api = clientFor(MockClient((r) async {
        seen = r.url;
        return json(fixture('receipt_recorded'));
      }));
      await api.intentReceipt('INT-2026/../x y');
      // the slashes and spaces in the reference are encoded, so it stays one path segment and cannot climb out
      expect(seen.path.split('/').length, 6); // '', api, v1, preferences, <reference>, receipt
      expect(seen.toString(), contains('%2F'));
      expect(seen.toString(), contains('%20'));
    });
  });

  group('failures become actionable errors', () {
    test('401 on an authenticated call tells the session to end', () async {
      var expired = 0;
      final api = clientFor(MockClient((_) async => json(fixture('error_unauthorized'), 401)), onUnauthorized: () => expired++);
      await expectLater(api.home(), throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.unauthorized)));
      expect(expired, 1);
    });

    test('401 while logging in is a wrong-details error, not a session expiry', () async {
      var expired = 0;
      final api = clientFor(MockClient((_) async => json({'detail': 'nope', 'code': 'BAD_CREDENTIALS'}, 401)), onUnauthorized: () => expired++);
      await expectLater(api.requestOtp('x', 'y'), throwsA(isA<ApiException>().having((e) => e.code, 'code', 'BAD_CREDENTIALS').having((e) => e.kind, 'kind', ApiErrorKind.client)));
      expect(expired, 0);
    });

    test('validation errors keep code, status and params', () async {
      final api = clientFor(MockClient((_) async => json(fixture('error_exceeds'), 422)));
      await expectLater(
          api.submitIntent(fpsId: 'x', riceKg: 50, wheatKg: 0, mode: 'SELF'),
          throwsA(isA<ApiException>().having((e) => e.code, 'code', 'EXCEEDS_REMAINING').having((e) => e.status, 'status', 422).having((e) => e.params.containsKey('rice'), 'params', isTrue)));
    });

    test('duplicate intent is a 409 client error', () async {
      final api = clientFor(MockClient((_) async => json(fixture('error_duplicate'), 409)));
      await expectLater(api.submitIntent(fpsId: 'x', riceKg: 1, wheatKg: 0, mode: 'SELF'), throwsA(isA<ApiException>().having((e) => e.code, 'code', 'INTENT_DUPLICATE')));
    });

    test('server errors, including non-JSON gateway pages', () async {
      await expectLater(clientFor(MockClient((_) async => json({'detail': 'boom'}, 500))).home(), throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.server)));
      await expectLater(clientFor(MockClient((_) async => http.Response('<html>Bad gateway</html>', 502))).home(), throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.server)));
    });

    test('no connection is reported as offline', () async {
      await expectLater(clientFor(MockClient((_) async => throw const SocketException('unreachable'))).home(), throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.offline)));
      await expectLater(clientFor(MockClient((_) async => throw http.ClientException('connection closed'))).home(), throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.offline)));
    });

    test('a slow server is reported as a timeout', () async {
      final api = clientFor(MockClient((_) async {
        await Future<void>.delayed(const Duration(milliseconds: 300));
        return json(fixture('home_open'));
      }), timeout: const Duration(milliseconds: 50));
      await expectLater(api.home(), throwsA(isA<ApiException>().having((e) => e.kind, 'kind', ApiErrorKind.timeout)));
    });

    test('logout never throws, even if the token was already dead', () async {
      final api = clientFor(MockClient((_) async => json(fixture('error_unauthorized'), 401)));
      await api.logout();
    });
  });

  test('an unexpected response shape fails loudly rather than showing wrong data', () async {
    final api = clientFor(MockClient((_) async => json({'unexpected': true})));
    await expectLater(api.home(), throwsA(anything));
  });
}

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_exception.dart';
import 'models.dart';

/// Everything the app can ask the backend. Screens depend on this interface only.
/// There is deliberately no method that takes a beneficiary id: the session token decides who is asking.
abstract class ApiClient {
  Future<OtpRequestResult> requestOtp(String rationCardId, String registeredMobile);
  Future<String> verifyOtp(String rationCardId, String otp); // returns the access token
  Future<void> logout();

  Future<HomeData> home();
  Future<Entitlement> entitlement({String? cycle});
  Future<List<Fps>> eligibleFps();
  Future<List<Cycle>> cycles();

  Future<IntentReceipt> submitIntent({required String fpsId, required int riceKg, required int wheatKg, required String mode});
  Future<IntentReceipt> intentReceipt(String reference);
  Future<IntentReceipt> cancelIntent(String reference);

  Future<Journey> tracking({String? cycle});
  Future<List<CollectionRecord>> collections();
  Future<List<TransactionRecord>> transactions();
  Future<List<IntentRecord>> intents();
  Future<DigitalReceipt> digitalReceipt(String transactionId);

  Future<AssistantAnswer> ask({String? question, String? intent, required String language});
  Future<IntelSummary> intelSummary();
  Future<IntelAnswer> intelAsk(String question);
  Future<GrievanceSuggestion> suggestGrievance(String description);
  Future<Grievance> submitGrievance({required String category, required String description, String? relatedTransactionId, String? cycle});
  Future<List<Grievance>> myGrievances();
  Future<List<AppNotification>> notifications({String? cycle});
}

class HttpApiClient implements ApiClient {
  HttpApiClient({required this.baseUrl, required this.token, this.onUnauthorized, http.Client? client,
      this.timeout = const Duration(seconds: 15)})
      : _http = client ?? http.Client();

  final String baseUrl;

  /// Read on every call so a new login is picked up without rebuilding the client.
  final String? Function() token;

  /// Called when the server says the session is no longer valid (expired, revoked, account disabled).
  final void Function()? onUnauthorized;
  final Duration timeout;
  final http.Client _http;

  Uri _uri(String path, [Map<String, String?> query = const {}]) {
    final q = {for (final e in query.entries) if (e.value != null) e.key: e.value!};
    return Uri.parse('$baseUrl$path').replace(queryParameters: q.isEmpty ? null : q);
  }

  Future<dynamic> _send(String method, String path, {Map<String, String?> query = const {}, Object? body, bool auth = true}) async {
    final headers = {'Content-Type': 'application/json', 'Accept': 'application/json'};
    final t = token();
    if (auth && t != null) headers['Authorization'] = 'Bearer $t';
    final uri = _uri(path, query);
    http.Response res;
    try {
      final future = method == 'GET'
          ? _http.get(uri, headers: headers)
          : _http.post(uri, headers: headers, body: body == null ? null : jsonEncode(body));
      res = await future.timeout(timeout);
    } on TimeoutException {
      throw ApiException(ApiErrorKind.timeout);
    } on http.ClientException {
      throw ApiException(ApiErrorKind.offline);
    } catch (_) {
      // dart:io SocketException and friends: no connection or an unreachable host
      throw ApiException(ApiErrorKind.offline);
    }
    return _decode(res, auth);
  }

  dynamic _decode(http.Response res, bool auth) {
    dynamic json;
    try {
      json = res.body.isEmpty ? null : jsonDecode(utf8.decode(res.bodyBytes));
    } catch (_) {
      json = null;
    }
    if (res.statusCode >= 200 && res.statusCode < 300) return json;
    final map = json is Map<String, dynamic> ? json : const <String, dynamic>{};
    final code = map['code'] as String?;
    final detail = map['detail'];
    final message = detail is String ? detail : '';
    final params = map['params'] is Map ? Map<String, dynamic>.from(map['params'] as Map) : const <String, dynamic>{};
    if (res.statusCode == 401 && auth) {
      onUnauthorized?.call();
      throw ApiException(ApiErrorKind.unauthorized, status: 401, code: code, message: message);
    }
    if (res.statusCode >= 500) {
      throw ApiException(ApiErrorKind.server, status: res.statusCode, code: code, message: message);
    }
    throw ApiException(ApiErrorKind.client, status: res.statusCode, code: code, message: message, params: params);
  }

  Map<String, dynamic> _obj(dynamic j) => j as Map<String, dynamic>;
  List<Map<String, dynamic>> _list(dynamic j, String key) => ((_obj(j)[key]) as List).cast<Map<String, dynamic>>();

  @override
  Future<OtpRequestResult> requestOtp(String rationCardId, String registeredMobile) async => OtpRequestResult.fromJson(_obj(
      await _send('POST', '/api/v1/auth/beneficiary/request-otp',
          body: {'ration_card_id': rationCardId, 'registered_mobile': registeredMobile}, auth: false)));

  @override
  Future<String> verifyOtp(String rationCardId, String otp) async => _obj(await _send('POST', '/api/v1/auth/beneficiary/verify-otp',
      body: {'ration_card_id': rationCardId, 'otp': otp}, auth: false))['access_token'] as String;

  @override
  Future<void> logout() async {
    try {
      await _send('POST', '/api/v1/auth/logout');
    } on ApiException {
      // the token may already be invalid; the local session is cleared either way
    }
  }

  @override
  Future<HomeData> home() async => HomeData.fromJson(_obj(await _send('GET', '/api/v1/beneficiaries/me/home')));

  @override
  Future<Entitlement> entitlement({String? cycle}) async =>
      Entitlement.fromJson(_obj(await _send('GET', '/api/v1/beneficiaries/me/entitlement', query: {'cycle': cycle})));

  @override
  Future<List<Fps>> eligibleFps() async => _list(await _send('GET', '/api/v1/fps/eligible'), 'fps').map(Fps.fromJson).toList();

  @override
  Future<List<Cycle>> cycles() async {
    final j = _obj(await _send('GET', '/api/v1/cycles'));
    return ((j['cycles'] as List).cast<Map<String, dynamic>>()).map(Cycle.fromJson).toList();
  }

  @override
  Future<IntentReceipt> submitIntent({required String fpsId, required int riceKg, required int wheatKg, required String mode}) async =>
      IntentReceipt.fromJson(_obj(await _send('POST', '/api/v1/preferences',
          body: {'fps_id': fpsId, 'rice_quantity_kg': riceKg, 'wheat_quantity_kg': wheatKg, 'collection_mode': mode})));

  @override
  Future<IntentReceipt> intentReceipt(String reference) async =>
      IntentReceipt.fromJson(_obj(await _send('GET', '/api/v1/preferences/${Uri.encodeComponent(reference)}/receipt')));

  @override
  Future<IntentReceipt> cancelIntent(String reference) async =>
      IntentReceipt.fromJson(_obj(await _send('POST', '/api/v1/preferences/${Uri.encodeComponent(reference)}/cancel')));

  @override
  Future<Journey> tracking({String? cycle}) async => Journey.fromJson(_obj(await _send('GET', '/api/v1/tracking/me', query: {'cycle': cycle})));

  @override
  Future<List<CollectionRecord>> collections() async =>
      _list(await _send('GET', '/api/v1/history/me', query: {'kind': 'collections'}), 'items').map(CollectionRecord.fromJson).toList();

  @override
  Future<List<TransactionRecord>> transactions() async =>
      _list(await _send('GET', '/api/v1/history/me', query: {'kind': 'transactions'}), 'items').map(TransactionRecord.fromJson).toList();

  @override
  Future<List<IntentRecord>> intents() async =>
      _list(await _send('GET', '/api/v1/history/me', query: {'kind': 'intents'}), 'items').map(IntentRecord.fromJson).toList();

  @override
  Future<DigitalReceipt> digitalReceipt(String transactionId) async =>
      DigitalReceipt.fromJson(_obj(await _send('GET', '/api/v1/transactions/${Uri.encodeComponent(transactionId)}/receipt')));

  @override
  Future<AssistantAnswer> ask({String? question, String? intent, required String language}) async =>
      AssistantAnswer.fromJson(_obj(await _send('POST', '/api/v1/ai/assistant',
          body: {if (question != null) 'question': question, if (intent != null) 'intent': intent, 'language': language})));

  /// Phase 8 cross-portal intelligence, strictly scoped server-side to the
  /// signed-in beneficiary's own records. Advisory only — no writes.
  @override
  Future<IntelSummary> intelSummary() async =>
      IntelSummary.fromJson(_obj(await _send('GET', '/api/v1/intelligence/beneficiary/me/summary')));

  @override
  Future<IntelAnswer> intelAsk(String question) async =>
      IntelAnswer.fromJson(_obj(await _send('POST', '/api/v1/intelligence/ask', body: {'question': question})));

  @override
  Future<GrievanceSuggestion> suggestGrievance(String description) async => GrievanceSuggestion.fromJson(
      _obj(await _send('POST', '/api/v1/ai/grievance-suggest', body: {'description': description})));

  @override
  Future<Grievance> submitGrievance({required String category, required String description, String? relatedTransactionId, String? cycle}) async =>
      Grievance.fromJson(_obj(await _send('POST', '/api/v1/grievances', body: {
        'category': category,
        'description': description,
        if (relatedTransactionId != null) 'related_transaction_id': relatedTransactionId,
        if (cycle != null) 'cycle': cycle,
      })));

  @override
  Future<List<Grievance>> myGrievances() async => _list(await _send('GET', '/api/v1/grievances/me'), 'grievances').map(Grievance.fromJson).toList();

  @override
  Future<List<AppNotification>> notifications({String? cycle}) async =>
      _list(await _send('GET', '/api/v1/notifications/me', query: {'cycle': cycle}), 'notifications').map(AppNotification.fromJson).toList();
}

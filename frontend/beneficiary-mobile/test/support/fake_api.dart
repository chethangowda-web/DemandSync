import 'dart:async';

import 'package:demandsync_beneficiary/core/api_client.dart';
import 'package:demandsync_beneficiary/core/models.dart';

import 'fixtures.dart';

/// A test double for the API client: it replays responses recorded from the real backend and remembers exactly
/// what the UI asked for. It lives in test/ only; the app itself contains no such thing.
class FakeApi implements ApiClient {
  final calls = <String>[];
  final overrides = <String, FutureOr<Object?> Function()>{};

  ({String fpsId, int rice, int wheat, String mode})? lastIntent;
  ({String? question, String? intent, String language})? lastAsk;
  ({String category, String description, String? tx})? lastGrievance;
  ({String card, String mobile})? lastOtpRequest;
  String? lastVerify;
  String? lastCancelled;
  String? lastReceiptRequested;

  Future<T> _do<T>(String name, T Function() base) async {
    calls.add(name);
    final o = overrides[name];
    if (o != null) return (await o()) as T;
    return base();
  }

  @override
  Future<OtpRequestResult> requestOtp(String rationCardId, String registeredMobile) {
    lastOtpRequest = (card: rationCardId, mobile: registeredMobile);
    return _do('requestOtp', () => OtpRequestResult.fromJson(fixture('otp_request')));
  }

  @override
  Future<String> verifyOtp(String rationCardId, String otp) {
    lastVerify = otp;
    return _do('verifyOtp', () => 'token-from-fake-backend');
  }

  @override
  Future<void> logout() => _do('logout', () {});

  @override
  Future<HomeData> home() => _do('home', () => HomeData.fromJson(fixture('home_open')));

  @override
  Future<Entitlement> entitlement({String? cycle}) => _do('entitlement', () => Entitlement.fromJson(fixture('entitlement')));

  @override
  Future<List<Fps>> eligibleFps() =>
      _do('eligibleFps', () => (fixture('fps_eligible')['fps'] as List).map((j) => Fps.fromJson(j as Map<String, dynamic>)).toList());

  @override
  Future<IntentReceipt> submitIntent({required String fpsId, required int riceKg, required int wheatKg, required String mode}) {
    lastIntent = (fpsId: fpsId, rice: riceKg, wheat: wheatKg, mode: mode);
    return _do('submitIntent', () => IntentReceipt.fromJson(fixture('receipt_recorded')));
  }

  @override
  Future<IntentReceipt> intentReceipt(String reference) {
    lastReceiptRequested = reference;
    return _do('intentReceipt', () => IntentReceipt.fromJson(fixture('receipt_recorded')));
  }

  @override
  Future<IntentReceipt> cancelIntent(String reference) {
    lastCancelled = reference;
    return _do('cancelIntent', () => IntentReceipt.fromJson(fixture('cancelled')));
  }

  @override
  Future<Journey> tracking({String? cycle}) => _do('tracking', () => Journey.fromJson(fixture('tracking_open')));

  @override
  Future<List<CollectionRecord>> collections() =>
      _do('collections', () => (fixture('history_collections')['items'] as List).map((j) => CollectionRecord.fromJson(j as Map<String, dynamic>)).toList());

  @override
  Future<List<TransactionRecord>> transactions() =>
      _do('transactions', () => (fixture('history_transactions')['items'] as List).map((j) => TransactionRecord.fromJson(j as Map<String, dynamic>)).toList());

  @override
  Future<List<IntentRecord>> intents() =>
      _do('intents', () => (fixture('history_intents')['items'] as List).map((j) => IntentRecord.fromJson(j as Map<String, dynamic>)).toList());

  @override
  Future<DigitalReceipt> digitalReceipt(String transactionId) => _do('digitalReceipt', () => DigitalReceipt.fromJson(fixture('digital_receipt')));

  @override
  Future<AssistantAnswer> ask({String? question, String? intent, required String language}) {
    lastAsk = (question: question, intent: intent, language: language);
    return _do('ask', () => AssistantAnswer.fromJson(fixture('assistant_entitlement_$language')));
  }

  @override
  Future<IntelSummary> intelSummary() =>
      _do('intelSummary', () => IntelSummary.fromJson(const {'cycle': '2026-03', 'insights': []}));

  @override
  Future<IntelAnswer> intelAsk(String question) =>
      _do('intelAsk', () => IntelAnswer.fromJson(const {'answer': 'Test answer', 'model': 'rule-intelligence-v1'}));

  @override
  Future<GrievanceSuggestion> suggestGrievance(String description) =>
      _do('suggestGrievance', () => GrievanceSuggestion.fromJson(fixture('grievance_suggest')));

  @override
  Future<Grievance> submitGrievance({required String category, required String description, String? relatedTransactionId, String? cycle}) {
    lastGrievance = (category: category, description: description, tx: relatedTransactionId);
    return _do('submitGrievance', () => Grievance.fromJson(fixture('grievance_created')));
  }

  @override
  Future<List<Grievance>> myGrievances() =>
      _do('myGrievances', () => (fixture('grievances')['grievances'] as List).map((j) => Grievance.fromJson(j as Map<String, dynamic>)).toList());

  @override
  Future<List<Cycle>> cycles() =>
      _do('cycles', () => [Cycle.fromJson(fixture('home_open')['cycle'] as Map<String, dynamic>)]);

  @override
  Future<List<AppNotification>> notifications({String? cycle}) => _do('notifications', () => <AppNotification>[]);
}

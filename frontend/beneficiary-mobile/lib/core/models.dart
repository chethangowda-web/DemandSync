// Typed views of the DemandSYNC API responses. Every value comes from the backend; nothing is defaulted here.
// Missing optional values stay null so the UI can say "Data unavailable" instead of inventing something.

DateTime? _date(dynamic v) => v == null ? null : DateTime.parse(v as String);
num _num(dynamic v) => v as num;
String? _str(dynamic v) => v as String?;

class Fps {
  Fps({required this.id, required this.name, required this.district, required this.taluk, required this.latitude,
      required this.longitude, required this.openingHours, required this.status, this.isCurrent = false, this.distanceKm});

  final String id, name, district, taluk, status;
  final double latitude, longitude;
  final String? openingHours;
  final bool isCurrent;
  final double? distanceKm;

  bool get isActive => status == 'ACTIVE';

  factory Fps.fromJson(Map<String, dynamic> j) => Fps(
        id: j['fps_id'] as String,
        name: j['name'] as String,
        district: j['district'] as String,
        taluk: j['taluk'] as String,
        latitude: _num(j['latitude']).toDouble(),
        longitude: _num(j['longitude']).toDouble(),
        openingHours: _str(j['opening_hours']),
        status: j['status'] as String,
        isCurrent: (j['is_current'] as bool?) ?? false,
        distanceKm: j['distance_km'] == null ? null : _num(j['distance_km']).toDouble(),
      );
}

class Beneficiary {
  Beneficiary({required this.id, required this.rationCardId, required this.name, required this.householdSize,
      required this.scheme, required this.district, required this.taluk, required this.status});

  final String id, rationCardId, name, scheme, district, status;
  final String? taluk;
  final int householdSize;

  factory Beneficiary.fromJson(Map<String, dynamic> j) => Beneficiary(
        id: j['beneficiary_id'] as String,
        rationCardId: j['ration_card_id'] as String,
        name: j['name'] as String,
        householdSize: j['household_size'] as int,
        scheme: j['scheme'] as String,
        district: j['district'] as String,
        taluk: _str(j['taluk']),
        status: (_str(j['status']) ?? 'ACTIVE'),
      );
}

class Cycle {
  Cycle({required this.cycle, required this.state, required this.windowOpen, required this.periodStart,
      required this.periodEnd, required this.windowStart, required this.windowEnd});

  final String cycle, state; // cycle is "YYYY-MM"
  final bool windowOpen;
  final DateTime periodStart, periodEnd;
  final DateTime? windowStart, windowEnd;

  factory Cycle.fromJson(Map<String, dynamic> j) => Cycle(
        cycle: j['cycle'] as String,
        state: j['state'] as String,
        windowOpen: j['window_open'] as bool,
        periodStart: _date(j['period_start'])!,
        periodEnd: _date(j['period_end'])!,
        windowStart: _date(j['choice_window_start']),
        windowEnd: _date(j['choice_window_end']),
      );
}

class Entitlement {
  Entitlement({required this.cycle, required this.scheme, required this.householdSize, required this.riceKg,
      required this.wheatKg, required this.totalKg, required this.collectedRiceKg, required this.collectedWheatKg,
      required this.collectedTotalKg, required this.remainingRiceKg, required this.remainingWheatKg,
      required this.remainingTotalKg});

  final String cycle, scheme;
  final int householdSize;
  final num riceKg, wheatKg, totalKg, collectedRiceKg, collectedWheatKg, collectedTotalKg;
  final num remainingRiceKg, remainingWheatKg, remainingTotalKg;

  factory Entitlement.fromJson(Map<String, dynamic> j) => Entitlement(
        cycle: j['cycle'] as String,
        scheme: j['scheme'] as String,
        householdSize: j['household_size'] as int,
        riceKg: _num(j['rice_kg']),
        wheatKg: _num(j['wheat_kg']),
        totalKg: _num(j['total_kg']),
        collectedRiceKg: _num(j['collected_rice_kg']),
        collectedWheatKg: _num(j['collected_wheat_kg']),
        collectedTotalKg: _num(j['collected_total_kg']),
        remainingRiceKg: _num(j['remaining_rice_kg']),
        remainingWheatKg: _num(j['remaining_wheat_kg']),
        remainingTotalKg: _num(j['remaining_total_kg']),
      );
}

class IntentReceipt {
  IntentReceipt({required this.reference, required this.cycle, required this.status, required this.fps,
      required this.riceKg, required this.wheatKg, required this.totalKg, required this.collectionMode,
      required this.submittedAt, required this.canCancel});

  final String reference, cycle, status, collectionMode;
  final Fps fps;
  final num riceKg, wheatKg, totalKg;
  final DateTime submittedAt;
  final bool canCancel;

  bool get isCancelled => status == 'CANCELLED';

  factory IntentReceipt.fromJson(Map<String, dynamic> j) => IntentReceipt(
        reference: j['reference'] as String,
        cycle: j['cycle'] as String,
        status: j['status'] as String,
        fps: Fps.fromJson(j['fps'] as Map<String, dynamic>),
        riceKg: _num(j['rice_kg']),
        wheatKg: _num(j['wheat_kg']),
        totalKg: _num(j['total_kg']),
        collectionMode: j['collection_mode'] as String,
        submittedAt: _date(j['submitted_at'])!,
        canCancel: j['can_cancel'] as bool,
      );
}

class Notice {
  Notice(this.code, this.params);
  final String code;
  final Map<String, dynamic> params;

  factory Notice.fromJson(Map<String, dynamic> j) =>
      Notice(j['code'] as String, Map<String, dynamic>.from((j['params'] as Map?) ?? const {}));
}

class HomeData {
  HomeData({required this.beneficiary, required this.statutory, required this.fps, required this.cycle,
      required this.entitlement, required this.intent, required this.statusKey, required this.notice});

  final Beneficiary beneficiary;
  final ({num rice, num wheat, num total}) statutory;
  final Fps fps;
  final Cycle? cycle;
  final Entitlement? entitlement;
  final IntentReceipt? intent;
  final String? statusKey;
  final Notice? notice;

  factory HomeData.fromJson(Map<String, dynamic> j) {
    final s = j['entitlement_statutory'] as Map<String, dynamic>;
    return HomeData(
      beneficiary: Beneficiary.fromJson(j['beneficiary'] as Map<String, dynamic>),
      statutory: (rice: _num(s['rice_kg']), wheat: _num(s['wheat_kg']), total: _num(s['total_kg'])),
      fps: Fps.fromJson(j['fps'] as Map<String, dynamic>),
      cycle: j['cycle'] == null ? null : Cycle.fromJson(j['cycle'] as Map<String, dynamic>),
      entitlement: j['entitlement'] == null ? null : Entitlement.fromJson(j['entitlement'] as Map<String, dynamic>),
      intent: j['intent'] == null ? null : IntentReceipt.fromJson(j['intent'] as Map<String, dynamic>),
      statusKey: _str(j['status_key']),
      notice: j['notice'] == null ? null : Notice.fromJson(j['notice'] as Map<String, dynamic>),
    );
  }
}

class JourneyStep {
  JourneyStep({required this.key, required this.status, required this.at, required this.detail});
  final String key, status; // status: DONE | ACTIVE | PENDING | DELAYED | UNAVAILABLE
  final DateTime? at;
  final String? detail;

  factory JourneyStep.fromJson(Map<String, dynamic> j) =>
      JourneyStep(key: j['key'] as String, status: j['status'] as String, at: _date(j['at']), detail: _str(j['detail']));
}

class Telemetry {
  Telemetry({required this.vehicleNumber, required this.latitude, required this.longitude, required this.speedKmph,
      required this.status, required this.lastUpdate});
  final String vehicleNumber, status;
  final double latitude, longitude;
  final num? speedKmph;
  final DateTime lastUpdate;

  factory Telemetry.fromJson(Map<String, dynamic> j) => Telemetry(
        vehicleNumber: j['vehicle_number'] as String,
        latitude: _num(j['latitude']).toDouble(),
        longitude: _num(j['longitude']).toDouble(),
        speedKmph: j['speed_kmph'] == null ? null : _num(j['speed_kmph']),
        status: j['status'] as String,
        lastUpdate: _date(j['last_update'])!,
      );
}

class RouteInfo {
  RouteInfo({required this.stopsTotal, required this.yourStop, required this.plannedEtaMinutes});
  final int stopsTotal, yourStop;
  final num? plannedEtaMinutes;

  factory RouteInfo.fromJson(Map<String, dynamic> j) => RouteInfo(
        stopsTotal: j['stops_total'] as int,
        yourStop: j['your_stop'] as int,
        plannedEtaMinutes: j['planned_eta_minutes'] == null ? null : _num(j['planned_eta_minutes']),
      );
}

class Journey {
  Journey({required this.cycle, required this.cycleState, required this.steps, required this.headline,
      required this.telemetry, required this.route, required this.telemetryNote});
  final String cycle, cycleState;
  final List<JourneyStep> steps;
  final String? headline, telemetryNote;
  final Telemetry? telemetry;
  final RouteInfo? route;

  factory Journey.fromJson(Map<String, dynamic> j) => Journey(
        cycle: j['cycle'] as String,
        cycleState: j['cycle_state'] as String,
        steps: (j['steps'] as List).map((s) => JourneyStep.fromJson(s as Map<String, dynamic>)).toList(),
        headline: _str(j['headline']),
        telemetry: j['telemetry'] == null ? null : Telemetry.fromJson(j['telemetry'] as Map<String, dynamic>),
        route: j['route'] == null ? null : RouteInfo.fromJson(j['route'] as Map<String, dynamic>),
        telemetryNote: _str(j['telemetry_note']),
      );
}

class CollectionRecord {
  CollectionRecord({required this.cycle, required this.fpsName, required this.at, required this.riceKg,
      required this.wheatKg, required this.totalKg, required this.transactionIds});
  final String cycle, fpsName;
  final DateTime at;
  final num riceKg, wheatKg, totalKg;
  final List<String> transactionIds;

  factory CollectionRecord.fromJson(Map<String, dynamic> j) => CollectionRecord(
        cycle: j['cycle'] as String,
        fpsName: j['fps_name'] as String,
        at: _date(j['at'])!,
        riceKg: _num(j['rice_kg']),
        wheatKg: _num(j['wheat_kg']),
        totalKg: _num(j['total_kg']),
        transactionIds: (j['transaction_ids'] as List).cast<String>(),
      );
}

class TransactionRecord {
  TransactionRecord({required this.reference, required this.cycle, required this.at, required this.fpsName,
      required this.commodity, required this.quantityKg, required this.status, required this.receiptNumber});
  final String reference, cycle, fpsName, commodity, status;
  final String? receiptNumber;
  final DateTime at;
  final num quantityKg;

  bool get isSuccess => status == 'SUCCESS';

  factory TransactionRecord.fromJson(Map<String, dynamic> j) => TransactionRecord(
        reference: j['reference'] as String,
        cycle: j['cycle'] as String,
        at: _date(j['at'])!,
        fpsName: j['fps_name'] as String,
        commodity: j['commodity'] as String,
        quantityKg: _num(j['quantity_kg']),
        status: j['status'] as String,
        receiptNumber: _str(j['receipt_number']),
      );
}

class IntentRecord {
  IntentRecord({required this.reference, required this.cycle, required this.at, required this.fpsName,
      required this.riceKg, required this.wheatKg, required this.totalKg, required this.status});
  final String reference, cycle, fpsName, status;
  final DateTime at;
  final num riceKg, wheatKg, totalKg;

  factory IntentRecord.fromJson(Map<String, dynamic> j) => IntentRecord(
        reference: j['reference'] as String,
        cycle: j['cycle'] as String,
        at: _date(j['at'])!,
        fpsName: j['fps_name'] as String,
        riceKg: _num(j['rice_kg']),
        wheatKg: _num(j['wheat_kg']),
        totalKg: _num(j['total_kg']),
        status: j['status'] as String,
      );
}

class DigitalReceipt {
  DigitalReceipt({required this.transactionId, required this.receiptNumber, required this.cycle,
      required this.beneficiaryName, required this.rationCardId, required this.fpsName, required this.fpsId,
      required this.commodity, required this.quantityKg, required this.time, required this.verificationRef,
      required this.qrPayload});
  final String transactionId, cycle, beneficiaryName, rationCardId, fpsName, fpsId, commodity, verificationRef, qrPayload;
  final String? receiptNumber;
  final num quantityKg;
  final DateTime time;

  factory DigitalReceipt.fromJson(Map<String, dynamic> j) {
    final f = j['fps'] as Map<String, dynamic>;
    return DigitalReceipt(
      transactionId: j['transaction_id'] as String,
      receiptNumber: _str(j['receipt_number']),
      cycle: j['cycle'] as String,
      beneficiaryName: j['beneficiary_name'] as String,
      rationCardId: j['ration_card_id'] as String,
      fpsName: f['name'] as String,
      fpsId: f['fps_id'] as String,
      commodity: j['commodity'] as String,
      quantityKg: _num(j['quantity_kg']),
      time: _date(j['transaction_time'])!,
      verificationRef: j['verification_ref'] as String,
      qrPayload: j['qr_payload'] as String,
    );
  }
}

class AssistantAnswer {
  AssistantAnswer({required this.answer, required this.intent, required this.source, required this.view,
      required this.disclaimer, required this.generative});
  final String answer, intent, disclaimer;
  final String? source, view; // view: entitlement | cycle | plan | track | history | profile
  final bool generative;

  factory AssistantAnswer.fromJson(Map<String, dynamic> j) => AssistantAnswer(
        answer: j['answer'] as String,
        intent: j['intent'] as String,
        source: _str(j['source']),
        view: _str(j['view']),
        disclaimer: j['disclaimer'] as String,
        generative: (j['generative'] as bool?) ?? false,
      );
}
class SuggestedTransaction {
  SuggestedTransaction(
      {required this.id,
      required this.cycle,
      required this.commodity,
      required this.quantityKg,
      required this.status,
      required this.at});
  final String id, cycle, commodity, status;
  final num quantityKg;
  final DateTime at;

  factory SuggestedTransaction.fromJson(Map<String, dynamic> j) => SuggestedTransaction(
        id: j['transaction_id'] as String,
        cycle: j['cycle'] as String,
        commodity: j['commodity'] as String,
        quantityKg: _num(j['quantity_kg']),
        status: j['status'] as String,
        at: _date(j['at'])!,
      );
}

class GrievanceSuggestion {
  GrievanceSuggestion({required this.category, required this.confidence, required this.related});
  final String category;
  final num confidence;
  final List<SuggestedTransaction> related;

  factory GrievanceSuggestion.fromJson(Map<String, dynamic> j) => GrievanceSuggestion(
        category: j['category'] as String,
        confidence: _num(j['confidence']),
        related: (j['related_transactions'] as List)
            .map((t) => SuggestedTransaction.fromJson(t as Map<String, dynamic>))
            .toList(),
      );
}

/// Phase 8: one advisory card from the beneficiary-scoped intelligence summary.
/// Only the signed-in beneficiary's own records — enforced server-side.
class IntelCard {
  IntelCard({required this.type, required this.title, required this.summary, this.recommendation});
  final String type, title, summary;
  final String? recommendation;

  factory IntelCard.fromJson(Map<String, dynamic> j) => IntelCard(
        type: j['type'] as String,
        title: j['title'] as String,
        summary: j['summary'] as String,
        recommendation: _str(j['recommendation']),
      );
}

class IntelSummary {
  IntelSummary({required this.cycle, required this.cards});
  final String? cycle;
  final List<IntelCard> cards;

  factory IntelSummary.fromJson(Map<String, dynamic> j) => IntelSummary(
        cycle: _str(j['cycle']),
        cards: ((j['insights'] as List?) ?? [])
            .map((c) => IntelCard.fromJson(c as Map<String, dynamic>))
            .toList(),
      );
}

/// Phase 8: grounded answer from POST /intelligence/ask. Advisory only.
class IntelAnswer {
  IntelAnswer({required this.answer, required this.model});
  final String answer, model;

  factory IntelAnswer.fromJson(Map<String, dynamic> j) => IntelAnswer(
        answer: j['answer'] as String,
        model: (j['model'] as String?) ?? 'rule-intelligence-v1',
      );
}

class Grievance {
  Grievance({required this.id, required this.category, required this.description, required this.status,
      required this.resolution, required this.createdAt});
  final String id, category, description, status;
  final String? resolution;
  final DateTime createdAt;
  factory Grievance.fromJson(Map<String, dynamic> j) => Grievance(
        id: j['grievance_id'] as String,
        category: j['category'] as String,
        description: j['description'] as String,
        status: j['status'] as String,
        resolution: _str(j['resolution']),
        createdAt: _date(j['created_at'])!,
      );
}

class AppNotification {
  AppNotification({required this.id, required this.message, required this.at, required this.cycle,
      required this.kind, required this.view});
  final String id, message, kind;
  final String? cycle, view;
  final DateTime? at;
  factory AppNotification.fromJson(Map<String, dynamic> j) => AppNotification(
        id: j['id'] as String,
        message: j['message'] as String,
        at: _date(j['at']),
        cycle: _str(j['cycle']),
        kind: j['kind'] as String,
        view: _str(j['view']),
      );
}

class OtpRequestResult {
  OtpRequestResult({required this.expiresInSeconds, required this.devOtp});
  final int expiresInSeconds;

  /// Present only when the server runs its development OTP provider. The UI must say so plainly.
  final String? devOtp;

  factory OtpRequestResult.fromJson(Map<String, dynamic> j) =>
      OtpRequestResult(expiresInSeconds: j['expires_in'] as int, devOtp: _str(j['dev_otp']));
}

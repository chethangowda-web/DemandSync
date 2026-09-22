import '../l10n/generated/app_localizations.dart';
import 'api_exception.dart';
import 'format.dart';
import 'models.dart';

/// Backend codes -> localised words. Unknown codes fall back to a generic message; nothing is invented.

String stageLabel(AppLocalizations l, String key) => switch (key) {
      'CHOICE_WINDOW_OPEN' => l.stChoiceWindowOpen,
      'CHOICE_WINDOW_CLOSED' => l.stChoiceWindowClosed,
      'INTENT_SUBMITTED' => l.stIntentSubmitted,
      'DEMAND_PLANNED' => l.stDemandPlanned,
      'ALLOCATED' => l.stAllocated,
      'DISPATCHED' => l.stDispatched,
      'IN_TRANSIT' => l.stInTransit,
      'RECEIVED_AT_FPS' => l.stReceivedAtFps,
      'AVAILABLE_FOR_COLLECTION' => l.stAvailableForCollection,
      'COLLECTED' => l.stCollected,
      _ => l.dataUnavailable,
    };

String stepStateLabel(AppLocalizations l, String status) => switch (status) {
      'DONE' => l.stateDone,
      'ACTIVE' => l.stateActive,
      'DELAYED' => l.stateDelayed,
      'UNAVAILABLE' => l.stateUnavailable,
      _ => l.statePending,
    };

String stepDetailText(AppLocalizations l, JourneyStep s) {
  final d = s.detail;
  if (d == null) return '';
  switch (d) {
    case 'NO_INTENT_SUBMITTED':
      return l.detailNoIntent;
    case 'ALLOCATION_ON_HOLD':
      return l.detailAllocationOnHold;
    case 'DELIVERY_REJECTED':
      return l.detailDeliveryRejected;
    case 'INFERRED_FROM_DELIVERY':
      return l.dataNoteInferred;
  }
  if (s.key == 'COLLECTED' && d.contains(':')) {
    // "RICE:18, WHEAT:6" as written by the backend
    final parts = {for (final p in d.split(',')) p.split(':')[0].trim(): p.split(':')[1].trim()};
    return l.collectedDetail(parts['RICE'] ?? '0', parts['WHEAT'] ?? '0');
  }
  return ''; // reference numbers and raw record status are not citizen-facing text
}

String schemeLabel(AppLocalizations l, String scheme) => switch (scheme) {
      'AAY' => l.schemeAAY,
      'PHH' => l.schemePHH,
      _ => scheme,
    };

String commodityLabel(AppLocalizations l, String c) => switch (c) {
      'RICE' => l.rice,
      'WHEAT' => l.wheat,
      _ => c,
    };

String txnStatusLabel(AppLocalizations l, String s) => switch (s) {
      'SUCCESS' => l.txnSuccess,
      'FAILED' => l.txnFailed,
      _ => l.txnCancelled,
    };

String intentStatusLabel(AppLocalizations l, String s) => s == 'RECORDED' ? l.statusRecorded : l.statusCancelled;

String modeLabel(AppLocalizations l, String m) => m == 'AUTHORIZED_PERSON' ? l.modeAuthorized : l.modeSelf;

String grievanceStatusLabel(AppLocalizations l, String s) => switch (s) {
      'OPEN' => l.grStatusOpen,
      'IN_REVIEW' => l.grStatusInReview,
      'RESOLVED' => l.grStatusResolved,
      _ => l.grStatusClosed,
    };

const grievanceCategories = [
  'SHORT_DELIVERY', 'WRONG_QUANTITY', 'FPS_ISSUE', 'QUALITY', 'TRANSACTION_FAILURE', 'ENTITLEMENT_QUERY', 'COLLECTION_ISSUE', 'OTHER'
];

String categoryLabel(AppLocalizations l, String c) => switch (c) {
      'SHORT_DELIVERY' => l.catShortDelivery,
      'WRONG_QUANTITY' => l.catWrongQuantity,
      'FPS_ISSUE' || 'FPS_CLOSED' => l.catFpsIssue,
      'QUALITY' => l.catQuality,
      'TRANSACTION_FAILURE' => l.catTransaction,
      'ENTITLEMENT_QUERY' => l.catEntitlement,
      'COLLECTION_ISSUE' => l.catCollection,
      _ => l.catOther,
    };

String noticeText(AppLocalizations l, Notice n, String locale) => switch (n.code) {
      'PLAN_NOW' => l.noticePlanNow(n.params['closes'] == null ? l.dataUnavailable : dateText(DateTime.parse(n.params['closes'] as String), locale)),
      'INTENT_RECORDED' => l.noticeIntentRecorded('${n.params['reference'] ?? ''}'),
      'RATION_AT_FPS' => l.noticeRationAtFps,
      'WINDOW_CLOSED_NO_INTENT' => l.noticeWindowClosedNoIntent,
      'FPS_NOT_ACTIVE' => l.noticeFpsNotActive('${n.params['fps'] ?? ''}'),
      'NO_CYCLE' => l.noticeNoCycle,
      _ => '',
    };

String cycleExplanation(AppLocalizations l, HomeData h) {
  if (h.intent != null) {
    return (h.statusKey == 'INTENT_SUBMITTED') ? l.explainPlanRecorded : l.explainInProgress;
  }
  return (h.cycle?.windowOpen ?? false) ? l.explainOpen : l.explainClosedNoPlan;
}

/// Turns any failure into words the beneficiary can act on, in their language.
String errorText(AppLocalizations l, Object error) {
  if (error is! ApiException) return l.errGeneric;
  switch (error.kind) {
    case ApiErrorKind.offline:
      return l.errOffline;
    case ApiErrorKind.timeout:
      return l.errTimeout;
    case ApiErrorKind.unauthorized:
      return l.errSession;
    case ApiErrorKind.server:
      return error.status == 503 && error.code == 'OTP_UNAVAILABLE' ? l.errOtpUnavailable : l.errServer;
    case ApiErrorKind.client:
      break;
  }
  final p = error.params;
  switch (error.code) {
    case 'INTENT_DUPLICATE':
      return l.errIntentDuplicate;
    case 'CHOICE_WINDOW_CLOSED':
      return l.errWindowClosed;
    case 'EXCEEDS_REMAINING':
      return l.errExceedsRemaining;
    case 'INVALID_QUANTITY':
      return l.errInvalidQuantity;
    case 'FPS_NOT_ELIGIBLE' || 'FPS_NOT_FOUND':
      return l.errFpsNotEligible;
    case 'NO_ACTIVE_CYCLE':
      return l.errNoCycle;
    case 'BAD_CREDENTIALS':
      return l.errBadCredentials;
    case 'ACCOUNT_DISABLED':
      return l.errAccountDisabled;
    case 'OTP_UNAVAILABLE':
      return l.errOtpUnavailable;
    case 'OTP_INVALID':
      return l.errOtpInvalid('${p['attempts_left'] ?? ''}');
    case 'OTP_INVALID_LAST':
      return l.errOtpInvalidLast;
    case 'OTP_EXPIRED':
      return l.errOtpExpired;
    case 'OTP_USED':
      return l.errOtpUsed;
    case 'OTP_TOO_MANY_ATTEMPTS':
      return l.errOtpTooMany;
    case 'OTP_NOT_REQUESTED':
      return l.errOtpNotRequested;
    case 'OTP_COOLDOWN':
      return l.errCooldown('${p['retry_after'] ?? ''}');
    case 'RECEIPT_NOT_FOUND' || 'TRANSACTION_NOT_FOUND' || 'RECEIPT_NOT_AVAILABLE':
      return l.errNotFound;
    case 'TOO_MANY_REQUESTS':
      return l.errTooMany;
  }
  return error.status == 429 ? l.errTooMany : l.errGeneric;
}

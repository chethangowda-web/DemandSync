// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Kannada (`kn`).
class AppLocalizationsKn extends AppLocalizations {
  AppLocalizationsKn([String locale = 'kn']) : super(locale);

  @override
  String get appName => 'DemandSYNC';

  @override
  String get appTagline => 'ನಿಮ್ಮ ಪಡಿತರ. ನಿಮ್ಮ ಹಕ್ಕು. ನಮ್ಮ ಆದ್ಯತೆ.';

  @override
  String get welcomeBody =>
      'ನಿಮ್ಮ ಪಡಿತರವನ್ನು ಯೋಜಿಸಲು, ಟ್ರ್ಯಾಕ್ ಮಾಡಲು ಮತ್ತು ಪಡೆಯಲು ಸರಳ, ಸುರಕ್ಷಿತ ಮತ್ತು ಪಾರದರ್ಶಕ ಮಾರ್ಗ.';

  @override
  String get getStarted => 'ಪ್ರಾರಂಭಿಸಿ';

  @override
  String get language => 'ಭಾಷೆ';

  @override
  String get cancel => 'ರದ್ದುಮಾಡಿ';

  @override
  String get confirm => 'ದೃಢೀಕರಿಸಿ';

  @override
  String get retry => 'ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ';

  @override
  String get back => 'ಹಿಂದೆ';

  @override
  String get close => 'ಮುಚ್ಚಿ';

  @override
  String get done => 'ಮುಗಿದಿದೆ';

  @override
  String get continueBtn => 'ಮುಂದುವರಿಸಿ';

  @override
  String kgValue(String value) {
    return '$value ಕೆಜಿ';
  }

  @override
  String get dataUnavailable => 'ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ';

  @override
  String get loading => 'ಲೋಡ್ ಆಗುತ್ತಿದೆ…';

  @override
  String get loginTitle => 'ಮರಳಿ ಸ್ವಾಗತ';

  @override
  String get loginSubtitle => 'ನಿಮ್ಮ ಪಡಿತರ ವಿವರಗಳನ್ನು ನೋಡಲು ಸೈನ್ ಇನ್ ಮಾಡಿ';

  @override
  String get rationCardLabel => 'ಪಡಿತರ ಚೀಟಿ ಸಂಖ್ಯೆ';

  @override
  String get mobileLabel => 'ನೋಂದಾಯಿತ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ';

  @override
  String get sendOtp => 'OTP ಕಳುಹಿಸಿ';

  @override
  String get otpTitle => 'OTP ನಮೂದಿಸಿ';

  @override
  String otpSentTo(String mobile) {
    return 'ನಾವು $mobile ಗೆ 6 ಅಂಕಿಯ ಕೋಡ್ ಕಳುಹಿಸಿದ್ದೇವೆ';
  }

  @override
  String get otpLabel => '6 ಅಂಕಿಯ OTP';

  @override
  String get verifyContinue => 'ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಮುಂದುವರಿಸಿ';

  @override
  String get resendOtp => 'OTP ಮತ್ತೆ ಕಳುಹಿಸಿ';

  @override
  String resendIn(String seconds) {
    return '$seconds ಸೆಕೆಂಡ್‌ನಲ್ಲಿ OTP ಮತ್ತೆ ಕಳುಹಿಸಿ';
  }

  @override
  String devModeBanner(String otp) {
    return 'ಡೆವಲಪ್‌ಮೆಂಟ್ ಮೋಡ್: SMS ಕಳುಹಿಸಲಾಗುವುದಿಲ್ಲ. ನಿಮ್ಮ ಕೋಡ್ $otp.';
  }

  @override
  String get useThisCode => 'ಈ ಕೋಡ್ ಬಳಸಿ';

  @override
  String get changeNumber => 'ವಿವರ ಬದಲಿಸಿ';

  @override
  String get fieldRequired => 'ಈ ಮಾಹಿತಿ ಅಗತ್ಯ';

  @override
  String get otpInvalidLength => 'ಎಲ್ಲಾ 6 ಅಂಕಿಗಳನ್ನು ನಮೂದಿಸಿ';

  @override
  String get loginHelp =>
      'ನಿಮ್ಮ ಕುಟುಂಬದ ನೋಂದಾಯಿತ ಪಡಿತರ ಚೀಟಿ ಸಂಖ್ಯೆ ಮತ್ತು ಮೊಬೈಲ್ ಸಂಖ್ಯೆಯನ್ನು ಬಳಸಿ.';

  @override
  String get navHome => 'ಮುಖಪುಟ';

  @override
  String get navMyRation => 'ನನ್ನ ಪಡಿತರ';

  @override
  String get navHistory => 'ಇತಿಹಾಸ';

  @override
  String get navHelp => 'ಸಹಾಯ';

  @override
  String get goodMorning => 'ಶುಭೋದಯ';

  @override
  String get goodAfternoon => 'ನಮಸ್ಕಾರ';

  @override
  String get goodEvening => 'ಶುಭ ಸಂಜೆ';

  @override
  String get myPds => 'ನನ್ನ ಪಿಡಿಎಸ್';

  @override
  String get currentCycle => 'ಪ್ರಸ್ತುತ ಚಕ್ರ';

  @override
  String collectionWindow(String start, String end) {
    return 'ಆಯ್ಕೆ ಅವಧಿ: $start ರಿಂದ $end';
  }

  @override
  String get myEntitlement => 'ನನ್ನ ಅರ್ಹತೆ';

  @override
  String get rice => 'ಅಕ್ಕಿ';

  @override
  String get wheat => 'ಗೋಧಿ';

  @override
  String get total => 'ಒಟ್ಟು';

  @override
  String get remaining => 'ಉಳಿದಿದೆ';

  @override
  String get collected => 'ಪಡೆದದ್ದು';

  @override
  String get currentFps => 'ನನ್ನ ನ್ಯಾಯಬೆಲೆ ಅಂಗಡಿ';

  @override
  String fpsIdLabel(String id) {
    return 'ಅಂಗಡಿ ಐಡಿ: $id';
  }

  @override
  String openingHours(String hours) {
    return 'ಸಮಯ $hours';
  }

  @override
  String get planMyCollection => 'ನನ್ನ ಸಂಗ್ರಹ ಯೋಜಿಸಿ';

  @override
  String get viewMyPlan => 'ನನ್ನ ಯೋಜನೆ ನೋಡಿ';

  @override
  String get trackMyRation => 'ನನ್ನ ಪಡಿತರ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ';

  @override
  String get viewEntitlement => 'ಅರ್ಹತೆ ನೋಡಿ';

  @override
  String get viewCycle => 'ಈ ಚಕ್ರದ ಬಗ್ಗೆ';

  @override
  String rationCardShort(String id) {
    return 'ಪಡಿತರ ಚೀಟಿ $id';
  }

  @override
  String get signedInAs => 'ಸೈನ್ ಇನ್ ಆಗಿದೆ';

  @override
  String get stChoiceWindowOpen => 'ಆಯ್ಕೆ ಅವಧಿ ತೆರೆದಿದೆ';

  @override
  String get stChoiceWindowClosed => 'ಆಯ್ಕೆ ಅವಧಿ ಮುಗಿದಿದೆ';

  @override
  String get stIntentSubmitted => 'ಯೋಜನೆ ಸಲ್ಲಿಸಲಾಗಿದೆ';

  @override
  String get stDemandPlanned => 'ಬೇಡಿಕೆ ನಿಗದಿಯಾಗಿದೆ';

  @override
  String get stAllocated => 'ಹಂಚಿಕೆಯಾಗಿದೆ';

  @override
  String get stDispatched => 'ರವಾನಿಸಲಾಗಿದೆ';

  @override
  String get stInTransit => 'ದಾರಿಯಲ್ಲಿದೆ';

  @override
  String get stReceivedAtFps => 'ಅಂಗಡಿಗೆ ತಲುಪಿದೆ';

  @override
  String get stAvailableForCollection => 'ಪಡೆಯಲು ಲಭ್ಯವಿದೆ';

  @override
  String get stCollected => 'ಪಡೆದಿದ್ದೀರಿ';

  @override
  String get stateDone => 'ಮುಗಿದಿದೆ';

  @override
  String get stateActive => 'ನಡೆಯುತ್ತಿದೆ';

  @override
  String get statePending => 'ಇನ್ನೂ ಇಲ್ಲ';

  @override
  String get stateDelayed => 'ತಡೆಹಿಡಿಯಲಾಗಿದೆ';

  @override
  String get stateUnavailable => 'ಲಭ್ಯವಿಲ್ಲ';

  @override
  String get notYetAvailable => 'ಇನ್ನೂ ಲಭ್ಯವಿಲ್ಲ';

  @override
  String noticePlanNow(String closes) {
    return 'ಆಯ್ಕೆ ಅವಧಿ $closes ರಂದು ಮುಗಿಯುತ್ತದೆ. ಈಗಲೇ ನಿಮ್ಮ ಸಂಗ್ರಹವನ್ನು ಯೋಜಿಸಿ.';
  }

  @override
  String noticeIntentRecorded(String ref) {
    return 'ನಿಮ್ಮ ಯೋಜನೆ $ref ದಾಖಲಾಗಿದೆ.';
  }

  @override
  String get noticeRationAtFps =>
      'ನಿಮ್ಮ ಪಡಿತರ ನಿಮ್ಮ ಅಂಗಡಿಗೆ ತಲುಪಿದೆ. ನೀವು ಪಡೆಯಬಹುದು.';

  @override
  String get noticeWindowClosedNoIntent =>
      'ಆಯ್ಕೆ ಅವಧಿ ಮುಗಿದಿದೆ ಮತ್ತು ಈ ಚಕ್ರಕ್ಕೆ ಯಾವುದೇ ಯೋಜನೆ ಸಲ್ಲಿಸಿಲ್ಲ.';

  @override
  String noticeFpsNotActive(String fps) {
    return 'ನಿಮ್ಮ ಅಂಗಡಿ $fps ಈಗ ಸಕ್ರಿಯವಾಗಿಲ್ಲ. ಯೋಜಿಸುವಾಗ ಬೇರೆ ಅಂಗಡಿಯನ್ನು ಆರಿಸಿ.';
  }

  @override
  String get noticeNoCycle => 'ಈಗ ಯಾವುದೇ ಸಕ್ರಿಯ ಚಕ್ರ ಇಲ್ಲ.';

  @override
  String get entitlementTitle => 'ನನ್ನ ಅರ್ಹತೆ';

  @override
  String get monthlyEntitlement => 'ಮಾಸಿಕ ಅರ್ಹತೆ';

  @override
  String get alreadyCollected => 'ಈಗಾಗಲೇ ಪಡೆದದ್ದು';

  @override
  String get remainingThisCycle => 'ಈ ಚಕ್ರದಲ್ಲಿ ಉಳಿದಿದೆ';

  @override
  String get schemeLabel => 'ಯೋಜನೆ';

  @override
  String get schemeAAY => 'ಅಂತ್ಯೋದಯ (AAY)';

  @override
  String get schemePHH => 'ಆದ್ಯತಾ ಕುಟುಂಬ (PHH)';

  @override
  String householdMembers(String n) {
    return '$n ಸದಸ್ಯರು';
  }

  @override
  String get householdLabel => 'ಕುಟುಂಬ';

  @override
  String get entitlementExplain =>
      'ನಿಮ್ಮ ಅರ್ಹತೆ ನಿಮ್ಮ ನೋಂದಾಯಿತ ಕುಟುಂಬ ಮತ್ತು ಯೋಜನೆಯ ಮಾಹಿತಿಯ ಮೇಲೆ ಆಧಾರಿತವಾಗಿದೆ.';

  @override
  String get entitlementReadOnly =>
      'ಇದನ್ನು ಸರ್ಕಾರ ನಿಗದಿಪಡಿಸುತ್ತದೆ. ನಿಮ್ಮ ಯೋಜನೆ ಇದನ್ನು ಎಂದಿಗೂ ಬದಲಿಸಲಾಗದು.';

  @override
  String get cycleTitle => 'ಪ್ರಸ್ತುತ ಚಕ್ರ';

  @override
  String get periodLabel => 'ಚಕ್ರದ ಅವಧಿ';

  @override
  String get windowLabel => 'ಆಯ್ಕೆ ಅವಧಿ';

  @override
  String get statusLabel => 'ಸ್ಥಿತಿ';

  @override
  String get whatThisMeans => 'ಇದರ ಅರ್ಥ';

  @override
  String get explainOpen =>
      'ಈ ತಿಂಗಳು ನೀವು ಏನು ಪಡೆಯಲು ಬಯಸುತ್ತೀರಿ ಎಂದು ಯೋಜಿಸಬಹುದು. ಅವಧಿ ಮುಗಿಯುವ ಮೊದಲು ಯೋಜನೆ ಸಲ್ಲಿಸಿ.';

  @override
  String get explainClosedNoPlan =>
      'ಅವಧಿ ಮುಗಿದಿದೆ ಮತ್ತು ನೀವು ಯೋಜನೆ ಸಲ್ಲಿಸಿಲ್ಲ, ಆದ್ದರಿಂದ ಈ ಚಕ್ರದಲ್ಲಿ ನಿಮಗಾಗಿ ಏನೂ ಯೋಜಿಸಲಾಗಿಲ್ಲ.';

  @override
  String get explainPlanRecorded =>
      'ನಿಮ್ಮ ಯೋಜನೆ ದಾಖಲಾಗಿದೆ. ಅದರ ಪ್ರಗತಿಯನ್ನು ನನ್ನ ಪಡಿತರದಲ್ಲಿ ನೋಡಿ.';

  @override
  String get explainInProgress =>
      'ನಿಮ್ಮ ಪಡಿತರ ಪೂರೈಕೆ ಸರಪಳಿಯಲ್ಲಿ ಮುಂದುವರಿಯುತ್ತಿದೆ. ಅದನ್ನು ನನ್ನ ಪಡಿತರದಲ್ಲಿ ನೋಡಿ.';

  @override
  String get planTitle => 'ನನ್ನ ಸಂಗ್ರಹ ಯೋಜಿಸಿ';

  @override
  String get stepSelect => 'ಆರಿಸಿ';

  @override
  String get stepReview => 'ಪರಿಶೀಲಿಸಿ';

  @override
  String get stepSubmit => 'ಸಲ್ಲಿಸಿ';

  @override
  String get chooseFps => 'ನಿಮ್ಮ ಅಂಗಡಿಯನ್ನು ಆರಿಸಿ';

  @override
  String get nearestFirst => 'ನಿಮ್ಮ ಜಿಲ್ಲೆಯಲ್ಲಿ, ಹತ್ತಿರದ್ದು ಮೊದಲು';

  @override
  String distanceKm(String km) {
    return '$km ಕಿಮೀ ದೂರ';
  }

  @override
  String get yourCurrentShop => 'ನಿಮ್ಮ ಪ್ರಸ್ತುತ ಅಂಗಡಿ';

  @override
  String get shopNotActive => 'ಈಗ ಸಕ್ರಿಯವಾಗಿಲ್ಲ';

  @override
  String get chooseQuantity => 'ನೀವು ಎಷ್ಟು ಪಡೆಯಲು ಬಯಸುತ್ತೀರಿ?';

  @override
  String get riceKg => 'ಅಕ್ಕಿ (ಕೆಜಿ)';

  @override
  String get wheatKg => 'ಗೋಧಿ (ಕೆಜಿ)';

  @override
  String upTo(String max) {
    return 'ಗರಿಷ್ಠ $max ಕೆಜಿ';
  }

  @override
  String get collectionMode => 'ಯಾರು ಪಡೆಯುತ್ತಾರೆ?';

  @override
  String get modeSelf => 'ನಾನೇ ಪಡೆಯುತ್ತೇನೆ';

  @override
  String get modeAuthorized => 'ಅಧಿಕೃತ ವ್ಯಕ್ತಿ';

  @override
  String get calcEntitlement => 'ನಿಮ್ಮ ಅರ್ಹತೆ';

  @override
  String get calcCollected => 'ಈಗಾಗಲೇ ಪಡೆದದ್ದು';

  @override
  String get calcRemaining => 'ಉಳಿದಿದೆ';

  @override
  String get calcRequested => 'ನೀವು ಕೇಳುತ್ತಿರುವುದು';

  @override
  String get reviewPlan => 'ಯೋಜನೆ ಪರಿಶೀಲಿಸಿ';

  @override
  String get enterQuantity => 'ಸ್ವಲ್ಪವಾದರೂ ಅಕ್ಕಿ ಅಥವಾ ಗೋಧಿ ಆರಿಸಿ';

  @override
  String increase(String item) {
    return '$item ಹೆಚ್ಚಿಸಿ';
  }

  @override
  String decrease(String item) {
    return '$item ಕಡಿಮೆ ಮಾಡಿ';
  }

  @override
  String selectedShop(String name) {
    return 'ಆರಿಸಿದ ಅಂಗಡಿ $name';
  }

  @override
  String get reviewTitle => 'ನಿಮ್ಮ ಯೋಜನೆ ಪರಿಶೀಲಿಸಿ';

  @override
  String get reviewFps => 'ಅಂಗಡಿ';

  @override
  String get reviewMode => 'ಯಾರು ಪಡೆಯುವರು';

  @override
  String get reviewCycle => 'ಚಕ್ರ';

  @override
  String get reviewRemainingAfter => 'ಈ ಯೋಜನೆಯ ನಂತರ ಉಳಿಯುವ ಅರ್ಹತೆ';

  @override
  String get reviewWarning =>
      'ಸಲ್ಲಿಸುವ ಮೊದಲು ಈ ವಿವರಗಳನ್ನು ದೃಢೀಕರಿಸಿ. ಆಯ್ಕೆ ಅವಧಿ ಮುಗಿದ ನಂತರ ನಿಮ್ಮ ಯೋಜನೆಯನ್ನು ಬದಲಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ.';

  @override
  String get submitIntent => 'ಸಂಗ್ರಹ ಯೋಜನೆ ಸಲ್ಲಿಸಿ';

  @override
  String get submitting => 'ಸಲ್ಲಿಸಲಾಗುತ್ತಿದೆ…';

  @override
  String get intentRecorded => 'ಸಂಗ್ರಹ ಯೋಜನೆ ದಾಖಲಾಗಿದೆ';

  @override
  String get intentCancelled => 'ಯೋಜನೆ ರದ್ದಾಗಿದೆ';

  @override
  String get referenceLabel => 'ಉಲ್ಲೇಖ';

  @override
  String get submittedOn => 'ಸಲ್ಲಿಸಿದ ದಿನಾಂಕ';

  @override
  String get statusRecorded => 'ದಾಖಲಾಗಿದೆ';

  @override
  String get statusCancelled => 'ರದ್ದಾಗಿದೆ';

  @override
  String get cancelPlan => 'ರದ್ದುಮಾಡಿ ಮತ್ತು ಯೋಜನೆ ಬದಲಿಸಿ';

  @override
  String get cancelConfirmTitle => 'ಈ ಯೋಜನೆಯನ್ನು ರದ್ದುಮಾಡುವುದೇ?';

  @override
  String get cancelConfirmBody =>
      'ನಿಮ್ಮ ಯೋಜನೆ ರದ್ದಾಗುತ್ತದೆ ಮತ್ತು ಅವಧಿ ತೆರೆದಿರುವಾಗ ನೀವು ಹೊಸದನ್ನು ಸಲ್ಲಿಸಬಹುದು.';

  @override
  String get keepPlan => 'ಯೋಜನೆ ಉಳಿಸಿ';

  @override
  String get yesCancel => 'ಹೌದು, ರದ್ದುಮಾಡಿ';

  @override
  String get backToHome => 'ಮುಖಪುಟಕ್ಕೆ ಹಿಂತಿರುಗಿ';

  @override
  String get receiptTitle => 'ಯೋಜನೆಯ ರಸೀದಿ';

  @override
  String get trackTitle => 'ನನ್ನ ಪಡಿತರ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ';

  @override
  String journeyOf(String cycle) {
    return 'ಚಕ್ರ $cycle';
  }

  @override
  String get liveTracking => 'ವಾಹನ ಟ್ರ್ಯಾಕಿಂಗ್';

  @override
  String get vehicleLabel => 'ವಾಹನ';

  @override
  String get lastUpdate => 'ಕೊನೆಯ ಅಪ್‌ಡೇಟ್';

  @override
  String get locationLabel => 'ಸ್ಥಳ';

  @override
  String routeStop(String n, String total) {
    return 'ನಿಮ್ಮ ನಿಲ್ದಾಣ $total ರಲ್ಲಿ $n';
  }

  @override
  String plannedEta(String min) {
    return 'ಯೋಜಿತ ಆಗಮನ: ಹೊರಟ ಸುಮಾರು $min ನಿಮಿಷಗಳ ನಂತರ';
  }

  @override
  String get liveLocationUnavailable => 'ಲೈವ್ ಸ್ಥಳ ಲಭ್ಯವಿಲ್ಲ';

  @override
  String get liveLocationUnavailableBody =>
      'ವಾಹನ ಸ್ಥಳವನ್ನು ಹಂಚಿಕೊಂಡಿಲ್ಲ. ಯಾವುದನ್ನೂ ಅಂದಾಜಿಸಿ ಅಥವಾ ಸೃಷ್ಟಿಸಿ ತೋರಿಸಲಾಗುವುದಿಲ್ಲ.';

  @override
  String get detailNoIntent => 'ನೀವು ಈ ಚಕ್ರಕ್ಕೆ ಯೋಜನೆ ಸಲ್ಲಿಸಿಲ್ಲ';

  @override
  String get detailAllocationOnHold => 'ನಿಮ್ಮ ಅಂಗಡಿಯ ಸ್ಟಾಕ್ ತಡೆಹಿಡಿಯಲಾಗಿದೆ';

  @override
  String get detailDeliveryRejected =>
      'ಅಂಗಡಿಯಲ್ಲಿ ಸರಬರಾಜು ತಿರಸ್ಕೃತವಾಗಿದ್ದು ಬಗೆಹರಿಸಲಾಗುತ್ತಿದೆ';

  @override
  String collectedDetail(String rice, String wheat) {
    return 'ಅಕ್ಕಿ $rice ಕೆಜಿ, ಗೋಧಿ $wheat ಕೆಜಿ';
  }

  @override
  String get cycleData => 'ಚಕ್ರ';

  @override
  String get dataNoteInferred => 'ರವಾನೆಯನ್ನು ಸರಬರಾಜು ದಾಖಲೆಯಿಂದ ದೃಢೀಕರಿಸಲಾಗಿದೆ';

  @override
  String get historyTitle => 'ನನ್ನ ಇತಿಹಾಸ';

  @override
  String get tabCollections => 'ಸಂಗ್ರಹಗಳು';

  @override
  String get tabTransactions => 'ವಹಿವಾಟುಗಳು';

  @override
  String get tabIntents => 'ಯೋಜನೆಗಳು';

  @override
  String get noHistory => 'ಯಾವುದೇ ಇತಿಹಾಸ ಲಭ್ಯವಿಲ್ಲ';

  @override
  String get txnSuccess => 'ಯಶಸ್ವಿ';

  @override
  String get txnFailed => 'ವಿಫಲ';

  @override
  String get txnCancelled => 'ರದ್ದು';

  @override
  String get viewReceipt => 'ರಸೀದಿ ನೋಡಿ';

  @override
  String transactionsCount(String n) {
    return '$n ವಹಿವಾಟುಗಳು';
  }

  @override
  String atShop(String shop) {
    return '$shop ನಲ್ಲಿ';
  }

  @override
  String get noReceiptForFailed =>
      'ರಸೀದಿಯನ್ನು ಯಶಸ್ವಿ ಸಂಗ್ರಹಗಳಿಗೆ ಮಾತ್ರ ನೀಡಲಾಗುತ್ತದೆ.';

  @override
  String get digitalReceipt => 'ಡಿಜಿಟಲ್ ರಸೀದಿ';

  @override
  String get beneficiaryLabel => 'ಫಲಾನುಭವಿ';

  @override
  String get transactionId => 'ವಹಿವಾಟು ಐಡಿ';

  @override
  String get receiptNumber => 'ರಸೀದಿ ಸಂಖ್ಯೆ';

  @override
  String get commodityLabel => 'ವಸ್ತು';

  @override
  String get quantityLabel => 'ಪ್ರಮಾಣ';

  @override
  String get dateTimeLabel => 'ದಿನಾಂಕ ಮತ್ತು ಸಮಯ';

  @override
  String get verificationRef => 'ಪರಿಶೀಲನೆ ಕೋಡ್';

  @override
  String get scanToVerify =>
      'ರಸೀದಿಯನ್ನು ಪರಿಶೀಲಿಸಲು ಈ ಕೋಡ್ ಅನ್ನು ಅಂಗಡಿಯಲ್ಲಿ ತೋರಿಸಿ';

  @override
  String get helpTitle => 'ಸಹಾಯ';

  @override
  String get assistantTitle => 'ನನ್ನ ಪಿಡಿಎಸ್ ಸಹಾಯಕ';

  @override
  String get assistantSubtitle =>
      'ನಿಮ್ಮ ಪಡಿತರ, ಅರ್ಹತೆ ಮತ್ತು ಸ್ಥಿತಿಯ ಬಗ್ಗೆ ಕೇಳಿ';

  @override
  String get raiseGrievance => 'ದೂರು ಸಲ್ಲಿಸಿ';

  @override
  String get raiseGrievanceSub => 'ಏನಾದರೂ ತಪ್ಪಾದರೆ ನಮಗೆ ತಿಳಿಸಿ';

  @override
  String get myGrievances => 'ನನ್ನ ದೂರುಗಳು';

  @override
  String get signOut => 'ಸೈನ್ ಔಟ್';

  @override
  String get signOutConfirm => 'DemandSYNC ನಿಂದ ಸೈನ್ ಔಟ್ ಮಾಡುವುದೇ?';

  @override
  String get helpFooter =>
      'ತುರ್ತು ಸಹಾಯಕ್ಕಾಗಿ ನಿಮ್ಮ ಜಿಲ್ಲಾ ಆಹಾರ ಕಚೇರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.';

  @override
  String get assistantHello =>
      'ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಸ್ವಂತ ಪಡಿತರ ದಾಖಲೆಗಳನ್ನು ವಿವರಿಸಬಲ್ಲೆ. ನೀವು ಏನು ತಿಳಿಯಲು ಬಯಸುತ್ತೀರಿ?';

  @override
  String get askPlaceholder => 'ಪ್ರಶ್ನೆ ಕೇಳಿ';

  @override
  String get send => 'ಕಳುಹಿಸಿ';

  @override
  String sourceLabel(String source) {
    return 'ಮೂಲ: $source';
  }

  @override
  String get viewRelated => 'ವಿವರ ನೋಡಿ';

  @override
  String get assistantNote =>
      'ಉತ್ತರಗಳು ನಿಮ್ಮ ಸ್ವಂತ ದಾಖಲೆಗಳಿಂದ ಬರುತ್ತವೆ. ಈ ಸಹಾಯಕ ಯಾವುದನ್ನೂ ಬದಲಿಸಲಾರದು.';

  @override
  String get chipEntitlement => 'ನಾನು ಎಷ್ಟು ಪಡೆಯಬಹುದು?';

  @override
  String get chipWindow => 'ನನ್ನ ಸಂಗ್ರಹ ಅವಧಿ ಯಾವಾಗ?';

  @override
  String get chipRequest => 'ನಾನು ಏನು ಕೇಳಿದ್ದೆ?';

  @override
  String get chipDispatch => 'ನನ್ನ ಪಡಿತರ ಎಲ್ಲಿದೆ?';

  @override
  String get chipFps => 'ನನ್ನ ಅಂಗಡಿ ಯಾವುದು?';

  @override
  String get chipCantSubmit => 'ನನಗೆ ಯೋಜನೆ ಸಲ್ಲಿಸಲು ಏಕೆ ಆಗುತ್ತಿಲ್ಲ?';

  @override
  String get assistantThinking => 'ನಿಮ್ಮ ದಾಖಲೆಗಳನ್ನು ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ…';

  @override
  String get grievanceTitle => 'ದೂರು ಸಲ್ಲಿಸಿ';

  @override
  String get chooseIssue => 'ಏನು ತಪ್ಪಾಯಿತು?';

  @override
  String get catShortDelivery => 'ಕಡಿಮೆ ಪ್ರಮಾಣ ಸಿಕ್ಕಿದೆ';

  @override
  String get catWrongQuantity => 'ತಪ್ಪು ಪ್ರಮಾಣ';

  @override
  String get catFpsIssue => 'ಅಂಗಡಿಯ ಸಮಸ್ಯೆ';

  @override
  String get catQuality => 'ಗುಣಮಟ್ಟದ ಸಮಸ್ಯೆ';

  @override
  String get catTransaction => 'ವಹಿವಾಟಿನ ಸಮಸ್ಯೆ';

  @override
  String get catEntitlement => 'ಅರ್ಹತೆಯ ಪ್ರಶ್ನೆ';

  @override
  String get catCollection => 'ಪಡೆಯುವಲ್ಲಿ ಸಮಸ್ಯೆ';

  @override
  String get catOther => 'ಇತರೆ';

  @override
  String get describeIssue => 'ಸಮಸ್ಯೆಯನ್ನು ವಿವರಿಸಿ';

  @override
  String get describeHint => 'ಏನಾಯಿತು ಎಂದು ಬರೆಯಿರಿ (ಕನಿಷ್ಠ 10 ಅಕ್ಷರಗಳು)';

  @override
  String charCount(String n) {
    return '$n / 500';
  }

  @override
  String get aiSuggest => 'ವರ್ಗವನ್ನು ಸೂಚಿಸಿ';

  @override
  String aiSuggestion(String category) {
    return 'ಸೂಚನೆ: $category';
  }

  @override
  String get aiSuggestNote =>
      'ಇದು ಕೇವಲ ಸೂಚನೆ. ಸಲ್ಲಿಸುವ ಮೊದಲು ನೀವೇ ಆರಿಸುತ್ತೀರಿ.';

  @override
  String get useSuggestion => 'ಇದನ್ನು ಬಳಸಿ';

  @override
  String get aboutTransaction => 'ಯಾವುದಾದರೂ ಸಂಗ್ರಹದ ಬಗ್ಗೆಯೇ?';

  @override
  String get noTransactionLink => 'ನಿರ್ದಿಷ್ಟ ಸಂಗ್ರಹದ ಬಗ್ಗೆ ಅಲ್ಲ';

  @override
  String get submitGrievance => 'ದೂರು ಸಲ್ಲಿಸಿ';

  @override
  String get grievanceSubmitted => 'ದೂರು ಸಲ್ಲಿಸಲಾಗಿದೆ';

  @override
  String get grievanceSubmittedBody =>
      'ನಿಮ್ಮ ದೂರು ದಾಖಲಾಗಿದೆ. ಅದರ ಸ್ಥಿತಿಯನ್ನು ನನ್ನ ದೂರುಗಳಲ್ಲಿ ನೋಡಿ.';

  @override
  String get grStatusOpen => 'ತೆರೆದಿದೆ';

  @override
  String get grStatusInReview => 'ಪರಿಶೀಲನೆಯಲ್ಲಿದೆ';

  @override
  String get grStatusResolved => 'ಪರಿಹರಿಸಲಾಗಿದೆ';

  @override
  String get grStatusClosed => 'ಮುಚ್ಚಲಾಗಿದೆ';

  @override
  String get noGrievances => 'ನೀವು ಯಾವುದೇ ದೂರು ಸಲ್ಲಿಸಿಲ್ಲ';

  @override
  String get resolutionLabel => 'ಪರಿಹಾರ';

  @override
  String get errOffline =>
      'ಪಿಡಿಎಸ್ ಸೇವೆಗಳೊಂದಿಗೆ ಸಂಪರ್ಕಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.';

  @override
  String get errTimeout =>
      'ಸರ್ವರ್ ಪ್ರತಿಕ್ರಿಯಿಸಲು ಬಹಳ ಸಮಯ ತೆಗೆದುಕೊಳ್ಳುತ್ತಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.';

  @override
  String get errServer =>
      'ನಮ್ಮ ಕಡೆಯಿಂದ ಏನೋ ತಪ್ಪಾಗಿದೆ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.';

  @override
  String get errSession =>
      'ನಿಮ್ಮ ಸೆಷನ್ ಮುಗಿದಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಸೈನ್ ಇನ್ ಮಾಡಿ.';

  @override
  String get errGeneric => 'ಏನೋ ತಪ್ಪಾಗಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.';

  @override
  String get errIntentDuplicate =>
      'ಈ ಚಕ್ರಕ್ಕೆ ನಿಮ್ಮ ಸಂಗ್ರಹ ಆದ್ಯತೆಯನ್ನು ಈಗಾಗಲೇ ಸಲ್ಲಿಸಲಾಗಿದೆ.';

  @override
  String get errWindowClosed => 'ಈ ಚಕ್ರದ ಆಯ್ಕೆ ಅವಧಿ ಮುಗಿದಿದೆ.';

  @override
  String get errExceedsRemaining => 'ಇದು ನಿಮ್ಮ ಉಳಿದ ಅರ್ಹತೆಗಿಂತ ಹೆಚ್ಚು.';

  @override
  String get errInvalidQuantity => 'ಸೊನ್ನೆಗಿಂತ ಹೆಚ್ಚಿನ ಪ್ರಮಾಣ ನಮೂದಿಸಿ.';

  @override
  String get errFpsNotEligible =>
      'ನೀವು ನಿಮ್ಮ ಸ್ವಂತ ಜಿಲ್ಲೆಯ ಸಕ್ರಿಯ ಅಂಗಡಿಯನ್ನು ಮಾತ್ರ ಆರಿಸಬಹುದು.';

  @override
  String get errNoCycle => 'ಈಗ ಯಾವುದೇ ಸಕ್ರಿಯ ಚಕ್ರ ಇಲ್ಲ.';

  @override
  String get errTooMany =>
      'ಹೆಚ್ಚು ಪ್ರಯತ್ನಗಳು. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಕಾಯಿರಿ ಮತ್ತು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.';

  @override
  String get errBadCredentials =>
      'ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಪಡಿತರ ಚೀಟಿ ಮತ್ತು ಮೊಬೈಲ್ ಸಂಖ್ಯೆಯನ್ನು ಪರಿಶೀಲಿಸಿ.';

  @override
  String get errAccountDisabled =>
      'ಈ ಖಾತೆ ನಿಷ್ಕ್ರಿಯವಾಗಿದೆ. ದಯವಿಟ್ಟು ಆಹಾರ ಕಚೇರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.';

  @override
  String get errOtpUnavailable =>
      'OTP ಕಳುಹಿಸುವ ಸೌಲಭ್ಯ ಈಗ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ನಂತರ ಪ್ರಯತ್ನಿಸಿ.';

  @override
  String get errNotFound => 'ಆ ದಾಖಲೆ ಸಿಗಲಿಲ್ಲ.';

  @override
  String errOtpInvalid(String left) {
    return 'ತಪ್ಪು OTP. $left ಪ್ರಯತ್ನಗಳು ಉಳಿದಿವೆ.';
  }

  @override
  String get errOtpInvalidLast => 'ತಪ್ಪು OTP. ದಯವಿಟ್ಟು ಹೊಸದನ್ನು ವಿನಂತಿಸಿ.';

  @override
  String get errOtpExpired =>
      'ಈ OTP ಅವಧಿ ಮುಗಿದಿದೆ. ದಯವಿಟ್ಟು ಹೊಸದನ್ನು ವಿನಂತಿಸಿ.';

  @override
  String get errOtpUsed =>
      'ಈ OTP ಅನ್ನು ಈಗಾಗಲೇ ಬಳಸಲಾಗಿದೆ. ದಯವಿಟ್ಟು ಹೊಸದನ್ನು ವಿನಂತಿಸಿ.';

  @override
  String get errOtpTooMany =>
      'ತುಂಬಾ ತಪ್ಪು ಪ್ರಯತ್ನಗಳು. ದಯವಿಟ್ಟು ಹೊಸ OTP ವಿನಂತಿಸಿ.';

  @override
  String get errOtpNotRequested => 'ದಯವಿಟ್ಟು ಮೊದಲು OTP ವಿನಂತಿಸಿ.';

  @override
  String errCooldown(String seconds) {
    return 'ಇನ್ನೊಂದು OTP ಕೇಳುವ ಮೊದಲು ದಯವಿಟ್ಟು $seconds ಸೆಕೆಂಡ್ ಕಾಯಿರಿ.';
  }

  @override
  String get sessionExpiredBanner =>
      'ನಿಮ್ಮ ಸೆಷನ್ ಮುಗಿದಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಸೈನ್ ಇನ್ ಮಾಡಿ.';
}

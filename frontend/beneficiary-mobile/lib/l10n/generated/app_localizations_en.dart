// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'DemandSYNC';

  @override
  String get appTagline => 'Your Ration. Your Rights. Our Priority.';

  @override
  String get welcomeBody =>
      'A simple, secure and transparent way to plan, track and receive your ration.';

  @override
  String get getStarted => 'Get started';

  @override
  String get language => 'Language';

  @override
  String get cancel => 'Cancel';

  @override
  String get confirm => 'Confirm';

  @override
  String get retry => 'Try again';

  @override
  String get back => 'Back';

  @override
  String get close => 'Close';

  @override
  String get done => 'Done';

  @override
  String get continueBtn => 'Continue';

  @override
  String kgValue(String value) {
    return '$value kg';
  }

  @override
  String get dataUnavailable => 'Data unavailable';

  @override
  String get loading => 'Loading…';

  @override
  String get loginTitle => 'Welcome back';

  @override
  String get loginSubtitle => 'Sign in to see your ration details';

  @override
  String get rationCardLabel => 'Ration card number';

  @override
  String get mobileLabel => 'Registered mobile number';

  @override
  String get sendOtp => 'Send OTP';

  @override
  String get otpTitle => 'Enter the OTP';

  @override
  String otpSentTo(String mobile) {
    return 'We sent a 6-digit code to $mobile';
  }

  @override
  String get otpLabel => '6-digit OTP';

  @override
  String get verifyContinue => 'Verify and continue';

  @override
  String get resendOtp => 'Resend OTP';

  @override
  String resendIn(String seconds) {
    return 'Resend OTP in ${seconds}s';
  }

  @override
  String devModeBanner(String otp) {
    return 'Development mode: no SMS is sent. Your code is $otp.';
  }

  @override
  String get useThisCode => 'Use this code';

  @override
  String get changeNumber => 'Change details';

  @override
  String get fieldRequired => 'This field is required';

  @override
  String get otpInvalidLength => 'Enter all 6 digits';

  @override
  String get loginHelp =>
      'Use the ration card number and mobile number registered with your household.';

  @override
  String get navHome => 'Home';

  @override
  String get navMyRation => 'My Ration';

  @override
  String get navHistory => 'History';

  @override
  String get navHelp => 'Help';

  @override
  String get goodMorning => 'Good morning';

  @override
  String get goodAfternoon => 'Good afternoon';

  @override
  String get goodEvening => 'Good evening';

  @override
  String get myPds => 'My PDS';

  @override
  String get currentCycle => 'Current cycle';

  @override
  String collectionWindow(String start, String end) {
    return 'Choice window: $start to $end';
  }

  @override
  String get myEntitlement => 'My entitlement';

  @override
  String get rice => 'Rice';

  @override
  String get wheat => 'Wheat';

  @override
  String get total => 'Total';

  @override
  String get remaining => 'Remaining';

  @override
  String get collected => 'Collected';

  @override
  String get currentFps => 'My fair price shop';

  @override
  String fpsIdLabel(String id) {
    return 'Shop ID: $id';
  }

  @override
  String openingHours(String hours) {
    return 'Open $hours';
  }

  @override
  String get planMyCollection => 'Plan my collection';

  @override
  String get viewMyPlan => 'View my plan';

  @override
  String get trackMyRation => 'Track my ration';

  @override
  String get viewEntitlement => 'View entitlement';

  @override
  String get viewCycle => 'About this cycle';

  @override
  String rationCardShort(String id) {
    return 'Ration card $id';
  }

  @override
  String get signedInAs => 'Signed in';

  @override
  String get stChoiceWindowOpen => 'Choice window open';

  @override
  String get stChoiceWindowClosed => 'Choice window closed';

  @override
  String get stIntentSubmitted => 'Intent submitted';

  @override
  String get stDemandPlanned => 'Demand planned';

  @override
  String get stAllocated => 'Allocated';

  @override
  String get stDispatched => 'Dispatched';

  @override
  String get stInTransit => 'In transit';

  @override
  String get stReceivedAtFps => 'Received at shop';

  @override
  String get stAvailableForCollection => 'Available for collection';

  @override
  String get stCollected => 'Collected';

  @override
  String get stateDone => 'Done';

  @override
  String get stateActive => 'In progress';

  @override
  String get statePending => 'Not yet';

  @override
  String get stateDelayed => 'On hold';

  @override
  String get stateUnavailable => 'Not available';

  @override
  String get notYetAvailable => 'Not yet available';

  @override
  String noticePlanNow(String closes) {
    return 'The choice window closes on $closes. Plan your collection now.';
  }

  @override
  String noticeIntentRecorded(String ref) {
    return 'Your plan $ref is recorded.';
  }

  @override
  String get noticeRationAtFps =>
      'Your ration has reached your shop. You can collect it.';

  @override
  String get noticeWindowClosedNoIntent =>
      'The choice window is closed and no plan was submitted for this cycle.';

  @override
  String noticeFpsNotActive(String fps) {
    return 'Your shop $fps is not active right now. Choose another shop when you plan.';
  }

  @override
  String get noticeNoCycle => 'There is no active cycle right now.';

  @override
  String get entitlementTitle => 'My entitlement';

  @override
  String get monthlyEntitlement => 'Monthly entitlement';

  @override
  String get alreadyCollected => 'Already collected';

  @override
  String get remainingThisCycle => 'Remaining this cycle';

  @override
  String get schemeLabel => 'Scheme';

  @override
  String get schemeAAY => 'Antyodaya (AAY)';

  @override
  String get schemePHH => 'Priority household (PHH)';

  @override
  String householdMembers(String n) {
    return '$n members';
  }

  @override
  String get householdLabel => 'Household';

  @override
  String get entitlementExplain =>
      'Your entitlement is based on your registered household and scheme information.';

  @override
  String get entitlementReadOnly =>
      'It is set by the government. Your plan can never change it.';

  @override
  String get cycleTitle => 'Current cycle';

  @override
  String get periodLabel => 'Cycle period';

  @override
  String get windowLabel => 'Choice window';

  @override
  String get statusLabel => 'Status';

  @override
  String get whatThisMeans => 'What this means';

  @override
  String get explainOpen =>
      'You can plan what you want to collect this month. Submit your plan before the window closes.';

  @override
  String get explainClosedNoPlan =>
      'The window is closed and you did not submit a plan, so nothing was planned for you this cycle.';

  @override
  String get explainPlanRecorded =>
      'Your plan is recorded. Follow its progress under My Ration.';

  @override
  String get explainInProgress =>
      'Your ration is moving through the supply chain. Follow it under My Ration.';

  @override
  String get planTitle => 'Plan my collection';

  @override
  String get stepSelect => 'Select';

  @override
  String get stepReview => 'Review';

  @override
  String get stepSubmit => 'Submit';

  @override
  String get chooseFps => 'Choose your shop';

  @override
  String get nearestFirst => 'Nearest first, in your district';

  @override
  String distanceKm(String km) {
    return '$km km away';
  }

  @override
  String get yourCurrentShop => 'Your current shop';

  @override
  String get shopNotActive => 'Not active right now';

  @override
  String get chooseQuantity => 'How much do you want to collect?';

  @override
  String get riceKg => 'Rice (kg)';

  @override
  String get wheatKg => 'Wheat (kg)';

  @override
  String upTo(String max) {
    return 'Up to $max kg';
  }

  @override
  String get collectionMode => 'Who will collect?';

  @override
  String get modeSelf => 'I will collect';

  @override
  String get modeAuthorized => 'Authorized person';

  @override
  String get calcEntitlement => 'Your entitlement';

  @override
  String get calcCollected => 'Already collected';

  @override
  String get calcRemaining => 'Remaining';

  @override
  String get calcRequested => 'You are requesting';

  @override
  String get reviewPlan => 'Review plan';

  @override
  String get enterQuantity => 'Choose at least some rice or wheat';

  @override
  String increase(String item) {
    return 'Increase $item';
  }

  @override
  String decrease(String item) {
    return 'Decrease $item';
  }

  @override
  String selectedShop(String name) {
    return 'Selected shop $name';
  }

  @override
  String get reviewTitle => 'Review your plan';

  @override
  String get reviewFps => 'Shop';

  @override
  String get reviewMode => 'Collected by';

  @override
  String get reviewCycle => 'Cycle';

  @override
  String get reviewRemainingAfter => 'Entitlement left after this plan';

  @override
  String get reviewWarning =>
      'Please confirm these details before submitting. You cannot change your plan after the choice window closes.';

  @override
  String get submitIntent => 'Submit collection intent';

  @override
  String get submitting => 'Submitting…';

  @override
  String get intentRecorded => 'Collection intent recorded';

  @override
  String get intentCancelled => 'Plan cancelled';

  @override
  String get referenceLabel => 'Reference';

  @override
  String get submittedOn => 'Submitted on';

  @override
  String get statusRecorded => 'Recorded';

  @override
  String get statusCancelled => 'Cancelled';

  @override
  String get cancelPlan => 'Cancel and change my plan';

  @override
  String get cancelConfirmTitle => 'Cancel this plan?';

  @override
  String get cancelConfirmBody =>
      'Your plan will be cancelled and you can submit a new one while the window is open.';

  @override
  String get keepPlan => 'Keep my plan';

  @override
  String get yesCancel => 'Yes, cancel it';

  @override
  String get backToHome => 'Back to home';

  @override
  String get receiptTitle => 'Intent receipt';

  @override
  String get trackTitle => 'Track my ration';

  @override
  String journeyOf(String cycle) {
    return 'Cycle $cycle';
  }

  @override
  String get liveTracking => 'Vehicle tracking';

  @override
  String get vehicleLabel => 'Vehicle';

  @override
  String get lastUpdate => 'Last update';

  @override
  String get locationLabel => 'Location';

  @override
  String routeStop(String n, String total) {
    return 'Your stop is $n of $total';
  }

  @override
  String plannedEta(String min) {
    return 'Planned arrival: about $min min after departure';
  }

  @override
  String get liveLocationUnavailable => 'LIVE LOCATION UNAVAILABLE';

  @override
  String get liveLocationUnavailableBody =>
      'The vehicle has not shared a location. Nothing is estimated or made up.';

  @override
  String get detailNoIntent => 'You did not submit a plan for this cycle';

  @override
  String get detailAllocationOnHold => 'Stock for your shop is on hold';

  @override
  String get detailDeliveryRejected =>
      'The delivery was rejected at the shop and is being resolved';

  @override
  String collectedDetail(String rice, String wheat) {
    return 'Rice $rice kg, wheat $wheat kg';
  }

  @override
  String get cycleData => 'Cycle';

  @override
  String get dataNoteInferred => 'Dispatch is confirmed by the delivery record';

  @override
  String get historyTitle => 'My history';

  @override
  String get tabCollections => 'Collections';

  @override
  String get tabTransactions => 'Transactions';

  @override
  String get tabIntents => 'Intents';

  @override
  String get noHistory => 'NO HISTORY AVAILABLE';

  @override
  String get txnSuccess => 'Successful';

  @override
  String get txnFailed => 'Failed';

  @override
  String get txnCancelled => 'Cancelled';

  @override
  String get viewReceipt => 'View receipt';

  @override
  String transactionsCount(String n) {
    return '$n transactions';
  }

  @override
  String atShop(String shop) {
    return 'at $shop';
  }

  @override
  String get noReceiptForFailed =>
      'A receipt is only issued for successful collections.';

  @override
  String get digitalReceipt => 'Digital receipt';

  @override
  String get beneficiaryLabel => 'Beneficiary';

  @override
  String get transactionId => 'Transaction ID';

  @override
  String get receiptNumber => 'Receipt number';

  @override
  String get commodityLabel => 'Commodity';

  @override
  String get quantityLabel => 'Quantity';

  @override
  String get dateTimeLabel => 'Date and time';

  @override
  String get verificationRef => 'Verification code';

  @override
  String get scanToVerify => 'Show this code at the shop to verify the receipt';

  @override
  String get helpTitle => 'Help';

  @override
  String get assistantTitle => 'My PDS Assistant';

  @override
  String get assistantSubtitle =>
      'Ask about your ration, entitlement and status';

  @override
  String get raiseGrievance => 'Raise a grievance';

  @override
  String get raiseGrievanceSub => 'Tell us if something went wrong';

  @override
  String get myGrievances => 'My grievances';

  @override
  String get signOut => 'Sign out';

  @override
  String get signOutConfirm => 'Sign out of DemandSYNC?';

  @override
  String get helpFooter =>
      'For urgent help, contact your district food office.';

  @override
  String get assistantHello =>
      'Hello! I can explain your own ration records. What would you like to know?';

  @override
  String get askPlaceholder => 'Ask a question';

  @override
  String get send => 'Send';

  @override
  String sourceLabel(String source) {
    return 'Source: $source';
  }

  @override
  String get viewRelated => 'View details';

  @override
  String get assistantNote =>
      'Answers come from your own records. This assistant cannot change anything.';

  @override
  String get chipEntitlement => 'How much can I collect?';

  @override
  String get chipWindow => 'When is my collection window?';

  @override
  String get chipRequest => 'What did I request?';

  @override
  String get chipDispatch => 'Where is my ration?';

  @override
  String get chipFps => 'Which shop am I assigned to?';

  @override
  String get chipCantSubmit => 'Why can\'t I submit my plan?';

  @override
  String get assistantThinking => 'Checking your records…';

  @override
  String get grievanceTitle => 'Raise a grievance';

  @override
  String get chooseIssue => 'What went wrong?';

  @override
  String get catShortDelivery => 'Short delivery';

  @override
  String get catWrongQuantity => 'Wrong quantity';

  @override
  String get catFpsIssue => 'Shop issue';

  @override
  String get catQuality => 'Quality issue';

  @override
  String get catTransaction => 'Transaction issue';

  @override
  String get catEntitlement => 'Entitlement question';

  @override
  String get catCollection => 'Collection issue';

  @override
  String get catOther => 'Other';

  @override
  String get describeIssue => 'Describe the issue';

  @override
  String get describeHint => 'Write what happened (at least 10 characters)';

  @override
  String charCount(String n) {
    return '$n / 500';
  }

  @override
  String get aiSuggest => 'Suggest a category';

  @override
  String aiSuggestion(String category) {
    return 'Suggested: $category';
  }

  @override
  String get aiSuggestNote =>
      'This is only a suggestion. You choose before submitting.';

  @override
  String get useSuggestion => 'Use this';

  @override
  String get aboutTransaction => 'About a collection?';

  @override
  String get noTransactionLink => 'Not about a specific collection';

  @override
  String get submitGrievance => 'Submit grievance';

  @override
  String get grievanceSubmitted => 'Grievance submitted';

  @override
  String get grievanceSubmittedBody =>
      'Your grievance has been recorded. You can follow its status under My grievances.';

  @override
  String get grStatusOpen => 'Open';

  @override
  String get grStatusInReview => 'In review';

  @override
  String get grStatusResolved => 'Resolved';

  @override
  String get grStatusClosed => 'Closed';

  @override
  String get noGrievances => 'You have not raised any grievance';

  @override
  String get resolutionLabel => 'Resolution';

  @override
  String get errOffline =>
      'Unable to connect to PDS services. Please try again.';

  @override
  String get errTimeout =>
      'The server is taking too long to respond. Please try again.';

  @override
  String get errServer =>
      'Something went wrong on our side. Please try again in a moment.';

  @override
  String get errSession => 'Your session has expired. Please sign in again.';

  @override
  String get errGeneric => 'Something went wrong. Please try again.';

  @override
  String get errIntentDuplicate =>
      'Your collection preference has already been submitted for this cycle.';

  @override
  String get errWindowClosed => 'The choice window for this cycle is closed.';

  @override
  String get errExceedsRemaining =>
      'That is more than your remaining entitlement.';

  @override
  String get errInvalidQuantity => 'Enter a quantity above zero.';

  @override
  String get errFpsNotEligible =>
      'You can only choose an active shop in your own district.';

  @override
  String get errNoCycle => 'There is no active cycle right now.';

  @override
  String get errTooMany =>
      'Too many attempts. Please wait a moment and try again.';

  @override
  String get errBadCredentials =>
      'The details could not be verified. Please check your ration card and mobile number.';

  @override
  String get errAccountDisabled =>
      'This account is disabled. Please contact the food office.';

  @override
  String get errOtpUnavailable =>
      'OTP delivery is not available right now. Please try again later.';

  @override
  String get errNotFound => 'We could not find that record.';

  @override
  String errOtpInvalid(String left) {
    return 'Wrong OTP. $left tries left.';
  }

  @override
  String get errOtpInvalidLast => 'Wrong OTP. Please request a new one.';

  @override
  String get errOtpExpired => 'This OTP has expired. Please request a new one.';

  @override
  String get errOtpUsed =>
      'This OTP was already used. Please request a new one.';

  @override
  String get errOtpTooMany => 'Too many wrong tries. Please request a new OTP.';

  @override
  String get errOtpNotRequested => 'Please request an OTP first.';

  @override
  String errCooldown(String seconds) {
    return 'Please wait ${seconds}s before asking for another OTP.';
  }

  @override
  String get sessionExpiredBanner =>
      'Your session expired. Please sign in again.';
}

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_hi.dart';
import 'app_localizations_kn.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('hi'),
    Locale('kn')
  ];

  /// No description provided for @appName.
  ///
  /// In en, this message translates to:
  /// **'DemandSYNC'**
  String get appName;

  /// No description provided for @appTagline.
  ///
  /// In en, this message translates to:
  /// **'Your Ration. Your Rights. Our Priority.'**
  String get appTagline;

  /// No description provided for @welcomeBody.
  ///
  /// In en, this message translates to:
  /// **'A simple, secure and transparent way to plan, track and receive your ration.'**
  String get welcomeBody;

  /// No description provided for @getStarted.
  ///
  /// In en, this message translates to:
  /// **'Get started'**
  String get getStarted;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @confirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get retry;

  /// No description provided for @back.
  ///
  /// In en, this message translates to:
  /// **'Back'**
  String get back;

  /// No description provided for @close.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get close;

  /// No description provided for @done.
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get done;

  /// No description provided for @continueBtn.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get continueBtn;

  /// No description provided for @kgValue.
  ///
  /// In en, this message translates to:
  /// **'{value} kg'**
  String kgValue(String value);

  /// No description provided for @dataUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Data unavailable'**
  String get dataUnavailable;

  /// No description provided for @loading.
  ///
  /// In en, this message translates to:
  /// **'Loading…'**
  String get loading;

  /// No description provided for @loginTitle.
  ///
  /// In en, this message translates to:
  /// **'Welcome back'**
  String get loginTitle;

  /// No description provided for @loginSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in to see your ration details'**
  String get loginSubtitle;

  /// No description provided for @rationCardLabel.
  ///
  /// In en, this message translates to:
  /// **'Ration card number'**
  String get rationCardLabel;

  /// No description provided for @mobileLabel.
  ///
  /// In en, this message translates to:
  /// **'Registered mobile number'**
  String get mobileLabel;

  /// No description provided for @sendOtp.
  ///
  /// In en, this message translates to:
  /// **'Send OTP'**
  String get sendOtp;

  /// No description provided for @otpTitle.
  ///
  /// In en, this message translates to:
  /// **'Enter the OTP'**
  String get otpTitle;

  /// No description provided for @otpSentTo.
  ///
  /// In en, this message translates to:
  /// **'We sent a 6-digit code to {mobile}'**
  String otpSentTo(String mobile);

  /// No description provided for @otpLabel.
  ///
  /// In en, this message translates to:
  /// **'6-digit OTP'**
  String get otpLabel;

  /// No description provided for @verifyContinue.
  ///
  /// In en, this message translates to:
  /// **'Verify and continue'**
  String get verifyContinue;

  /// No description provided for @resendOtp.
  ///
  /// In en, this message translates to:
  /// **'Resend OTP'**
  String get resendOtp;

  /// No description provided for @resendIn.
  ///
  /// In en, this message translates to:
  /// **'Resend OTP in {seconds}s'**
  String resendIn(String seconds);

  /// No description provided for @devModeBanner.
  ///
  /// In en, this message translates to:
  /// **'Development mode: no SMS is sent. Your code is {otp}.'**
  String devModeBanner(String otp);

  /// No description provided for @useThisCode.
  ///
  /// In en, this message translates to:
  /// **'Use this code'**
  String get useThisCode;

  /// No description provided for @changeNumber.
  ///
  /// In en, this message translates to:
  /// **'Change details'**
  String get changeNumber;

  /// No description provided for @fieldRequired.
  ///
  /// In en, this message translates to:
  /// **'This field is required'**
  String get fieldRequired;

  /// No description provided for @otpInvalidLength.
  ///
  /// In en, this message translates to:
  /// **'Enter all 6 digits'**
  String get otpInvalidLength;

  /// No description provided for @loginHelp.
  ///
  /// In en, this message translates to:
  /// **'Use the ration card number and mobile number registered with your household.'**
  String get loginHelp;

  /// No description provided for @navHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get navHome;

  /// No description provided for @navMyRation.
  ///
  /// In en, this message translates to:
  /// **'My Ration'**
  String get navMyRation;

  /// No description provided for @navHistory.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get navHistory;

  /// No description provided for @navHelp.
  ///
  /// In en, this message translates to:
  /// **'Help'**
  String get navHelp;

  /// No description provided for @goodMorning.
  ///
  /// In en, this message translates to:
  /// **'Good morning'**
  String get goodMorning;

  /// No description provided for @goodAfternoon.
  ///
  /// In en, this message translates to:
  /// **'Good afternoon'**
  String get goodAfternoon;

  /// No description provided for @goodEvening.
  ///
  /// In en, this message translates to:
  /// **'Good evening'**
  String get goodEvening;

  /// No description provided for @myPds.
  ///
  /// In en, this message translates to:
  /// **'My PDS'**
  String get myPds;

  /// No description provided for @currentCycle.
  ///
  /// In en, this message translates to:
  /// **'Current cycle'**
  String get currentCycle;

  /// No description provided for @collectionWindow.
  ///
  /// In en, this message translates to:
  /// **'Choice window: {start} to {end}'**
  String collectionWindow(String start, String end);

  /// No description provided for @myEntitlement.
  ///
  /// In en, this message translates to:
  /// **'My entitlement'**
  String get myEntitlement;

  /// No description provided for @rice.
  ///
  /// In en, this message translates to:
  /// **'Rice'**
  String get rice;

  /// No description provided for @wheat.
  ///
  /// In en, this message translates to:
  /// **'Wheat'**
  String get wheat;

  /// No description provided for @total.
  ///
  /// In en, this message translates to:
  /// **'Total'**
  String get total;

  /// No description provided for @remaining.
  ///
  /// In en, this message translates to:
  /// **'Remaining'**
  String get remaining;

  /// No description provided for @collected.
  ///
  /// In en, this message translates to:
  /// **'Collected'**
  String get collected;

  /// No description provided for @currentFps.
  ///
  /// In en, this message translates to:
  /// **'My fair price shop'**
  String get currentFps;

  /// No description provided for @fpsIdLabel.
  ///
  /// In en, this message translates to:
  /// **'Shop ID: {id}'**
  String fpsIdLabel(String id);

  /// No description provided for @openingHours.
  ///
  /// In en, this message translates to:
  /// **'Open {hours}'**
  String openingHours(String hours);

  /// No description provided for @planMyCollection.
  ///
  /// In en, this message translates to:
  /// **'Plan my collection'**
  String get planMyCollection;

  /// No description provided for @viewMyPlan.
  ///
  /// In en, this message translates to:
  /// **'View my plan'**
  String get viewMyPlan;

  /// No description provided for @trackMyRation.
  ///
  /// In en, this message translates to:
  /// **'Track my ration'**
  String get trackMyRation;

  /// No description provided for @viewEntitlement.
  ///
  /// In en, this message translates to:
  /// **'View entitlement'**
  String get viewEntitlement;

  /// No description provided for @viewCycle.
  ///
  /// In en, this message translates to:
  /// **'About this cycle'**
  String get viewCycle;

  /// No description provided for @rationCardShort.
  ///
  /// In en, this message translates to:
  /// **'Ration card {id}'**
  String rationCardShort(String id);

  /// No description provided for @signedInAs.
  ///
  /// In en, this message translates to:
  /// **'Signed in'**
  String get signedInAs;

  /// No description provided for @stChoiceWindowOpen.
  ///
  /// In en, this message translates to:
  /// **'Choice window open'**
  String get stChoiceWindowOpen;

  /// No description provided for @stChoiceWindowClosed.
  ///
  /// In en, this message translates to:
  /// **'Choice window closed'**
  String get stChoiceWindowClosed;

  /// No description provided for @stIntentSubmitted.
  ///
  /// In en, this message translates to:
  /// **'Intent submitted'**
  String get stIntentSubmitted;

  /// No description provided for @stDemandPlanned.
  ///
  /// In en, this message translates to:
  /// **'Demand planned'**
  String get stDemandPlanned;

  /// No description provided for @stAllocated.
  ///
  /// In en, this message translates to:
  /// **'Allocated'**
  String get stAllocated;

  /// No description provided for @stDispatched.
  ///
  /// In en, this message translates to:
  /// **'Dispatched'**
  String get stDispatched;

  /// No description provided for @stInTransit.
  ///
  /// In en, this message translates to:
  /// **'In transit'**
  String get stInTransit;

  /// No description provided for @stReceivedAtFps.
  ///
  /// In en, this message translates to:
  /// **'Received at shop'**
  String get stReceivedAtFps;

  /// No description provided for @stAvailableForCollection.
  ///
  /// In en, this message translates to:
  /// **'Available for collection'**
  String get stAvailableForCollection;

  /// No description provided for @stCollected.
  ///
  /// In en, this message translates to:
  /// **'Collected'**
  String get stCollected;

  /// No description provided for @stateDone.
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get stateDone;

  /// No description provided for @stateActive.
  ///
  /// In en, this message translates to:
  /// **'In progress'**
  String get stateActive;

  /// No description provided for @statePending.
  ///
  /// In en, this message translates to:
  /// **'Not yet'**
  String get statePending;

  /// No description provided for @stateDelayed.
  ///
  /// In en, this message translates to:
  /// **'On hold'**
  String get stateDelayed;

  /// No description provided for @stateUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Not available'**
  String get stateUnavailable;

  /// No description provided for @notYetAvailable.
  ///
  /// In en, this message translates to:
  /// **'Not yet available'**
  String get notYetAvailable;

  /// No description provided for @noticePlanNow.
  ///
  /// In en, this message translates to:
  /// **'The choice window closes on {closes}. Plan your collection now.'**
  String noticePlanNow(String closes);

  /// No description provided for @noticeIntentRecorded.
  ///
  /// In en, this message translates to:
  /// **'Your plan {ref} is recorded.'**
  String noticeIntentRecorded(String ref);

  /// No description provided for @noticeRationAtFps.
  ///
  /// In en, this message translates to:
  /// **'Your ration has reached your shop. You can collect it.'**
  String get noticeRationAtFps;

  /// No description provided for @noticeWindowClosedNoIntent.
  ///
  /// In en, this message translates to:
  /// **'The choice window is closed and no plan was submitted for this cycle.'**
  String get noticeWindowClosedNoIntent;

  /// No description provided for @noticeFpsNotActive.
  ///
  /// In en, this message translates to:
  /// **'Your shop {fps} is not active right now. Choose another shop when you plan.'**
  String noticeFpsNotActive(String fps);

  /// No description provided for @noticeNoCycle.
  ///
  /// In en, this message translates to:
  /// **'There is no active cycle right now.'**
  String get noticeNoCycle;

  /// No description provided for @entitlementTitle.
  ///
  /// In en, this message translates to:
  /// **'My entitlement'**
  String get entitlementTitle;

  /// No description provided for @monthlyEntitlement.
  ///
  /// In en, this message translates to:
  /// **'Monthly entitlement'**
  String get monthlyEntitlement;

  /// No description provided for @alreadyCollected.
  ///
  /// In en, this message translates to:
  /// **'Already collected'**
  String get alreadyCollected;

  /// No description provided for @remainingThisCycle.
  ///
  /// In en, this message translates to:
  /// **'Remaining this cycle'**
  String get remainingThisCycle;

  /// No description provided for @schemeLabel.
  ///
  /// In en, this message translates to:
  /// **'Scheme'**
  String get schemeLabel;

  /// No description provided for @schemeAAY.
  ///
  /// In en, this message translates to:
  /// **'Antyodaya (AAY)'**
  String get schemeAAY;

  /// No description provided for @schemePHH.
  ///
  /// In en, this message translates to:
  /// **'Priority household (PHH)'**
  String get schemePHH;

  /// No description provided for @householdMembers.
  ///
  /// In en, this message translates to:
  /// **'{n} members'**
  String householdMembers(String n);

  /// No description provided for @householdLabel.
  ///
  /// In en, this message translates to:
  /// **'Household'**
  String get householdLabel;

  /// No description provided for @entitlementExplain.
  ///
  /// In en, this message translates to:
  /// **'Your entitlement is based on your registered household and scheme information.'**
  String get entitlementExplain;

  /// No description provided for @entitlementReadOnly.
  ///
  /// In en, this message translates to:
  /// **'It is set by the government. Your plan can never change it.'**
  String get entitlementReadOnly;

  /// No description provided for @cycleTitle.
  ///
  /// In en, this message translates to:
  /// **'Current cycle'**
  String get cycleTitle;

  /// No description provided for @periodLabel.
  ///
  /// In en, this message translates to:
  /// **'Cycle period'**
  String get periodLabel;

  /// No description provided for @windowLabel.
  ///
  /// In en, this message translates to:
  /// **'Choice window'**
  String get windowLabel;

  /// No description provided for @statusLabel.
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get statusLabel;

  /// No description provided for @whatThisMeans.
  ///
  /// In en, this message translates to:
  /// **'What this means'**
  String get whatThisMeans;

  /// No description provided for @explainOpen.
  ///
  /// In en, this message translates to:
  /// **'You can plan what you want to collect this month. Submit your plan before the window closes.'**
  String get explainOpen;

  /// No description provided for @explainClosedNoPlan.
  ///
  /// In en, this message translates to:
  /// **'The window is closed and you did not submit a plan, so nothing was planned for you this cycle.'**
  String get explainClosedNoPlan;

  /// No description provided for @explainPlanRecorded.
  ///
  /// In en, this message translates to:
  /// **'Your plan is recorded. Follow its progress under My Ration.'**
  String get explainPlanRecorded;

  /// No description provided for @explainInProgress.
  ///
  /// In en, this message translates to:
  /// **'Your ration is moving through the supply chain. Follow it under My Ration.'**
  String get explainInProgress;

  /// No description provided for @planTitle.
  ///
  /// In en, this message translates to:
  /// **'Plan my collection'**
  String get planTitle;

  /// No description provided for @stepSelect.
  ///
  /// In en, this message translates to:
  /// **'Select'**
  String get stepSelect;

  /// No description provided for @stepReview.
  ///
  /// In en, this message translates to:
  /// **'Review'**
  String get stepReview;

  /// No description provided for @stepSubmit.
  ///
  /// In en, this message translates to:
  /// **'Submit'**
  String get stepSubmit;

  /// No description provided for @chooseFps.
  ///
  /// In en, this message translates to:
  /// **'Choose your shop'**
  String get chooseFps;

  /// No description provided for @nearestFirst.
  ///
  /// In en, this message translates to:
  /// **'Nearest first, in your district'**
  String get nearestFirst;

  /// No description provided for @distanceKm.
  ///
  /// In en, this message translates to:
  /// **'{km} km away'**
  String distanceKm(String km);

  /// No description provided for @yourCurrentShop.
  ///
  /// In en, this message translates to:
  /// **'Your current shop'**
  String get yourCurrentShop;

  /// No description provided for @shopNotActive.
  ///
  /// In en, this message translates to:
  /// **'Not active right now'**
  String get shopNotActive;

  /// No description provided for @chooseQuantity.
  ///
  /// In en, this message translates to:
  /// **'How much do you want to collect?'**
  String get chooseQuantity;

  /// No description provided for @riceKg.
  ///
  /// In en, this message translates to:
  /// **'Rice (kg)'**
  String get riceKg;

  /// No description provided for @wheatKg.
  ///
  /// In en, this message translates to:
  /// **'Wheat (kg)'**
  String get wheatKg;

  /// No description provided for @upTo.
  ///
  /// In en, this message translates to:
  /// **'Up to {max} kg'**
  String upTo(String max);

  /// No description provided for @collectionMode.
  ///
  /// In en, this message translates to:
  /// **'Who will collect?'**
  String get collectionMode;

  /// No description provided for @modeSelf.
  ///
  /// In en, this message translates to:
  /// **'I will collect'**
  String get modeSelf;

  /// No description provided for @modeAuthorized.
  ///
  /// In en, this message translates to:
  /// **'Authorized person'**
  String get modeAuthorized;

  /// No description provided for @calcEntitlement.
  ///
  /// In en, this message translates to:
  /// **'Your entitlement'**
  String get calcEntitlement;

  /// No description provided for @calcCollected.
  ///
  /// In en, this message translates to:
  /// **'Already collected'**
  String get calcCollected;

  /// No description provided for @calcRemaining.
  ///
  /// In en, this message translates to:
  /// **'Remaining'**
  String get calcRemaining;

  /// No description provided for @calcRequested.
  ///
  /// In en, this message translates to:
  /// **'You are requesting'**
  String get calcRequested;

  /// No description provided for @reviewPlan.
  ///
  /// In en, this message translates to:
  /// **'Review plan'**
  String get reviewPlan;

  /// No description provided for @enterQuantity.
  ///
  /// In en, this message translates to:
  /// **'Choose at least some rice or wheat'**
  String get enterQuantity;

  /// No description provided for @increase.
  ///
  /// In en, this message translates to:
  /// **'Increase {item}'**
  String increase(String item);

  /// No description provided for @decrease.
  ///
  /// In en, this message translates to:
  /// **'Decrease {item}'**
  String decrease(String item);

  /// No description provided for @selectedShop.
  ///
  /// In en, this message translates to:
  /// **'Selected shop {name}'**
  String selectedShop(String name);

  /// No description provided for @reviewTitle.
  ///
  /// In en, this message translates to:
  /// **'Review your plan'**
  String get reviewTitle;

  /// No description provided for @reviewFps.
  ///
  /// In en, this message translates to:
  /// **'Shop'**
  String get reviewFps;

  /// No description provided for @reviewMode.
  ///
  /// In en, this message translates to:
  /// **'Collected by'**
  String get reviewMode;

  /// No description provided for @reviewCycle.
  ///
  /// In en, this message translates to:
  /// **'Cycle'**
  String get reviewCycle;

  /// No description provided for @reviewRemainingAfter.
  ///
  /// In en, this message translates to:
  /// **'Entitlement left after this plan'**
  String get reviewRemainingAfter;

  /// No description provided for @reviewWarning.
  ///
  /// In en, this message translates to:
  /// **'Please confirm these details before submitting. You cannot change your plan after the choice window closes.'**
  String get reviewWarning;

  /// No description provided for @submitIntent.
  ///
  /// In en, this message translates to:
  /// **'Submit collection intent'**
  String get submitIntent;

  /// No description provided for @submitting.
  ///
  /// In en, this message translates to:
  /// **'Submitting…'**
  String get submitting;

  /// No description provided for @intentRecorded.
  ///
  /// In en, this message translates to:
  /// **'Collection intent recorded'**
  String get intentRecorded;

  /// No description provided for @intentCancelled.
  ///
  /// In en, this message translates to:
  /// **'Plan cancelled'**
  String get intentCancelled;

  /// No description provided for @referenceLabel.
  ///
  /// In en, this message translates to:
  /// **'Reference'**
  String get referenceLabel;

  /// No description provided for @submittedOn.
  ///
  /// In en, this message translates to:
  /// **'Submitted on'**
  String get submittedOn;

  /// No description provided for @statusRecorded.
  ///
  /// In en, this message translates to:
  /// **'Recorded'**
  String get statusRecorded;

  /// No description provided for @statusCancelled.
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get statusCancelled;

  /// No description provided for @cancelPlan.
  ///
  /// In en, this message translates to:
  /// **'Cancel and change my plan'**
  String get cancelPlan;

  /// No description provided for @cancelConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Cancel this plan?'**
  String get cancelConfirmTitle;

  /// No description provided for @cancelConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'Your plan will be cancelled and you can submit a new one while the window is open.'**
  String get cancelConfirmBody;

  /// No description provided for @keepPlan.
  ///
  /// In en, this message translates to:
  /// **'Keep my plan'**
  String get keepPlan;

  /// No description provided for @yesCancel.
  ///
  /// In en, this message translates to:
  /// **'Yes, cancel it'**
  String get yesCancel;

  /// No description provided for @backToHome.
  ///
  /// In en, this message translates to:
  /// **'Back to home'**
  String get backToHome;

  /// No description provided for @receiptTitle.
  ///
  /// In en, this message translates to:
  /// **'Intent receipt'**
  String get receiptTitle;

  /// No description provided for @trackTitle.
  ///
  /// In en, this message translates to:
  /// **'Track my ration'**
  String get trackTitle;

  /// No description provided for @journeyOf.
  ///
  /// In en, this message translates to:
  /// **'Cycle {cycle}'**
  String journeyOf(String cycle);

  /// No description provided for @liveTracking.
  ///
  /// In en, this message translates to:
  /// **'Vehicle tracking'**
  String get liveTracking;

  /// No description provided for @vehicleLabel.
  ///
  /// In en, this message translates to:
  /// **'Vehicle'**
  String get vehicleLabel;

  /// No description provided for @lastUpdate.
  ///
  /// In en, this message translates to:
  /// **'Last update'**
  String get lastUpdate;

  /// No description provided for @locationLabel.
  ///
  /// In en, this message translates to:
  /// **'Location'**
  String get locationLabel;

  /// No description provided for @routeStop.
  ///
  /// In en, this message translates to:
  /// **'Your stop is {n} of {total}'**
  String routeStop(String n, String total);

  /// No description provided for @plannedEta.
  ///
  /// In en, this message translates to:
  /// **'Planned arrival: about {min} min after departure'**
  String plannedEta(String min);

  /// No description provided for @liveLocationUnavailable.
  ///
  /// In en, this message translates to:
  /// **'LIVE LOCATION UNAVAILABLE'**
  String get liveLocationUnavailable;

  /// No description provided for @liveLocationUnavailableBody.
  ///
  /// In en, this message translates to:
  /// **'The vehicle has not shared a location. Nothing is estimated or made up.'**
  String get liveLocationUnavailableBody;

  /// No description provided for @detailNoIntent.
  ///
  /// In en, this message translates to:
  /// **'You did not submit a plan for this cycle'**
  String get detailNoIntent;

  /// No description provided for @detailAllocationOnHold.
  ///
  /// In en, this message translates to:
  /// **'Stock for your shop is on hold'**
  String get detailAllocationOnHold;

  /// No description provided for @detailDeliveryRejected.
  ///
  /// In en, this message translates to:
  /// **'The delivery was rejected at the shop and is being resolved'**
  String get detailDeliveryRejected;

  /// No description provided for @collectedDetail.
  ///
  /// In en, this message translates to:
  /// **'Rice {rice} kg, wheat {wheat} kg'**
  String collectedDetail(String rice, String wheat);

  /// No description provided for @cycleData.
  ///
  /// In en, this message translates to:
  /// **'Cycle'**
  String get cycleData;

  /// No description provided for @dataNoteInferred.
  ///
  /// In en, this message translates to:
  /// **'Dispatch is confirmed by the delivery record'**
  String get dataNoteInferred;

  /// No description provided for @historyTitle.
  ///
  /// In en, this message translates to:
  /// **'My history'**
  String get historyTitle;

  /// No description provided for @tabCollections.
  ///
  /// In en, this message translates to:
  /// **'Collections'**
  String get tabCollections;

  /// No description provided for @tabTransactions.
  ///
  /// In en, this message translates to:
  /// **'Transactions'**
  String get tabTransactions;

  /// No description provided for @tabIntents.
  ///
  /// In en, this message translates to:
  /// **'Intents'**
  String get tabIntents;

  /// No description provided for @noHistory.
  ///
  /// In en, this message translates to:
  /// **'NO HISTORY AVAILABLE'**
  String get noHistory;

  /// No description provided for @txnSuccess.
  ///
  /// In en, this message translates to:
  /// **'Successful'**
  String get txnSuccess;

  /// No description provided for @txnFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed'**
  String get txnFailed;

  /// No description provided for @txnCancelled.
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get txnCancelled;

  /// No description provided for @viewReceipt.
  ///
  /// In en, this message translates to:
  /// **'View receipt'**
  String get viewReceipt;

  /// No description provided for @transactionsCount.
  ///
  /// In en, this message translates to:
  /// **'{n} transactions'**
  String transactionsCount(String n);

  /// No description provided for @atShop.
  ///
  /// In en, this message translates to:
  /// **'at {shop}'**
  String atShop(String shop);

  /// No description provided for @noReceiptForFailed.
  ///
  /// In en, this message translates to:
  /// **'A receipt is only issued for successful collections.'**
  String get noReceiptForFailed;

  /// No description provided for @digitalReceipt.
  ///
  /// In en, this message translates to:
  /// **'Digital receipt'**
  String get digitalReceipt;

  /// No description provided for @beneficiaryLabel.
  ///
  /// In en, this message translates to:
  /// **'Beneficiary'**
  String get beneficiaryLabel;

  /// No description provided for @transactionId.
  ///
  /// In en, this message translates to:
  /// **'Transaction ID'**
  String get transactionId;

  /// No description provided for @receiptNumber.
  ///
  /// In en, this message translates to:
  /// **'Receipt number'**
  String get receiptNumber;

  /// No description provided for @commodityLabel.
  ///
  /// In en, this message translates to:
  /// **'Commodity'**
  String get commodityLabel;

  /// No description provided for @quantityLabel.
  ///
  /// In en, this message translates to:
  /// **'Quantity'**
  String get quantityLabel;

  /// No description provided for @dateTimeLabel.
  ///
  /// In en, this message translates to:
  /// **'Date and time'**
  String get dateTimeLabel;

  /// No description provided for @verificationRef.
  ///
  /// In en, this message translates to:
  /// **'Verification code'**
  String get verificationRef;

  /// No description provided for @scanToVerify.
  ///
  /// In en, this message translates to:
  /// **'Show this code at the shop to verify the receipt'**
  String get scanToVerify;

  /// No description provided for @helpTitle.
  ///
  /// In en, this message translates to:
  /// **'Help'**
  String get helpTitle;

  /// No description provided for @assistantTitle.
  ///
  /// In en, this message translates to:
  /// **'My PDS Assistant'**
  String get assistantTitle;

  /// No description provided for @assistantSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Ask about your ration, entitlement and status'**
  String get assistantSubtitle;

  /// No description provided for @raiseGrievance.
  ///
  /// In en, this message translates to:
  /// **'Raise a grievance'**
  String get raiseGrievance;

  /// No description provided for @raiseGrievanceSub.
  ///
  /// In en, this message translates to:
  /// **'Tell us if something went wrong'**
  String get raiseGrievanceSub;

  /// No description provided for @myGrievances.
  ///
  /// In en, this message translates to:
  /// **'My grievances'**
  String get myGrievances;

  /// No description provided for @signOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get signOut;

  /// No description provided for @signOutConfirm.
  ///
  /// In en, this message translates to:
  /// **'Sign out of DemandSYNC?'**
  String get signOutConfirm;

  /// No description provided for @helpFooter.
  ///
  /// In en, this message translates to:
  /// **'For urgent help, contact your district food office.'**
  String get helpFooter;

  /// No description provided for @assistantHello.
  ///
  /// In en, this message translates to:
  /// **'Hello! I can explain your own ration records. What would you like to know?'**
  String get assistantHello;

  /// No description provided for @askPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Ask a question'**
  String get askPlaceholder;

  /// No description provided for @send.
  ///
  /// In en, this message translates to:
  /// **'Send'**
  String get send;

  /// No description provided for @sourceLabel.
  ///
  /// In en, this message translates to:
  /// **'Source: {source}'**
  String sourceLabel(String source);

  /// No description provided for @viewRelated.
  ///
  /// In en, this message translates to:
  /// **'View details'**
  String get viewRelated;

  /// No description provided for @assistantNote.
  ///
  /// In en, this message translates to:
  /// **'Answers come from your own records. This assistant cannot change anything.'**
  String get assistantNote;

  /// No description provided for @chipEntitlement.
  ///
  /// In en, this message translates to:
  /// **'How much can I collect?'**
  String get chipEntitlement;

  /// No description provided for @chipWindow.
  ///
  /// In en, this message translates to:
  /// **'When is my collection window?'**
  String get chipWindow;

  /// No description provided for @chipRequest.
  ///
  /// In en, this message translates to:
  /// **'What did I request?'**
  String get chipRequest;

  /// No description provided for @chipDispatch.
  ///
  /// In en, this message translates to:
  /// **'Where is my ration?'**
  String get chipDispatch;

  /// No description provided for @chipFps.
  ///
  /// In en, this message translates to:
  /// **'Which shop am I assigned to?'**
  String get chipFps;

  /// No description provided for @chipCantSubmit.
  ///
  /// In en, this message translates to:
  /// **'Why can\'t I submit my plan?'**
  String get chipCantSubmit;

  /// No description provided for @assistantThinking.
  ///
  /// In en, this message translates to:
  /// **'Checking your records…'**
  String get assistantThinking;

  /// No description provided for @grievanceTitle.
  ///
  /// In en, this message translates to:
  /// **'Raise a grievance'**
  String get grievanceTitle;

  /// No description provided for @chooseIssue.
  ///
  /// In en, this message translates to:
  /// **'What went wrong?'**
  String get chooseIssue;

  /// No description provided for @catShortDelivery.
  ///
  /// In en, this message translates to:
  /// **'Short delivery'**
  String get catShortDelivery;

  /// No description provided for @catWrongQuantity.
  ///
  /// In en, this message translates to:
  /// **'Wrong quantity'**
  String get catWrongQuantity;

  /// No description provided for @catFpsIssue.
  ///
  /// In en, this message translates to:
  /// **'Shop issue'**
  String get catFpsIssue;

  /// No description provided for @catQuality.
  ///
  /// In en, this message translates to:
  /// **'Quality issue'**
  String get catQuality;

  /// No description provided for @catTransaction.
  ///
  /// In en, this message translates to:
  /// **'Transaction issue'**
  String get catTransaction;

  /// No description provided for @catEntitlement.
  ///
  /// In en, this message translates to:
  /// **'Entitlement question'**
  String get catEntitlement;

  /// No description provided for @catCollection.
  ///
  /// In en, this message translates to:
  /// **'Collection issue'**
  String get catCollection;

  /// No description provided for @catOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get catOther;

  /// No description provided for @describeIssue.
  ///
  /// In en, this message translates to:
  /// **'Describe the issue'**
  String get describeIssue;

  /// No description provided for @describeHint.
  ///
  /// In en, this message translates to:
  /// **'Write what happened (at least 10 characters)'**
  String get describeHint;

  /// No description provided for @charCount.
  ///
  /// In en, this message translates to:
  /// **'{n} / 500'**
  String charCount(String n);

  /// No description provided for @aiSuggest.
  ///
  /// In en, this message translates to:
  /// **'Suggest a category'**
  String get aiSuggest;

  /// No description provided for @aiSuggestion.
  ///
  /// In en, this message translates to:
  /// **'Suggested: {category}'**
  String aiSuggestion(String category);

  /// No description provided for @aiSuggestNote.
  ///
  /// In en, this message translates to:
  /// **'This is only a suggestion. You choose before submitting.'**
  String get aiSuggestNote;

  /// No description provided for @useSuggestion.
  ///
  /// In en, this message translates to:
  /// **'Use this'**
  String get useSuggestion;

  /// No description provided for @aboutTransaction.
  ///
  /// In en, this message translates to:
  /// **'About a collection?'**
  String get aboutTransaction;

  /// No description provided for @noTransactionLink.
  ///
  /// In en, this message translates to:
  /// **'Not about a specific collection'**
  String get noTransactionLink;

  /// No description provided for @submitGrievance.
  ///
  /// In en, this message translates to:
  /// **'Submit grievance'**
  String get submitGrievance;

  /// No description provided for @grievanceSubmitted.
  ///
  /// In en, this message translates to:
  /// **'Grievance submitted'**
  String get grievanceSubmitted;

  /// No description provided for @grievanceSubmittedBody.
  ///
  /// In en, this message translates to:
  /// **'Your grievance has been recorded. You can follow its status under My grievances.'**
  String get grievanceSubmittedBody;

  /// No description provided for @grStatusOpen.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get grStatusOpen;

  /// No description provided for @grStatusInReview.
  ///
  /// In en, this message translates to:
  /// **'In review'**
  String get grStatusInReview;

  /// No description provided for @grStatusResolved.
  ///
  /// In en, this message translates to:
  /// **'Resolved'**
  String get grStatusResolved;

  /// No description provided for @grStatusClosed.
  ///
  /// In en, this message translates to:
  /// **'Closed'**
  String get grStatusClosed;

  /// No description provided for @noGrievances.
  ///
  /// In en, this message translates to:
  /// **'You have not raised any grievance'**
  String get noGrievances;

  /// No description provided for @resolutionLabel.
  ///
  /// In en, this message translates to:
  /// **'Resolution'**
  String get resolutionLabel;

  /// No description provided for @errOffline.
  ///
  /// In en, this message translates to:
  /// **'Unable to connect to PDS services. Please try again.'**
  String get errOffline;

  /// No description provided for @errTimeout.
  ///
  /// In en, this message translates to:
  /// **'The server is taking too long to respond. Please try again.'**
  String get errTimeout;

  /// No description provided for @errServer.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong on our side. Please try again in a moment.'**
  String get errServer;

  /// No description provided for @errSession.
  ///
  /// In en, this message translates to:
  /// **'Your session has expired. Please sign in again.'**
  String get errSession;

  /// No description provided for @errGeneric.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong. Please try again.'**
  String get errGeneric;

  /// No description provided for @errIntentDuplicate.
  ///
  /// In en, this message translates to:
  /// **'Your collection preference has already been submitted for this cycle.'**
  String get errIntentDuplicate;

  /// No description provided for @errWindowClosed.
  ///
  /// In en, this message translates to:
  /// **'The choice window for this cycle is closed.'**
  String get errWindowClosed;

  /// No description provided for @errExceedsRemaining.
  ///
  /// In en, this message translates to:
  /// **'That is more than your remaining entitlement.'**
  String get errExceedsRemaining;

  /// No description provided for @errInvalidQuantity.
  ///
  /// In en, this message translates to:
  /// **'Enter a quantity above zero.'**
  String get errInvalidQuantity;

  /// No description provided for @errFpsNotEligible.
  ///
  /// In en, this message translates to:
  /// **'You can only choose an active shop in your own district.'**
  String get errFpsNotEligible;

  /// No description provided for @errNoCycle.
  ///
  /// In en, this message translates to:
  /// **'There is no active cycle right now.'**
  String get errNoCycle;

  /// No description provided for @errTooMany.
  ///
  /// In en, this message translates to:
  /// **'Too many attempts. Please wait a moment and try again.'**
  String get errTooMany;

  /// No description provided for @errBadCredentials.
  ///
  /// In en, this message translates to:
  /// **'The details could not be verified. Please check your ration card and mobile number.'**
  String get errBadCredentials;

  /// No description provided for @errAccountDisabled.
  ///
  /// In en, this message translates to:
  /// **'This account is disabled. Please contact the food office.'**
  String get errAccountDisabled;

  /// No description provided for @errOtpUnavailable.
  ///
  /// In en, this message translates to:
  /// **'OTP delivery is not available right now. Please try again later.'**
  String get errOtpUnavailable;

  /// No description provided for @errNotFound.
  ///
  /// In en, this message translates to:
  /// **'We could not find that record.'**
  String get errNotFound;

  /// No description provided for @errOtpInvalid.
  ///
  /// In en, this message translates to:
  /// **'Wrong OTP. {left} tries left.'**
  String errOtpInvalid(String left);

  /// No description provided for @errOtpInvalidLast.
  ///
  /// In en, this message translates to:
  /// **'Wrong OTP. Please request a new one.'**
  String get errOtpInvalidLast;

  /// No description provided for @errOtpExpired.
  ///
  /// In en, this message translates to:
  /// **'This OTP has expired. Please request a new one.'**
  String get errOtpExpired;

  /// No description provided for @errOtpUsed.
  ///
  /// In en, this message translates to:
  /// **'This OTP was already used. Please request a new one.'**
  String get errOtpUsed;

  /// No description provided for @errOtpTooMany.
  ///
  /// In en, this message translates to:
  /// **'Too many wrong tries. Please request a new OTP.'**
  String get errOtpTooMany;

  /// No description provided for @errOtpNotRequested.
  ///
  /// In en, this message translates to:
  /// **'Please request an OTP first.'**
  String get errOtpNotRequested;

  /// No description provided for @errCooldown.
  ///
  /// In en, this message translates to:
  /// **'Please wait {seconds}s before asking for another OTP.'**
  String errCooldown(String seconds);

  /// No description provided for @sessionExpiredBanner.
  ///
  /// In en, this message translates to:
  /// **'Your session expired. Please sign in again.'**
  String get sessionExpiredBanner;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'hi', 'kn'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'hi':
      return AppLocalizationsHi();
    case 'kn':
      return AppLocalizationsKn();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}

// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get appName => 'DemandSYNC';

  @override
  String get appTagline => 'आपका राशन। आपका अधिकार। हमारी प्राथमिकता।';

  @override
  String get welcomeBody =>
      'अपना राशन तय करने, ट्रैक करने और पाने का सरल, सुरक्षित और पारदर्शी तरीका।';

  @override
  String get getStarted => 'शुरू करें';

  @override
  String get language => 'भाषा';

  @override
  String get cancel => 'रद्द करें';

  @override
  String get confirm => 'पुष्टि करें';

  @override
  String get retry => 'फिर कोशिश करें';

  @override
  String get back => 'वापस';

  @override
  String get close => 'बंद करें';

  @override
  String get done => 'पूरा हुआ';

  @override
  String get continueBtn => 'आगे बढ़ें';

  @override
  String kgValue(String value) {
    return '$value किग्रा';
  }

  @override
  String get dataUnavailable => 'जानकारी उपलब्ध नहीं';

  @override
  String get loading => 'लोड हो रहा है…';

  @override
  String get loginTitle => 'वापसी पर स्वागत है';

  @override
  String get loginSubtitle => 'अपने राशन का विवरण देखने के लिए साइन इन करें';

  @override
  String get rationCardLabel => 'राशन कार्ड नंबर';

  @override
  String get mobileLabel => 'पंजीकृत मोबाइल नंबर';

  @override
  String get sendOtp => 'OTP भेजें';

  @override
  String get otpTitle => 'OTP दर्ज करें';

  @override
  String otpSentTo(String mobile) {
    return 'हमने $mobile पर 6 अंकों का कोड भेजा है';
  }

  @override
  String get otpLabel => '6 अंकों का OTP';

  @override
  String get verifyContinue => 'सत्यापित करें और आगे बढ़ें';

  @override
  String get resendOtp => 'OTP दोबारा भेजें';

  @override
  String resendIn(String seconds) {
    return '$seconds सेकंड में OTP दोबारा भेजें';
  }

  @override
  String devModeBanner(String otp) {
    return 'डेवलपमेंट मोड: कोई SMS नहीं भेजा जाता। आपका कोड $otp है।';
  }

  @override
  String get useThisCode => 'यह कोड उपयोग करें';

  @override
  String get changeNumber => 'विवरण बदलें';

  @override
  String get fieldRequired => 'यह जानकारी आवश्यक है';

  @override
  String get otpInvalidLength => 'सभी 6 अंक दर्ज करें';

  @override
  String get loginHelp =>
      'अपने परिवार के पंजीकृत राशन कार्ड नंबर और मोबाइल नंबर का उपयोग करें।';

  @override
  String get navHome => 'होम';

  @override
  String get navMyRation => 'मेरा राशन';

  @override
  String get navHistory => 'इतिहास';

  @override
  String get navHelp => 'सहायता';

  @override
  String get goodMorning => 'सुप्रभात';

  @override
  String get goodAfternoon => 'नमस्कार';

  @override
  String get goodEvening => 'शुभ संध्या';

  @override
  String get myPds => 'मेरा पीडीएस';

  @override
  String get currentCycle => 'वर्तमान चक्र';

  @override
  String collectionWindow(String start, String end) {
    return 'विकल्प की अवधि: $start से $end';
  }

  @override
  String get myEntitlement => 'मेरी पात्रता';

  @override
  String get rice => 'चावल';

  @override
  String get wheat => 'गेहूँ';

  @override
  String get total => 'कुल';

  @override
  String get remaining => 'शेष';

  @override
  String get collected => 'लिया गया';

  @override
  String get currentFps => 'मेरी उचित मूल्य की दुकान';

  @override
  String fpsIdLabel(String id) {
    return 'दुकान आईडी: $id';
  }

  @override
  String openingHours(String hours) {
    return 'खुलने का समय $hours';
  }

  @override
  String get planMyCollection => 'मेरा संग्रह तय करें';

  @override
  String get viewMyPlan => 'मेरी योजना देखें';

  @override
  String get trackMyRation => 'मेरा राशन ट्रैक करें';

  @override
  String get viewEntitlement => 'पात्रता देखें';

  @override
  String get viewCycle => 'इस चक्र के बारे में';

  @override
  String rationCardShort(String id) {
    return 'राशन कार्ड $id';
  }

  @override
  String get signedInAs => 'साइन इन';

  @override
  String get stChoiceWindowOpen => 'विकल्प की अवधि खुली है';

  @override
  String get stChoiceWindowClosed => 'विकल्प की अवधि बंद है';

  @override
  String get stIntentSubmitted => 'योजना जमा की गई';

  @override
  String get stDemandPlanned => 'मांग तय हुई';

  @override
  String get stAllocated => 'आवंटित';

  @override
  String get stDispatched => 'भेजा गया';

  @override
  String get stInTransit => 'रास्ते में';

  @override
  String get stReceivedAtFps => 'दुकान पर पहुँचा';

  @override
  String get stAvailableForCollection => 'लेने के लिए उपलब्ध';

  @override
  String get stCollected => 'ले लिया गया';

  @override
  String get stateDone => 'पूरा';

  @override
  String get stateActive => 'जारी है';

  @override
  String get statePending => 'अभी नहीं';

  @override
  String get stateDelayed => 'रुका हुआ';

  @override
  String get stateUnavailable => 'उपलब्ध नहीं';

  @override
  String get notYetAvailable => 'अभी उपलब्ध नहीं';

  @override
  String noticePlanNow(String closes) {
    return 'विकल्प की अवधि $closes को बंद होगी। अभी अपना संग्रह तय करें।';
  }

  @override
  String noticeIntentRecorded(String ref) {
    return 'आपकी योजना $ref दर्ज है।';
  }

  @override
  String get noticeRationAtFps =>
      'आपका राशन आपकी दुकान पर पहुँच गया है। आप इसे ले सकते हैं।';

  @override
  String get noticeWindowClosedNoIntent =>
      'विकल्प की अवधि बंद है और इस चक्र के लिए कोई योजना जमा नहीं की गई।';

  @override
  String noticeFpsNotActive(String fps) {
    return 'आपकी दुकान $fps अभी सक्रिय नहीं है। योजना बनाते समय दूसरी दुकान चुनें।';
  }

  @override
  String get noticeNoCycle => 'अभी कोई सक्रिय चक्र नहीं है।';

  @override
  String get entitlementTitle => 'मेरी पात्रता';

  @override
  String get monthlyEntitlement => 'मासिक पात्रता';

  @override
  String get alreadyCollected => 'पहले ही लिया गया';

  @override
  String get remainingThisCycle => 'इस चक्र में शेष';

  @override
  String get schemeLabel => 'योजना';

  @override
  String get schemeAAY => 'अंत्योदय (AAY)';

  @override
  String get schemePHH => 'प्राथमिकता वाला परिवार (PHH)';

  @override
  String householdMembers(String n) {
    return '$n सदस्य';
  }

  @override
  String get householdLabel => 'परिवार';

  @override
  String get entitlementExplain =>
      'आपकी पात्रता आपके पंजीकृत परिवार और योजना की जानकारी पर आधारित है।';

  @override
  String get entitlementReadOnly =>
      'यह सरकार द्वारा तय है। आपकी योजना इसे कभी नहीं बदल सकती।';

  @override
  String get cycleTitle => 'वर्तमान चक्र';

  @override
  String get periodLabel => 'चक्र की अवधि';

  @override
  String get windowLabel => 'विकल्प की अवधि';

  @override
  String get statusLabel => 'स्थिति';

  @override
  String get whatThisMeans => 'इसका मतलब';

  @override
  String get explainOpen =>
      'आप इस महीने जो लेना चाहते हैं उसे तय कर सकते हैं। अवधि बंद होने से पहले अपनी योजना जमा करें।';

  @override
  String get explainClosedNoPlan =>
      'अवधि बंद हो चुकी है और आपने योजना जमा नहीं की, इसलिए इस चक्र में आपके लिए कुछ तय नहीं हुआ।';

  @override
  String get explainPlanRecorded =>
      'आपकी योजना दर्ज है। इसकी प्रगति मेरा राशन में देखें।';

  @override
  String get explainInProgress =>
      'आपका राशन आपूर्ति श्रृंखला में आगे बढ़ रहा है। इसे मेरा राशन में देखें।';

  @override
  String get planTitle => 'मेरा संग्रह तय करें';

  @override
  String get stepSelect => 'चुनें';

  @override
  String get stepReview => 'जाँचें';

  @override
  String get stepSubmit => 'जमा करें';

  @override
  String get chooseFps => 'अपनी दुकान चुनें';

  @override
  String get nearestFirst => 'आपके जिले में, सबसे नज़दीकी पहले';

  @override
  String distanceKm(String km) {
    return '$km किमी दूर';
  }

  @override
  String get yourCurrentShop => 'आपकी वर्तमान दुकान';

  @override
  String get shopNotActive => 'अभी सक्रिय नहीं';

  @override
  String get chooseQuantity => 'आप कितना लेना चाहते हैं?';

  @override
  String get riceKg => 'चावल (किग्रा)';

  @override
  String get wheatKg => 'गेहूँ (किग्रा)';

  @override
  String upTo(String max) {
    return 'अधिकतम $max किग्रा';
  }

  @override
  String get collectionMode => 'कौन लेगा?';

  @override
  String get modeSelf => 'मैं लूँगा/लूँगी';

  @override
  String get modeAuthorized => 'अधिकृत व्यक्ति';

  @override
  String get calcEntitlement => 'आपकी पात्रता';

  @override
  String get calcCollected => 'पहले ही लिया गया';

  @override
  String get calcRemaining => 'शेष';

  @override
  String get calcRequested => 'आप माँग रहे हैं';

  @override
  String get reviewPlan => 'योजना जाँचें';

  @override
  String get enterQuantity => 'कम से कम कुछ चावल या गेहूँ चुनें';

  @override
  String increase(String item) {
    return '$item बढ़ाएँ';
  }

  @override
  String decrease(String item) {
    return '$item घटाएँ';
  }

  @override
  String selectedShop(String name) {
    return 'चुनी गई दुकान $name';
  }

  @override
  String get reviewTitle => 'अपनी योजना जाँचें';

  @override
  String get reviewFps => 'दुकान';

  @override
  String get reviewMode => 'कौन लेगा';

  @override
  String get reviewCycle => 'चक्र';

  @override
  String get reviewRemainingAfter => 'इस योजना के बाद बची पात्रता';

  @override
  String get reviewWarning =>
      'जमा करने से पहले कृपया इन विवरणों की पुष्टि करें। विकल्प की अवधि बंद होने के बाद आप अपनी योजना नहीं बदल सकेंगे।';

  @override
  String get submitIntent => 'संग्रह योजना जमा करें';

  @override
  String get submitting => 'जमा हो रहा है…';

  @override
  String get intentRecorded => 'संग्रह योजना दर्ज हो गई';

  @override
  String get intentCancelled => 'योजना रद्द की गई';

  @override
  String get referenceLabel => 'संदर्भ';

  @override
  String get submittedOn => 'जमा करने की तिथि';

  @override
  String get statusRecorded => 'दर्ज';

  @override
  String get statusCancelled => 'रद्द';

  @override
  String get cancelPlan => 'रद्द करें और योजना बदलें';

  @override
  String get cancelConfirmTitle => 'यह योजना रद्द करें?';

  @override
  String get cancelConfirmBody =>
      'आपकी योजना रद्द हो जाएगी और अवधि खुली रहने तक आप नई योजना जमा कर सकेंगे।';

  @override
  String get keepPlan => 'योजना रखें';

  @override
  String get yesCancel => 'हाँ, रद्द करें';

  @override
  String get backToHome => 'होम पर वापस';

  @override
  String get receiptTitle => 'योजना की रसीद';

  @override
  String get trackTitle => 'मेरा राशन ट्रैक करें';

  @override
  String journeyOf(String cycle) {
    return 'चक्र $cycle';
  }

  @override
  String get liveTracking => 'वाहन की स्थिति';

  @override
  String get vehicleLabel => 'वाहन';

  @override
  String get lastUpdate => 'अंतिम अपडेट';

  @override
  String get locationLabel => 'स्थान';

  @override
  String routeStop(String n, String total) {
    return 'आपकी दुकान $total में से $nवीं है';
  }

  @override
  String plannedEta(String min) {
    return 'अनुमानित पहुँच: रवाना होने के लगभग $min मिनट बाद';
  }

  @override
  String get liveLocationUnavailable => 'लाइव लोकेशन उपलब्ध नहीं';

  @override
  String get liveLocationUnavailableBody =>
      'वाहन ने अपना स्थान साझा नहीं किया है। कुछ भी अनुमान या बनावटी नहीं दिखाया जाता।';

  @override
  String get detailNoIntent => 'आपने इस चक्र के लिए योजना जमा नहीं की';

  @override
  String get detailAllocationOnHold => 'आपकी दुकान का स्टॉक रुका हुआ है';

  @override
  String get detailDeliveryRejected =>
      'दुकान पर डिलीवरी अस्वीकार हुई और उसे सुलझाया जा रहा है';

  @override
  String collectedDetail(String rice, String wheat) {
    return 'चावल $rice किग्रा, गेहूँ $wheat किग्रा';
  }

  @override
  String get cycleData => 'चक्र';

  @override
  String get dataNoteInferred => 'भेजे जाने की पुष्टि डिलीवरी रिकॉर्ड से हुई';

  @override
  String get historyTitle => 'मेरा इतिहास';

  @override
  String get notificationsTitle => 'सूचनाएं';

  @override
  String get noNotifications => 'अभी कोई सूचना नहीं है';

  @override
  String get tabCollections => 'संग्रह';

  @override
  String get tabTransactions => 'लेन-देन';

  @override
  String get tabIntents => 'योजनाएँ';

  @override
  String get noHistory => 'कोई इतिहास उपलब्ध नहीं';

  @override
  String get txnSuccess => 'सफल';

  @override
  String get txnFailed => 'विफल';

  @override
  String get txnCancelled => 'रद्द';

  @override
  String get viewReceipt => 'रसीद देखें';

  @override
  String transactionsCount(String n) {
    return '$n लेन-देन';
  }

  @override
  String atShop(String shop) {
    return '$shop पर';
  }

  @override
  String get noReceiptForFailed => 'रसीद केवल सफल संग्रह के लिए दी जाती है।';

  @override
  String get digitalReceipt => 'डिजिटल रसीद';

  @override
  String get beneficiaryLabel => 'लाभार्थी';

  @override
  String get transactionId => 'लेन-देन आईडी';

  @override
  String get receiptNumber => 'रसीद नंबर';

  @override
  String get commodityLabel => 'वस्तु';

  @override
  String get quantityLabel => 'मात्रा';

  @override
  String get dateTimeLabel => 'तिथि और समय';

  @override
  String get verificationRef => 'सत्यापन कोड';

  @override
  String get scanToVerify => 'रसीद सत्यापित करने के लिए यह कोड दुकान पर दिखाएँ';

  @override
  String get helpTitle => 'सहायता';

  @override
  String get assistantTitle => 'मेरा पीडीएस सहायक';

  @override
  String get assistantSubtitle =>
      'अपने राशन, पात्रता और स्थिति के बारे में पूछें';

  @override
  String get raiseGrievance => 'शिकायत दर्ज करें';

  @override
  String get raiseGrievanceSub => 'कुछ गलत हुआ हो तो हमें बताएँ';

  @override
  String get myGrievances => 'मेरी शिकायतें';

  @override
  String get signOut => 'साइन आउट';

  @override
  String get signOutConfirm => 'DemandSYNC से साइन आउट करें?';

  @override
  String get helpFooter =>
      'तत्काल सहायता के लिए अपने जिला खाद्य कार्यालय से संपर्क करें।';

  @override
  String get assistantHello =>
      'नमस्ते! मैं आपके अपने राशन रिकॉर्ड समझा सकता हूँ। आप क्या जानना चाहेंगे?';

  @override
  String get askPlaceholder => 'प्रश्न पूछें';

  @override
  String get send => 'भेजें';

  @override
  String sourceLabel(String source) {
    return 'स्रोत: $source';
  }

  @override
  String get viewRelated => 'विवरण देखें';

  @override
  String get assistantNote =>
      'उत्तर आपके अपने रिकॉर्ड से आते हैं। यह सहायक कुछ भी बदल नहीं सकता।';

  @override
  String get chipEntitlement => 'मैं कितना ले सकता/सकती हूँ?';

  @override
  String get chipWindow => 'मेरी संग्रह अवधि कब है?';

  @override
  String get chipRequest => 'मैंने क्या माँगा था?';

  @override
  String get chipDispatch => 'मेरा राशन कहाँ है?';

  @override
  String get chipFps => 'मेरी दुकान कौन सी है?';

  @override
  String get chipCantSubmit => 'मैं योजना जमा क्यों नहीं कर पा रहा/रही?';

  @override
  String get assistantThinking => 'आपके रिकॉर्ड देखे जा रहे हैं…';

  @override
  String get grievanceTitle => 'शिकायत दर्ज करें';

  @override
  String get chooseIssue => 'क्या गलत हुआ?';

  @override
  String get catShortDelivery => 'कम मात्रा मिली';

  @override
  String get catWrongQuantity => 'गलत मात्रा';

  @override
  String get catFpsIssue => 'दुकान की समस्या';

  @override
  String get catQuality => 'गुणवत्ता की समस्या';

  @override
  String get catTransaction => 'लेन-देन की समस्या';

  @override
  String get catEntitlement => 'पात्रता का प्रश्न';

  @override
  String get catCollection => 'राशन लेने में समस्या';

  @override
  String get catOther => 'अन्य';

  @override
  String get describeIssue => 'समस्या बताएँ';

  @override
  String get describeHint => 'क्या हुआ लिखें (कम से कम 10 अक्षर)';

  @override
  String charCount(String n) {
    return '$n / 500';
  }

  @override
  String get aiSuggest => 'श्रेणी सुझाएँ';

  @override
  String aiSuggestion(String category) {
    return 'सुझाव: $category';
  }

  @override
  String get aiSuggestNote =>
      'यह केवल एक सुझाव है। जमा करने से पहले आप ही चुनते हैं।';

  @override
  String get useSuggestion => 'इसे चुनें';

  @override
  String get aboutTransaction => 'किसी संग्रह के बारे में?';

  @override
  String get noTransactionLink => 'किसी विशेष संग्रह के बारे में नहीं';

  @override
  String get submitGrievance => 'शिकायत जमा करें';

  @override
  String get grievanceSubmitted => 'शिकायत जमा हो गई';

  @override
  String get grievanceSubmittedBody =>
      'आपकी शिकायत दर्ज हो गई है। इसकी स्थिति मेरी शिकायतें में देखें।';

  @override
  String get grStatusOpen => 'खुली';

  @override
  String get grStatusInReview => 'समीक्षा में';

  @override
  String get grStatusResolved => 'सुलझी';

  @override
  String get grStatusClosed => 'बंद';

  @override
  String get noGrievances => 'आपने कोई शिकायत दर्ज नहीं की है';

  @override
  String get resolutionLabel => 'समाधान';

  @override
  String get errOffline =>
      'पीडीएस सेवाओं से कनेक्ट नहीं हो पा रहा। कृपया फिर कोशिश करें।';

  @override
  String get errTimeout =>
      'सर्वर जवाब देने में बहुत समय ले रहा है। कृपया फिर कोशिश करें।';

  @override
  String get errServer =>
      'हमारी ओर से कुछ गड़बड़ हुई। कृपया थोड़ी देर बाद फिर कोशिश करें।';

  @override
  String get errSession =>
      'आपका सत्र समाप्त हो गया है। कृपया फिर साइन इन करें।';

  @override
  String get errGeneric => 'कुछ गलत हो गया। कृपया फिर कोशिश करें।';

  @override
  String get errIntentDuplicate =>
      'इस चक्र के लिए आपकी संग्रह पसंद पहले ही जमा हो चुकी है।';

  @override
  String get errWindowClosed => 'इस चक्र के लिए विकल्प की अवधि बंद है।';

  @override
  String get errExceedsRemaining => 'यह आपकी शेष पात्रता से अधिक है।';

  @override
  String get errInvalidQuantity => 'शून्य से अधिक मात्रा दर्ज करें।';

  @override
  String get errFpsNotEligible =>
      'आप केवल अपने जिले की सक्रिय दुकान चुन सकते हैं।';

  @override
  String get errNoCycle => 'अभी कोई सक्रिय चक्र नहीं है।';

  @override
  String get errTooMany =>
      'बहुत अधिक प्रयास। कृपया थोड़ी देर रुककर फिर कोशिश करें।';

  @override
  String get errBadCredentials =>
      'विवरण सत्यापित नहीं हो सके। कृपया अपना राशन कार्ड और मोबाइल नंबर जाँचें।';

  @override
  String get errAccountDisabled =>
      'यह खाता निष्क्रिय है। कृपया खाद्य कार्यालय से संपर्क करें।';

  @override
  String get errOtpUnavailable =>
      'OTP भेजने की सुविधा अभी उपलब्ध नहीं है। कृपया बाद में कोशिश करें।';

  @override
  String get errNotFound => 'वह रिकॉर्ड नहीं मिला।';

  @override
  String errOtpInvalid(String left) {
    return 'गलत OTP। $left कोशिशें बाकी हैं।';
  }

  @override
  String get errOtpInvalidLast => 'गलत OTP। कृपया नया OTP मँगवाएँ।';

  @override
  String get errOtpExpired => 'यह OTP समाप्त हो गया है। कृपया नया OTP मँगवाएँ।';

  @override
  String get errOtpUsed =>
      'यह OTP पहले ही इस्तेमाल हो चुका है। कृपया नया OTP मँगवाएँ।';

  @override
  String get errOtpTooMany => 'बहुत अधिक गलत कोशिशें। कृपया नया OTP मँगवाएँ।';

  @override
  String get errOtpNotRequested => 'कृपया पहले OTP मँगवाएँ।';

  @override
  String errCooldown(String seconds) {
    return 'दूसरा OTP माँगने से पहले कृपया $seconds सेकंड रुकें।';
  }

  @override
  String get sessionExpiredBanner =>
      'आपका सत्र समाप्त हो गया। कृपया फिर साइन इन करें।';
}

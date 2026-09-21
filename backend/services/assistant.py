"""My PDS Assistant: explains the authenticated beneficiary's own records.

Design (see docs/AI_ARCHITECTURE.md): BENEFICIARY DATA -> CONTEXT -> EXPLANATION -> BENEFICIARY.
- It is rule-based, not generative, so every number in an answer is read from the database at request time.
- It never writes to entitlement, intents, allocations or any authoritative record. The only write is one
  advisory row in ai_predictions (intent key + model version, never the question text) for auditability.
- Answers come in the caller's language (en / hi / kn). Unknown questions get a help message, never a guess.
"""
from __future__ import annotations

import re
import uuid
from datetime import date

from backend.services import beneficiary as svc

MODEL_VERSION = "rule-assistant-v1"
LANGS = ("en", "hi", "kn")

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "kn": ["ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್", "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್"],
}
UNAVAILABLE = {"en": "Data unavailable", "hi": "जानकारी उपलब्ध नहीं", "kn": "ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ"}

# Order matters: the first intent whose pattern matches wins.
PATTERNS = [
    ("CANT_SUBMIT", r"why.*(can'?t|cannot|unable|not able|won'?t)|cannot submit|can'?t submit|unable to submit|"
                    r"क्यों नहीं|जमा नहीं|सबमिट नहीं|नहीं कर पा|ಸಲ್ಲಿಸಲು ಆಗ|ಯಾಕೆ.*ಆಗ|ಸಾಧ್ಯವಾಗ"),
    ("DISPATCH", r"dispatch|truck|reach|arriv|deliver|transit|where is|track|receiv|"
                 r"भेज|ट्रक|पहुं|पहुँ|मिला|ट्रैक|ರವಾನ|ಲಾರಿ|ತಲುಪ|ಟ್ರ್ಯಾಕ್|ಬಂದಿ"),
    ("WINDOW", r"\bwhen\b|window|deadline|last day|which date|what date|कब|तारीख|तिथि|खिड़की|अंतिम|ಯಾವಾಗ|ದಿನಾಂಕ|ಕೊನೆ"),
    ("REQUEST", r"request|intent|submitted|my plan|did i|what did i|अनुरोध|मैंने|योजना|ವಿನಂತಿ|ಯೋಜನೆ|ಸಲ್ಲಿಸಿ"),
    ("FPS", r"\bfps\b|shop|assigned|which store|location|दुकान|एफपीएस|कौन सी|ಅಂಗಡಿ|ನ್ಯಾಯಬೆಲೆ"),
    ("ENTITLEMENT", r"entitle|how much|remain|\bleft\b|quota|amount|\bkg\b|collect|कितना|पात्रता|बाकी|शेष|राशन|ಎಷ್ಟು|ಅರ್ಹತೆ|ಉಳಿ"),
]

STAGE_TEXT = {
    "en": {"INTENT_SUBMITTED": "your plan is recorded; the demand is not locked yet",
           "DEMAND_PLANNED": "the demand for your area is planned",
           "ALLOCATED": "stock has been allocated to your shop",
           "DISPATCHED": "your shop's ration has been dispatched",
           "IN_TRANSIT": "your shop's ration is on the way",
           "RECEIVED_AT_FPS": "the ration has reached your shop",
           "AVAILABLE_FOR_COLLECTION": "the ration is available for collection at your shop",
           "COLLECTED": "you have collected your ration",
           "NONE": "nothing has been dispatched yet for this cycle",
           "CHOICE_WINDOW_CLOSED": "you did not submit a plan and the choice window is closed"},
    "hi": {"INTENT_SUBMITTED": "आपकी योजना दर्ज है; मांग अभी लॉक नहीं हुई है",
           "DEMAND_PLANNED": "आपके क्षेत्र की मांग तय हो गई है",
           "ALLOCATED": "आपकी दुकान के लिए स्टॉक आवंटित हो गया है",
           "DISPATCHED": "आपकी दुकान का राशन भेज दिया गया है",
           "IN_TRANSIT": "आपकी दुकान का राशन रास्ते में है",
           "RECEIVED_AT_FPS": "राशन आपकी दुकान पर पहुँच गया है",
           "AVAILABLE_FOR_COLLECTION": "राशन आपकी दुकान पर लेने के लिए उपलब्ध है",
           "COLLECTED": "आपने अपना राशन ले लिया है",
           "NONE": "इस चक्र के लिए अभी कुछ नहीं भेजा गया है",
           "CHOICE_WINDOW_CLOSED": "आपने योजना जमा नहीं की और विकल्प की अवधि बंद हो गई है"},
    "kn": {"INTENT_SUBMITTED": "ನಿಮ್ಮ ಯೋಜನೆ ದಾಖಲಾಗಿದೆ; ಬೇಡಿಕೆ ಇನ್ನೂ ಲಾಕ್ ಆಗಿಲ್ಲ",
           "DEMAND_PLANNED": "ನಿಮ್ಮ ಪ್ರದೇಶದ ಬೇಡಿಕೆ ನಿಗದಿಯಾಗಿದೆ",
           "ALLOCATED": "ನಿಮ್ಮ ಅಂಗಡಿಗೆ ಸ್ಟಾಕ್ ಹಂಚಿಕೆಯಾಗಿದೆ",
           "DISPATCHED": "ನಿಮ್ಮ ಅಂಗಡಿಯ ಪಡಿತರ ರವಾನೆಯಾಗಿದೆ",
           "IN_TRANSIT": "ನಿಮ್ಮ ಅಂಗಡಿಯ ಪಡಿತರ ದಾರಿಯಲ್ಲಿದೆ",
           "RECEIVED_AT_FPS": "ಪಡಿತರ ನಿಮ್ಮ ಅಂಗಡಿಗೆ ತಲುಪಿದೆ",
           "AVAILABLE_FOR_COLLECTION": "ಪಡಿತರ ನಿಮ್ಮ ಅಂಗಡಿಯಲ್ಲಿ ಪಡೆಯಲು ಲಭ್ಯವಿದೆ",
           "COLLECTED": "ನೀವು ನಿಮ್ಮ ಪಡಿತರವನ್ನು ಪಡೆದಿದ್ದೀರಿ",
           "NONE": "ಈ ಚಕ್ರಕ್ಕೆ ಇನ್ನೂ ಏನೂ ರವಾನೆಯಾಗಿಲ್ಲ",
           "CHOICE_WINDOW_CLOSED": "ನೀವು ಯೋಜನೆ ಸಲ್ಲಿಸಿಲ್ಲ ಮತ್ತು ಆಯ್ಕೆ ಅವಧಿ ಮುಗಿದಿದೆ"},
}

T = {
    "en": {
        "ENTITLEMENT": "In {cycle} you are entitled to {rice} kg rice and {wheat} kg wheat ({total} kg in all). {collected} kg has been collected so far, so {remaining} kg remains.",
        "WINDOW_OPEN": "The choice window for {cycle} is open from {start} to {end}. Plan your collection in the app before it closes.",
        "WINDOW_CLOSED": "The choice window for {cycle} is closed (it ran from {start} to {end}).",
        "REQUEST": "For {cycle} you asked to collect {rice} kg rice and {wheat} kg wheat ({total} kg) at {fps}. Your reference is {ref}.",
        "NO_REQUEST": "You have not submitted a collection plan for {cycle}.",
        "DISPATCH": "For {cycle}: {stage}.",
        "FPS": "Your fair price shop is {fps} ({fps_id}) in {taluk}, {district}. Opening hours: {hours}.",
        "CANT_CLOSED": "The choice window for {cycle} is closed, so new plans cannot be submitted.",
        "CANT_DUP": "You have already submitted a plan ({ref}). Only one plan is allowed per cycle. While the window is open you can cancel it and submit a new one.",
        "CANT_ZERO": "You have no remaining entitlement in {cycle}, so there is nothing left to plan.",
        "CANT_FPS": "Your current fair price shop ({fps}) is not active. Choose another shop in your district while planning.",
        "CANT_OK": "Nothing is blocking you. You can plan your collection for {cycle} now.",
        "NO_CYCLE": "There is no active cycle right now.",
        "HELP": "I can explain your entitlement, the collection window, what you requested, where your ration is, your fair price shop, or why you cannot submit. Try one of the suggestions.",
        "DISCLAIMER": "This explains your records. It cannot change your entitlement or approve anything.",
    },
    "hi": {
        "ENTITLEMENT": "{cycle} में आप {rice} किग्रा चावल और {wheat} किग्रा गेहूँ (कुल {total} किग्रा) के पात्र हैं। अब तक {collected} किग्रा लिया जा चुका है, इसलिए {remaining} किग्रा बाकी है।",
        "WINDOW_OPEN": "{cycle} के लिए विकल्प की अवधि {start} से {end} तक खुली है। बंद होने से पहले ऐप में अपना संग्रह चुनें।",
        "WINDOW_CLOSED": "{cycle} के लिए विकल्प की अवधि बंद हो चुकी है (यह {start} से {end} तक थी)।",
        "REQUEST": "{cycle} के लिए आपने {fps} पर {rice} किग्रा चावल और {wheat} किग्रा गेहूँ (कुल {total} किग्रा) लेने का अनुरोध किया है। आपका संदर्भ {ref} है।",
        "NO_REQUEST": "आपने {cycle} के लिए संग्रह योजना जमा नहीं की है।",
        "DISPATCH": "{cycle} के लिए: {stage}।",
        "FPS": "आपकी उचित मूल्य की दुकान {fps} ({fps_id}), {taluk}, {district} में है। खुलने का समय: {hours}।",
        "CANT_CLOSED": "{cycle} के लिए विकल्प की अवधि बंद है, इसलिए नई योजना जमा नहीं हो सकती।",
        "CANT_DUP": "आप पहले ही योजना ({ref}) जमा कर चुके हैं। हर चक्र में केवल एक योजना मान्य है। अवधि खुली रहने तक आप उसे रद्द करके नई जमा कर सकते हैं।",
        "CANT_ZERO": "{cycle} में आपकी कोई पात्रता शेष नहीं है, इसलिए योजना बनाने को कुछ नहीं है।",
        "CANT_FPS": "आपकी वर्तमान दुकान ({fps}) सक्रिय नहीं है। योजना बनाते समय अपने जिले की कोई दूसरी दुकान चुनें।",
        "CANT_OK": "आपको कोई रोक नहीं रही है। आप अभी {cycle} के लिए अपना संग्रह चुन सकते हैं।",
        "NO_CYCLE": "अभी कोई सक्रिय चक्र नहीं है।",
        "HELP": "मैं आपकी पात्रता, संग्रह की अवधि, आपके अनुरोध, राशन कहाँ है, आपकी दुकान, या जमा न हो पाने का कारण समझा सकता हूँ। कोई सुझाव चुनें।",
        "DISCLAIMER": "यह आपके रिकॉर्ड समझाता है। यह आपकी पात्रता नहीं बदल सकता और कुछ मंज़ूर नहीं कर सकता।",
    },
    "kn": {
        "ENTITLEMENT": "{cycle} ರಲ್ಲಿ ನೀವು {rice} ಕೆಜಿ ಅಕ್ಕಿ ಮತ್ತು {wheat} ಕೆಜಿ ಗೋಧಿ (ಒಟ್ಟು {total} ಕೆಜಿ) ಪಡೆಯಲು ಅರ್ಹರು. ಇದುವರೆಗೆ {collected} ಕೆಜಿ ಪಡೆದಿದ್ದೀರಿ, ಆದ್ದರಿಂದ {remaining} ಕೆಜಿ ಉಳಿದಿದೆ.",
        "WINDOW_OPEN": "{cycle} ಗಾಗಿ ಆಯ್ಕೆ ಅವಧಿ {start} ರಿಂದ {end} ವರೆಗೆ ತೆರೆದಿದೆ. ಮುಗಿಯುವ ಮೊದಲು ಆ್ಯಪ್‌ನಲ್ಲಿ ನಿಮ್ಮ ಸಂಗ್ರಹವನ್ನು ಯೋಜಿಸಿ.",
        "WINDOW_CLOSED": "{cycle} ಗಾಗಿ ಆಯ್ಕೆ ಅವಧಿ ಮುಗಿದಿದೆ ({start} ರಿಂದ {end} ವರೆಗೆ ಇತ್ತು).",
        "REQUEST": "{cycle} ಗಾಗಿ ನೀವು {fps} ನಲ್ಲಿ {rice} ಕೆಜಿ ಅಕ್ಕಿ ಮತ್ತು {wheat} ಕೆಜಿ ಗೋಧಿ (ಒಟ್ಟು {total} ಕೆಜಿ) ಪಡೆಯಲು ವಿನಂತಿಸಿದ್ದೀರಿ. ನಿಮ್ಮ ಉಲ್ಲೇಖ {ref}.",
        "NO_REQUEST": "ನೀವು {cycle} ಗಾಗಿ ಸಂಗ್ರಹ ಯೋಜನೆಯನ್ನು ಸಲ್ಲಿಸಿಲ್ಲ.",
        "DISPATCH": "{cycle} ಗಾಗಿ: {stage}.",
        "FPS": "ನಿಮ್ಮ ನ್ಯಾಯಬೆಲೆ ಅಂಗಡಿ {fps} ({fps_id}), {taluk}, {district}. ಸಮಯ: {hours}.",
        "CANT_CLOSED": "{cycle} ಗಾಗಿ ಆಯ್ಕೆ ಅವಧಿ ಮುಗಿದಿದೆ, ಆದ್ದರಿಂದ ಹೊಸ ಯೋಜನೆ ಸಲ್ಲಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ.",
        "CANT_DUP": "ನೀವು ಈಗಾಗಲೇ ಯೋಜನೆ ({ref}) ಸಲ್ಲಿಸಿದ್ದೀರಿ. ಪ್ರತಿ ಚಕ್ರಕ್ಕೆ ಒಂದೇ ಯೋಜನೆ ಅನುಮತಿ. ಅವಧಿ ತೆರೆದಿರುವಾಗ ಅದನ್ನು ರದ್ದುಮಾಡಿ ಹೊಸದನ್ನು ಸಲ್ಲಿಸಬಹುದು.",
        "CANT_ZERO": "{cycle} ರಲ್ಲಿ ನಿಮಗೆ ಉಳಿದ ಅರ್ಹತೆ ಇಲ್ಲ, ಆದ್ದರಿಂದ ಯೋಜಿಸಲು ಏನೂ ಇಲ್ಲ.",
        "CANT_FPS": "ನಿಮ್ಮ ಪ್ರಸ್ತುತ ಅಂಗಡಿ ({fps}) ಸಕ್ರಿಯವಾಗಿಲ್ಲ. ಯೋಜಿಸುವಾಗ ನಿಮ್ಮ ಜಿಲ್ಲೆಯ ಬೇರೆ ಅಂಗಡಿಯನ್ನು ಆಯ್ಕೆಮಾಡಿ.",
        "CANT_OK": "ನಿಮ್ಮನ್ನು ಯಾವುದೂ ತಡೆಯುತ್ತಿಲ್ಲ. ನೀವು ಈಗ {cycle} ಗಾಗಿ ಸಂಗ್ರಹವನ್ನು ಯೋಜಿಸಬಹುದು.",
        "NO_CYCLE": "ಈಗ ಯಾವುದೇ ಸಕ್ರಿಯ ಚಕ್ರ ಇಲ್ಲ.",
        "HELP": "ನಾನು ನಿಮ್ಮ ಅರ್ಹತೆ, ಸಂಗ್ರಹ ಅವಧಿ, ನೀವು ವಿನಂತಿಸಿದ್ದು, ಪಡಿತರ ಎಲ್ಲಿದೆ, ನಿಮ್ಮ ಅಂಗಡಿ, ಅಥವಾ ಸಲ್ಲಿಸಲು ಆಗದ ಕಾರಣವನ್ನು ವಿವರಿಸಬಲ್ಲೆ. ಒಂದು ಸಲಹೆಯನ್ನು ಆರಿಸಿ.",
        "DISCLAIMER": "ಇದು ನಿಮ್ಮ ದಾಖಲೆಗಳನ್ನು ವಿವರಿಸುತ್ತದೆ. ಇದು ನಿಮ್ಮ ಅರ್ಹತೆಯನ್ನು ಬದಲಾಯಿಸಲು ಅಥವಾ ಯಾವುದನ್ನೂ ಅನುಮೋದಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ.",
    },
}

SOURCES = {
    "ENTITLEMENT": "beneficiaries + epos_transactions", "WINDOW": "cycles", "REQUEST": "intent_signals",
    "DISPATCH": "cycles + allocations + dispatch_manifests + delivery_history + epos_transactions",
    "FPS": "beneficiaries + fps", "CANT_SUBMIT": "cycles + intent_signals + epos_transactions + fps", "HELP": None,
}
VIEWS = {"ENTITLEMENT": "entitlement", "WINDOW": "cycle", "REQUEST": "history", "DISPATCH": "track", "FPS": "profile",
         "CANT_SUBMIT": "plan", "HELP": None}


def classify(question: str) -> str:
    q = question.lower()
    for key, pattern in PATTERNS:
        if re.search(pattern, q):
            return key
    return "HELP"


def _cycle_label(cycle: str, lang: str) -> str:
    return f"{MONTHS[lang][int(cycle[5:7]) - 1]} {cycle[:4]}"


def _d(iso_date: str | None, lang: str) -> str:
    if not iso_date:
        return UNAVAILABLE[lang]
    d = date.fromisoformat(iso_date)
    return f"{d.day} {MONTHS[lang][d.month - 1][:3] if lang == 'en' else MONTHS[lang][d.month - 1]}"


def answer(conn, beneficiary_id: str, question: str | None, intent: str | None, lang: str) -> dict:
    lang = lang if lang in LANGS else "en"
    key = intent if intent in dict(PATTERNS) or intent == "HELP" else classify(question or "")
    t = T[lang]
    profile = svc.get_profile(conn, beneficiary_id)
    cyc = svc.get_cycle(conn)
    facts: dict = {"cycle": cyc["cycle"] if cyc else None}
    text = t["HELP"] if key == "HELP" else None

    if cyc is None and key != "HELP":
        key, text = "HELP", t["NO_CYCLE"]
    elif key != "HELP":
        label = _cycle_label(cyc["cycle"], lang)
        ent = svc.get_entitlement(conn, beneficiary_id, cyc["cycle"])
        intent_row = svc.live_intent(conn, beneficiary_id, cyc["cycle"])
        fps = profile["fps"]
        if key == "ENTITLEMENT":
            facts.update(rice_kg=ent["rice_kg"], wheat_kg=ent["wheat_kg"], total_kg=ent["total_kg"],
                         collected_kg=ent["collected_total_kg"], remaining_kg=ent["remaining_total_kg"])
            text = t["ENTITLEMENT"].format(cycle=label, rice=ent["rice_kg"], wheat=ent["wheat_kg"], total=ent["total_kg"],
                                           collected=ent["collected_total_kg"], remaining=ent["remaining_total_kg"])
        elif key == "WINDOW":
            facts.update(window_open=cyc["window_open"], start=cyc["choice_window_start"], end=cyc["choice_window_end"])
            text = t["WINDOW_OPEN" if cyc["window_open"] else "WINDOW_CLOSED"].format(
                cycle=label, start=_d(cyc["choice_window_start"], lang), end=_d(cyc["choice_window_end"], lang))
        elif key == "REQUEST":
            if intent_row:
                facts.update(reference=intent_row["intent_id"], rice_kg=intent_row["rice_quantity_kg"],
                             wheat_kg=intent_row["wheat_quantity_kg"], fps_id=intent_row["fps_id"])
                name = svc.one(conn, "SELECT fps_name FROM fps WHERE fps_id = %s", (intent_row["fps_id"],))["fps_name"]
                text = t["REQUEST"].format(cycle=label, rice=intent_row["rice_quantity_kg"], wheat=intent_row["wheat_quantity_kg"],
                                           total=intent_row["total_quantity_kg"], fps=name, ref=intent_row["intent_id"])
            else:
                facts["reference"] = None
                text = t["NO_REQUEST"].format(cycle=label)
        elif key == "DISPATCH":
            journey = svc.get_journey(conn, beneficiary_id, cyc["cycle"])
            stage_key = journey["headline"] or "NONE"
            facts.update(stage=stage_key)
            text = t["DISPATCH"].format(cycle=label, stage=STAGE_TEXT[lang].get(stage_key, STAGE_TEXT[lang]["NONE"]))
        elif key == "FPS":
            facts.update(fps_id=fps["fps_id"], fps_name=fps["name"])
            text = t["FPS"].format(fps=fps["name"], fps_id=fps["fps_id"], taluk=fps["taluk"], district=fps["district"],
                                   hours=fps["opening_hours"] or UNAVAILABLE[lang])
        elif key == "CANT_SUBMIT":
            if not cyc["window_open"]:
                facts["reason"] = "CHOICE_WINDOW_CLOSED"
                text = t["CANT_CLOSED"].format(cycle=label)
            elif intent_row:
                facts.update(reason="INTENT_DUPLICATE", reference=intent_row["intent_id"])
                text = t["CANT_DUP"].format(ref=intent_row["intent_id"])
            elif ent["remaining_total_kg"] <= 0:
                facts["reason"] = "NO_REMAINING_ENTITLEMENT"
                text = t["CANT_ZERO"].format(cycle=label)
            elif fps["status"] != "ACTIVE":
                facts.update(reason="FPS_NOT_ACTIVE", fps_id=fps["fps_id"])
                text = t["CANT_FPS"].format(fps=fps["name"])
            else:
                facts["reason"] = "NONE"
                text = t["CANT_OK"].format(cycle=label)

    conn.execute(
        """INSERT INTO ai_predictions (prediction_id, service, cycle, entity_type, entity_id, prediction, reason, supporting_data,
                                       model_version) VALUES (%s, 'beneficiary_assistant', %s, 'BENEFICIARY', %s, %s, %s, %s, %s)""",
        ("AIP-" + uuid.uuid4().hex[:12].upper(), cyc["cycle"] if cyc else None, beneficiary_id,
         '{"intent": "%s"}' % key, "Rule-based explanation of the beneficiary's own records", "{}", MODEL_VERSION))
    return {"answer": text, "intent": key, "language": lang, "facts": facts, "source": SOURCES.get(key), "view": VIEWS.get(key),
            "model": MODEL_VERSION, "generative": False, "disclaimer": t["DISCLAIMER"]}


# ------------------------------------------------------------------ grievance assistance (advisory only)

CATEGORY_HINTS = [
    ("TRANSACTION_FAILURE", r"transaction|biometric|finger|thumb|e-?pos|machine|server|receipt|failed|पॉस|मशीन|अंगूठा|बायोमेट्रिक|ಯಂತ್ರ|ಬೆರಳಚ್ಚು|ರಸೀದಿ"),
    ("SHORT_DELIVERY", r"short|less|missing|not full|incomplete|कम|अधूरा|ಕಡಿಮೆ|ಅಪೂರ್ಣ"),
    ("WRONG_QUANTITY", r"wrong quantity|weigh|weight|scale|tola|quantity|वजन|तौल|मात्रा|ತೂಕ|ಪ್ರಮಾಣ"),
    ("QUALITY", r"quality|rotten|stone|dirty|smell|insect|bad rice|spoil|खराब|गंदा|सड़|ಗುಣಮಟ್ಟ|ಕೆಟ್ಟ|ಕೊಳೆ"),
    ("FPS_ISSUE", r"closed|not open|dealer|rude|behav|shop|बंद|दुकान|डीलर|ಮುಚ್ಚ|ಅಂಗಡಿ|ಡೀಲರ್"),
    ("COLLECTION_ISSUE", r"refus|denied|not given|didn'?t give|queue|waiting|turned away|नहीं दिया|मना|कतार|ನಿರಾಕರ|ಕೊಟ್ಟಿಲ್ಲ|ಸಾಲು"),
    ("ENTITLEMENT_QUERY", r"entitle|household|member|how much|card|पात्रता|सदस्य|ಅರ್ಹತೆ|ಸದಸ್ಯ"),
]
NEEDS_TRANSACTION = {"TRANSACTION_FAILURE", "SHORT_DELIVERY", "WRONG_QUANTITY", "COLLECTION_ISSUE"}


def suggest_grievance(conn, beneficiary_id: str, description: str) -> dict:
    """Advisory only: proposes a category and the beneficiary's own recent transactions. Writes nothing;
    the beneficiary reviews and confirms before anything is submitted."""
    text = description.lower()
    scored = [(len(re.findall(p, text)), k) for k, p in CATEGORY_HINTS]
    hits, best = max(scored, key=lambda s: s[0])
    category = best if hits else "OTHER"
    related = []
    if category in NEEDS_TRANSACTION:
        related = svc.rows(conn, """SELECT t.transaction_id, t.cycle, t.commodity, t.quantity_kg, t.status, t.transaction_time AS at,
                                           f.fps_name AS fps_name
                                    FROM epos_transactions t JOIN fps f USING (fps_id) WHERE t.beneficiary_id = %s
                                    ORDER BY t.transaction_time DESC LIMIT 3""", (beneficiary_id,))
    return {"category": category, "confidence": min(90, 35 + 20 * hits) if hits else 0,
            "reason": "Matched keywords in your description" if hits else "No category keywords found",
            "summary": " ".join(description.split())[:140], "related_transactions": related,
            "model": MODEL_VERSION, "generative": False, "requires_confirmation": True}

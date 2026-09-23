"""Beneficiary service API. Identity comes only from the authenticated token; no endpoint accepts a beneficiary id.
Every record is read from and written to PostgreSQL. Ownership is enforced in the SQL of each service call."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.core.audit import write_audit
from backend.core.auth_middleware import require_role
from backend.core.errors import ApiError
from backend.core.rbac import Role
from backend.db.conn import get_db
from backend.services import assistant, beneficiary as svc
from backend.services import workflow as wf

router = APIRouter(prefix="/api/v1", tags=["beneficiary"])
Beneficiary = Depends(require_role(Role.BENEFICIARY))


class IntentRequest(BaseModel):
    fps_id: str
    rice_quantity_kg: int
    wheat_quantity_kg: int
    collection_mode: str = "SELF"
    cycle: str | None = None  # defaults to the current cycle


class GrievanceRequest(BaseModel):
    category: str
    description: str
    fps_id: str | None = None
    cycle: str | None = None
    related_transaction_id: str | None = None


class AssistantRequest(BaseModel):
    question: str | None = None
    intent: str | None = None  # a tapped suggestion chip
    language: str = "en"


class SuggestRequest(BaseModel):
    description: str


# ------------------------------------------------------------------ profile, cycle, entitlement, home

@router.get("/beneficiaries/me")
def me(user=Beneficiary, conn=Depends(get_db)):
    return svc.get_profile(conn, user["beneficiary_id"])


@router.get("/cycles/current")
def current_cycle(user=Beneficiary, conn=Depends(get_db)):
    c = svc.get_cycle(conn)
    if c is None:
        raise ApiError(404, "NO_ACTIVE_CYCLE", "There is no active cycle right now.")
    return c


@router.get("/cycles")
def list_cycles(user=Beneficiary, conn=Depends(get_db)):
    """All cycles the beneficiary may view — for the month selector. No fake months are ever synthesised."""
    return {"cycles": svc.list_cycles(conn)}


@router.get("/beneficiaries/me/entitlement")
def entitlement(cycle: str | None = None, user=Beneficiary, conn=Depends(get_db)):
    c = svc.get_cycle(conn, cycle)
    if c is None:
        raise ApiError(404, "NO_ACTIVE_CYCLE", "There is no active cycle right now.")
    return svc.get_entitlement(conn, user["beneficiary_id"], c["cycle"])


@router.get("/beneficiaries/me/home")
def home(user=Beneficiary, conn=Depends(get_db)):
    """Everything the service home needs in one round trip. Notices are codes; the app words them in the user's language."""
    bid = user["beneficiary_id"]
    profile = svc.get_profile(conn, bid)
    cyc = svc.get_cycle(conn)
    out = {**profile, "cycle": cyc, "entitlement": None, "intent": None, "status_key": None, "notice": None}
    if cyc is None:
        out["notice"] = {"code": "NO_CYCLE", "params": {}}
        return out
    out["entitlement"] = svc.get_entitlement(conn, bid, cyc["cycle"])
    intent = svc.live_intent(conn, bid, cyc["cycle"])
    journey = svc.get_journey(conn, bid, cyc["cycle"])
    done = {s["key"] for s in journey["steps"] if s["status"] == "DONE"}
    if intent:
        out["intent"] = svc.receipt_view(conn, intent, cyc["window_open"])
        out["status_key"] = journey["headline"]
        received_not_collected = "RECEIVED_AT_FPS" in done and "COLLECTED" not in done
        out["notice"] = {"code": "RATION_AT_FPS" if received_not_collected else "INTENT_RECORDED",
                         "params": {"reference": intent["intent_id"]}}
    elif cyc["window_open"]:
        out["status_key"] = "CHOICE_WINDOW_OPEN"
        if profile["fps"]["status"] != "ACTIVE":
            out["notice"] = {"code": "FPS_NOT_ACTIVE", "params": {"fps": profile["fps"]["name"]}}
        else:
            out["notice"] = {"code": "PLAN_NOW", "params": {"closes": cyc["choice_window_end"]}}
    else:
        out["status_key"] = "CHOICE_WINDOW_CLOSED"
        out["notice"] = {"code": "WINDOW_CLOSED_NO_INTENT", "params": {}}
    return out


@router.get("/fps/eligible")
def fps_eligible(limit: int = Query(25, ge=1, le=50), user=Beneficiary, conn=Depends(get_db)):
    return {"fps": svc.eligible_fps(conn, user["beneficiary_id"], limit)}


# ------------------------------------------------------------------ collection intent

@router.post("/preferences", status_code=201)
def submit_intent(req: IntentRequest, user=Beneficiary, conn=Depends(get_db)):
    bid = user["beneficiary_id"]
    receipt = svc.submit_intent(conn, bid, req.fps_id, req.rice_quantity_kg, req.wheat_quantity_kg, req.collection_mode, req.cycle)
    conn.commit()  # the record exists before it is audited
    write_audit(bid, "BENEFICIARY", "PREFERENCE_SUBMITTED", "SUCCESS", f"{receipt['total_kg']} kg at {receipt['fps']['fps_id']}",
                "INTENT", receipt["reference"], receipt["cycle"])
    wf.emit(conn, cycle=receipt["cycle"], event_type="BENEFICIARY_INTENT_SUBMITTED",
            source_role="BENEFICIARY", target_role="DSO", entity_type="INTENT",
            entity_id=receipt["reference"], created_by=bid,
            payload={"fps_id": receipt["fps"]["fps_id"], "total_kg": receipt["total_kg"]})
    conn.commit()
    return receipt


@router.get("/preferences/me")
def my_preferences(cycle: str | None = None, user=Beneficiary, conn=Depends(get_db)):
    items = svc.history(conn, user["beneficiary_id"], "intents", 100, 0)
    return {"intents": [i for i in items if cycle is None or i["cycle"] == cycle]}


@router.get("/preferences/{reference}/receipt")
def intent_receipt(reference: str, user=Beneficiary, conn=Depends(get_db)):
    return svc.get_receipt(conn, user["beneficiary_id"], reference)


@router.post("/preferences/{reference}/cancel")
def cancel_intent(reference: str, user=Beneficiary, conn=Depends(get_db)):
    receipt = svc.cancel_intent(conn, user["beneficiary_id"], reference)
    conn.commit()
    write_audit(user["beneficiary_id"], "BENEFICIARY", "PREFERENCE_CANCELLED", "SUCCESS", "cancelled while the choice window was open",
                "INTENT", reference, receipt["cycle"])
    return receipt


# ------------------------------------------------------------------ tracking, history, receipts

@router.get("/tracking/me")
def tracking(cycle: str | None = None, user=Beneficiary, conn=Depends(get_db)):
    c = svc.get_cycle(conn, cycle)
    if c is None:
        raise ApiError(404, "NO_ACTIVE_CYCLE", "There is no active cycle right now.")
    return svc.get_journey(conn, user["beneficiary_id"], c["cycle"])


@router.get("/notifications/me")
def notifications(cycle: str | None = None, user=Beneficiary, conn=Depends(get_db)):
    return {"notifications": svc.notifications(conn, user["beneficiary_id"], cycle)}


@router.get("/history/me")
def history(kind: str = "collections", limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
            user=Beneficiary, conn=Depends(get_db)):
    return {"kind": kind, "items": svc.history(conn, user["beneficiary_id"], kind, limit, offset)}


@router.get("/transactions/{transaction_id}/receipt")
def digital_receipt(transaction_id: str, user=Beneficiary, conn=Depends(get_db)):
    return svc.transaction_receipt(conn, user["beneficiary_id"], transaction_id)


# ------------------------------------------------------------------ grievances

@router.post("/grievances", status_code=201)
def submit_grievance(req: GrievanceRequest, user=Beneficiary, conn=Depends(get_db)):
    bid = user["beneficiary_id"]
    g = svc.create_grievance(conn, bid, req.category, req.description, req.fps_id, req.cycle, req.related_transaction_id)
    conn.commit()
    write_audit(bid, "BENEFICIARY", "GRIEVANCE_SUBMITTED", "SUCCESS", g["category"], "GRIEVANCE", g["grievance_id"], g["cycle"])
    return g


@router.get("/grievances/me")
def my_grievances(user=Beneficiary, conn=Depends(get_db)):
    return {"grievances": svc.list_grievances(conn, user["beneficiary_id"])}


# ------------------------------------------------------------------ AI (advisory, read-only)

@router.post("/ai/assistant")
def ask_assistant(req: AssistantRequest, user=Beneficiary, conn=Depends(get_db)):
    if not (req.question and req.question.strip()) and not req.intent:
        raise ApiError(422, "EMPTY_QUESTION", "Type a question or pick a suggestion.")
    return assistant.answer(conn, user["beneficiary_id"], (req.question or "")[:300], req.intent, req.language)


@router.post("/ai/grievance-suggest")
def grievance_suggest(req: SuggestRequest, user=Beneficiary, conn=Depends(get_db)):
    if len(req.description.strip()) < 5:
        raise ApiError(422, "INVALID_DESCRIPTION", "Please describe the issue first.")
    return assistant.suggest_grievance(conn, user["beneficiary_id"], req.description[:500])

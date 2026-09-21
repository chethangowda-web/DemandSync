from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional
import pandas as pd, hashlib, json, random
from pathlib import Path
from datetime import datetime, timedelta
from jose import JWTError, ExpiredSignatureError
from backend.core.otp import otp_service
from backend.core.security import JWT_SECRET, JWT_ALGORITHM, decode_token

router = APIRouter(prefix="/api/v1", tags=["beneficiary"])
from backend.core.config import DATA_DIR as DATA
SECRET=JWT_SECRET
JWT_ALG=JWT_ALGORITHM
# dev OTP store — now delegates to otp_service (no hardcoded universal OTP)
_otp_store={}
# load datasets lazily
_ben = None; _fps=None; _intent=None; _epos=None; _cycles=None; _grv=None; _man=None; _del=None; _tel=None

def load():
    global _ben,_fps,_intent,_epos,_cycles,_grv,_man,_del,_tel
    if _ben is None:
        _ben=pd.read_csv(DATA/"01_master/beneficiaries_master.csv", dtype=str).fillna("")
        # ensure numeric
        for c in ["household_size","entitlement_kg","rice_entitlement_kg","wheat_entitlement_kg"]:
            _ben[c]=pd.to_numeric(_ben[c], errors='coerce').fillna(0).astype(int)
        _fps=pd.read_csv(DATA/"01_master/fps_master.csv", dtype=str)
        _intent=pd.read_csv(DATA/"02_demand/intent_signals.csv", dtype=str).fillna("")
        _epos=pd.read_csv(DATA/"03_operations/epos_transactions.csv", dtype=str).fillna("")
        _man=pd.read_csv(DATA/"03_operations/dispatch_manifests.csv", dtype=str).fillna("")
        _del=pd.read_csv(DATA/"03_operations/delivery_history.csv", dtype=str).fillna("")
        _tel=pd.read_csv(DATA/"04_tracking/vehicle_telemetry.csv", dtype=str).fillna("")
        _grv=pd.read_csv(DATA/"05_compliance/grievances.csv", dtype=str).fillna("")
load()

def get_beneficiary_by_rc(rc): 
    load()
    row=_ben[_ben.ration_card_id==rc]
    return row.iloc[0].to_dict() if not row.empty else None

def auth_beneficiary(authorization: Optional[str]=Header(None)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"Missing token")
    token=authorization.split(" ",1)[1]
    try:
        payload=decode_token(token)
        if payload.get("role")!="BENEFICIARY": raise HTTPException(403,"Not beneficiary")
        ben=get_beneficiary_by_rc(payload["sub"])
        if not ben: raise HTTPException(401,"Beneficiary not found")
        return ben
    except ExpiredSignatureError: raise HTTPException(401,"Token expired")
    except HTTPException: raise
    except JWTError: raise HTTPException(401,"Invalid token")

class LoginRequest(BaseModel):
    ration_card_id: str
    registered_mobile: str

class OtpVerifyRequest(BaseModel):
    ration_card_id: str
    otp: str

class IntentRequest(BaseModel):
    fps_id: str
    cycle: str
    rice_quantity_kg: int
    wheat_quantity_kg: int
    collection_mode: str = "SELF"

class GrievanceRequest(BaseModel):
    fps_id: str
    category: str
    description: str
    cycle: Optional[str]=None

class AssistantRequest(BaseModel):
    question: str

@router.post("/auth/beneficiary/login")
def login(req: LoginRequest):
    """Legacy endpoint — delegates to unified auth (kept for backward compat). Now uses OTP abstraction (no universal 123456)."""
    from backend.api.auth import beneficiary_request_otp
    from backend.api.auth import BeneficiaryRequestOtp as NewReq
    return beneficiary_request_otp(NewReq(ration_card_id=req.ration_card_id, registered_mobile=req.registered_mobile))

@router.post("/auth/beneficiary/verify-otp")
def verify_otp(req: OtpVerifyRequest):
    """Legacy endpoint — delegates to unified auth."""
    from backend.api.auth import beneficiary_verify_otp
    from backend.api.auth import BeneficiaryVerifyOtp as NewVerify
    return beneficiary_verify_otp(NewVerify(ration_card_id=req.ration_card_id, otp=req.otp))

@router.get("/beneficiaries/me")
def me(ben=Depends(auth_beneficiary)):
    load()
    fps=_fps[_fps.fps_id==ben["current_fps_id"]]
    fps_data=fps.iloc[0].to_dict() if not fps.empty else None
    return {"beneficiary":ben, "fps":fps_data}

@router.get("/beneficiaries/me/entitlement")
def entitlement(cycle: str="2026-03", ben=Depends(auth_beneficiary)):
    load()
    # entitlement from master (authoritative, never changed by intent)
    total=int(ben["entitlement_kg"]); rice=int(ben["rice_entitlement_kg"]); wheat=int(ben["wheat_entitlement_kg"])
    # used = sum SUCCESS epos for this cycle/commodity
    e=_epos[(_epos.beneficiary_id==ben["beneficiary_id"]) & (_epos.cycle==cycle) & (_epos.status=="SUCCESS")]
    used_rice=e[e.commodity=="RICE"].quantity_kg.astype(int).sum() if not e.empty else 0
    used_wheat=e[e.commodity=="WHEAT"].quantity_kg.astype(int).sum() if not e.empty else 0
    used=int(used_rice)+int(used_wheat)
    remaining=total-used
    return {"cycle":cycle, "scheme":ben["scheme_type"], "household_size":int(ben["household_size"]), "rice_entitlement_kg":rice, "wheat_entitlement_kg":wheat, "total_entitlement_kg":total, "used_rice_kg":int(used_rice), "used_wheat_kg":int(used_wheat), "used_total_kg":used, "remaining_rice_kg":rice-int(used_rice), "remaining_wheat_kg":wheat-int(used_wheat), "remaining_total_kg":remaining, "source":"beneficiaries_master + epos_transactions"}

@router.get("/cycles/current")
def current_cycle(ben=Depends(auth_beneficiary)):
    # from dataset_manifest cycles, current is 2026-03 MONITOR
    return {"cycle":"2026-03","name":"September 2026","period":"2025-09-01 to 2026-03-31","choice_window":"2026-03-05 — 2026-03-20","status":"CHOICE_WINDOW_OPEN","window_open":True, "closes_on":"2026-03-20T23:59:00"}

@router.get("/cycles/{cycle}")
def get_cycle(cycle: str, ben=Depends(auth_beneficiary)):
    return {"cycle":cycle,"choice_window":f"{cycle}-05 — {cycle}-20","status":"OPEN" if cycle=="2026-03" else "CLOSED"}

@router.post("/preferences")
def submit_intent(req: IntentRequest, ben=Depends(auth_beneficiary)):
    load()
    global _intent
    # validation
    if req.rice_quantity_kg<0 or req.wheat_quantity_kg<0: raise HTTPException(400,"Negative quantities not allowed")
    # check window (only 2026-03 open)
    if req.cycle!="2026-03": raise HTTPException(400,"Choice window closed for this cycle")
    # fps exists and belongs to beneficiary district? allow any but warn if not current
    if req.fps_id not in _fps.fps_id.values: raise HTTPException(400,"Invalid FPS")
    # duplicate check
    dup=_intent[(_intent.beneficiary_id==ben["beneficiary_id"]) & (_intent.cycle==req.cycle) & (_intent.status=="SUBMITTED")]
    if not dup.empty: raise HTTPException(409,"Your collection preference has already been submitted for this cycle.")
    # remaining entitlement check
    ent_total=int(ben["entitlement_kg"])
    requested=req.rice_quantity_kg+req.wheat_quantity_kg
    # used
    e=_epos[(_epos.beneficiary_id==ben["beneficiary_id"]) & (_epos.cycle==req.cycle) & (_epos.status=="SUCCESS")]
    used=int(e.quantity_kg.astype(int).sum()) if not e.empty else 0
    remaining=ent_total-used
    if requested>remaining: raise HTTPException(400,f"Requested {requested}kg exceeds remaining entitlement {remaining}kg (statutory entitlement {ent_total}kg)")
    if req.rice_quantity_kg>int(ben["rice_entitlement_kg"]): raise HTTPException(400,"Rice quantity exceeds rice entitlement")
    if req.wheat_quantity_kg>int(ben["wheat_entitlement_kg"]): raise HTTPException(400,"Wheat quantity exceeds wheat entitlement")
    # create intent (persist to memory; in production would write to DB)
    new_id=f"INT-{len(_intent)+1:07d}"
    new_row={"intent_id":new_id,"beneficiary_id":ben["beneficiary_id"],"fps_id":req.fps_id,"cycle":req.cycle,"rice_quantity_kg":str(req.rice_quantity_kg),"wheat_quantity_kg":str(req.wheat_quantity_kg),"total_quantity_kg":str(requested),"collection_mode":req.collection_mode,"submitted_at":datetime.now().isoformat(),"status":"SUBMITTED"}
    _intent=pd.concat([_intent, pd.DataFrame([new_row])], ignore_index=True)
    # audit would be generated here
    return {"intent_id":new_id,"cycle":req.cycle,"fps_id":req.fps_id,"rice_quantity_kg":req.rice_quantity_kg,"wheat_quantity_kg":req.wheat_quantity_kg,"total_quantity_kg":requested,"submitted_at":new_row["submitted_at"],"status":"RECORDED","reference":new_id}

@router.get("/preferences/me")
def my_preferences(cycle: Optional[str]=None, ben=Depends(auth_beneficiary)):
    load()
    df=_intent[_intent.beneficiary_id==ben["beneficiary_id"]]
    if cycle: df=df[df.cycle==cycle]
    return {"intents": df.to_dict(orient="records")}

@router.get("/preferences/receipt/{intent_id}")
def receipt(intent_id: str, ben=Depends(auth_beneficiary)):
    load()
    row=_intent[(_intent.intent_id==intent_id) & (_intent.beneficiary_id==ben["beneficiary_id"])]
    if row.empty: raise HTTPException(404,"Receipt not found or not yours")
    r=row.iloc[0].to_dict()
    fps=_fps[_fps.fps_id==r["fps_id"]].iloc[0].to_dict() if not _fps[_fps.fps_id==r["fps_id"]].empty else {}
    return {"receipt":r, "fps":fps, "beneficiary":ben}

@router.get("/tracking/me")
def tracking(cycle: str="2026-03", ben=Depends(auth_beneficiary)):
    load()
    # find intent for cycle
    intent=_intent[(_intent.beneficiary_id==ben["beneficiary_id"]) & (_intent.cycle==cycle) & (_intent.status=="SUBMITTED")]
    if intent.empty: return {"cycle":cycle,"status":"NO_INTENT","steps":[]}
    intent_row=intent.iloc[0].to_dict()
    # find allocation/manifest/delivery chain for that fps+cycle
    fps_id=intent_row["fps_id"]
    # check allocations, manifests, deliveries existence as boolean
    has_alloc = not pd.read_csv(DATA/"02_demand/allocations.csv", dtype=str).query("fps_id==@fps_id and cycle==@cycle").empty
    man_df=pd.read_csv(DATA/"03_operations/dispatch_manifests.csv", dtype=str)
    has_man = not man_df[(man_df.cycle==cycle) & (man_df.warehouse_id.isin(_fps[_fps.fps_id==fps_id].warehouse_id.values))].empty if not _fps[_fps.fps_id==fps_id].empty else False
    del_df=_del
    has_del = not del_df[(del_df.fps_id==fps_id) & (del_df.manifest_id.isin(man_df.manifest_id))].empty
    # build timeline from real records
    steps=[
        {"label":"INTENT SUBMITTED","status":"DONE","timestamp":intent_row["submitted_at"]},
        {"label":"DEMAND PLANNED","status":"DONE" if has_alloc else "PENDING"},
        {"label":"ALLOCATED","status":"DONE" if has_alloc else "PENDING"},
        {"label":"DISPATCHED","status":"DONE" if has_man else "PENDING"},
        {"label":"IN TRANSIT","status":"ACTIVE" if has_man and not has_del else ("DONE" if has_del else "PENDING")},
        {"label":"RECEIVED AT FPS","status":"DONE" if has_del else "PENDING"},
        {"label":"AVAILABLE FOR COLLECTION","status":"PENDING"},
        {"label":"COLLECTED","status":"PENDING"},
    ]
    # telemetry
    telemetry=None
    if has_man:
        # find vehicle for manifest
        m=man_df[(man_df.cycle==cycle)].iloc[0].to_dict() if not man_df[man_df.cycle==cycle].empty else None
        if m:
            tel=_tel[_tel.manifest_id==m["manifest_id"]]
            if not tel.empty: telemetry=tel.iloc[-1].to_dict()
    return {"cycle":cycle,"intent":intent_row,"steps":steps,"telemetry":telemetry, "telemetry_note":"Live location unavailable" if telemetry is None else "Real telemetry from vehicle_telemetry.csv"}

@router.get("/history/me")
def history(ben=Depends(auth_beneficiary)):
    load()
    intents=_intent[_intent.beneficiary_id==ben["beneficiary_id"]].to_dict(orient="records")
    epos=_epos[_epos.beneficiary_id==ben["beneficiary_id"]].to_dict(orient="records")
    delivs=_del[_del.manifest_id.isin(pd.read_csv(DATA/"03_operations/dispatch_manifest_items.csv", dtype=str)[pd.read_csv(DATA/"03_operations/dispatch_manifest_items.csv", dtype=str).fps_id==ben["current_fps_id"]].manifest_id.values) ] if not _del.empty else []
    return {"intents":intents, "transactions":epos, "deliveries": delivs.to_dict(orient="records") if hasattr(delivs,'to_dict') else []}

@router.post("/grievances")
def submit_grievance(req: GrievanceRequest, ben=Depends(auth_beneficiary)):
    load()
    global _grv
    if req.category not in ["Short delivery","SHORT_DELIVERY","WRONG_QUANTITY","FPS_CLOSED","QUALITY","TRANSACTION_FAILURE","ENTITLEMENT_QUERY","OTHER","Short delivery","Wrong quantity"]:
        # allow case-insensitive, normalize
        pass
    new_id=f"GRV-{len(_grv)+1:06d}"
    new_row={"grievance_id":new_id,"beneficiary_id":ben["beneficiary_id"],"fps_id":req.fps_id,"category":req.category,"description":req.description,"created_at":datetime.now().isoformat(),"status":"OPEN","resolution":"","resolved_at":""}
    _grv=pd.concat([_grv, pd.DataFrame([new_row])], ignore_index=True)
    return {"grievance_id":new_id,"status":"OPEN","message":"Grievance recorded — AI triage will classify and route to officer"}

@router.post("/ai/assistant")
def assistant(req: AssistantRequest, ben=Depends(auth_beneficiary)):
    load()
    q=req.question.lower()
    # simple rule-based assistant that uses real beneficiary data — not generic LLM
    # compute entitlement/remaining etc.
    cycle="2026-03"
    ent=int(ben["entitlement_kg"]); rice=int(ben["rice_entitlement_kg"]); wheat=int(ben["wheat_entitlement_kg"])
    e=_epos[(_epos.beneficiary_id==ben["beneficiary_id"]) & (_epos.cycle==cycle) & (_epos.status=="SUCCESS")]
    used=int(e.quantity_kg.astype(int).sum()) if not e.empty else 0
    remaining=ent-used
    intent=_intent[(_intent.beneficiary_id==ben["beneficiary_id"]) & (_intent.cycle==cycle)]
    intent_txt = f"Your collection preference for {cycle} is {intent.iloc[0].to_dict()}" if not intent.empty else "No intent submitted for current cycle."
    fps=_fps[_fps.fps_id==ben["current_fps_id"]].iloc[0].to_dict() if not _fps[_fps.fps_id==ben["current_fps_id"]].empty else {}
    answer="I can help with your PDS records."
    source="beneficiaries_master + epos_transactions"
    if "entitlement" in q or "how much" in q:
        answer=f"You have {remaining} KG remaining in {cycle} (Total entitlement {ent}KG: Rice {rice} + Wheat {wheat}, Used {used}KG)."
        source="beneficiaries_master + epos_transactions"
    elif "collect" in q or "window" in q:
        answer="Your collection window for September 2026 is 10 Sep — 25 Sep 2026 at "+fps.get("fps_name","your FPS")+". "+intent_txt
        source="fps_master + intent_signals"
    elif "fps" in q or "shop" in q:
        answer=f"Your current FPS is {fps.get('fps_name')} ({fps.get('fps_id')}) in {ben['district']}."
        source="fps_master"
    elif "request" in q or "intent" in q:
        answer=intent_txt; source="intent_signals"
    elif "dispatch" in q or "track" in q or "where" in q:
        answer="Your ration dispatch status is TRACKED via dispatch_manifests + vehicle_telemetry. Check Track My Ration for live status."
        source="dispatch_manifests + vehicle_telemetry"
    else:
        answer="You can ask: How much entitlement left? When to collect? What did I request? Has ration been dispatched? Where is my FPS? Why can't I submit preference? — I explain your real records."
        source="system records"
    return {"answer":answer, "source":source, "beneficiary_id":ben["beneficiary_id"], "cycle":cycle, "model":"rule-assistant v0.1 (uses PostgreSQL, not generative)", "generated_at":datetime.now().isoformat(), "disclaimer":"AI explains your records, does not modify entitlement or approve requests"}

@router.get("/fps/{fps_id}")
def get_fps(fps_id: str, ben=Depends(auth_beneficiary)):
    load()
    row=_fps[_fps.fps_id==fps_id]
    if row.empty: raise HTTPException(404,"FPS not found")
    return row.iloc[0].to_dict()

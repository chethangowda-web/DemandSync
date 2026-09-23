"""Phase 8 — Intelligence APIs (read-oriented, RBAC-enforced).

All endpoints are reads over persisted records plus one advisory
ai_predictions log row (AI_INSIGHT_GENERATED). Frontend-supplied ids are
never trusted for authorization: beneficiary id comes from the token,
fps_id from the officer record, district from the officer record.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel

from backend.core.audit import write_audit
from backend.core.auth_middleware import get_current_user, require_permission
from backend.core.errors import ApiError
from backend.core.rbac import Permission, Role
from backend.db.conn import get_db
from backend.services import forecast as forecast_svc
from backend.services.beneficiary import one
from backend.services.intelligence import anomalies as an
from backend.services.intelligence import ask as ask_svc
from backend.services.intelligence import explain as ex
from backend.services.intelligence import orchestrator as orch
from backend.services.intelligence import risk as rk
from backend.services.intelligence import signals as sig

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

ViewDemand = Depends(require_permission(Permission.VIEW_DEMAND))
ViewCycle = Depends(require_permission(Permission.VIEW_CYCLE))
ViewAudit = Depends(require_permission(Permission.VIEW_AUDIT))
ViewFpsInv = Depends(require_permission(Permission.VIEW_FPS_INVENTORY))
ViewInspect = Depends(require_permission(Permission.VIEW_INSPECTIONS))
ViewHealth = Depends(require_permission(Permission.VIEW_SYSTEM_HEALTH))
ViewOwn = Depends(require_permission(Permission.VIEW_OWN_ENTITLEMENT))


def _log_insight(conn, cycle, entity_type, entity_id, insight_type, summary, model_version="rule-intelligence-v1"):
    try:
        conn.execute(
            """INSERT INTO ai_predictions (prediction_id, service, cycle, entity_type, entity_id,
                    prediction, reason, supporting_data, model_version, generated_at)
                VALUES (%s, 'intelligence', %s, %s, %s, %s, %s, %s, %s, %s)""",
            ("AIP-" + uuid.uuid4().hex[:12].upper(), cycle, entity_type, entity_id,
             f'{{"type": "{insight_type}"}}', summary[:500], "{}", model_version,
             datetime.now(timezone.utc)))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def _cycle_or_latest(conn, cycle: str | None) -> str:
    if cycle:
        if not one(conn, "SELECT 1 FROM cycles WHERE cycle = %s", (cycle,)):
            raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
        return cycle
    r = one(conn, "SELECT cycle FROM cycles ORDER BY cycle DESC LIMIT 1")
    if not r:
        raise ApiError(404, "NO_CYCLES", "No cycles exist.")
    return r["cycle"]


# ---------------------------------------------------------------- DSO

@router.get("/dso/summary")
def dso_summary(cycle: str | None = None, user=ViewDemand, conn=Depends(get_db)):
    c = _cycle_or_latest(conn, cycle)
    out = orch.dso_summary(conn, c)
    _log_insight(conn, c, "CYCLE", c, "DSO_SUMMARY",
                 f"DSO summary: {out['counts'].get('total', 0)} insights.")
    write_audit(user["user_id"], user["role"], "AI_INSIGHT_GENERATED", "SUCCESS",
                "DSO intelligence summary viewed", "CYCLE", c, c)
    return out


@router.get("/dso/demand")
def dso_demand(cycle: str | None = None, user=ViewDemand, conn=Depends(get_db)):
    c = _cycle_or_latest(conn, cycle)
    rows_ = sig.forecast_signals(conn, c)
    _log_insight(conn, c, "CYCLE", c, "FORECAST_INTEL", f"{len(rows_)} forecast signals.")
    return {"cycle": c, "model": forecast_svc.MODEL_VERSION,
            "note": "Forecast reuses the XGBoost demand_forecast records; confidence is"
                    " unavailable on persisted rows by design (see demand.read_forecast).",
            "signals": rows_}


@router.get("/dso/anomalies")
def dso_anomalies(cycle: str | None = None, user=ViewDemand, conn=Depends(get_db)):
    c = _cycle_or_latest(conn, cycle)
    out = an.demand_anomalies(conn, c) + an.reconciliation_anomalies(conn, c)
    _log_insight(conn, c, "CYCLE", c, "ANOMALIES", f"{len(out)} anomalies.")
    return {"cycle": c, "anomalies": out}


@router.get("/dso/risks")
def dso_risks(cycle: str | None = None, kind: str | None = None, user=ViewDemand, conn=Depends(get_db)):
    c = _cycle_or_latest(conn, cycle)
    all_risks = (rk.stockout_risks(conn, c) + rk.allocation_insights(conn, c)
                 + rk.route_fleet_risks(conn, c) + rk.dispatch_risks(conn, c)
                 + rk.delivery_risks(conn, c))
    if kind:
        all_risks = [r for r in all_risks if r["type"] == kind]
    _log_insight(conn, c, "CYCLE", c, "RISKS", f"{len(all_risks)} risks.")
    return {"cycle": c, "risks": all_risks}


@router.get("/dso/brief")
def dso_brief(cycle: str | None = None, user=ViewDemand, conn=Depends(get_db)):
    c = _cycle_or_latest(conn, cycle)
    return ex.ops_brief(conn, c)


@router.get("/dso/exceptions")
def dso_exceptions(cycle: str | None = None, user=ViewDemand, conn=Depends(get_db)):
    c = _cycle_or_latest(conn, cycle)
    return {"cycle": c, "exceptions": rk.exception_intel(conn, c)}


@router.get("/dso/allocation-explanation")
def dso_allocation_explanation(cycle: str, fps_id: str, commodity: str, user=ViewDemand, conn=Depends(get_db)):
    if commodity not in ("RICE", "WHEAT"):
        raise ApiError(422, "INVALID_COMMODITY", "commodity must be RICE or WHEAT.")
    _cycle_or_latest(conn, cycle)
    return {"cycle": cycle, **ex.explain_allocation(conn, cycle, fps_id, commodity)}


# ---------------------------------------------------------------- Inspector

@router.get("/inspector/summary")
def inspector_summary(cycle: str | None = None, user=ViewInspect, conn=Depends(get_db)):
    c = _cycle_or_latest(conn, cycle)
    out = orch.inspector_summary(conn, c, user.get("district"))
    _log_insight(conn, c, "DISTRICT", user.get("district") or "ALL", "INSPECTOR_SUMMARY",
                 f"{len(out['inspection_priorities'])} priorities.")
    write_audit(user["user_id"], user["role"], "AI_INSIGHT_GENERATED", "SUCCESS",
                "Inspector intelligence summary viewed", "DISTRICT",
                user.get("district") or "ALL", c)
    return out


# ---------------------------------------------------------------- FPS owner (scoped to owned shop)

def _owned_fps(conn, user) -> str:
    r = one(conn, "SELECT fps_id FROM fps WHERE owner_id = %s", (user["user_id"],))
    if not r:
        raise ApiError(403, "NO_FPS_ASSIGNED", "No FPS shop is assigned to this account.")
    return r["fps_id"]


@router.get("/fps/me/summary")
def fps_summary(cycle: str | None = None, user=ViewFpsInv, conn=Depends(get_db)):
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "FPS intelligence is scoped to the FPS owner account.")
    fps_id = _owned_fps(conn, user)
    c = _cycle_or_latest(conn, cycle)
    out = orch.fps_summary(conn, c, fps_id)
    _log_insight(conn, c, "FPS", fps_id, "FPS_SUMMARY", "FPS summary viewed.")
    return out


# ---------------------------------------------------------------- Auditor

@router.get("/auditor/summary")
def auditor_summary(cycle: str | None = None, user=ViewAudit, conn=Depends(get_db)):
    c = _cycle_or_latest(conn, cycle)
    out = orch.auditor_summary(conn, c)
    _log_insight(conn, c, "CYCLE", c, "AUDITOR_SUMMARY", "Auditor summary viewed.")
    write_audit(user["user_id"], user["role"], "AI_INSIGHT_GENERATED", "SUCCESS",
                "Auditor intelligence summary viewed", "CYCLE", c, c)
    return out


# ---------------------------------------------------------------- Admin

@router.get("/admin/summary")
def admin_summary(user=ViewHealth, conn=Depends(get_db)):
    out = orch.admin_summary(conn)
    write_audit(user["user_id"], user["role"], "AI_INSIGHT_GENERATED", "SUCCESS",
                "Admin intelligence summary viewed", "SYSTEM", "platform", None)
    return out


# ---------------------------------------------------------------- Beneficiary (own data only)

@router.get("/beneficiary/me/summary")
def beneficiary_summary(user=ViewOwn, conn=Depends(get_db)):
    if user["role"] != Role.BENEFICIARY.value or not user.get("beneficiary_id"):
        raise ApiError(403, "FORBIDDEN", "Beneficiary intelligence is scoped to the beneficiary account.")
    return orch.beneficiary_summary(conn, user["beneficiary_id"])


# ---------------------------------------------------------------- Grounded ask

class AskBody(BaseModel):
    question: str
    context_entity_type: str | None = None
    context_entity_id: str | None = None
    cycle: str | None = None


@router.post("/ask")
def ask(body: AskBody, user: dict = Depends(get_current_user), conn=Depends(get_db)):
    """Role-aware grounded Q&A. Authorization never trusts frontend-supplied ids."""
    role = user["role"]
    question = (body.question or "").strip()
    if not question:
        raise ApiError(422, "QUESTION_REQUIRED", "question is required.")
    if role == Role.BENEFICIARY.value:
        resp = ask_svc.answer_beneficiary(conn, user["beneficiary_id"], question)
        _log_insight(conn, None, "BENEFICIARY", user["beneficiary_id"], "ASK", question[:200])
        return {**resp, "generated_at": datetime.now(timezone.utc).isoformat()}
    c = _cycle_or_latest(conn, body.cycle)
    if role == Role.FPS_OWNER.value:
        fps_id = _owned_fps(conn, user)
        refs = ask_svc._fps_ids_in(question)
        if refs and any(r != fps_id for r in refs):
            raise ApiError(403, "FORBIDDEN",
                           f"This account may only query its own shop ({fps_id}).")
        question = f"{question} {fps_id}" if not refs else question
        resp = ask_svc.answer_dso(conn, c, question)
        resp["answer"] = resp["answer"] + f" [Scoped to {fps_id}.]"
    elif role in (Role.DSO.value, Role.AUDITOR.value, Role.SYSTEM_ADMIN.value,
                  Role.FIELD_FOOD_INSPECTOR.value):
        if role == Role.FIELD_FOOD_INSPECTOR.value and user.get("district"):
            resp = ask_svc.answer_dso(conn, c, question)
        else:
            resp = ask_svc.answer_dso(conn, c, question)
    else:
        raise ApiError(403, "FORBIDDEN", "This account cannot use the intelligence assistant.")
    _log_insight(conn, c, "USER", user["user_id"], "ASK", question[:200])
    write_audit(user["user_id"], role, "AI_RECOMMENDATION_VIEWED", "SUCCESS", question[:200],
                "CYCLE", c, c)
    return {**resp, "cycle": c, "generated_at": datetime.now(timezone.utc).isoformat(),
            "stale_note": "Figures reflect persisted records at request time."}

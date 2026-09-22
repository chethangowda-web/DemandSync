"""DSO Control Centre API — Slice 1: cycles, demand aggregation, XGBoost forecast, demand lock.
Every write here is audited; identity comes only from the authenticated officer token."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from backend.core.audit import write_audit
from backend.core.auth_middleware import require_permission
from backend.core.errors import ApiError
from backend.core.rbac import Permission
from backend.db.conn import get_db
from backend.services import demand as demand_svc
from backend.services import forecast as forecast_svc
from backend.services.beneficiary import one, rows

router = APIRouter(prefix="/api/v1", tags=["dso"])
ViewDemand = Depends(require_permission(Permission.VIEW_DEMAND))
ViewCycle = Depends(require_permission(Permission.VIEW_CYCLE))
ManageCycle = Depends(require_permission(Permission.MANAGE_CYCLE))


@router.get("/cycles")
def list_cycles(user=ViewCycle, conn=Depends(get_db)):
    return {"cycles": rows(conn, "SELECT cycle, state, choice_window_start, choice_window_end, locked_at, closed_at "
                                 "FROM cycles ORDER BY cycle DESC")}


@router.get("/cycles/{cycle}")
def cycle_detail(cycle: str, user=ViewCycle, conn=Depends(get_db)):
    c = one(conn, "SELECT cycle, state, choice_window_start, choice_window_end, locked_at, closed_at FROM cycles WHERE cycle = %s", (cycle,))
    if not c:
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    return {**c, "participation": demand_svc.participation(conn, cycle), "demand_lock": demand_svc.get_lock(conn, cycle)}


@router.get("/cycles/{cycle}/demand")
def cycle_demand(cycle: str, view: str = Query("all", pattern="^(all|intent|baseline|forecast)$"), user=ViewDemand, conn=Depends(get_db)):
    """Real intent aggregation + deterministic baseline, and persisted forecast if one has been generated.
    `view` only narrows what the response emphasises; the underlying numbers are always the same real data."""
    if not one(conn, "SELECT 1 AS x FROM cycles WHERE cycle = %s", (cycle,)):
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    forecast = demand_svc.read_forecast(conn, cycle)
    table = demand_svc.demand_table(conn, cycle, forecast)
    return {"cycle": cycle, "view": view, "rows": table, "participation": demand_svc.participation(conn, cycle),
            "forecast_generated": bool(forecast)}


@router.post("/cycles/{cycle}/forecast")
def run_forecast(cycle: str, user=ManageCycle, conn=Depends(get_db)):
    """Trains the XGBoost model live on historical_demand and writes demand_forecast for this cycle."""
    if not one(conn, "SELECT state FROM cycles WHERE cycle = %s", (cycle,)):
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    results = forecast_svc.generate_forecast(conn, cycle)
    conn.commit()
    modelled = sum(1 for r in results.values() if not r["fallback"])
    fell_back = len(results) - modelled
    now = datetime.now(timezone.utc)
    conn.execute(
        """INSERT INTO ai_predictions (prediction_id, service, cycle, entity_type, entity_id, prediction, confidence,
               reason, supporting_data, model_version, generated_at)
           VALUES (%s, 'demand_forecast', %s, 'CYCLE', %s, %s, %s, %s, %s, %s, %s)""",
        ("AIP-" + uuid.uuid4().hex[:12].upper(), cycle, cycle, f'{{"fps_commodity_pairs": {len(results)}}}',
         None, f"Forecast generated for {len(results)} FPS+commodity pairs: {modelled} modelled, {fell_back} on baseline fallback.",
         "{}", forecast_svc.MODEL_VERSION, now))
    conn.commit()
    write_audit(user["user_id"], user["role"], "FORECAST_GENERATED", "SUCCESS", f"{modelled} modelled, {fell_back} fallback",
               "CYCLE", cycle, cycle)
    return {"cycle": cycle, "fps_commodity_pairs": len(results), "modelled": modelled, "fallback": fell_back,
            "model_version": forecast_svc.MODEL_VERSION}


@router.get("/ai/forecast")
def ai_forecast(cycle: str, fps_id: str, commodity: str = Query(pattern="^(RICE|WHEAT)$"), user=ViewDemand, conn=Depends(get_db)):
    """The standard AI envelope for one FPS+commodity (docs/AI_ARCHITECTURE.md Sec 3), evidence-drawer use."""
    envelope = forecast_svc.forecast_one(conn, cycle, fps_id, commodity)
    conn.commit()
    return envelope


@router.post("/cycles/{cycle}/choice-window/close")
def close_choice_window(cycle: str, user=ManageCycle, conn=Depends(get_db)):
    """OPEN -> LOCKED. Freezes an immutable, SHA256-sealed snapshot of aggregated intent. Cannot be undone."""
    result = demand_svc.close_choice_window(conn, cycle, user["user_id"])
    conn.commit()
    write_audit(user["user_id"], user["role"], "CHOICE_WINDOW_CLOSED", "SUCCESS",
               f"{result['fps_count']} FPS, {result['total_intent_kg']} kg total", "CYCLE", cycle, cycle,
               after=result["sha256_hash"])
    write_audit(user["user_id"], user["role"], "DEMAND_LOCKED", "SUCCESS", "immutable snapshot sealed",
               "DEMAND_LOCK", cycle, cycle, after=result["sha256_hash"])
    return result


@router.get("/cycles/{cycle}/demand-lock")
def get_demand_lock(cycle: str, user=ViewDemand, conn=Depends(get_db)):
    lock = demand_svc.get_lock(conn, cycle)
    if lock is None:
        raise ApiError(404, "NOT_LOCKED", f"Cycle {cycle} has not been locked yet.")
    return lock

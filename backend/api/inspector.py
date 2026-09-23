"""Phase 3: Field Food Inspector API.

Reuses officer auth + RBAC (VIEW_INSPECTIONS for reads, SUBMIT_INSPECTION for the
inspector's own workflow writes). Reads real FPS/inventory/e-PoS/grievance/
inspection data; risk assessment only prioritises and explains — findings are
recorded solely by the inspector.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.core.audit import write_audit
from backend.core.auth_middleware import require_permission
from backend.core.errors import ApiError
from backend.core.rbac import Permission
from backend.db.conn import get_db
from backend.services import inspection_risk as risk_svc
from backend.services.beneficiary import one, rows

router = APIRouter(prefix="/api/v1/inspector", tags=["inspector"])
ViewInsp = Depends(require_permission(Permission.VIEW_INSPECTIONS))
SubmitInsp = Depends(require_permission(Permission.SUBMIT_INSPECTION))


def _insp_row(r) -> dict:
    keys = ("inspection_id", "fps_id", "inspector_id", "inspection_date", "stock_expected_kg",
            "stock_observed_kg", "stock_variance_kg", "weighing_accuracy", "moisture_status",
            "shop_condition", "stock_register_verified", "epos_verified", "finding", "status",
            "evidence_reference", "sealed_hash", "verification", "checklist", "findings",
            "evidence", "notes", "submitted_at", "updated_at")
    d = dict(zip(keys, r))
    for k in ("verification", "checklist", "findings", "evidence"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except ValueError:
                pass
    for k in ("submitted_at", "updated_at", "inspection_date"):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _get_inspection(conn, inspection_id: str) -> dict:
    r = conn.execute(
        "SELECT inspection_id, fps_id, inspector_id, inspection_date, stock_expected_kg,"
        " stock_observed_kg, stock_variance_kg, weighing_accuracy, moisture_status, shop_condition,"
        " stock_register_verified, epos_verified, finding, status, evidence_reference, sealed_hash,"
        " verification, checklist, findings, evidence, notes, submitted_at, updated_at"
        " FROM inspections WHERE inspection_id = %s", (inspection_id,)).fetchone()
    if not r:
        raise ApiError(404, "INSPECTION_NOT_FOUND", f"Inspection {inspection_id} does not exist.")
    return _insp_row(r)


def _next_id(conn) -> str:
    row = conn.execute("SELECT max(inspection_id) FROM inspections WHERE inspection_id ~ '^INSP-[0-9]+$'").fetchone()
    n = int((row[0] or "INSP-000000").split("-")[1]) + 1 if row and row[0] else 1
    return f"INSP-{n:06d}"


@router.get("/summary")
def summary(user=ViewInsp, conn=Depends(get_db)):
    district = user.get("district")
    fps_count = conn.execute("SELECT count(*) FROM fps WHERE district = %s",
                             (district,)).fetchone()[0] if district else 0
    mine = rows(conn,
                "SELECT status, count(*) AS n FROM inspections WHERE inspector_id = %s GROUP BY status",
                (user["user_id"],))
    by_status = {m["status"]: int(m["n"]) for m in mine}
    return {"inspector_id": user["user_id"], "name": user["name"], "district": district,
            "fps_in_district": fps_count,
            "pending": by_status.get("DRAFT", 0),
            "submitted": by_status.get("SUBMITTED", 0) + by_status.get("SEALED", 0),
            "today": conn.execute(
                "SELECT count(*) FROM inspections WHERE inspector_id = %s AND inspection_date = CURRENT_DATE",
                (user["user_id"],)).fetchone()[0]}


@router.get("/targets")
def targets(district: str | None = None, limit: int = Query(50, ge=1, le=200),
            user=ViewInsp, conn=Depends(get_db)):
    dist = district or user.get("district")
    out = []
    for fps in risk_svc._fps_list(conn, dist):
        a = risk_svc.assess(conn, fps)
        li = (a["signals"] or {}).get("last_inspection") or {}
        inv = (a["signals"] or {}).get("inventory") or []
        g = (a["signals"] or {}).get("grievances") or {}
        e = (a["signals"] or {}).get("epos") or {}
        out.append({"fps_id": fps["fps_id"], "fps_name": fps["fps_name"], "district": fps["district"],
                    "taluk": fps.get("taluk"), "latitude": fps.get("latitude"),
                    "longitude": fps.get("longitude"), "status": fps.get("status"),
                    "risk_score": a["score"], "risk_level": a["level"],
                    "risk_factors": a["factors"], "recommended_focus": a["focus"],
                    "last_inspection": li.get("inspection_date") if isinstance(li, dict) else None,
                    "last_finding": (li.get("finding") if isinstance(li, dict) else None),
                    "inventory": inv,
                    "grievances_recent": int(g.get("recent") or 0), "grievances_open": int(g.get("open") or 0),
                    "epos_failed_90d": int(e.get("failed") or 0), "epos_odd_hours_90d": int(e.get("odd_hours") or 0)})
    out.sort(key=lambda t: -t["risk_score"])
    high = sum(1 for t in out if t["risk_level"] == "HIGH")
    return {"district": dist, "count": len(out), "high_risk": high, "targets": out[:limit]}


@router.get("/targets/{fps_id}")
def target_detail(fps_id: str, user=ViewInsp, conn=Depends(get_db)):
    fps = one(conn, "SELECT fps_id, fps_name, owner_id, district, taluk, latitude, longitude,"
                    " capacity_kg, warehouse_id, status, opening_hours FROM fps WHERE fps_id = %s", (fps_id,))
    if not fps:
        raise ApiError(404, "FPS_NOT_FOUND", f"FPS {fps_id} does not exist.")
    owner = None
    if fps.get("owner_id"):
        owner = one(conn, "SELECT officer_id, name, phone FROM officers WHERE officer_id = %s",
                    (fps["owner_id"],))
    a = risk_svc.assess(conn, fps)
    cur = one(conn, "SELECT cycle FROM cycles WHERE state <> 'CLOSED' ORDER BY cycle DESC LIMIT 1")
    dispatch = []
    if cur:
        dispatch = rows(conn, """SELECT m.manifest_id, m.cycle, m.vehicle_id, m.warehouse_id, m.manifest_status,
                                        mi.commodity, mi.planned_kg,
                                        d.delivered_kg, d.status AS delivery_status, d.delivery_date
                                 FROM dispatch_manifest_items mi
                                 JOIN dispatch_manifests m USING (manifest_id)
                                 LEFT JOIN delivery_history d ON d.manifest_item_id = mi.manifest_item_id
                                 WHERE mi.fps_id = %s AND m.cycle = %s
                                 ORDER BY m.manifest_id, mi.sequence_number LIMIT 50""", (fps_id, cur["cycle"]))
    return {"fps": fps, "owner": owner, "risk": {"score": a["score"], "level": a["level"],
              "factors": a["factors"], "recommended_focus": a["focus"]},
            "signals": a["signals"], "dispatch": {"cycle": cur["cycle"] if cur else None, "items": dispatch}}


class StartInspection(BaseModel):
    fps_id: str = Field(min_length=1, max_length=32)


@router.post("/inspections", status_code=201)
def start_inspection(req: StartInspection, user=SubmitInsp, conn=Depends(get_db)):
    fps = one(conn, "SELECT fps_id FROM fps WHERE fps_id = %s", (req.fps_id,))
    if not fps:
        raise ApiError(404, "FPS_NOT_FOUND", f"FPS {req.fps_id} does not exist.")
    existing = one(conn, "SELECT inspection_id FROM inspections WHERE fps_id = %s AND inspector_id = %s"
                          " AND status = 'DRAFT' ORDER BY inspection_date DESC LIMIT 1",
                   (req.fps_id, user["user_id"]))
    if existing:
        return {"inspection_id": existing["inspection_id"], "resumed": True, **_get_inspection(
            conn, existing["inspection_id"])}
    iid = _next_id(conn)
    now = datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO inspections (inspection_id, fps_id, inspector_id, inspection_date, status, updated_at)"
        " VALUES (%s, %s, %s, CURRENT_DATE, 'DRAFT', %s)", (iid, req.fps_id, user["user_id"], now))
    conn.commit()
    write_audit(user["user_id"], user["role"], "INSPECTION_STARTED", "SUCCESS",
                f"inspection {iid} for {req.fps_id}", "INSPECTION", iid)
    return {"inspection_id": iid, "resumed": False, **_get_inspection(conn, iid)}


@router.get("/inspections")
def my_inspections(status: str | None = Query(None, pattern="^(DRAFT|SUBMITTED|SEALED)$"),
                   limit: int = Query(50, ge=1, le=200), user=ViewInsp, conn=Depends(get_db)):
    q = ("SELECT i.inspection_id, i.fps_id, f.fps_name, i.inspection_date, i.status,"
         " i.finding, i.submitted_at, i.updated_at,"
         " COALESCE(jsonb_array_length(i.findings), 0) AS findings_count,"
         " (i.verification <> '{}'::jsonb) AS has_verification,"
         " (i.checklist <> '{}'::jsonb) AS has_checklist"
         " FROM inspections i JOIN fps f USING (fps_id) WHERE i.inspector_id = %s")
    args: list = [user["user_id"]]
    if status:
        q += " AND i.status = %s"
        args.append(status)
    q += " ORDER BY i.inspection_date DESC, i.inspection_id DESC LIMIT %s"
    args.append(limit)
    return {"inspections": rows(conn, q, tuple(args))}


@router.get("/inspections/{inspection_id}")
def inspection_detail(inspection_id: str, user=ViewInsp, conn=Depends(get_db)):
    insp = _get_inspection(conn, inspection_id)
    if insp["inspector_id"] != user["user_id"] and user["role"] not in ("DSO", "AUDITOR", "SYSTEM_ADMIN"):
        raise ApiError(403, "FORBIDDEN", "You can only open your own inspections.")
    fps = one(conn, "SELECT fps_id, fps_name, district, taluk, latitude, longitude, status FROM fps"
                    " WHERE fps_id = %s", (insp["fps_id"],))
    risk = risk_svc.assess(conn, {"fps_id": insp["fps_id"], **(fps or {})}) if fps else None
    return {"inspection": insp, "fps": fps,
            "risk": {"score": risk["score"], "level": risk["level"], "factors": risk["factors"],
                     "recommended_focus": risk["focus"]} if risk else None}


class UpdateInspection(BaseModel):
    verification: dict | None = None
    checklist: dict | None = None
    findings: list | None = None
    evidence: list | None = None
    notes: str | None = None
    finding: str | None = None
    stock_observed_kg: float | None = None
    stock_expected_kg: float | None = None


@router.patch("/inspections/{inspection_id}")
def update_inspection(inspection_id: str, req: UpdateInspection, user=SubmitInsp, conn=Depends(get_db)):
    insp = _get_inspection(conn, inspection_id)
    if insp["inspector_id"] != user["user_id"]:
        raise ApiError(403, "FORBIDDEN", "You can only edit your own inspections.")
    if insp["status"] != "DRAFT":
        raise ApiError(409, "INSPECTION_LOCKED", "Only draft inspections can be edited.")
    patch = req.model_dump(exclude_unset=True)
    sets, args = [], []
    for col in ("verification", "checklist", "findings", "evidence"):
        if patch.get(col) is not None:
            sets.append(f"{col} = %s::jsonb")
            args.append(json.dumps(patch[col]))
    if patch.get("notes") is not None:
        sets.append("notes = %s")
        args.append(patch["notes"][:5000])
    if patch.get("finding") is not None:
        sets.append("finding = %s")
        args.append(patch["finding"][:500])
    for col in ("stock_observed_kg", "stock_expected_kg"):
        if patch.get(col) is not None:
            sets.append(f"{col} = %s")
            args.append(patch[col])
    if not sets:
        return _get_inspection(conn, inspection_id)
    sets.append("stock_variance_kg = COALESCE(stock_observed_kg, 0) - COALESCE(stock_expected_kg, 0)")
    sets.append("updated_at = %s")
    args.append(datetime.now(timezone.utc))
    args.append(inspection_id)
    conn.execute(f"UPDATE inspections SET {', '.join(sets)} WHERE inspection_id = %s", tuple(args))
    conn.commit()
    return _get_inspection(conn, inspection_id)


@router.post("/inspections/{inspection_id}/submit")
def submit_inspection(inspection_id: str, user=SubmitInsp, conn=Depends(get_db)):
    insp = _get_inspection(conn, inspection_id)
    if insp["inspector_id"] != user["user_id"]:
        raise ApiError(403, "FORBIDDEN", "You can only submit your own inspections.")
    if insp["status"] != "DRAFT":
        raise ApiError(409, "INSPECTION_LOCKED", "Only draft inspections can be submitted.")
    missing = []
    if not insp.get("verification"):
        missing.append("FPS verification")
    if not insp.get("checklist"):
        missing.append("inspection checklist")
    if not insp.get("findings"):
        missing.append("findings (record explicitly, incl. no-violation)")
    if missing:
        raise ApiError(422, "INSPECTION_INCOMPLETE",
                       f"Cannot submit: missing {', '.join(missing)}.")
    now = datetime.now(timezone.utc)
    conn.execute("UPDATE inspections SET status = 'SUBMITTED', submitted_at = %s, updated_at = %s"
                 " WHERE inspection_id = %s", (now, now, inspection_id))
    conn.commit()
    write_audit(user["user_id"], user["role"], "INSPECTION_SUBMITTED", "SUCCESS",
                f"inspection {inspection_id} for {insp['fps_id']}", "INSPECTION", inspection_id)
    return {"inspection_id": inspection_id, "fps_id": insp["fps_id"],
            "submitted_by": user["user_id"], "timestamp": now.isoformat(), "status": "SUBMITTED"}

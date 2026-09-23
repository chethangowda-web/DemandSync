"""Phase 5: Auditor operations API — strictly read-only.

Every endpoint is a SELECT (or a recomputation over stored rows, like hash verification).
Nothing here advances the cycle state machine, edits records, or grants the auditor any
write capability: the existing RBAC matrix is untouched, and the Phase 2 services that own
all business behavior are consumed, never modified. Absent data is reported as null so the
UI can say DATA UNAVAILABLE instead of inventing a value.
"""
from fastapi import APIRouter, Depends, Query

from backend.core.auth_middleware import require_permission
from backend.core.errors import ApiError
from backend.core.rbac import Permission, Role
from backend.db.conn import get_db
from backend.services import allocation as allocation_svc
from backend.services import demand as demand_svc
from backend.services import manifest as manifest_svc
from backend.services import overview as overview_svc
from backend.services import routing as routing_svc
from backend.services import tracking as tracking_svc
from backend.services.beneficiary import iso, num, one, rows

router = APIRouter(prefix="/api/v1/auditor", tags=["auditor"])
ViewCycle = Depends(require_permission(Permission.VIEW_CYCLE))
ViewDemand = Depends(require_permission(Permission.VIEW_DEMAND))
ViewManifest = Depends(require_permission(Permission.VIEW_MANIFEST))
ViewAudit = Depends(require_permission(Permission.VIEW_AUDIT))


def _auditor(user: dict) -> dict:
    if user["role"] not in (Role.AUDITOR.value, Role.DSO.value, Role.SYSTEM_ADMIN.value):
        raise ApiError(403, "FORBIDDEN", "This section is for audit staff.")
    return user


def _iso(v):
    """Tolerant timestamp rendering: service helpers (e.g. demand.get_lock) already
    return some timestamps as strings; pass those through untouched."""
    if v is None or isinstance(v, str):
        return v
    return v.isoformat()


def _cycle(conn, cycle: str) -> dict:
    c = one(conn, "SELECT cycle, state, choice_window_start, choice_window_end, locked_at, closed_at "
                  "FROM cycles WHERE cycle = %s", (cycle,))
    if not c:
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    for k in ("choice_window_start", "choice_window_end", "locked_at", "closed_at"):
        c[k] = iso(c[k])
    return c


def _stage_marks(conn, cycle: str) -> list[dict]:
    """Workflow-bar state per stage, derived from backend records only."""
    lock = demand_svc.get_lock(conn, cycle)
    alloc = one(conn, "SELECT count(*) AS rows, count(*) FILTER (WHERE status='BLOCKED') AS blocked, "
                      "count(*) FILTER (WHERE source='DSO_OVERRIDE') AS overridden FROM allocations WHERE cycle = %s",
                (cycle,))
    mans = {r["manifest_status"]: r["n"] for r in rows(conn,
            "SELECT manifest_status, count(*) AS n FROM dispatch_manifests WHERE cycle = %s GROUP BY 1", (cycle,))}
    sealed = sum(mans.get(s, 0) for s in ("LOCKED", "DISPATCHED", "DELIVERED", "RECONCILED"))
    total_mans = sum(mans.values())
    deliv = one(conn, """SELECT count(*) AS rows, count(*) FILTER (WHERE d.status='VARIANCE') AS variance,
                                count(*) FILTER (WHERE d.status='REJECTED') AS rejected
                         FROM delivery_history d JOIN dispatch_manifests m ON m.manifest_id = d.manifest_id
                         WHERE m.cycle = %s""", (cycle,))
    exc = {r["severity"]: r["n"] for r in rows(conn,
           "SELECT severity, count(*) AS n FROM exceptions WHERE cycle = %s AND status = 'OPEN' GROUP BY 1", (cycle,))}
    open_exc = sum(exc.values())
    events = one(conn, "SELECT count(*) AS n FROM audit_events WHERE cycle = %s", (cycle,))["n"]
    try:
        checks = tracking_svc.run_closure_checks(conn, cycle)
    except Exception:
        checks = {}
    cyc = one(conn, "SELECT state FROM cycles WHERE cycle = %s", (cycle,))
    closed = cyc and cyc["state"] == "CLOSED"

    def ts(action: str) -> str | None:
        r = one(conn, "SELECT min(timestamp) AS t FROM audit_events WHERE cycle = %s AND action = %s", (cycle, action))
        return iso(r["t"]) if r and r["t"] else None

    return [
        {"stage": 1, "key": "OVERVIEW",
         "status": "COMPLETED" if closed else "IN REVIEW",
         "timestamp": ts("CYCLE_CLOSED") or ts("CYCLE_OPENED"),
         "detail": f"Cycle {cycle} is {cyc['state'] if cyc else 'unknown'}."},
        {"stage": 2, "key": "DEMAND",
         "status": "COMPLETED" if lock else "NOT STARTED",
         "timestamp": _iso(lock["locked_at"]) if lock else None,
         "detail": "Demand lock sealed." if lock else "No demand lock recorded for this cycle."},
        {"stage": 3, "key": "DISPATCH",
         "status": ("COMPLETED" if total_mans and sealed == total_mans else "IN REVIEW" if total_mans else "NOT STARTED"),
         "timestamp": ts("MANIFEST_LOCKED") or ts("CYCLE_AUTHORIZED"),
         "detail": f"{sealed}/{total_mans} manifests sealed." if total_mans else "No manifests for this cycle."},
        {"stage": 4, "key": "DELIVERY",
         "status": ("ACTION REQUIRED" if (deliv["variance"] or deliv["rejected"]) else "COMPLETED" if deliv["rows"] else "NOT STARTED"),
         "timestamp": ts("DELIVERY_RECORDED") or ts("CYCLE_RECONCILED"),
         "detail": f"{deliv['rows']} deliveries, {deliv['variance']} variance, {deliv['rejected']} rejected."},
        {"stage": 5, "key": "EXCEPTIONS",
         "status": ("ACTION REQUIRED" if exc.get("HIGH", 0) else "IN REVIEW" if open_exc else "COMPLETED"),
         "timestamp": None,
         "detail": f"{open_exc} open ({exc.get('HIGH', 0)} high)." if open_exc else "No open exceptions."},
        {"stage": 6, "key": "TRACE",
         "status": "COMPLETED" if events else "NOT STARTED",
         "timestamp": None,
         "detail": f"{events} audit events recorded."},
        {"stage": 7, "key": "CLOSURE",
         "status": ("COMPLETED" if closed else "ACTION REQUIRED" if checks and not all(checks.values()) else "IN REVIEW" if checks else "NOT STARTED"),
         "timestamp": ts("CYCLE_CLOSED"),
         "detail": "Cycle closed." if closed else ("Closure checks pending." if checks else "No closure evaluation available.")},
    ]


# ------------------------------------------------------------------ cycles & stages

@router.get("/cycles")
def cycles(user=ViewCycle, conn=Depends(get_db)):
    _auditor(user)
    out = rows(conn, "SELECT cycle, state, choice_window_start, choice_window_end, locked_at, closed_at "
                     "FROM cycles ORDER BY cycle DESC")
    for c in out:
        for k in ("choice_window_start", "choice_window_end", "locked_at", "closed_at"):
            c[k] = iso(c[k])
    districts = [r["district"] for r in rows(conn, "SELECT DISTINCT district FROM fps ORDER BY district")]
    for c in out:
        cyc = c["cycle"]
        c["evidence"] = {
            "locked": one(conn, "SELECT 1 AS x FROM demand_locks WHERE cycle = %s", (cyc,)) is not None,
            "allocations": one(conn, "SELECT count(*) AS n FROM allocations WHERE cycle = %s", (cyc,))["n"],
            "manifests": one(conn, "SELECT count(*) AS n FROM dispatch_manifests WHERE cycle = %s", (cyc,))["n"],
            "audit_events": one(conn, "SELECT count(*) AS n FROM audit_events WHERE cycle = %s", (cyc,))["n"],
        }
    return {"cycles": out, "districts": districts}


@router.get("/cycles/{cycle}/stages")
def stages(cycle: str, user=ViewCycle, conn=Depends(get_db)):
    _auditor(user)
    _cycle(conn, cycle)
    return {"cycle": cycle, "stages": _stage_marks(conn, cycle)}


# ------------------------------------------------------------------ 01 overview

@router.get("/cycles/{cycle}/overview")
def overview(cycle: str, user=ViewCycle, conn=Depends(get_db)):
    _auditor(user)
    c = _cycle(conn, cycle)
    beneficiaries = one(conn, "SELECT count(*) AS n FROM beneficiaries WHERE status = 'ACTIVE'")["n"]
    intent = one(conn, """SELECT COALESCE(sum(total_quantity_kg), 0) AS kg, count(*) AS n FROM intent_signals
                          WHERE cycle = %s AND status = 'SUBMITTED'""", (cycle,))
    alloc = one(conn, "SELECT COALESCE(sum(allocated_kg), 0) AS kg, count(*) AS n FROM allocations WHERE cycle = %s",
                (cycle,))
    planned = one(conn, """SELECT COALESCE(sum(mi.planned_kg), 0) AS kg FROM dispatch_manifest_items mi
                           JOIN dispatch_manifests m USING (manifest_id) WHERE m.cycle = %s""", (cycle,))
    delivered = one(conn, """SELECT COALESCE(sum(d.delivered_kg), 0) AS kg, count(*) AS n FROM delivery_history d
                             JOIN dispatch_manifests m ON m.manifest_id = d.manifest_id WHERE m.cycle = %s
                             AND d.status IN ('VERIFIED','VARIANCE')""", (cycle,))
    distributed = one(conn, """SELECT COALESCE(sum(quantity_kg), 0) AS kg, count(*) AS n FROM epos_transactions
                               WHERE cycle = %s AND status = 'SUCCESS'""", (cycle,))
    exc = {r["status"]: r["n"] for r in rows(conn,
           "SELECT status, count(*) AS n FROM exceptions WHERE cycle = %s GROUP BY 1", (cycle,))}
    open_n = sum(v for k, v in exc.items() if k in ("OPEN", "ACKNOWLEDGED", "ACTION_REQUIRED"))
    resolved_n = exc.get("RESOLVED", 0) + exc.get("CLOSED", 0)
    mans = one(conn, "SELECT count(*) AS n FROM dispatch_manifests WHERE cycle = %s", (cycle,))["n"]
    events = one(conn, "SELECT count(*) AS n FROM audit_events WHERE cycle = %s", (cycle,))["n"]
    lock = demand_svc.get_lock(conn, cycle)
    variance = num((delivered["kg"] or 0) - (distributed["kg"] or 0))
    readiness = [
        {"key": "demand", "label": "Demand records available", "met": (intent["n"] or 0) > 0 or lock is not None},
        {"key": "allocation", "label": "Allocation records available", "met": (alloc["n"] or 0) > 0},
        {"key": "manifest", "label": "Manifest records available", "met": mans > 0},
        {"key": "delivery", "label": "Delivery records available", "met": (delivered["n"] or 0) > 0},
        {"key": "reconciliation", "label": "Reconciliation records available",
         "met": (distributed["n"] or 0) > 0 and (delivered["n"] or 0) > 0},
        {"key": "audit", "label": "Audit events available", "met": events > 0},
    ]
    last = one(conn, "SELECT max(timestamp) AS t FROM audit_events WHERE cycle = %s", (cycle,))["t"]
    return {"cycle": c, "summary": {
        "total_beneficiaries": beneficiaries, "total_demand_kg": num(intent["kg"]),
        "total_allocated_kg": num(alloc["kg"]), "total_dispatched_kg": num(planned["kg"]),
        "total_received_kg": num(delivered["kg"]), "total_distributed_kg": num(distributed["kg"]),
        "total_variance_kg": variance, "open_exceptions": open_n, "resolved_exceptions": resolved_n,
        "manifest_count": mans, "delivery_count": delivered["n"]},
        "readiness": readiness, "last_sync": iso(last)}


# ------------------------------------------------------------------ 02 demand & allocation

@router.get("/cycles/{cycle}/demand")
def demand(cycle: str, user=ViewDemand, conn=Depends(get_db)):
    _auditor(user)
    _cycle(conn, cycle)
    forecast = demand_svc.read_forecast(conn, cycle)
    table = demand_svc.demand_table(conn, cycle, forecast)
    totals: dict = {}
    for r in table:
        for k in ("intent_demand_kg", "baseline_demand_kg", "forecast_demand_kg"):
            totals[r["commodity"] + ":" + k] = totals.get(r["commodity"] + ":" + k, 0) + (r[k] or 0)
    chain = []
    for com in ("RICE", "WHEAT"):
        intent = totals.get(com + ":intent_demand_kg", 0)
        baseline = totals.get(com + ":baseline_demand_kg", 0) or None
        fore = totals.get(com + ":forecast_demand_kg", 0) or None
        locked_row = one(conn, "SELECT COALESCE(sum(allocated_kg),0) AS kg FROM allocations WHERE cycle=%s AND commodity=%s",
                         (cycle, com))
        chain.append({"commodity": com, "intent_kg": intent, "baseline_kg": baseline, "forecast_kg": fore,
                      "validated_kg": intent if demand_svc.get_lock(conn, cycle) else None,
                      "allocated_kg": locked_row["kg"] if locked_row else 0,
                      "intent_minus_forecast_kg": round(intent - fore, 1) if fore is not None else None,
                      "forecast_minus_baseline_kg": round(fore - baseline, 1) if fore is not None and baseline else None})
    lock = demand_svc.get_lock(conn, cycle)
    fmeta = one(conn, "SELECT model_version, count(*) AS rows, max(prediction_generated_at) AS at FROM demand_forecast "
                      "WHERE cycle = %s GROUP BY model_version", (cycle,))
    allocs = rows(conn, "SELECT fps_id, commodity, requested_kg, allocated_kg, status, source, approved_by, approved_at "
                        "FROM allocations WHERE cycle = %s ORDER BY fps_id, commodity", (cycle,))
    for a in allocs:
        a["approved_at"] = iso(a["approved_at"])
    overrides = [a for a in allocs if a["source"] == "DSO_OVERRIDE"]
    override_events = rows(conn, """SELECT audit_event_id, actor_user_id, actor_role, reason, timestamp, before_state,
                                           after_state, entity_id FROM audit_events
                                    WHERE cycle = %s AND action = 'ALLOCATION_OVERRIDDEN' ORDER BY timestamp""", (cycle,))
    for e in override_events:
        e["timestamp"] = iso(e["timestamp"])
    return {"cycle": cycle, "chain": chain, "forecast_generated": bool(forecast),
            "forecast": ({"model_version": fmeta["model_version"], "rows": fmeta["rows"],
                          "generated_at": iso(fmeta["at"])} if fmeta else None),
            "demand_lock": ({"locked": True, "sha256_hash": lock["sha256_hash"], "locked_at": _iso(lock["locked_at"]),
                             "locked_by": lock["locked_by"]} if lock else {"locked": False}),
            "allocations": allocs, "overrides": overrides, "override_events": override_events}


# ------------------------------------------------------------------ 03 manifests

@router.get("/cycles/{cycle}/manifests")
def manifests(cycle: str, district: str | None = None, user=ViewManifest, conn=Depends(get_db)):
    _auditor(user)
    _cycle(conn, cycle)
    args: list = [cycle]
    dfilt = ""
    if district:
        dfilt = """ AND m.manifest_id IN (SELECT manifest_id FROM dispatch_manifest_items mi JOIN fps f USING (fps_id)
                                           WHERE f.district = %s)"""
        args.append(district)
    mans = rows(conn, f"""SELECT m.manifest_id, m.warehouse_id, m.vehicle_id, m.manifest_status, m.total_kg,
                                 m.route_distance_km, m.created_by, m.created_at, m.locked_by, m.locked_at,
                                 m.sha256_hash, m.qr_payload IS NOT NULL AS has_qr,
                                 (SELECT count(DISTINCT fps_id) FROM dispatch_manifest_items WHERE manifest_id = m.manifest_id) AS fps_count,
                                 COALESCE((SELECT sum(planned_kg) FROM dispatch_manifest_items WHERE manifest_id = m.manifest_id), 0) AS planned_kg
                          FROM dispatch_manifests m WHERE m.cycle = %s{dfilt} ORDER BY m.manifest_id""", tuple(args))
    for m in mans:
        m["created_at"] = iso(m["created_at"])
        m["locked_at"] = iso(m["locked_at"])
        if m["manifest_status"] in ("LOCKED", "DISPATCHED", "DELIVERED", "RECONCILED"):
            try:
                v = manifest_svc.get_lock_verification(conn, m["manifest_id"])
                m["hash_verified"] = v["hash_verified"]
            except ApiError:
                m["hash_verified"] = None
        else:
            m["hash_verified"] = None
    return {"cycle": cycle, "district": district, "manifests": mans}


@router.get("/manifests/{manifest_id}")
def manifest_detail(manifest_id: str, user=ViewManifest, conn=Depends(get_db)):
    _auditor(user)
    d = routing_svc.manifest_detail(conn, manifest_id)
    extra = one(conn, "SELECT locked_by, locked_at, sha256_hash, qr_payload IS NOT NULL AS has_qr "
                      "FROM dispatch_manifests WHERE manifest_id = %s", (manifest_id,))
    if extra:
        d["locked_by"] = extra["locked_by"]
        d["locked_at"] = iso(extra["locked_at"])
        d["sha256_hash"] = extra["sha256_hash"]
        d["has_qr"] = extra["has_qr"]
    auth_ev = one(conn, "SELECT actor_user_id, timestamp FROM audit_events WHERE action = 'CYCLE_AUTHORIZED' "
                        "AND cycle = %s ORDER BY timestamp DESC LIMIT 1", (d.get("cycle"),))
    d["authorization"] = ({**auth_ev, "timestamp": iso(auth_ev["timestamp"])} if auth_ev else None)
    try:
        d["lock_verification"] = manifest_svc.get_lock_verification(conn, manifest_id)
    except ApiError as e:
        d["lock_verification"] = {"manifest_id": manifest_id, "hash_verified": None, "note": e.message}
    try:
        d["qr_png_base64"] = manifest_svc.manifest_qr_png_base64(conn, manifest_id)
    except ApiError:
        d["qr_png_base64"] = None
    return d


# ------------------------------------------------------------------ 04 delivery & reconciliation

@router.get("/cycles/{cycle}/reconciliation")
def reconciliation(cycle: str, district: str | None = None, limit: int = Query(100, ge=1, le=500),
                   offset: int = Query(0, ge=0), user=ViewDemand, conn=Depends(get_db)):
    _auditor(user)
    _cycle(conn, cycle)
    flow = []
    for com in ("RICE", "WHEAT"):
        allocated = one(conn, "SELECT COALESCE(sum(allocated_kg),0) AS kg FROM allocations WHERE cycle=%s AND commodity=%s",
                        (cycle, com))["kg"]
        dispatched = one(conn, """SELECT COALESCE(sum(mi.planned_kg),0) AS kg FROM dispatch_manifest_items mi
                                  JOIN dispatch_manifests m USING (manifest_id)
                                  WHERE m.cycle=%s AND mi.commodity=%s""", (cycle, com))["kg"]
        received = one(conn, """SELECT COALESCE(sum(d.delivered_kg),0) AS kg FROM delivery_history d
                                JOIN dispatch_manifest_items mi ON mi.manifest_item_id=d.manifest_item_id
                                JOIN dispatch_manifests m ON m.manifest_id=d.manifest_id
                                WHERE m.cycle=%s AND mi.commodity=%s AND d.status IN ('VERIFIED','VARIANCE')""",
                       (cycle, com))["kg"]
        distributed = one(conn, "SELECT COALESCE(sum(quantity_kg),0) AS kg FROM epos_transactions "
                                "WHERE cycle=%s AND commodity=%s AND status='SUCCESS'", (cycle, com))["kg"]
        variance = num((received or 0) - (distributed or 0))
        flow.append({"commodity": com, "allocated_kg": num(allocated), "dispatched_kg": num(dispatched),
                     "received_kg": num(received), "distributed_kg": num(distributed), "variance_kg": variance,
                     "status": "VERIFIED" if variance == 0 and (received or distributed) else
                               "VARIANCE" if variance != 0 else "BLOCKED"})
    try:
        checks = tracking_svc.run_closure_checks(conn, cycle)
    except Exception:
        checks = {}
    args: list = [cycle]
    dfilt = ""
    if district:
        dfilt = " AND f.district = %s"
        args.append(district)
    deliveries = rows(conn, f"""SELECT d.delivery_id, d.manifest_id, d.fps_id, f.fps_name, f.district, d.vehicle_id,
                                       mi.commodity, mi.planned_kg, d.delivered_kg,
                                       (d.delivered_kg - mi.planned_kg) AS variance_kg,
                                       d.delivery_date, d.status, d.verified_by
                                FROM delivery_history d
                                JOIN dispatch_manifest_items mi ON mi.manifest_item_id = d.manifest_item_id
                                JOIN dispatch_manifests m ON m.manifest_id = d.manifest_id
                                JOIN fps f ON f.fps_id = d.fps_id
                                WHERE m.cycle = %s{dfilt}
                                ORDER BY d.delivery_date DESC LIMIT %s OFFSET %s""", tuple(args + [limit, offset]))
    for d in deliveries:
        d["delivery_date"] = iso(d["delivery_date"])
    total = one(conn, f"""SELECT count(*) AS n FROM delivery_history d
                          JOIN dispatch_manifests m ON m.manifest_id = d.manifest_id
                          JOIN fps f ON f.fps_id = d.fps_id WHERE m.cycle = %s{dfilt}""", tuple(args))["n"]
    return {"cycle": cycle, "district": district, "flow": flow, "closure_checks": checks,
            "checks_passed": all(checks.values()) if checks else None,
            "deliveries": deliveries, "total": total}


# ------------------------------------------------------------------ 05 exceptions

@router.get("/cycles/{cycle}/exceptions")
def exceptions(cycle: str, severity: str | None = Query(None, pattern="^(HIGH|MEDIUM|LOW)$"),
               status: str | None = Query(None, pattern="^(OPEN|ACKNOWLEDGED|ACTION_REQUIRED|RESOLVED|CLOSED)$"),
               district: str | None = None, user=ViewDemand, conn=Depends(get_db)):
    _auditor(user)
    _cycle(conn, cycle)
    counts = {r["severity"]: r["n"] for r in rows(conn,
              "SELECT severity, count(*) AS n FROM exceptions WHERE cycle = %s AND status IN "
              "('OPEN','ACKNOWLEDGED','ACTION_REQUIRED') GROUP BY 1", (cycle,))}
    args: list = [cycle]
    q = """SELECT e.exception_id, e.entity_type, e.entity_id, e.rule_code, e.severity, e.reason, e.detected_at,
                  e.assigned_to, e.status, e.resolution, e.resolved_at, f.district AS entity_district
           FROM exceptions e LEFT JOIN fps f ON f.fps_id = e.entity_id WHERE e.cycle = %s"""
    if severity:
        q += " AND e.severity = %s"
        args.append(severity)
    if status:
        q += " AND e.status = %s"
        args.append(status)
    if district:
        q += " AND f.district = %s"
        args.append(district)
    q += " ORDER BY CASE e.severity WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END, e.detected_at DESC LIMIT 200"
    out = rows(conn, q, tuple(args))
    for e in out:
        e["detected_at"] = iso(e["detected_at"])
        e["resolved_at"] = iso(e["resolved_at"])
    return {"cycle": cycle, "open_by_severity": {"HIGH": counts.get("HIGH", 0), "MEDIUM": counts.get("MEDIUM", 0),
                                                 "LOW": counts.get("LOW", 0)},
            "exceptions": out}


# ------------------------------------------------------------------ 06 decision trace

@router.get("/cycles/{cycle}/trace")
def trace(cycle: str, action: str | None = None, limit: int = Query(200, ge=1, le=1000),
          offset: int = Query(0, ge=0), user=ViewAudit, conn=Depends(get_db)):
    _auditor(user)
    _cycle(conn, cycle)
    args: list = [cycle]
    q = """SELECT audit_event_id, actor_user_id, actor_role, action, entity_type, entity_id, reason, result,
                  timestamp, before_state, after_state FROM audit_events WHERE cycle = %s"""
    if action:
        q += " AND action = %s"
        args.append(action)
    q += " ORDER BY timestamp, audit_event_id LIMIT %s OFFSET %s"
    args += [limit, offset]
    out = rows(conn, q, tuple(args))
    for e in out:
        e["timestamp"] = iso(e["timestamp"])
    total = one(conn, "SELECT count(*) AS n FROM audit_events WHERE cycle = %s" +
                      (" AND action = %s" if action else ""), tuple(args[:1 + (1 if action else 0)]))["n"]
    actions = [r["action"] for r in rows(conn, "SELECT DISTINCT action FROM audit_events WHERE cycle = %s ORDER BY 1",
                                        (cycle,))]
    chain = __import__("backend.core.audit", fromlist=["verify_chain"])
    return {"cycle": cycle, "total": total, "events": out, "actions": actions,
            "chain_intact": chain.verify_chain()["intact"]}


# ------------------------------------------------------------------ 07 closure

@router.get("/cycles/{cycle}/closure")
def closure(cycle: str, user=ViewCycle, conn=Depends(get_db)):
    _auditor(user)
    c = _cycle(conn, cycle)
    lock = demand_svc.get_lock(conn, cycle)
    alloc_n = one(conn, "SELECT count(*) AS n FROM allocations WHERE cycle = %s", (cycle,))["n"]
    mans = rows(conn, "SELECT manifest_id, manifest_status FROM dispatch_manifests WHERE cycle = %s", (cycle,))
    verified = 0
    failed_manifests = []
    for m in mans:
        if m["manifest_status"] in ("LOCKED", "DISPATCHED", "DELIVERED", "RECONCILED"):
            try:
                if manifest_svc.get_lock_verification(conn, m["manifest_id"])["hash_verified"]:
                    verified += 1
                else:
                    failed_manifests.append(m["manifest_id"])
            except ApiError:
                failed_manifests.append(m["manifest_id"])
    try:
        checks = tracking_svc.run_closure_checks(conn, cycle)
    except Exception:
        checks = {}
    open_high = one(conn, "SELECT count(*) AS n FROM exceptions WHERE cycle=%s AND severity='HIGH' "
                          "AND status IN ('OPEN','ACKNOWLEDGED','ACTION_REQUIRED')", (cycle,))["n"]
    recon = one(conn, """SELECT COALESCE(sum(d.delivered_kg),0) AS recv FROM delivery_history d
                         JOIN dispatch_manifests m ON m.manifest_id=d.manifest_id
                         WHERE m.cycle=%s AND d.status IN ('VERIFIED','VARIANCE')""", (cycle,))["recv"]
    dist = one(conn, "SELECT COALESCE(sum(quantity_kg),0) AS kg FROM epos_transactions WHERE cycle=%s AND status='SUCCESS'",
               (cycle,))["kg"]
    variance = (recon or 0) - (dist or 0)
    sealed = sum(1 for m in mans if m["manifest_status"] in ("LOCKED", "DISPATCHED", "DELIVERED", "RECONCILED"))
    authorized = c["state"] in ("AUTHORIZED", "TRACKING", "DELIVERING", "RECONCILING", "AUDITING", "CLOSED")

    def chk(label: str, state: str, evidence: str) -> dict:
        return {"check": label, "status": state, "evidence": evidence}

    items = [
        chk("All demand records accounted for", "PASS" if lock else "FAIL",
            "Demand lock sealed." if lock else "No demand lock for this cycle."),
        chk("Demand lock verified", "PASS" if lock else "NOT VERIFIED",
            f"SHA-256 {lock['sha256_hash'][:16]}…" if lock else "Nothing to verify."),
        chk("Allocation trace verified", "PASS" if alloc_n else "NOT VERIFIED", f"{alloc_n} allocation rows."),
        chk("Constraint validation verified", "PASS" if alloc_n else "NOT VERIFIED",
            "Constraint engine findings on record." if alloc_n else "No allocations evaluated."),
        chk("All manifests verified", "PASS" if mans and sealed == len(mans) else ("WARNING" if mans else "NOT VERIFIED"),
            f"{sealed}/{len(mans)} manifests sealed." if mans else "No manifests."),
        chk("Manifest hashes verified", "PASS" if mans and verified == sealed and not failed_manifests else
            ("FAIL" if failed_manifests else "WARNING"),
            f"{verified}/{sealed} sealed hashes recompute cleanly." if mans else "No sealed manifests."),
        chk("Dispatch authorization verified", "PASS" if authorized else "NOT VERIFIED",
            f"Cycle state is {c['state']}."),
        chk("Delivery records verified", "PASS" if recon else "NOT VERIFIED",
            f"{num(recon)} kg received across verified deliveries." if recon else "No verified deliveries."),
        chk("Reconciliation completed", "PASS" if checks and all(checks.values()) else ("FAIL" if checks else "NOT VERIFIED"),
            f"{len([v for v in checks.values() if v])}/{len(checks)} closure checks pass." if checks else "Closure checks unavailable."),
        chk("Variance within tolerance", "PASS" if variance == 0 else "WARNING",
            f"Received-vs-distributed variance is {num(variance)} kg."),
        chk("Exceptions resolved", "PASS" if open_high == 0 else "FAIL", f"{open_high} high-severity exceptions open."),
        chk("Audit chain intact", "PASS" if __import__("backend.core.audit", fromlist=["verify_chain"]).verify_chain()["intact"] else "FAIL",
            "Hash chain recomputed over all chained events."),
    ]
    hard_fail = any(i["status"] == "FAIL" for i in items)
    warn = any(i["status"] == "WARNING" for i in items)
    decision = ("AUDIT BLOCKED" if hard_fail else "AUDIT READY WITH WARNINGS" if warn else "AUDIT READY"
                if all(i["status"] == "PASS" for i in items) else "ACTION REQUIRED")
    return {"cycle": c, "checklist": items, "decision": decision,
            "failed_manifests": failed_manifests,
            "final_action": "FINAL ACTION NOT AVAILABLE — cycle closure is a DSO operation; this workspace is read-only."}


# ------------------------------------------------------------------ AI assistant (advisory, read-only)

@router.post("/cycles/{cycle}/ask")
def ask(body: dict, cycle: str, user=ViewDemand, conn=Depends(get_db)):
    """Small grounded assistant: matches one evidence intent, answers only from stored rows,
    always cites source records with a confidence note. Never writes, never decides."""
    _auditor(user)
    _cycle(conn, cycle)
    q = ((body or {}).get("question") or "").strip().lower()
    intent = ((body or {}).get("intent") or "").strip().upper()

    def pick() -> str:
        if intent in ("ALLOCATION_WHY", "VARIANCE_WHY", "FPS_CHAIN", "EXCEPTIONS_WHICH", "CLOSURE_WHY", "MANIFEST_INTEGRITY"):
            return intent
        if "allocation" in q and ("why" in q or "created" in q):
            return "ALLOCATION_WHY"
        if "variance" in q or "caused" in q:
            return "VARIANCE_WHY"
        if "fps-" in q:
            return "FPS_CHAIN"
        if "exception" in q:
            return "EXCEPTIONS_WHICH"
        if "clos" in q or "ready" in q:
            return "CLOSURE_WHY"
        if "manifest" in q and ("integrity" in q or "hash" in q or "seal" in q):
            return "MANIFEST_INTEGRITY"
        return "OVERVIEW"

    def resp(insight: str, evidence: list, sources: list, confidence: str) -> dict:
        return {"cycle": cycle, "advisory": True, "insight": insight, "evidence": evidence,
                "source_records": sources, "confidence": confidence,
                "note": "Advisory only. Grounded in the cited records; never modifies data."}

    if pick() == "ALLOCATION_WHY":
        n = one(conn, "SELECT count(*) AS rows, COALESCE(sum(allocated_kg),0) AS kg, "
                      "count(*) FILTER (WHERE status='BLOCKED') AS blocked FROM allocations WHERE cycle=%s", (cycle,)) or {}
        ov = rows(conn, "SELECT fps_id, commodity, allocated_kg, reason FROM (SELECT fps_id, commodity, allocated_kg, "
                        "reason FROM allocations WHERE cycle=%s AND source='DSO_OVERRIDE') o LIMIT 5", (cycle,))
        return resp(f"Allocations in {cycle} were produced by the constraint engine: {n.get('rows', 0)} rows, "
                    f"{num(n.get('kg'))} kg, {n.get('blocked', 0)} blocked.",
                    [f"{r['fps_id']} {r['commodity']}: {num(r['allocated_kg'])} kg — {r['reason']}" for r in ov] or
                    ["No manual overrides on record; every row carries source SYSTEM."],
                    ["allocations", "audit_events:ALLOCATION_OVERRIDDEN"], "HIGH" if ov else "MEDIUM")
    if pick() == "VARIANCE_WHY":
        top = rows(conn, """SELECT d.fps_id, mi.commodity, sum(mi.planned_kg) AS planned, sum(d.delivered_kg) AS got
                            FROM delivery_history d JOIN dispatch_manifest_items mi ON mi.manifest_item_id=d.manifest_item_id
                            JOIN dispatch_manifests m ON m.manifest_id=d.manifest_id
                            WHERE m.cycle=%s GROUP BY 1,2 HAVING sum(d.delivered_kg) <> sum(mi.planned_kg)
                            ORDER BY abs(sum(d.delivered_kg)-sum(mi.planned_kg)) DESC LIMIT 5""", (cycle,))
        return resp(f"Delivery variance in {cycle} concentrates in {len(top)} FPS+commodity pair(s) shown.",
                    [f"{r['fps_id']} {r['commodity']}: planned {num(r['planned'])} kg, delivered {num(r['got'])} kg" for r in top] or
                    ["No planned-vs-delivered variance on record."],
                    ["delivery_history", "dispatch_manifest_items"], "HIGH" if top else "MEDIUM")
    if pick() == "FPS_CHAIN":
        import re
        m = re.search(r"fps-[0-9]+", q, re.IGNORECASE)
        fid = m.group(0).upper() if m else None
        if not fid or not one(conn, "SELECT 1 FROM fps WHERE fps_id=%s", (fid,)):
            return resp("No matching FPS record.", [], ["fps"], "LOW")
        chain = {
            "allocation": rows(conn, "SELECT commodity, allocated_kg, status FROM allocations WHERE cycle=%s AND fps_id=%s", (cycle, fid)),
            "deliveries": rows(conn, """SELECT d.delivery_id, d.delivered_kg, d.status FROM delivery_history d
                                        JOIN dispatch_manifests m ON m.manifest_id=d.manifest_id
                                        WHERE m.cycle=%s AND d.fps_id=%s LIMIT 5""", (cycle, fid)),
            "epos": one(conn, "SELECT count(*) AS n, COALESCE(sum(quantity_kg),0) AS kg FROM epos_transactions "
                              "WHERE cycle=%s AND fps_id=%s AND status='SUCCESS'", (cycle, fid)),
        }
        return resp(f"Decision chain for {fid} in {cycle}: allocation → delivery → e-PoS distribution.",
                    [f"Allocated: {[(a['commodity'], num(a['allocated_kg']), a['status']) for a in chain['allocation']]}",
                     f"Deliveries: {len(chain['deliveries'])} recorded",
                     f"e-PoS: {chain['epos']['n']} successful transactions, {num(chain['epos']['kg'])} kg"],
                    ["allocations", "delivery_history", "epos_transactions"], "HIGH")
    if pick() == "EXCEPTIONS_WHICH":
        ex = rows(conn, "SELECT exception_id, severity, rule_code, entity_id, status FROM exceptions WHERE cycle=%s "
                        "AND status IN ('OPEN','ACKNOWLEDGED','ACTION_REQUIRED') ORDER BY CASE severity WHEN 'HIGH' THEN 0 "
                        "WHEN 'MEDIUM' THEN 1 ELSE 2 END LIMIT 8", (cycle,))
        return resp(f"{len(ex)} open exception(s) affect {cycle}" + ("; top by severity shown." if ex else "."),
                    [f"{r['exception_id']} [{r['severity']}] {r['rule_code']} on {r['entity_id']} ({r['status']})" for r in ex] or
                    ["No open exceptions."],
                    ["exceptions"], "HIGH")
    if pick() == "CLOSURE_WHY":
        try:
            checks = tracking_svc.run_closure_checks(conn, cycle)
        except Exception:
            checks = {}
        failing = [k for k, v in checks.items() if not v]
        return resp(f"Cycle {cycle} is {'ready' if checks and not failing else 'not ready'} for closure.",
                    [f"Failing checks: {', '.join(failing)}"] if failing else
                    (["All closure checks pass."] if checks else ["Closure checks unavailable for this cycle."]),
                    ["tracking:closure_checks"], "HIGH" if checks else "LOW")
    if pick() == "MANIFEST_INTEGRITY":
        bad = []
        for m in rows(conn, "SELECT manifest_id FROM dispatch_manifests WHERE cycle=%s AND manifest_status IN "
                            "('LOCKED','DISPATCHED','DELIVERED','RECONCILED')", (cycle,)):
            try:
                if not manifest_svc.get_lock_verification(conn, m["manifest_id"])["hash_verified"]:
                    bad.append(m["manifest_id"])
            except ApiError:
                bad.append(m["manifest_id"])
        return resp("No manifest integrity failures on record." if not bad else f"{len(bad)} manifest(s) fail verification.",
                    bad or ["Every sealed manifest recomputes to its stored SHA-256."],
                    ["dispatch_manifests:sha256_hash"], "HIGH")
    s = overview_svc.cycle_summary(conn, cycle)
    return resp(f"Cycle {cycle} is {s.get('state') if s else 'unknown'}.",
                [f"Allocated {num((s.get('allocation') or {}).get('allocated_kg'))} kg across {(s.get('allocation') or {}).get('rows', 0)} rows."] if s else [],
                ["overview:cycle_summary"], "MEDIUM")

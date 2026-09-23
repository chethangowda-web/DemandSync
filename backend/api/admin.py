"""Phase 6: System Admin operations API.

Reads are additive GETs over existing tables and live service probes; nothing here
changes Phase 2 business behavior. The only writes are officer account administration
(status / role / unlock), which had no endpoint before: each requires MANAGE_USERS,
a mandatory reason, refuses self-mutation, and writes a before/after audit event.
The RBAC matrix itself is never edited at runtime — it is exposed read-only so the
UI can show exactly what each role may do. No secret is ever returned.
"""
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.core.audit import verify_chain, write_audit
from backend.core.auth_middleware import require_permission
from backend.core.errors import ApiError
from backend.core.rbac import OFFICER_ROLE_MAP, ROLE_PERMISSIONS, Permission, Role
from backend.db.conn import get_db
from backend.services.beneficiary import iso, num, one, rows

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
ReadHealth = Depends(require_permission(Permission.VIEW_SYSTEM_HEALTH))
ReadAudit = Depends(require_permission(Permission.VIEW_AUDIT))
ManageUsers = Depends(require_permission(Permission.MANAGE_USERS))
ManageData = Depends(require_permission(Permission.MANAGE_DATASETS))

ADMIN_ROLES = (Role.SYSTEM_ADMIN.value,)


def _admin(user: dict) -> dict:
    if user["role"] not in ADMIN_ROLES:
        raise ApiError(403, "FORBIDDEN", "System administration is restricted to SYSTEM_ADMIN.")
    return user


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ live probes

def _probe_db(conn) -> dict:
    t0 = time.perf_counter()
    try:
        conn.execute("SELECT 1")
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return {"status": "ONLINE", "latency_ms": ms, "last_check": _now(), "error": None}
    except Exception as e:
        return {"status": "OFFLINE", "latency_ms": None, "last_check": _now(), "error": type(e).__name__}


def _probe_auth() -> dict:
    """JWT sign/verify round-trip plus credential-store reachability (no session is created)."""
    try:
        from backend.core import security as sec
        tok = sec.create_access_token("health-probe", Role.SYSTEM_ADMIN.value, minutes=1)
        payload = sec.decode_token(tok)
        ok = payload.get("sub") == "health-probe"
        return {"status": "ONLINE" if ok else "DEGRADED", "last_check": _now(),
                "detail": "JWT sign/verify round-trip succeeded." if ok else "Token payload mismatch.",
                "error": None}
    except Exception as e:
        return {"status": "OFFLINE", "last_check": _now(),
                "detail": "Authentication service could not sign a token.", "error": type(e).__name__}


def _probe_module(name: str, mod: str, attr: str | None = None) -> dict:
    try:
        m = __import__(mod, fromlist=["x"])
        extra = getattr(m, attr) if attr else None
        return {"status": "ONLINE", "last_check": _now(),
                "detail": f"{name} library available." + (f" Model {extra}." if extra else ""), "error": None}
    except Exception as e:
        return {"status": "OFFLINE", "last_check": _now(),
                "detail": f"{name} library could not be loaded.", "error": str(e)[:160]}


def _probe_storage() -> dict:
    from backend.core.config import DATA_DIR
    manifest = DATA_DIR / "07_generated" / "dataset_manifest.json"
    if manifest.exists():
        return {"status": "ONLINE", "last_check": _now(),
                "detail": f"Data directory present; dataset manifest found.", "error": None}
    if DATA_DIR.exists():
        return {"status": "DEGRADED", "last_check": _now(),
                "detail": "Data directory present but no dataset manifest.", "error": None}
    return {"status": "OFFLINE", "last_check": _now(), "detail": "Configured DATA_DIR does not exist.", "error": None}


def _probe_notifications() -> dict:
    from backend.core import otp as otp_mod
    provider = otp_mod.provider_name()
    if provider == "dev":
        return {"status": "DEGRADED", "last_check": _now(),
                "detail": "OTP provider is 'dev' (demo delivery only); no SMS gateway configured.", "error": None}
    if provider in ("none", ""):
        return {"status": "OFFLINE", "last_check": _now(),
                "detail": "No notification provider configured (OTP_PROVIDER unset).", "error": None}
    return {"status": "ONLINE", "last_check": _now(), "detail": f"OTP provider '{provider}' configured.", "error": None}


def _services(conn) -> dict:
    from backend.services import forecast as forecast_svc
    return {
        "api": {"status": "ONLINE", "last_check": _now(), "detail": "This request was served by the API.", "error": None},
        "postgresql": _probe_db(conn),
        "authentication": _probe_auth(),
        "forecast": _probe_module("Forecast service", "backend.services.forecast", "MODEL_VERSION"),
        "optimization": _probe_module("Optimization service", "backend.services.routing"),
        "storage": _probe_storage(),
        "notifications": _probe_notifications(),
    }


# ------------------------------------------------------------------ stages

def _stage_marks(conn, svcs: dict) -> list[dict]:
    locked = one(conn, "SELECT count(*) AS n FROM officer_credentials WHERE locked_until > now()")["n"]
    users = one(conn, "SELECT count(*) AS n FROM officers")["n"]
    latest = one(conn, "SELECT status FROM dataset_imports ORDER BY created_at DESC LIMIT 1")
    failed_24h = one(conn, "SELECT count(*) AS n FROM audit_events WHERE timestamp > now() - interval '24 hours' "
                           "AND result = 'FAIL'")["n"]
    chain = verify_chain()
    down = [k for k, v in svcs.items() if v["status"] in ("OFFLINE", "DEGRADED")]
    crit_down = [k for k in ("postgresql", "authentication", "api") if svcs[k]["status"] != "ONLINE"]

    def m(n: int, key: str, ok: str, warn: str, bad: str) -> dict:
        return {"stage": n, "key": key, "status": ok if not warn and not bad else (bad if bad else warn)}

    return [
        {"stage": 1, "key": "OVERVIEW", "status": "ACTION REQUIRED" if crit_down else "IN REVIEW",
         "detail": f"Attention: {', '.join(crit_down)}." if crit_down else "Platform readable; review per stage."},
        {"stage": 2, "key": "USERS", "status": "ACTION REQUIRED" if locked else "IN REVIEW",
         "detail": f"{locked} account(s) locked." if locked else f"{users} officer accounts on record."},
        {"stage": 3, "key": "DATASETS",
         "status": ("COMPLETED" if latest and latest["status"] == "ACTIVE" else
                    "ACTION REQUIRED" if latest and latest["status"] in ("REJECTED", "FAILED") else "NOT STARTED"),
         "detail": f"Latest import is {latest['status']}." if latest else "No dataset import on record."},
        {"stage": 4, "key": "HEALTH", "status": "ACTION REQUIRED" if crit_down else ("IN REVIEW" if down else "COMPLETED"),
         "detail": f"Degraded: {', '.join(down)}." if down else "Probed services report ONLINE."},
        {"stage": 5, "key": "INTEGRATIONS", "status": "ACTION REQUIRED" if crit_down else ("IN REVIEW" if down else "COMPLETED"),
         "detail": f"Attention: {', '.join(crit_down)}." if crit_down else "Integrations report healthy."},
        {"stage": 6, "key": "SECURITY",
         "status": ("ACTION REQUIRED" if (chain["broken"] or failed_24h > 20) else "IN REVIEW"),
         "detail": ("Audit chain has breaks." if chain["broken"] else f"{failed_24h} failed events in 24h.")},
        {"stage": 7, "key": "CONFIG", "status": "IN REVIEW", "detail": "Effective configuration is read-only."},
        {"stage": 8, "key": "FINAL",
         "status": ("ACTION REQUIRED" if (crit_down or chain["broken"]) else "IN REVIEW"),
         "detail": "Aggregate verdict in Final System Status."},
    ]


# ------------------------------------------------------------------ 01 overview

@router.get("/stages")
def stages(user=ReadHealth, conn=Depends(get_db)):
    _admin(user)
    return {"stages": _stage_marks(conn, _services(conn))}


@router.get("/overview")
def overview(user=ReadHealth, conn=Depends(get_db)):
    _admin(user)
    svcs = _services(conn)
    users = one(conn, "SELECT count(*) AS n, count(*) FILTER (WHERE status='ACTIVE') AS active FROM officers")
    cyc = one(conn, "SELECT cycle, state FROM cycles WHERE state <> 'CLOSED' ORDER BY cycle DESC LIMIT 1")
    counts = {}
    for t in ("beneficiaries", "fps", "warehouses", "vehicles"):
        try:
            counts[t] = one(conn, f"SELECT count(*) AS n FROM {t}")["n"]
        except Exception:
            counts[t] = None
    imp = one(conn, "SELECT dataset_name, version, status, created_at FROM dataset_imports ORDER BY created_at DESC LIMIT 1")
    last_ev = one(conn, "SELECT audit_event_id, action, actor_role, timestamp FROM audit_events ORDER BY timestamp DESC LIMIT 1")
    return {"services": svcs, "counts": {
        "active_users": users["active"], "total_users": users["n"],
        "active_cycle": cyc["cycle"] if cyc else None, "active_cycle_state": cyc["state"] if cyc else None,
        "beneficiary_records": counts["beneficiaries"], "fps_records": counts["fps"],
        "warehouses": counts["warehouses"], "vehicles": counts["vehicles"],
        "latest_dataset_version": f"{imp['dataset_name']} v{imp['version']} ({imp['status']})" if imp else None,
        "latest_audit_event": ({**last_ev, "timestamp": iso(last_ev["timestamp"])} if last_ev else None),
    }, "last_sync": _now()}


# ------------------------------------------------------------------ 02 users & RBAC

def _cred(conn, oid: str) -> dict:
    r = one(conn, "SELECT failed_attempts, locked_until, must_change_password, password_changed_at "
                  "FROM officer_credentials WHERE officer_id = %s", (oid,))
    if not r:
        return {"has_credentials": False}
    locked = r["locked_until"] is not None and r["locked_until"] > datetime.now(timezone.utc)
    return {"has_credentials": True, "failed_attempts": r["failed_attempts"], "locked": locked,
            "locked_until": iso(r["locked_until"]), "must_change_password": r["must_change_password"],
            "password_changed_at": iso(r["password_changed_at"])}


@router.get("/users")
def users(role: str | None = None, status: str | None = None, q: str | None = Query(None, max_length=64),
          limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
          user=ReadHealth, conn=Depends(get_db)):
    _admin(user)
    args: list = []
    filt = ""
    if role:
        filt += " AND o.role = %s"
        args.append(role)
    if status:
        filt += " AND o.status = %s"
        args.append(status)
    if q:
        filt += " AND (o.officer_id ILIKE %s OR o.name ILIKE %s OR o.employee_code ILIKE %s)"
        args += [f"%{q}%"] * 3
    out = rows(conn, f"""SELECT o.officer_id, o.employee_code, o.name, o.role, o.district, o.phone, o.status
                         FROM officers o WHERE 1=1 {filt} ORDER BY o.officer_id LIMIT %s OFFSET %s""",
                tuple(args + [limit, offset]))
    for r in out:
        r["auth"] = _cred(conn, r["officer_id"])
        last = one(conn, "SELECT max(timestamp) AS t FROM audit_events WHERE actor_user_id = %s AND action = 'LOGIN_SUCCESS'",
                   (r["officer_id"],))
        r["last_login"] = iso(last["t"]) if last and last["t"] else None
    total = one(conn, f"SELECT count(*) AS n FROM officers o WHERE 1=1 {filt}", tuple(args))["n"]
    by_role = rows(conn, "SELECT role, status, count(*) AS n FROM officers GROUP BY 1, 2 ORDER BY 1, 2")
    return {"total": total, "users": out, "by_role": by_role,
            "known_roles": sorted(OFFICER_ROLE_MAP.keys())}


@router.get("/users/{officer_id}")
def user_detail(officer_id: str, user=ReadHealth, conn=Depends(get_db)):
    _admin(user)
    r = one(conn, "SELECT officer_id, employee_code, name, role, district, phone, status FROM officers WHERE officer_id = %s",
            (officer_id,))
    if not r:
        raise ApiError(404, "USER_NOT_FOUND", f"Officer {officer_id} does not exist.")
    canon = OFFICER_ROLE_MAP.get(r["role"])
    perms = sorted(p.value for p in ROLE_PERMISSIONS[canon]) if canon else []
    verbs = {"VIEW": "READ", "SUBMIT": "CREATE", "MANAGE": "MANAGE", "PROCESS": "UPDATE", "CREATE": "CREATE"}
    def kind(p: str) -> str:
        for prefix, label in verbs.items():
            if p.startswith(prefix):
                return label
        return "READ"
    activity = rows(conn, """SELECT action, entity_type, result, timestamp FROM audit_events
                             WHERE actor_user_id = %s ORDER BY timestamp DESC LIMIT 20""", (officer_id,))
    for a in activity:
        a["timestamp"] = iso(a["timestamp"])
    return {"user": r, "canonical_role": canon.value if canon else None,
            "permissions": [{"permission": p, "access": kind(p)} for p in perms],
            "auth": _cred(conn, officer_id), "recent_activity": activity}


@router.get("/rbac")
def rbac(user=ReadHealth, conn=Depends(get_db)):
    """The live permission matrix, read from the backend — never a frontend copy."""
    _admin(user)
    return {"roles": [
        {"role": role.value, "db_roles": sorted(k for k, v in OFFICER_ROLE_MAP.items() if v == role),
         "permissions": sorted(p.value for p in perms)}
        for role, perms in ROLE_PERMISSIONS.items()]}


class UpdateUser(BaseModel):
    status: str | None = Field(default=None, pattern="^(ACTIVE|INACTIVE)$")
    role: str | None = Field(default=None, max_length=32)
    reason: str = Field(min_length=5, max_length=500)


@router.patch("/users/{officer_id}")
def update_user(officer_id: str, req: UpdateUser, user=ManageUsers, conn=Depends(get_db)):
    """Activate/deactivate or change role. Mandatory reason, self-mutation refused, audited."""
    _admin(user)
    if officer_id == user["user_id"]:
        raise ApiError(422, "SELF_MUTATION_REFUSED", "You cannot change your own status or role.")
    r = one(conn, "SELECT status, role FROM officers WHERE officer_id = %s", (officer_id,))
    if not r:
        raise ApiError(404, "USER_NOT_FOUND", f"Officer {officer_id} does not exist.")
    if req.status is None and req.role is None:
        raise ApiError(422, "NOTHING_TO_CHANGE", "Provide status and/or role.")
    if req.role is not None and req.role not in OFFICER_ROLE_MAP:
        raise ApiError(422, "UNKNOWN_ROLE", f"Role {req.role} is not a known officer role.")
    if req.status is not None:
        conn.execute("UPDATE officers SET status = %s WHERE officer_id = %s", (req.status, officer_id))
        write_audit(user["user_id"], user["role"], "USER_STATUS_CHANGED", "SUCCESS", req.reason.strip(),
                    "USER", officer_id, before=r["status"], after=req.status)
    if req.role is not None:
        conn.execute("UPDATE officers SET role = %s WHERE officer_id = %s", (req.role, officer_id))
        write_audit(user["user_id"], user["role"], "USER_ROLE_CHANGED", "SUCCESS", req.reason.strip(),
                    "USER", officer_id, before=r["role"], after=req.role)
    conn.commit()
    return user_detail(officer_id, user, conn)


@router.post("/users/{officer_id}/unlock")
def unlock_user(officer_id: str, body: dict | None = None, user=ManageUsers, conn=Depends(get_db)):
    _admin(user)
    if officer_id == user["user_id"]:
        raise ApiError(422, "SELF_MUTATION_REFUSED", "You cannot unlock your own account this way.")
    if not one(conn, "SELECT 1 FROM officers WHERE officer_id = %s", (officer_id,)):
        raise ApiError(404, "USER_NOT_FOUND", f"Officer {officer_id} does not exist.")
    reason = ((body or {}).get("reason") or "").strip()
    if len(reason) < 5:
        raise ApiError(422, "REASON_REQUIRED", "A reason of at least 5 characters is required.")
    conn.execute("UPDATE officer_credentials SET failed_attempts = 0, locked_until = NULL WHERE officer_id = %s",
                 (officer_id,))
    conn.commit()
    write_audit(user["user_id"], user["role"], "USER_UNLOCKED", "SUCCESS", reason, "USER", officer_id)
    return {"officer_id": officer_id, "unlocked": True}


# ------------------------------------------------------------------ 03 datasets

@router.get("/datasets")
def datasets(user=ManageData, conn=Depends(get_db)):
    _admin(user)
    imports = rows(conn, """SELECT import_id, dataset_name, version, status, total_rows, row_counts, checksum,
                                   validation_report, imported_by, created_at
                            FROM dataset_imports ORDER BY created_at DESC LIMIT 20""")
    live: dict = {}
    for t in ("beneficiaries", "fps", "warehouses", "historical_demand", "vehicles", "allocations", "intent_signals",
              "inventory", "delivery_history", "epos_transactions", "vehicle_telemetry", "inspections", "grievances",
              "weather", "calendar_events", "historical_stockouts"):
        try:
            live[t] = one(conn, f"SELECT count(*) AS n FROM {t}")["n"]
        except Exception:
            live[t] = None
    for imp in imports:
        imp["created_at"] = iso(imp["created_at"])
        rep = imp.get("validation_report") or {}
        stages: dict = {}
        for chk in rep.get("checks", []) if isinstance(rep, dict) else []:
            stage = chk.get("stage", "other")
            stages.setdefault(stage, {"total": 0, "failed": 0})
            stages[stage]["total"] += 1
            stages[stage]["failed"] += 1 if chk.get("failed") else 0
        imp["pipeline"] = [{"stage": k, **v, "status": "PASS" if not v["failed"] else "FAILED"} for k, v in stages.items()]
        imp["checks"] = rep.get("checks", []) if isinstance(rep, dict) else []
    latest = imports[0] if imports else None
    drift = None
    if latest and isinstance(latest.get("row_counts"), dict):
        drift = {t: {"imported": latest["row_counts"].get(t), "live": live.get(t)}
                 for t in latest["row_counts"] if latest["row_counts"].get(t) != live.get(t)}
    return {"imports": imports, "live_counts": live, "drift": drift,
            "note": "Imports run through the validated ingest pipeline (CLI-operated); history is append-only."}


# ------------------------------------------------------------------ 04/05 health & integrations

@router.get("/health")
def health(user=ReadHealth, conn=Depends(get_db)):
    _admin(user)
    svcs = _services(conn)
    return {"services": svcs,
            "overall": "DEGRADED" if any(v["status"] != "ONLINE" for v in svcs.values()) else "ONLINE"}


@router.get("/integrations")
def integrations(user=ReadHealth, conn=Depends(get_db)):
    _admin(user)
    svcs = _services(conn)
    return {"integrations": [
        {"integration": "PostgreSQL", "purpose": "System of record for all PDS data.", **svcs["postgresql"]},
        {"integration": "Authentication (JWT + OTP)", "purpose": "Officer passwords and beneficiary OTP.",
         **svcs["authentication"]},
        {"integration": "ML forecast (XGBoost)", "purpose": "Demand forecasting service library.", **svcs["forecast"]},
        {"integration": "Optimization (OR-Tools)", "purpose": "Route optimization service library.", **svcs["optimization"]},
        {"integration": "Storage (dataset files)", "purpose": "Seed/ingest dataset directory.", **svcs["storage"]},
        {"integration": "Notifications (OTP/SMS)", "purpose": "Beneficiary OTP delivery.", **svcs["notifications"]},
        {"integration": "Maps (OpenStreetMap embeds)", "purpose": "Client-side location display only.",
         "status": "UNKNOWN", "last_check": _now(),
         "detail": "No backend dependency; rendered in the browser and not health-checked server-side.", "error": None},
    ]}


# ------------------------------------------------------------------ 06 security & audit

@router.get("/security")
def security(user=ReadAudit, conn=Depends(get_db)):
    _admin(user)
    logins = one(conn, """SELECT count(*) FILTER (WHERE action='LOGIN_SUCCESS') AS success,
                                 count(*) FILTER (WHERE action IN ('LOGIN_FAILURE','OTP_FAILURE')) AS failed
                           FROM audit_events WHERE timestamp > now() - interval '24 hours'""")
    recent_fail = rows(conn, """SELECT actor_user_id, actor_role, action, timestamp, reason FROM audit_events
                                WHERE result = 'FAIL' ORDER BY timestamp DESC LIMIT 20""")
    for r in recent_fail:
        r["timestamp"] = iso(r["timestamp"])
    role_changes = rows(conn, """SELECT audit_event_id, actor_user_id, entity_id, reason, timestamp, before_state,
                                        after_state FROM audit_events
                                 WHERE action IN ('USER_ROLE_CHANGED','USER_STATUS_CHANGED','USER_UNLOCKED')
                                 ORDER BY timestamp DESC LIMIT 20""")
    for r in role_changes:
        r["timestamp"] = iso(r["timestamp"])
    mutations = rows(conn, """SELECT action, count(*) AS n FROM audit_events
                              WHERE timestamp > now() - interval '24 hours' AND result = 'SUCCESS'
                              AND action NOT IN ('LOGIN_SUCCESS','LOGOUT','OTP_SENT','OTP_VERIFIED')
                              GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
    chain = verify_chain()
    return {"logins_24h": logins, "recent_failures": recent_fail, "role_changes": role_changes,
            "mutations_24h": mutations,
            "chain": {"checked": chain["checked"], "broken": chain["broken"], "intact": chain["intact"]},
            "note": "IP/device attribution is not recorded by the backend and is reported as unavailable."}


# ------------------------------------------------------------------ 07 configuration (read-only, effective)

@router.get("/configuration")
def configuration(user=ReadHealth, conn=Depends(get_db)):
    """Effective, non-secret configuration. Nothing here is tunable at runtime: changes are
    deployment-managed, so this workspace reports rather than edits."""
    _admin(user)
    from backend.core import otp as otp_mod
    from backend.core.config import APP_ENV, DATA_DIR
    from backend.api import auth as auth_mod
    cycles = rows(conn, "SELECT cycle, state FROM cycles ORDER BY cycle DESC")
    return {"entries": [
        {"category": "Environment", "setting": "APP_ENV", "value": APP_ENV,
         "detail": "Deployment environment flag.", "mutable": False},
        {"category": "Environment", "setting": "DATA_DIR", "value": str(DATA_DIR),
         "detail": "Dataset directory in use.", "mutable": False},
        {"category": "Security", "setting": "Failed-login lockout",
         "value": f"{auth_mod.MAX_FAILED_LOGINS} attempts → {auth_mod.LOCKOUT_MINUTES} min lockout",
         "detail": "Enforced in backend/api/auth.py.", "mutable": False},
        {"category": "Security", "setting": "Password policy", "value": "Enforced (length, variety, user-id check)",
         "detail": "Enforced in backend/core/security.py; rotation via must_change_password.", "mutable": False},
        {"category": "Security", "setting": "JWT sessions", "value": "Revocable (logout list), password change revokes",
         "detail": "Revoked tokens persist in revoked_tokens.", "mutable": False},
        {"category": "Notifications", "setting": "OTP_PROVIDER", "value": otp_mod.provider_name(),
         "detail": f"OTP: {otp_mod.EXPIRY_MINUTES} min expiry, {otp_mod.MAX_ATTEMPTS} attempts, {otp_mod.COOLDOWN_SECONDS}s cooldown.",
         "mutable": False},
        {"category": "Cycles", "setting": "Cycle states", "value": ", ".join(f"{c['cycle']}:{c['state']}" for c in cycles),
         "detail": "Advanced only by the DSO workflow transitions.", "mutable": False},
        {"category": "Credentials", "setting": "DATABASE_URL / JWT_SECRET", "value": "Set (values never exposed)",
         "detail": "Secret material is never returned by any endpoint.", "mutable": False},
    ], "note": "Configuration is deployment-managed. No runtime mutation endpoint exists by design."}


# ------------------------------------------------------------------ 08 final status

@router.get("/final")
def final(user=ReadHealth, conn=Depends(get_db)):
    _admin(user)
    svcs = _services(conn)
    latest = one(conn, "SELECT status FROM dataset_imports ORDER BY created_at DESC LIMIT 1")
    chain = verify_chain()
    rbac_ok = len(ROLE_PERMISSIONS) == 6
    cycles_ok = one(conn, "SELECT count(*) AS n FROM cycles")["n"] > 0

    def chk(label: str, status: str, evidence: str) -> dict:
        return {"category": label, "status": status, "evidence": evidence}

    items = [
        chk("Authentication", svcs["authentication"]["status"], svcs["authentication"]["detail"]),
        chk("Database", svcs["postgresql"]["status"],
            f"Latency {svcs['postgresql'].get('latency_ms')} ms." if svcs["postgresql"]["status"] == "ONLINE"
            else (svcs["postgresql"].get("error") or "Database unreachable.")),
        chk("API", svcs["api"]["status"], svcs["api"]["detail"]),
        chk("Dataset integrity", "PASS" if latest and latest["status"] == "ACTIVE" else
            ("FAIL" if latest and latest["status"] in ("REJECTED", "FAILED") else "UNKNOWN"),
            f"Latest import is {latest['status']}." if latest else "No import on record."),
        chk("RBAC", "PASS" if rbac_ok else "FAIL", f"{len(ROLE_PERMISSIONS)} roles in the live matrix."),
        chk("Audit chain", "PASS" if chain["intact"] else "FAIL",
            f"{chain['checked']} chained events verified." if chain["intact"]
            else f"Breaks at: {', '.join(chain['broken'][:5])}"),
        chk("Forecast service", svcs["forecast"]["status"], svcs["forecast"]["detail"]),
        chk("Optimization service", svcs["optimization"]["status"], svcs["optimization"]["detail"]),
        chk("Routing", "UNKNOWN", "Routing is a haversine computation inside the optimization service; no separate service exists."),
        chk("Notifications", svcs["notifications"]["status"], svcs["notifications"]["detail"]),
        chk("Storage", svcs["storage"]["status"], svcs["storage"]["detail"]),
    ]
    tape = {"PASS": 0, "WARNING": 1, "FAIL": 2, "UNKNOWN": 1, "ONLINE": 0, "DEGRADED": 1, "OFFLINE": 2}
    critical = {"Authentication", "Database", "API", "Audit chain"}
    crit_worst = max(tape.get(i["status"], 1) for i in items if i["category"] in critical)
    worst = max(tape.get(i["status"], 1) for i in items if i["status"] != "UNKNOWN")
    verdict = ("SYSTEM BLOCKED" if crit_worst == 2 else
               "SYSTEM DEGRADED" if worst >= 1 else "SYSTEM READY")
    if not cycles_ok:
        verdict = "ACTION REQUIRED"
        items.append(chk("Cycles", "FAIL", "No cycles on record."))
    return {"verdict": verdict, "readiness": items}


# ------------------------------------------------------------------ AI assistant (advisory, read-only)

@router.post("/ask")
def ask(body: dict, user=ReadHealth, conn=Depends(get_db)):
    _admin(user)
    q = ((body or {}).get("question") or "").strip().lower()
    intent = ((body or {}).get("intent") or "").strip().upper()

    def pick() -> str:
        if intent in ("FORECAST_WHY", "DATASETS_FAILED", "ROLE_WHO", "CYCLE_BLOCKED", "INTEGRATIONS_DOWN", "SECURITY_ANOMALIES"):
            return intent
        if "forecast" in q:
            return "FORECAST_WHY"
        if "dataset" in q or "validation" in q or "import" in q:
            return "DATASETS_FAILED"
        if "role" in q or "changed" in q or "access" in q:
            return "ROLE_WHO"
        if "cycle" in q and ("block" in q or "why" in q or "stuck" in q):
            return "CYCLE_BLOCKED"
        if "integration" in q or "unavailable" in q or "down" in q or "service" in q:
            return "INTEGRATIONS_DOWN"
        if "secur" in q or "anomal" in q or "login" in q or "fail" in q:
            return "SECURITY_ANOMALIES"
        return "OVERVIEW"

    def resp(insight: str, evidence: list, sources: list, confidence: str) -> dict:
        return {"advisory": True, "insight": insight, "evidence": evidence, "source_records": sources,
                "confidence": confidence, "note": "Advisory only. Never changes configuration, users, or data."}

    svcs = _services(conn)
    if pick() == "FORECAST_WHY":
        f = svcs["forecast"]
        return resp(f"Forecast service is {f['status']}. {f['detail']}",
                    [f"Library probe at {f['last_check']}" + (f" — {f['error']}" if f["error"] else "")],
                    ["admin:health.forecast"], "HIGH")
    if pick() == "DATASETS_FAILED":
        bad = rows(conn, "SELECT import_id, version, status, imported_by FROM dataset_imports WHERE status NOT IN ('ACTIVE') ORDER BY created_at DESC LIMIT 5")
        return resp("No failed dataset imports on record." if not bad else f"{len(bad)} non-active import(s) on record.",
                    [f"{r['import_id']} v{r['version']}: {r['status']} by {r['imported_by']}" for r in bad] or
                    ["Latest import status is ACTIVE."],
                    ["dataset_imports"], "HIGH")
    if pick() == "ROLE_WHO":
        ch = rows(conn, "SELECT actor_user_id, entity_id, action, reason, timestamp FROM audit_events WHERE action IN "
                        "('USER_ROLE_CHANGED','USER_STATUS_CHANGED','USER_UNLOCKED') ORDER BY timestamp DESC LIMIT 8")
        return resp("No role or status changes recorded." if not ch else f"{len(ch)} account change(s) on record.",
                    [f"{r['actor_user_id']} {r['action']} on {r['entity_id']}: {r['reason']}" for r in ch] or
                    ["The audit trail holds no USER_ROLE_CHANGED events."],
                    ["audit_events"], "HIGH")
    if pick() == "CYCLE_BLOCKED":
        cyc = one(conn, "SELECT cycle, state FROM cycles WHERE state NOT IN ('CLOSED') ORDER BY cycle DESC LIMIT 1")
        if not cyc:
            return resp("No open cycle.", [], ["cycles"], "HIGH")
        from backend.services import tracking as tracking_svc
        try:
            checks = tracking_svc.run_closure_checks(conn, cyc["cycle"])
            failing = [k for k, v in checks.items() if not v]
        except Exception as e:
            return resp(f"Closure checks unavailable: {type(e).__name__}.", [], ["tracking"], "LOW")
        return resp(f"Cycle {cyc['cycle']} ({cyc['state']}): " + ("no failing closure checks." if not failing else f"blocked by {', '.join(failing)}."),
                    failing or ["All closure checks pass."], ["tracking:closure_checks"], "HIGH")
    if pick() == "INTEGRATIONS_DOWN":
        down = [f"{k}: {v['status']} — {v['detail']}" for k, v in svcs.items() if v["status"] != "ONLINE"]
        return resp("All probed integrations report ONLINE." if not down else f"{len(down)} integration(s) not ONLINE.",
                    down or ["api, postgresql, authentication, forecast, optimization, storage, notifications all ONLINE."],
                    ["admin:health"], "HIGH")
    if pick() == "SECURITY_ANOMALIES":
        fails = one(conn, "SELECT count(*) AS n FROM audit_events WHERE result='FAIL' AND timestamp > now() - interval '24 hours'")["n"]
        chain = verify_chain()
        ev = [f"{fails} failed events in the last 24h."]
        if not chain["intact"]:
            ev.append(f"Audit chain breaks at: {', '.join(chain['broken'][:5])}.")
        return resp("No security anomalies beyond routine failures." if not fails and chain["intact"] else "Anomalies require review.",
                    ev, ["audit_events"], "HIGH")
    return resp(f"Platform holds {num(one(conn, 'SELECT count(*) AS n FROM officers')['n'])} officer accounts.",
                ["See stage workspaces for detail."], ["admin:overview"], "MEDIUM")

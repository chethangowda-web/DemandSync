"""Unified authentication API: beneficiaries (ration card + mobile + OTP) and officers (ID + password)."""
import hmac

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.core import otp as otp_service
from backend.core.errors import ApiError
from backend.core.audit import write_audit
from backend.core.auth_middleware import (BENEFICIARY_LOGIN_STATUSES, MSG_DISABLED, OFFICER_LOGIN_STATUSES,
                                          get_current_user, require_permission)
from backend.core.rbac import Permission, Role, canonical_officer_role, portal_for
from backend.core.security import (create_access_token, hash_password, password_policy_error, verify_password)
from backend.db.conn import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

MSG_BAD_CREDENTIALS = "The credentials provided could not be verified. Please check your details and try again."
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password-1")  # so unknown IDs cost the same as known ones


class BeneficiaryRequestOtp(BaseModel):
    ration_card_id: str = Field(min_length=1, max_length=32)
    registered_mobile: str = Field(min_length=1, max_length=20)


class BeneficiaryVerifyOtp(BaseModel):
    ration_card_id: str = Field(min_length=1, max_length=32)
    otp: str = Field(min_length=1, max_length=12)


class OfficerLogin(BaseModel):
    officer_id: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=256)


class BootstrapFirstAdmin(BaseModel):
    officer_id: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=256)


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


# ------------------------------------------------------------------ beneficiary

def _otp_error(reason: str) -> ApiError:
    """Turn an OTP failure reason into a stable code the mobile app can localise."""
    import re
    m = re.match(r"Invalid OTP\. (\d) attempts remaining", reason)
    if m:
        return ApiError(401, "OTP_INVALID", reason, {"attempts_left": int(m.group(1))})
    table = (("Invalid OTP", "OTP_INVALID_LAST"), ("No OTP requested", "OTP_NOT_REQUESTED"), ("OTP already used", "OTP_USED"),
             ("OTP expired", "OTP_EXPIRED"), ("Too many attempts", "OTP_TOO_MANY_ATTEMPTS"))
    code = next((c for prefix, c in table if reason.startswith(prefix)), "OTP_FAILED")
    return ApiError(401, code, reason)


@router.post("/beneficiary/request-otp")
def beneficiary_request_otp(req: BeneficiaryRequestOtp, conn=Depends(get_db)):
    rc = req.ration_card_id
    row = conn.execute("SELECT registered_mobile, status FROM beneficiaries WHERE ration_card_id = %s", (rc,)).fetchone()
    if not row or not hmac.compare_digest(row[0], req.registered_mobile):
        write_audit(rc, "BENEFICIARY", "LOGIN_FAILURE", "FAIL", "Unknown ration card or mobile mismatch")
        raise ApiError(401, "BAD_CREDENTIALS", MSG_BAD_CREDENTIALS)  # same answer for both: no account enumeration
    if row[1] not in BENEFICIARY_LOGIN_STATUSES:
        write_audit(rc, "BENEFICIARY", "ACCOUNT_DISABLED", "FAIL", f"status {row[1]}")
        raise ApiError(401, "ACCOUNT_DISABLED", MSG_DISABLED)
    try:
        result = otp_service.request_otp(conn, rc)
    except otp_service.OtpProviderNotConfigured:
        raise ApiError(503, "OTP_UNAVAILABLE", "OTP delivery is not available right now. Please try again later.")
    except otp_service.OtpThrottled as e:
        write_audit(rc, "BENEFICIARY", "OTP_REQUEST_THROTTLED", "FAIL", f"cooldown {e.retry_after}s")
        err = ApiError(429, "OTP_COOLDOWN", str(e), {"retry_after": e.retry_after})
        err.headers = {"Retry-After": str(e.retry_after)}
        raise err
    conn.commit()
    write_audit(rc, "BENEFICIARY", "OTP_SENT", "SUCCESS")
    return result


@router.post("/beneficiary/verify-otp")
def beneficiary_verify_otp(req: BeneficiaryVerifyOtp, conn=Depends(get_db)):
    rc = req.ration_card_id
    row = conn.execute("SELECT beneficiary_id, status FROM beneficiaries WHERE ration_card_id = %s", (rc,)).fetchone()
    if not row:
        write_audit(rc, "BENEFICIARY", "OTP_FAILURE", "FAIL", "Unknown ration card")
        raise ApiError(401, "BAD_CREDENTIALS", MSG_BAD_CREDENTIALS)
    valid, reason = otp_service.verify_otp(conn, rc, req.otp)
    conn.commit()  # failed attempts must persist even though we raise below
    if not valid:
        write_audit(rc, "BENEFICIARY", "OTP_FAILURE", "FAIL", reason)
        raise _otp_error(reason)
    if row[1] not in BENEFICIARY_LOGIN_STATUSES:
        write_audit(rc, "BENEFICIARY", "ACCOUNT_DISABLED", "FAIL", f"status {row[1]}")
        raise ApiError(401, "ACCOUNT_DISABLED", MSG_DISABLED)
    write_audit(rc, "BENEFICIARY", "OTP_VERIFIED", "SUCCESS")
    write_audit(rc, "BENEFICIARY", "LOGIN_SUCCESS", "SUCCESS")
    return {"access_token": create_access_token(rc, Role.BENEFICIARY.value), "token_type": "bearer",
            "role": Role.BENEFICIARY.value, "beneficiary_id": row[0], "ration_card_id": rc,
            "portal": portal_for(Role.BENEFICIARY.value)}


# ------------------------------------------------------------------ officer

def _register_failed_login(conn, officer_id: str) -> None:
    conn.execute(
        """UPDATE officer_credentials SET failed_attempts = failed_attempts + 1,
               locked_until = CASE WHEN failed_attempts + 1 >= %s THEN now() + make_interval(mins => %s) ELSE locked_until END
           WHERE officer_id = %s""", (MAX_FAILED_LOGINS, LOCKOUT_MINUTES, officer_id))
    conn.commit()


@router.post("/officer/bootstrap-first-admin", status_code=201)
def bootstrap_first_admin(req: BootstrapFirstAdmin, conn=Depends(get_db)):
    """One-time-only initial credential provisioning: works ONLY while officer_credentials is completely
    empty (a fresh deployment nobody has logged into yet). The moment any officer has a password set --
    whether by this endpoint or any other means -- this permanently refuses, forever. No separate secret
    or token is needed; "nobody has ever set a password yet" is itself the one-time gate. must_change_password
    is set, so whoever provisions it here is required to pick their own password on first real login."""
    existing = conn.execute("SELECT count(*) FROM officer_credentials").fetchone()[0]
    if existing > 0:
        raise HTTPException(403, "Bootstrap already used: this instance already has officer credentials set.")
    if not conn.execute("SELECT 1 FROM officers WHERE officer_id = %s", (req.officer_id,)).fetchone():
        raise HTTPException(404, "Unknown officer_id.")
    problem = password_policy_error(req.password, req.officer_id)
    if problem:
        raise HTTPException(422, problem)
    conn.execute(
        """INSERT INTO officer_credentials (officer_id, password_hash, must_change_password)
           VALUES (%s, %s, true)""",
        (req.officer_id, hash_password(req.password)))
    conn.commit()
    write_audit(req.officer_id, "SYSTEM", "CREDENTIAL_BOOTSTRAP", "SUCCESS", "first-run bootstrap: no prior credentials existed")
    return {"status": "ok", "officer_id": req.officer_id, "must_change_password": True}


@router.post("/officer/login")
def officer_login(req: OfficerLogin, conn=Depends(get_db)):
    oid = req.officer_id
    row = conn.execute(
        """SELECT o.name, o.role, o.status, c.password_hash, c.must_change_password,
                  COALESCE(c.locked_until > now(), false)
           FROM officers o LEFT JOIN officer_credentials c USING (officer_id) WHERE o.officer_id = %s""",
        (oid,)).fetchone()
    if not row or not row[3]:
        verify_password(req.password, _DUMMY_HASH)
        write_audit(oid, "unknown", "LOGIN_FAILURE", "FAIL", "Unknown officer or no credentials set")
        raise HTTPException(401, MSG_BAD_CREDENTIALS)
    name, db_role, status, pw_hash, must_change, locked = row
    if locked:
        write_audit(oid, db_role, "LOGIN_FAILURE", "FAIL", "Account temporarily locked")
        raise HTTPException(401, MSG_BAD_CREDENTIALS)
    if not verify_password(req.password, pw_hash):
        _register_failed_login(conn, oid)
        write_audit(oid, db_role, "LOGIN_FAILURE", "FAIL", "Wrong password")
        raise HTTPException(401, MSG_BAD_CREDENTIALS)
    role = canonical_officer_role(db_role)
    if status not in OFFICER_LOGIN_STATUSES or role is None:
        write_audit(oid, db_role, "ACCOUNT_DISABLED", "FAIL", f"status {status}")
        raise HTTPException(401, MSG_DISABLED)
    conn.execute("UPDATE officer_credentials SET failed_attempts = 0, locked_until = NULL WHERE officer_id = %s", (oid,))
    conn.commit()
    write_audit(oid, role.value, "LOGIN_SUCCESS", "SUCCESS")
    return {"access_token": create_access_token(oid, role.value), "token_type": "bearer", "role": role.value,
            "officer_id": oid, "name": name, "portal": portal_for(role.value), "must_change_password": must_change}


@router.post("/change-password")
def change_password(req: ChangePassword, user=Depends(get_current_user), conn=Depends(get_db)):
    if user["role"] == Role.BENEFICIARY.value:
        raise HTTPException(403, "Beneficiaries sign in with an OTP and have no password.")
    oid = user["user_id"]
    stored = conn.execute("SELECT password_hash FROM officer_credentials WHERE officer_id = %s", (oid,)).fetchone()
    if not stored or not verify_password(req.current_password, stored[0]):
        _register_failed_login(conn, oid)
        write_audit(oid, user["role"], "PASSWORD_CHANGE_FAILURE", "FAIL", "Current password incorrect")
        raise HTTPException(401, MSG_BAD_CREDENTIALS)
    problem = password_policy_error(req.new_password, oid)
    if problem is None and req.new_password == req.current_password:
        problem = "New password must differ from the current one."
    if problem:
        raise HTTPException(422, problem)
    conn.execute(
        """UPDATE officer_credentials SET password_hash = %s, must_change_password = false, failed_attempts = 0,
               locked_until = NULL, password_changed_at = now() WHERE officer_id = %s""",
        (hash_password(req.new_password), oid))
    _revoke(conn, user)  # the session that changed the password must sign in again
    write_audit(oid, user["role"], "PASSWORD_CHANGED", "SUCCESS")
    return {"message": "Password changed. Please sign in again."}


# ------------------------------------------------------------------ session

def _revoke(conn, user: dict) -> None:
    conn.execute("DELETE FROM revoked_tokens WHERE expires_at < now()")
    conn.execute("INSERT INTO revoked_tokens (jti, expires_at) VALUES (%s, to_timestamp(%s)) ON CONFLICT DO NOTHING",
                 (user["token"]["jti"], user["token"]["exp"]))


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"user_id": user["user_id"], "role": user["role"], "name": user["name"], "status": user["status"],
            "district": user["district"], "portal": portal_for(user["role"]), "permissions": user["permissions"],
            "beneficiary_id": user["beneficiary_id"], "must_change_password": user["must_change_password"]}


@router.post("/logout")
def logout(user=Depends(get_current_user), conn=Depends(get_db)):
    _revoke(conn, user)
    conn.commit()
    write_audit(user["user_id"], user["role"], "LOGOUT", "SUCCESS")
    return {"message": "Logged out. Please sign in again."}


@router.get("/audit")
def auth_audit(limit: int = 100, action: str | None = None, user=Depends(require_permission(Permission.VIEW_AUDIT)),
               conn=Depends(get_db)):
    """Most recent audit events (newest first). SYSTEM_ADMIN, AUDITOR and DSO only."""
    limit = max(1, min(limit, 200))
    rows = conn.execute(
        """SELECT audit_event_id, actor_user_id, actor_role, action, entity_type, entity_id, result, reason, timestamp
           FROM audit_events WHERE (%(a)s::text IS NULL OR action = %(a)s) ORDER BY timestamp DESC LIMIT %(n)s""",
        {"a": action, "n": limit}).fetchall()
    keys = ("audit_event_id", "actor_user_id", "actor_role", "action", "entity_type", "entity_id", "result", "reason", "timestamp")
    return {"events": [dict(zip(keys, (r[:-1] + (r[-1].isoformat(),)))) for r in rows]}

"""Authentication and authorization dependencies. One path for every role.

- 401: not authenticated (missing/invalid/expired/revoked token, unknown or disabled account)
- 403: authenticated but not allowed (role mismatch vs the database, missing permission, password change pending)
The role in a token is never trusted on its own: it must match the role stored in the database.
"""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.audit import write_audit
from backend.core.rbac import Permission, Role, canonical_officer_role, get_permissions, has_permission
from backend.core.security import ExpiredSignatureError, JWTError, decode_token
from backend.db.conn import get_db

bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access_token returned by a login endpoint")

BENEFICIARY_LOGIN_STATUSES = {"ACTIVE", "MIGRATED"}  # MIGRATED cardholders may still collect (ONORC portability)
OFFICER_LOGIN_STATUSES = {"ACTIVE"}
PASSWORD_CHANGE_ALLOWED_PATHS = {"/api/v1/auth/me", "/api/v1/auth/change-password", "/api/v1/auth/logout"}

MSG_AUTH_REQUIRED = "Authentication required. Please sign in again."
MSG_SESSION_EXPIRED = "Session expired. Please sign in again."
MSG_FORBIDDEN = "Access restricted. Your account does not have permission to access this section."
MSG_DISABLED = "Account disabled. Contact administrator."


def _deny(status: int, detail: str, actor: str, role: str, action: str, reason: str) -> HTTPException:
    write_audit(actor, role, action, "FAIL", reason)
    return HTTPException(status, detail)


def get_current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
                     conn=Depends(get_db)) -> dict:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(401, MSG_AUTH_REQUIRED)
    try:
        payload = decode_token(creds.credentials)
    except ExpiredSignatureError:
        raise _deny(401, MSG_SESSION_EXPIRED, "unknown", "unknown", "TOKEN_EXPIRED", "JWT expired")
    except JWTError:
        raise _deny(401, "Invalid token. Please sign in again.", "unknown", "unknown", "INVALID_TOKEN", "JWT invalid")

    sub, role, jti = payload.get("sub"), payload.get("role"), payload.get("jti")
    if not (sub and role and jti) or payload.get("type") != "access":
        raise _deny(401, "Invalid token. Please sign in again.", "unknown", "unknown", "INVALID_TOKEN", "malformed claims")
    if conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = %s", (jti,)).fetchone():
        raise HTTPException(401, MSG_SESSION_EXPIRED)

    if role == Role.BENEFICIARY.value:
        row = conn.execute(
            "SELECT beneficiary_id, head_of_household, status, district FROM beneficiaries WHERE ration_card_id = %s",
            (sub,)).fetchone()
        if not row:
            raise _deny(401, "Account not found.", sub, role, "UNAUTHORIZED_ACCESS_ATTEMPT", "unknown subject")
        if row[2] not in BENEFICIARY_LOGIN_STATUSES:
            raise _deny(401, MSG_DISABLED, sub, role, "ACCOUNT_DISABLED", f"status {row[2]}")
        user = {"user_id": sub, "role": role, "name": row[1], "status": row[2], "district": row[3],
                "beneficiary_id": row[0], "ration_card_id": sub, "must_change_password": False}
    else:
        row = conn.execute(
            """SELECT o.officer_id, o.name, o.role, o.status, o.district, COALESCE(c.must_change_password, false)
               FROM officers o LEFT JOIN officer_credentials c USING (officer_id) WHERE o.officer_id = %s""",
            (sub,)).fetchone()
        if not row:
            raise _deny(401, "Account not found.", sub, role, "UNAUTHORIZED_ACCESS_ATTEMPT", "unknown subject")
        db_role = canonical_officer_role(row[2])
        if db_role is None or db_role.value != role:
            raise _deny(403, MSG_FORBIDDEN, sub, role, "FORBIDDEN_ACCESS_ATTEMPT",
                        f"token role {role} does not match database role {row[2]}")
        if row[3] not in OFFICER_LOGIN_STATUSES:
            raise _deny(401, MSG_DISABLED, sub, role, "ACCOUNT_DISABLED", f"status {row[3]}")
        user = {"user_id": sub, "role": role, "name": row[1], "status": row[3], "district": row[4],
                "beneficiary_id": None, "must_change_password": row[5]}

    if user["must_change_password"] and request.url.path not in PASSWORD_CHANGE_ALLOWED_PATHS:
        raise HTTPException(403, "Password change required before continuing.")
    user["permissions"] = sorted(p.value for p in get_permissions(role))
    user["token"] = {"jti": jti, "exp": payload.get("exp")}
    return user


def require_role(*roles: Role):
    allowed = {r.value for r in roles}

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed:
            raise _deny(403, MSG_FORBIDDEN, user["user_id"], user["role"], "FORBIDDEN_ACCESS_ATTEMPT",
                        f"requires one of {sorted(allowed)}")
        return user

    return checker


def require_permission(permission: Permission):
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if not has_permission(user["role"], permission):
            raise _deny(403, MSG_FORBIDDEN, user["user_id"], user["role"], "FORBIDDEN_ACCESS_ATTEMPT",
                        f"missing permission {permission.value}")
        return user

    return checker

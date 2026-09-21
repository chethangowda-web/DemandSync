"""
Authentication middleware — get_current_user, require_role, audit logging.
"""
from fastapi import Depends, HTTPException, Header
from typing import Optional
import pandas as pd
from pathlib import Path
from jose import JWTError, ExpiredSignatureError
from .security import decode_token
from .rbac import Role, get_permissions
from datetime import datetime

from .config import DATA_DIR as DATA
# In-memory audit (Phase 0); DB-backed in Phase 1
_auth_audit = []
_token_blacklist = set()

def audit_log(actor, role, action, result, reason=""):
    _auth_audit.append({
        "actor": actor, "role": role, "action": action,
        "timestamp": datetime.utcnow().isoformat(), "result": result, "reason": reason
    })

def get_audit(): return _auth_audit

def load_officers():
    try: return pd.read_csv(DATA/"01_master/officers_master.csv", dtype=str).fillna("")
    except: return pd.DataFrame()

def load_beneficiaries():
    try: return pd.read_csv(DATA/"01_master/beneficiaries_master.csv", dtype=str).fillna("")
    except: return pd.DataFrame()

# Password hashes for officers — generated on startup from officers_master, with default password hashed (for prototype)
# In production, officers set own passwords via secure flow.
_officer_password_hashes = {}
def ensure_officer_hashes():
    if _officer_password_hashes: return
    from .security import hash_password
    df = load_officers()
    # For prototype, seed each officer with password = officer_id + "@123" hashed (documented, not hardcoded universal)
    # Example: OFF-00001 password is OFF-00001@123 — clearly per-user, not universal 123456
    for _, r in df.iterrows():
        oid = r["officer_id"]
        # Use deterministic per-officer password for testing: <OFFICER_ID>@Test123
        default_pwd = f"{oid}@Test123"
        _officer_password_hashes[oid] = hash_password(default_pwd)

ensure_officer_hashes()

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        audit_log("unknown", "unknown", "UNAUTHORIZED_ACCESS_ATTEMPT", "FAIL", "Missing token")
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in again.")
    token = authorization.split(" ",1)[1]
    if token in _token_blacklist:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        role = payload.get("role")
        if not sub or not role:
            raise HTTPException(status_code=401, detail="Invalid token.")
        # Verify user exists and ACTIVE
        if role == Role.BENEFICIARY:
            df = load_beneficiaries()
            row = df[df.ration_card_id==sub] if "ration_card_id" in df.columns else df[df.beneficiary_id==sub]
            if row.empty:
                raise HTTPException(status_code=401, detail="Account not found.")
            status = row.iloc[0].get("status","ACTIVE")
            if status in ["DISABLED","SUSPENDED"]:
                audit_log(sub, role, "ACCOUNT_DISABLED", "FAIL", f"Status {status}")
                raise HTTPException(status_code=401, detail="Account disabled. Contact administrator.")
            return {"user_id": sub, "role": role, "beneficiary_id": row.iloc[0].get("beneficiary_id"), "status": status, "permissions": list(get_permissions(role))}
        else:
            df = load_officers()
            row = df[df.officer_id==sub]
            if row.empty:
                raise HTTPException(status_code=401, detail="Account not found.")
            status = row.iloc[0].get("status","ACTIVE")
            if status in ["DISABLED","SUSPENDED"]:
                audit_log(sub, role, "ACCOUNT_DISABLED", "FAIL", f"Status {status}")
                raise HTTPException(status_code=401, detail="Account disabled. Contact administrator.")
            # Verify role matches token vs DB (prevent frontend role spoofing)
            db_role = row.iloc[0].get("role")
            # Allow DSO alias
            if db_role != role and not (db_role=="DISTRICT_OFFICER" and role=="DSO") and not (db_role=="ADMIN" and role=="SYSTEM_ADMIN"):
                audit_log(sub, role, "FORBIDDEN_ACCESS_ATTEMPT", "FAIL", f"Role mismatch token {role} vs DB {db_role}")
                raise HTTPException(status_code=403, detail="Access restricted. Your account does not have permission for this role.")
            return {"user_id": sub, "role": role, "name": row.iloc[0].get("name"), "status": status, "permissions": list(get_permissions(role))}
    except ExpiredSignatureError:
        audit_log("unknown", "unknown", "TOKEN_EXPIRED", "FAIL", "JWT expired")
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    except JWTError as e:
        audit_log("unknown", "unknown", "UNAUTHORIZED_ACCESS_ATTEMPT", "FAIL", str(e))
        raise HTTPException(status_code=401, detail="Invalid token. Please sign in again.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication failed. Please sign in again.")

def require_role(*roles):
    def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            audit_log(user["user_id"], user["role"], "FORBIDDEN_ACCESS_ATTEMPT", "FAIL", f"Required {roles}, has {user['role']}")
            raise HTTPException(status_code=403, detail="Access restricted. Your account does not have permission to access this section.")
        return user
    return checker

def require_permission(permission):
    def checker(user=Depends(get_current_user)):
        from .rbac import has_permission, Permission
        # permission may be string
        perm = Permission(permission) if isinstance(permission, str) else permission
        if not has_permission(user["role"], perm):
            audit_log(user["user_id"], user["role"], "FORBIDDEN_ACCESS_ATTEMPT", "FAIL", f"Missing permission {perm}")
            raise HTTPException(status_code=403, detail="Access restricted. Your account does not have permission to access this section.")
        return user
    return checker

def blacklist_token(token: str):
    _token_blacklist.add(token)

"""
Unified Authentication API — Phase 0
Supports BENEFICIARY (RC+mobile+OTP) and OFFICER (officer_id+password).
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from pathlib import Path
from datetime import datetime
from ..core.otp import otp_service
from ..core.security import verify_password, create_access_token, hash_password
from ..core.auth_middleware import get_current_user, require_role, audit_log, blacklist_token, ensure_officer_hashes, _officer_password_hashes, load_officers, load_beneficiaries
from ..core.rbac import get_permissions

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
from ..core.config import DATA_DIR as DATA

class BeneficiaryRequestOtp(BaseModel):
    ration_card_id: str
    registered_mobile: str

class BeneficiaryVerifyOtp(BaseModel):
    ration_card_id: str
    otp: str

class OfficerLogin(BaseModel):
    officer_id: str
    password: str

@router.post("/beneficiary/request-otp")
def beneficiary_request_otp(req: BeneficiaryRequestOtp):
    df = load_beneficiaries()
    row = df[df.ration_card_id==req.ration_card_id]
    if row.empty:
        audit_log(req.ration_card_id, "BENEFICIARY", "LOGIN_FAILURE", "FAIL", "Ration card not found")
        raise HTTPException(404, "Ration card not found in system.")
    ben = row.iloc[0]
    if ben["registered_mobile"] != req.registered_mobile:
        audit_log(req.ration_card_id, "BENEFICIARY", "LOGIN_FAILURE", "FAIL", "Mobile mismatch")
        raise HTTPException(401, "The credentials provided could not be verified. Please check your details and try again.")
    if ben.get("status") in ["DISABLED","SUSPENDED"]:
        audit_log(req.ration_card_id, "BENEFICIARY", "ACCOUNT_DISABLED", "FAIL", ben.get("status"))
        raise HTTPException(401, "Account disabled. Contact administrator.")
    # Use ration_card as OTP identifier (unique per beneficiary)
    result = otp_service.request_otp(req.ration_card_id)
    if "error" in result:
        raise HTTPException(429, result["error"])
    return result

@router.post("/beneficiary/verify-otp")
def beneficiary_verify_otp(req: BeneficiaryVerifyOtp):
    df = load_beneficiaries()
    row = df[df.ration_card_id==req.ration_card_id]
    if row.empty:
        raise HTTPException(404, "Ration card not found.")
    result = otp_service.verify_otp(req.ration_card_id, req.otp)
    if not result["valid"]:
        audit_log(req.ration_card_id, "BENEFICIARY", "OTP_FAILURE", "FAIL", result["error"])
        raise HTTPException(401, result["error"])
    # success — create JWT
    token = create_access_token(sub=req.ration_card_id, role="BENEFICIARY")
    ben = row.iloc[0]
    audit_log(req.ration_card_id, "BENEFICIARY", "LOGIN_SUCCESS", "SUCCESS")
    return {"access_token": token, "token_type": "bearer", "role": "BENEFICIARY", "beneficiary_id": ben["beneficiary_id"], "ration_card_id": ben["ration_card_id"]}

@router.post("/officer/login")
def officer_login(req: OfficerLogin):
    ensure_officer_hashes()
    df = load_officers()
    row = df[df.officer_id==req.officer_id]
    if row.empty:
        audit_log(req.officer_id, "unknown", "LOGIN_FAILURE", "FAIL", "Officer not found")
        raise HTTPException(401, "The credentials provided could not be verified. Please check your details and try again.")
    officer = row.iloc[0]
    if officer.get("status") in ["DISABLED","SUSPENDED"]:
        audit_log(req.officer_id, officer.get("role"), "ACCOUNT_DISABLED", "FAIL", officer.get("status"))
        raise HTTPException(401, "Account disabled. Contact administrator.")
    # Verify password against per-officer hash
    expected_hash = _officer_password_hashes.get(req.officer_id)
    if not expected_hash or not verify_password(req.password, expected_hash):
        audit_log(req.officer_id, officer.get("role"), "LOGIN_FAILURE", "FAIL", "Wrong password")
        raise HTTPException(401, "The credentials provided could not be verified. Please check your details and try again.")
    # Map legacy roles to canonical
    role_map = {"DISTRICT_OFFICER":"DSO","ADMIN":"SYSTEM_ADMIN"}
    role = role_map.get(officer.get("role"), officer.get("role"))
    token = create_access_token(sub=req.officer_id, role=role)
    audit_log(req.officer_id, role, "LOGIN_SUCCESS", "SUCCESS")
    return {"access_token": token, "token_type":"bearer","role": role, "officer_id": req.officer_id, "name": officer.get("name")}

@router.get("/me")
def me(user=Depends(get_current_user)):
    # Return normalized authenticated user
    return {
        "user_id": user["user_id"],
        "role": user["role"],
        "name": user.get("name",""),
        "status": user["status"],
        "permissions": user["permissions"],
        "beneficiary_id": user.get("beneficiary_id"),
    }

@router.post("/logout")
def logout(authorization: Optional[str]=Header(None), user=Depends(get_current_user)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ",1)[1]
        blacklist_token(token)
    audit_log(user["user_id"], user["role"], "LOGOUT", "SUCCESS")
    return {"message":"Logged out. Please sign in again."}

@router.get("/audit")
def get_audit(user=Depends(get_current_user)):
    # Only SYSTEM_ADMIN and AUDITOR can view audit
    if user["role"] not in ["SYSTEM_ADMIN","AUDITOR","DSO"]:
        raise HTTPException(403, "Access restricted. Your account does not have permission to access this section.")
    from ..core.auth_middleware import get_audit
    from ..core.otp import otp_service
    return {"auth_audit": get_audit(), "otp_audit": otp_service.get_audit()}

# Legacy compatibility — keep old beneficiary routes but delegate to new
@router.post("/beneficiary/login-legacy")
def legacy_login():
    raise HTTPException(410, "Use /auth/beneficiary/request-otp and /auth/beneficiary/verify-otp")

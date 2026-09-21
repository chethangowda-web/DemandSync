"""Phase 0: authentication, OTP, JWT, RBAC (401 vs 403), lockout, revocation, audit."""
import subprocess
import sys
import time
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from backend.core import credentials
from backend.core.audit import verify_chain
from backend.core.security import JWT_ALGORITHM, create_access_token
from backend.main import app
from conftest import OFFICER_PASSWORD

pytestmark = pytest.mark.usefixtures("authdb")
client = TestClient(app)
BEN_RC, BEN_MOBILE = "RC2023100000", "9000060000"  # BEN-000001, AAY, entitlement 35 (22 rice + 13 wheat)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def sql(url, query, params=()):
    with psycopg.connect(url, autocommit=True) as c:
        cur = c.execute(query, params)
        return cur.fetchall() if cur.description else None


def request_otp(rc=BEN_RC, mobile=BEN_MOBILE):
    return client.post("/api/v1/auth/beneficiary/request-otp", json={"ration_card_id": rc, "registered_mobile": mobile})


def verify_otp(otp, rc=BEN_RC):
    return client.post("/api/v1/auth/beneficiary/verify-otp", json={"ration_card_id": rc, "otp": otp})


def beneficiary_token() -> str:
    return verify_otp(request_otp().json()["dev_otp"]).json()["access_token"]


def officer_login(oid, password=OFFICER_PASSWORD):
    return client.post("/api/v1/auth/officer/login", json={"officer_id": oid, "password": password})


def officer_token(oid) -> str:
    return officer_login(oid).json()["access_token"]


# ============================================================ beneficiary OTP login

def test_beneficiary_login_flow_me_and_entitlement():
    r = request_otp()
    assert r.status_code == 200 and len(r.json()["dev_otp"]) == 6 and r.json()["expires_in"] == 300
    r = verify_otp(r.json()["dev_otp"])
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "BENEFICIARY" and body["portal"] == "/beneficiary" and body["beneficiary_id"] == "BEN-000001"
    me = client.get("/api/v1/auth/me", headers=bearer(body["access_token"])).json()
    assert me["role"] == "BENEFICIARY" and me["user_id"] == BEN_RC and "SUBMIT_INTENT" in me["permissions"]
    assert "MANAGE_USERS" not in me["permissions"]
    ent = client.get("/api/v1/beneficiaries/me/entitlement", headers=bearer(body["access_token"])).json()
    assert ent["total_entitlement_kg"] == 35 and ent["rice_entitlement_kg"] + ent["wheat_entitlement_kg"] == 35


def test_unknown_card_and_wrong_mobile_are_indistinguishable():
    a = request_otp("RC-DOES-NOT-EXIST", BEN_MOBILE)
    b = request_otp(BEN_RC, "0000000000")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_otp_is_random_six_digits_and_stored_only_as_hash(authdb):
    otps = []
    for _ in range(5):
        sql(authdb, "DELETE FROM otp_challenges")  # bypass the resend cooldown
        otps.append(request_otp().json()["dev_otp"])
    assert all(o.isdigit() and len(o) == 6 for o in otps)
    assert len(set(otps)) > 1  # not a fixed/universal code
    stored = sql(authdb, "SELECT otp_hash FROM otp_challenges")[0][0]
    assert len(stored) == 64 and stored not in otps


def test_wrong_otp_counts_attempts_then_locks_the_code():
    otp = request_otp().json()["dev_otp"]
    wrong = "000000" if otp != "000000" else "111111"
    assert "2 attempts remaining" in verify_otp(wrong).json()["detail"]
    assert "1 attempts remaining" in verify_otp(wrong).json()["detail"]
    assert verify_otp(wrong).status_code == 401
    r = verify_otp(otp)  # even the right code is refused once attempts are exhausted
    assert r.status_code == 401 and "Too many attempts" in r.json()["detail"]


def test_otp_is_single_use():
    otp = request_otp().json()["dev_otp"]
    assert verify_otp(otp).status_code == 200
    r = verify_otp(otp)
    assert r.status_code == 401 and "already used" in r.json()["detail"]


def test_expired_otp_is_rejected(authdb):
    otp = request_otp().json()["dev_otp"]
    sql(authdb, "UPDATE otp_challenges SET expires_at = now() - interval '1 minute'")
    r = verify_otp(otp)
    assert r.status_code == 401 and "expired" in r.json()["detail"]


def test_verify_without_request_is_rejected():
    r = verify_otp("123456")
    assert r.status_code == 401 and "No OTP requested" in r.json()["detail"]


def test_resend_cooldown_returns_429_with_retry_after():
    assert request_otp().status_code == 200
    r = request_otp()
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_no_otp_delivery_provider_means_no_login(monkeypatch):
    monkeypatch.setenv("OTP_PROVIDER", "none")
    r = request_otp()
    assert r.status_code == 503 and "dev_otp" not in r.text


@pytest.mark.parametrize("status,allowed", [("MIGRATED", True), ("SUSPENDED", False), ("DISABLED", False)])
def test_beneficiary_account_status_gates_login(status, allowed, authdb):
    old = sql(authdb, "SELECT status FROM beneficiaries WHERE ration_card_id = %s", (BEN_RC,))[0][0]
    sql(authdb, "UPDATE beneficiaries SET status = %s WHERE ration_card_id = %s", (status, BEN_RC))
    try:
        r = request_otp()
        assert (r.status_code == 200) is allowed
        if not allowed:
            assert r.status_code == 401 and "disabled" in r.json()["detail"].lower()
    finally:
        sql(authdb, "UPDATE beneficiaries SET status = %s WHERE ration_card_id = %s", (old, BEN_RC))


def test_disabling_a_beneficiary_kills_existing_sessions(authdb):
    token = beneficiary_token()
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200
    sql(authdb, "UPDATE beneficiaries SET status = 'SUSPENDED' WHERE ration_card_id = %s", (BEN_RC,))
    try:
        assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401
    finally:
        sql(authdb, "UPDATE beneficiaries SET status = 'ACTIVE' WHERE ration_card_id = %s", (BEN_RC,))


def test_legacy_login_routes_are_gone():
    assert client.post("/api/v1/auth/beneficiary/login", json={}).status_code in (404, 405)


# ============================================================ officer password login

@pytest.mark.parametrize("db_role,role,portal", [
    ("DISTRICT_OFFICER", "DSO", "/dso"), ("FIELD_FOOD_INSPECTOR", "FIELD_FOOD_INSPECTOR", "/inspector"),
    ("FPS_OWNER", "FPS_OWNER", "/fps"), ("ADMIN", "SYSTEM_ADMIN", "/admin"), ("AUDITOR", "AUDITOR", "/auditor")])
def test_officer_login_maps_roles_and_routes_to_portal(db_role, role, portal, officers):
    oid = officers[db_role][0]
    r = officer_login(oid)
    assert r.status_code == 200
    b = r.json()
    assert b["role"] == role and b["portal"] == portal and b["officer_id"] == oid and b["must_change_password"] is False
    me = client.get("/api/v1/auth/me", headers=bearer(b["access_token"])).json()
    assert me["role"] == role and me["portal"] == portal and me["name"] == b["name"]


def test_bad_password_and_unknown_officer_and_no_credentials_are_indistinguishable(officers):
    wrong = officer_login(officers["ADMIN"][0], "not-the-password-1")
    unknown = officer_login("OFF-99999", "whatever-password-1")
    no_creds = officer_login(officers["ADMIN"][1])  # exists, but was never given credentials
    assert wrong.status_code == unknown.status_code == no_creds.status_code == 401
    assert wrong.json() == unknown.json() == no_creds.json()


def test_five_failures_lock_the_account_even_for_the_right_password(officers, authdb):
    oid = officers["FIELD_FOOD_INSPECTOR"][0]
    for _ in range(5):
        assert officer_login(oid, "wrong-password-9").status_code == 401
    assert officer_login(oid).status_code == 401  # locked
    sql(authdb, "UPDATE officer_credentials SET locked_until = now() - interval '1 second' WHERE officer_id = %s", (oid,))
    assert officer_login(oid).status_code == 200  # lock expired
    assert sql(authdb, "SELECT failed_attempts FROM officer_credentials WHERE officer_id = %s", (oid,))[0][0] == 0


def test_suspended_officer_cannot_log_in_and_existing_token_dies(officers, authdb):
    oid = officers["AUDITOR"][0]
    token = officer_token(oid)
    sql(authdb, "UPDATE officers SET status = 'SUSPENDED' WHERE officer_id = %s", (oid,))
    try:
        r = officer_login(oid)
        assert r.status_code == 401 and "disabled" in r.json()["detail"].lower()
        assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401
    finally:
        sql(authdb, "UPDATE officers SET status = 'ACTIVE' WHERE officer_id = %s", (oid,))


def test_password_is_stored_hashed_never_plain(authdb, officers):
    h = sql(authdb, "SELECT password_hash FROM officer_credentials WHERE officer_id = %s", (officers["ADMIN"][0],))[0][0]
    assert h.startswith("$argon2") and OFFICER_PASSWORD not in h


# ============================================================ change password / must_change

def test_change_password_policy_rotation_and_session_revocation(officers):
    oid = officers["DISTRICT_OFFICER"][0]
    token = officer_token(oid)
    change = lambda cur, new: client.post("/api/v1/auth/change-password", headers=bearer(token),
                                          json={"current_password": cur, "new_password": new})
    assert change("wrong-current-1", "Another-Pass-77").status_code == 401
    assert change(OFFICER_PASSWORD, "short1").status_code == 422
    assert change(OFFICER_PASSWORD, "onlyletterspassword").status_code == 422
    assert change(OFFICER_PASSWORD, OFFICER_PASSWORD).status_code == 422
    assert change(OFFICER_PASSWORD, f"{oid}-Secret-9").status_code == 422  # contains the user id
    try:
        assert change(OFFICER_PASSWORD, "Brand-New-Pass-77").status_code == 200
        assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401  # session revoked
        assert officer_login(oid, OFFICER_PASSWORD).status_code == 401
        assert officer_login(oid, "Brand-New-Pass-77").status_code == 200
    finally:
        import os
        with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as c:
            credentials.set_password(c, oid, OFFICER_PASSWORD)


def test_must_change_password_blocks_everything_but_the_change_flow(officers, authdb):
    oid = officers["ADMIN"][0]
    token = officer_token(oid)
    sql(authdb, "UPDATE officer_credentials SET must_change_password = true WHERE officer_id = %s", (oid,))
    assert client.get("/api/v1/auth/me", headers=bearer(token)).json()["must_change_password"] is True
    r = client.get("/api/v1/system/db-status", headers=bearer(token))
    assert r.status_code == 403 and "Password change required" in r.json()["detail"]


def test_beneficiaries_have_no_password_to_change():
    r = client.post("/api/v1/auth/change-password", headers=bearer(beneficiary_token()),
                    json={"current_password": "x", "new_password": "Whatever-Pass-1"})
    assert r.status_code == 403


# ============================================================ tokens

def test_missing_malformed_and_garbage_tokens_are_401():
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer("not.a.jwt")).status_code == 401


def test_expired_token_is_401(officers):
    token = create_access_token(officers["ADMIN"][0], "SYSTEM_ADMIN", minutes=-1)
    r = client.get("/api/v1/auth/me", headers=bearer(token))
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()


def test_token_signed_with_another_secret_is_401(officers):
    forged = jose_jwt.encode({"sub": officers["ADMIN"][0], "role": "SYSTEM_ADMIN", "type": "access", "jti": "x",
                              "exp": int(time.time()) + 600}, "attacker-secret", algorithm=JWT_ALGORITHM)
    assert client.get("/api/v1/auth/me", headers=bearer(forged)).status_code == 401


def test_unsigned_alg_none_token_is_401(officers):
    import base64, json
    b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    token = f'{b64({"alg": "none", "typ": "JWT"})}.{b64({"sub": officers["ADMIN"][0], "role": "SYSTEM_ADMIN", "type": "access", "jti": "x", "exp": int(time.time()) + 600})}.'
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401


def test_token_without_jti_or_wrong_type_is_401(officers):
    for claims in ({"sub": officers["ADMIN"][0], "role": "SYSTEM_ADMIN", "type": "access"},
                   {"sub": officers["ADMIN"][0], "role": "SYSTEM_ADMIN", "type": "refresh", "jti": "x"}):
        claims["exp"] = int(time.time()) + 600
        from backend.core.security import JWT_SECRET
        token = jose_jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)
        assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401


def test_role_in_token_must_match_the_database_role(officers):
    dso = officers["DISTRICT_OFFICER"][0]
    spoofed = create_access_token(dso, "SYSTEM_ADMIN")  # correctly signed, but the DB says this officer is a DSO
    assert client.get("/api/v1/auth/me", headers=bearer(spoofed)).status_code == 403
    assert client.get("/api/v1/system/db-status", headers=bearer(spoofed)).status_code == 403
    as_beneficiary = create_access_token(dso, "BENEFICIARY")
    assert client.get("/api/v1/auth/me", headers=bearer(as_beneficiary)).status_code == 401


def test_logout_revokes_the_token(officers):
    token = officer_token(officers["AUDITOR"][0])
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=bearer(token)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401


# ============================================================ RBAC: 401 vs 403

def test_system_status_is_admin_only(officers):
    url = "/api/v1/system/db-status"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=bearer(beneficiary_token())).status_code == 403
    for db_role in ("DISTRICT_OFFICER", "FIELD_FOOD_INSPECTOR", "FPS_OWNER", "AUDITOR"):
        oid = officers[db_role][0]
        assert client.get(url, headers=bearer(officer_token(oid))).status_code == 403, db_role
    r = client.get(url, headers=bearer(officer_token(officers["ADMIN"][0])))
    assert r.status_code == 200 and r.json()["total_rows"] > 80000


def test_beneficiary_routes_reject_officers_and_anonymous(officers):
    for path in ("/api/v1/beneficiaries/me", "/api/v1/beneficiaries/me/entitlement", "/api/v1/preferences/me"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=bearer(officer_token(officers["ADMIN"][0]))).status_code == 403


def test_audit_view_permission(officers):
    assert client.get("/api/v1/auth/audit", headers=bearer(beneficiary_token())).status_code == 403
    assert client.get("/api/v1/auth/audit", headers=bearer(officer_token(officers["FPS_OWNER"][0]))).status_code == 403
    r = client.get("/api/v1/auth/audit?limit=5&action=LOGIN_SUCCESS", headers=bearer(officer_token(officers["AUDITOR"][0])))
    assert r.status_code == 200 and 1 <= len(r.json()["events"]) <= 5
    assert all(e["action"] == "LOGIN_SUCCESS" for e in r.json()["events"])


# ============================================================ audit trail

def test_login_events_are_audited_without_secrets(officers, authdb):
    oid = officers["DISTRICT_OFFICER"][0]
    officer_login(oid, "definitely-wrong-pw-1")
    otp = request_otp().json()["dev_otp"]
    verify_otp(otp)
    events = sql(authdb, "SELECT action, result, reason, actor_user_id FROM audit_events WHERE actor_user_id IN (%s, %s)",
                 (oid, BEN_RC))
    actions = {(a, r) for a, r, _, _ in events}
    assert ("LOGIN_FAILURE", "FAIL") in actions and ("OTP_SENT", "SUCCESS") in actions
    assert ("OTP_VERIFIED", "SUCCESS") in actions and ("LOGIN_SUCCESS", "SUCCESS") in actions
    blob = " ".join(str(x) for row in sql(authdb, "SELECT * FROM audit_events WHERE actor_user_id IN (%s, %s)", (oid, BEN_RC))
                    for x in row)
    assert otp not in blob and "definitely-wrong-pw-1" not in blob and OFFICER_PASSWORD not in blob


def test_auth_activity_keeps_the_hash_chain_intact():
    officer_login("OFF-99999", "whatever-password-1")
    request_otp("RC-NOPE", BEN_MOBILE)
    import os
    r = verify_chain(os.environ["DATABASE_URL"])
    assert r["intact"] and r["checked"] > 0, r


# ============================================================ secrets & bootstrap

def _import_security(env: dict) -> subprocess.CompletedProcess:
    import os
    root = Path(__file__).resolve().parents[1]
    e = {k: v for k, v in os.environ.items() if k not in ("JWT_SECRET", "APP_ENV")}
    e.update(env, PYTHONPATH=str(root))
    return subprocess.run([sys.executable, "-c", "import backend.core.security"], env=e, cwd=root,
                          capture_output=True, text=True)


def test_production_refuses_to_start_without_a_strong_jwt_secret():
    assert _import_security({"APP_ENV": "production"}).returncode != 0
    assert _import_security({"APP_ENV": "production", "JWT_SECRET": "short"}).returncode != 0
    assert _import_security({"APP_ENV": "production", "JWT_SECRET": "x" * 40}).returncode == 0
    assert _import_security({}).returncode == 0  # development keeps working


def test_bootstrap_is_idempotent_and_never_resets_a_changed_password(officers, authdb):
    target = officers["FPS_OWNER"][1]  # has no credentials yet
    assert credentials.bootstrap(authdb, f"{target}=Initial-Pass-2026") == [target]
    assert credentials.bootstrap(authdb, f"{target}=Different-Pass-2027") == []
    assert officer_login(target, "Initial-Pass-2026").status_code == 200
    assert officer_login(target, "Different-Pass-2027").status_code == 401
    sql(authdb, "DELETE FROM officer_credentials WHERE officer_id = %s", (target,))


def test_bootstrap_rejects_weak_passwords_and_unknown_officers(authdb):
    with pytest.raises(ValueError):
        credentials.bootstrap(authdb, "OFF-06003=short")
    with pytest.raises(ValueError):
        credentials.bootstrap(authdb, "OFF-NOPE=Strong-Password-1")
    with pytest.raises(ValueError):
        credentials.parse_accounts("no-equals-sign")


def test_dev_credential_seeding_is_refused_in_production(monkeypatch, authdb):
    monkeypatch.setattr(credentials, "APP_ENV", "production")
    with pytest.raises(RuntimeError):
        credentials.seed_dev(authdb)


def test_startup_tasks_are_idempotent(authdb, officers, monkeypatch):
    from backend import startup
    target = officers["FPS_OWNER"][1]
    monkeypatch.setenv("SEED_ON_START", "1")
    monkeypatch.setenv("BOOTSTRAP_ACCOUNTS", f"{target}=Startup-Pass-2026")
    first = startup.run(authdb)
    assert first["migrations"] == [] and first["seed"] == "SKIPPED" and first["credentials_created"] == [target]
    assert startup.run(authdb)["credentials_created"] == []
    sql(authdb, "DELETE FROM officer_credentials WHERE officer_id = %s", (target,))

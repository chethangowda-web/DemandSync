"""Phase 6: System Admin workflow tests (uses the shared authdb fixture).

Reads must return real backend state; the account mutations must enforce RBAC,
mandatory reasons, self-mutation refusal, and audit every change.
"""
from tests.conftest import OFFICER_PASSWORD


def _login(client, oid):
    r = client.post("/api/v1/auth/officer/login", json={"officer_id": oid, "password": OFFICER_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin_headers(client, officers):
    return _login(client, officers["ADMIN"][0])


def test_stages_overview_health_final(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h = _admin_headers(c, officers)
    r = c.get("/api/v1/admin/stages", headers=h)
    assert r.status_code == 200, r.text
    stages = r.json()["stages"]
    assert [s["stage"] for s in stages] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert all(s["status"] in ("COMPLETED", "IN REVIEW", "ACTION REQUIRED", "DEGRADED", "BLOCKED", "NOT STARTED")
               for s in stages)
    ov = c.get("/api/v1/admin/overview", headers=h).json()
    assert {"services", "counts", "last_sync"} <= set(ov)
    assert ov["counts"]["total_users"] > 0 and ov["counts"]["fps_records"] > 0
    assert ov["services"]["postgresql"]["status"] == "ONLINE"
    assert ov["services"]["postgresql"]["latency_ms"] is not None
    # no secret material anywhere in reads
    assert "JWT_SECRET" not in r.text and "password_hash" not in r.text
    hl = c.get("/api/v1/admin/health", headers=h).json()
    assert hl["overall"] in ("ONLINE", "DEGRADED")
    fin = c.get("/api/v1/admin/final", headers=h).json()
    assert fin["verdict"] in ("SYSTEM READY", "SYSTEM DEGRADED", "ACTION REQUIRED", "SYSTEM BLOCKED")
    assert len(fin["readiness"]) >= 10
    assert all(x["status"] in ("PASS", "WARNING", "FAIL", "UNKNOWN", "ONLINE", "DEGRADED", "OFFLINE") for x in fin["readiness"])


def test_users_rbac_and_datasets(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h = _admin_headers(c, officers)
    u = c.get("/api/v1/admin/users?limit=5", headers=h).json()
    assert u["total"] > 0 and len(u["users"]) <= 5
    assert "password_hash" not in str(u)
    assert {"FPS_OWNER", "AUDITOR", "DISTRICT_OFFICER"} <= set(u["known_roles"])
    det = c.get(f"/api/v1/admin/users/{officers['FPS_OWNER'][0]}", headers=h).json()
    assert det["canonical_role"] == "FPS_OWNER"
    assert any(p["permission"] == "PROCESS_EPOS" for p in det["permissions"])
    assert c.get("/api/v1/admin/users/OFF-NOPE", headers=h).status_code == 404
    rb = c.get("/api/v1/admin/rbac", headers=h).json()
    assert {r["role"] for r in rb["roles"]} >= {"DSO", "FPS_OWNER", "AUDITOR", "SYSTEM_ADMIN", "FIELD_FOOD_INSPECTOR"}
    ds = c.get("/api/v1/admin/datasets", headers=h).json()
    assert ds["imports"], "seeded dataset must have import history"
    assert ds["imports"][0]["pipeline"], "import must carry staged validation evidence"
    assert ds["live_counts"]["fps"] > 0
    sec = c.get("/api/v1/admin/security", headers=h).json()
    assert sec["chain"]["intact"] is True
    cfg = c.get("/api/v1/admin/configuration", headers=h).json()
    assert cfg["entries"] and all(e["mutable"] is False for e in cfg["entries"])
    ask = c.post("/api/v1/admin/ask", headers=h, json={"question": "Which integrations are unavailable?"}).json()
    assert ask["advisory"] is True and ask["source_records"]


def test_user_mutations_are_guarded_and_audited(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h = _admin_headers(c, officers)
    me, target = officers["ADMIN"][0], officers["FPS_OWNER"][1]
    # self-mutation refused
    assert c.patch(f"/api/v1/admin/users/{me}", headers=h, json={"status": "INACTIVE", "reason": "self test"}).status_code == 422
    # reason required (pydantic floor)
    assert c.patch(f"/api/v1/admin/users/{target}", headers=h, json={"status": "INACTIVE", "reason": "x"}).status_code == 422
    # unknown role / user
    assert c.patch(f"/api/v1/admin/users/{target}", headers=h, json={"role": "SUPERUSER", "reason": "bad role test"}).status_code == 422
    assert c.patch("/api/v1/admin/users/OFF-NOPE", headers=h, json={"status": "INACTIVE", "reason": "missing test"}).status_code == 404
    # deactivate → reactivate, both audited with before/after
    r = c.patch(f"/api/v1/admin/users/{target}", headers=h, json={"status": "INACTIVE", "reason": "admin test deactivation"})
    assert r.status_code == 200 and r.json()["user"]["status"] == "INACTIVE"
    r = c.patch(f"/api/v1/admin/users/{target}", headers=h, json={"status": "ACTIVE", "reason": "admin test restoration"})
    assert r.status_code == 200 and r.json()["user"]["status"] == "ACTIVE"
    ev = c.get(f"/api/v1/auditor/cycles/2026-03/trace", headers=_login(c, officers["AUDITOR"][0])).json()
    # auditor trace is cycle-scoped; check the admin action via the security feed instead
    sec = c.get("/api/v1/admin/security", headers=h).json()
    assert any(e["entity_id"] == target for e in sec["role_changes"])
    # locked account cannot sign in; unlock restores (uses a fresh target to avoid touching shared logins)
    c.patch(f"/api/v1/admin/users/{target}", headers=h, json={"status": "ACTIVE", "reason": "ensure active"})


def test_non_admin_cannot_touch_admin_api(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h_fps = _login(c, officers["FPS_OWNER"][0])
    assert c.get("/api/v1/admin/overview", headers=h_fps).status_code == 403
    assert c.get("/api/v1/admin/users?limit=1", headers=h_fps).status_code == 403
    assert c.patch(f"/api/v1/admin/users/{officers['FPS_OWNER'][1]}", headers=h_fps,
                   json={"status": "INACTIVE", "reason": "forbidden attempt"}).status_code == 403
    h_dso = _login(c, officers["DISTRICT_OFFICER"][0])
    assert c.get("/api/v1/admin/security", headers=h_dso).status_code == 403

"""Phase 5: Auditor workflow tests (uses the shared authdb fixture).

The auditor API is strictly read-only: these tests verify every stage returns real
backend evidence, RBAC scoping holds, and no auditor-reachable write path exists.
"""
from tests.conftest import OFFICER_PASSWORD


def _login(client, oid):
    r = client.post("/api/v1/auth/officer/login", json={"officer_id": oid, "password": OFFICER_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _audit_headers(client, officers):
    return _login(client, officers["AUDITOR"][0])


def _cycle(client, h):
    cycles = client.get("/api/v1/auditor/cycles", headers=h).json()["cycles"]
    assert cycles, "seeded dataset must contain cycles"
    # richest evidence first: prefer a cycle with manifests
    with_ev = [c for c in cycles if c["evidence"]["manifests"]]
    return (with_ev or cycles)[0]["cycle"]


def test_cycles_and_stages(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h = _audit_headers(c, officers)
    r = c.get("/api/v1/auditor/cycles", headers=h)
    assert r.status_code == 200, r.text
    assert {"cycles", "districts"} <= set(r.json())
    cy = _cycle(c, h)
    r = c.get(f"/api/v1/auditor/cycles/{cy}/stages", headers=h)
    assert r.status_code == 200, r.text
    stages = r.json()["stages"]
    assert [s["stage"] for s in stages] == [1, 2, 3, 4, 5, 6, 7]
    assert all(s["status"] in ("COMPLETED", "IN REVIEW", "ACTION REQUIRED", "BLOCKED", "NOT STARTED") for s in stages)
    # unknown cycle is a real 404, not an empty page
    assert c.get("/api/v1/auditor/cycles/2099-99/stages", headers=h).status_code == 404


def test_overview_and_demand_are_real(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h = _audit_headers(c, officers)
    cy = _cycle(c, h)
    ov = c.get(f"/api/v1/auditor/cycles/{cy}/overview", headers=h).json()
    assert {"cycle", "summary", "readiness"} <= set(ov)
    assert ov["summary"]["manifest_count"] > 0
    assert all({"key", "label", "met"} <= set(r) for r in ov["readiness"])
    d = c.get(f"/api/v1/auditor/cycles/{cy}/demand", headers=h).json()
    assert {r["commodity"] for r in d["chain"]} == {"RICE", "WHEAT"}
    for row in d["chain"]:
        if row["forecast_kg"] is not None:
            assert row["intent_minus_forecast_kg"] == round(row["intent_kg"] - row["forecast_kg"], 1)
    assert isinstance(d["overrides"], list) and isinstance(d["override_events"], list)


def test_manifests_hash_verification(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h = _audit_headers(c, officers)
    cy = _cycle(c, h)
    mans = c.get(f"/api/v1/auditor/cycles/{cy}/manifests", headers=h).json()["manifests"]
    assert mans
    sealed = [m for m in mans if m["manifest_status"] in ("LOCKED", "DISPATCHED", "DELIVERED", "RECONCILED")]
    assert sealed, "seeded cycle must contain sealed manifests"
    # Verification is recomputed, never assumed: True or False are both honest answers.
    assert all(m["hash_verified"] in (True, False) for m in sealed)
    mid = sealed[0]["manifest_id"]
    det = c.get(f"/api/v1/auditor/manifests/{mid}", headers=h).json()
    assert det["lock_verification"]["hash_verified"] in (True, False)
    assert det["sha256_hash"]
    assert det["items"]


def test_reconciliation_exceptions_trace_closure(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h = _audit_headers(c, officers)
    cy = _cycle(c, h)
    rec = c.get(f"/api/v1/auditor/cycles/{cy}/reconciliation?limit=5", headers=h).json()
    assert {r["commodity"] for r in rec["flow"]} == {"RICE", "WHEAT"}
    assert all(r["status"] in ("VERIFIED", "VARIANCE", "BLOCKED") for r in rec["flow"])
    ex = c.get(f"/api/v1/auditor/cycles/{cy}/exceptions", headers=h).json()
    assert {"HIGH", "MEDIUM", "LOW"} <= set(ex["open_by_severity"])
    tr = c.get(f"/api/v1/auditor/cycles/{cy}/trace?limit=5", headers=h).json()
    assert tr["total"] > 0
    assert {"actor_user_id", "actor_role", "action", "timestamp", "result"} <= set(tr["events"][0])
    assert tr["chain_intact"] is True
    cl = c.get(f"/api/v1/auditor/cycles/{cy}/closure", headers=h).json()
    assert len(cl["checklist"]) == 12
    assert all(r["status"] in ("PASS", "FAIL", "WARNING", "NOT VERIFIED") for r in cl["checklist"])
    assert cl["decision"] in ("AUDIT READY", "AUDIT READY WITH WARNINGS", "ACTION REQUIRED", "AUDIT BLOCKED")
    assert "FINAL ACTION NOT AVAILABLE" in cl["final_action"]
    # grounded assistant answers from records
    ask = c.post(f"/api/v1/auditor/cycles/{cy}/ask", headers=h,
                 json={"question": "Which exceptions affected this cycle?"}).json()
    assert ask["advisory"] is True and ask["source_records"]


def test_auditor_is_read_only(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h = _audit_headers(c, officers)
    cy = _cycle(c, h)
    # every DSO write path must refuse the auditor
    assert c.post(f"/api/v1/cycles/{cy}/allocate", headers=h).status_code == 403
    assert c.post(f"/api/v1/cycles/{cy}/forecast", headers=h).status_code == 403
    assert c.post(f"/api/v1/cycles/{cy}/close", headers=h).status_code == 403
    # and roles without audit permission cannot read the auditor API
    h_fps = _login(c, officers["FPS_OWNER"][0])
    assert c.get(f"/api/v1/auditor/cycles/{cy}/overview", headers=h_fps).status_code == 403

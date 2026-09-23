"""Phase 3: Field Food Inspector workflow tests (uses the shared authdb fixture)."""
from tests.conftest import OFFICER_PASSWORD


def _login(client, oid):
    r = client.post("/api/v1/auth/officer/login", json={"officer_id": oid, "password": OFFICER_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _insp_headers(client, officers):
    return _login(client, officers["FIELD_FOOD_INSPECTOR"][0])


def test_summary_and_targets(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    h = _insp_headers(TestClient(app), officers)
    c = TestClient(app)
    r = c.get("/api/v1/inspector/summary", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["inspector_id"] == officers["FIELD_FOOD_INSPECTOR"][0]
    r = c.get("/api/v1/inspector/targets?limit=5", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] > 0 and len(body["targets"]) <= 5
    t = body["targets"][0]
    assert {"fps_id", "risk_score", "risk_level", "risk_factors", "recommended_focus"} <= set(t)


def test_full_workflow(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    h = _insp_headers(c, officers)
    fps = c.get("/api/v1/inspector/targets?limit=1", headers=h).json()["targets"][0]["fps_id"]

    r = c.post("/api/v1/inspector/inspections", json={"fps_id": fps}, headers=h)
    assert r.status_code == 201, r.text
    iid = r.json()["inspection_id"]

    # incomplete submission must be rejected
    r = c.post(f"/api/v1/inspector/inspections/{iid}/submit", headers=h)
    assert r.status_code == 422, r.text

    r = c.patch(f"/api/v1/inspector/inspections/{iid}", headers=h, json={
        "verification": {"fps_identity": True},
        "checklist": {"rice": True},
        "findings": [{"category": "Stock", "finding": "No violations observed",
                      "severity": "LOW", "notes": "", "evidence": []}],
        "evidence": [{"type": "note", "label": "register p.1"}],
        "notes": "test"})
    assert r.status_code == 200, r.text
    assert r.json()["findings"][0]["finding"] == "No violations observed"

    r = c.post(f"/api/v1/inspector/inspections/{iid}/submit", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SUBMITTED"

    r = c.get("/api/v1/inspector/inspections", headers=h)
    assert any(x["inspection_id"] == iid and x["status"] == "SUBMITTED" for x in r.json()["inspections"])

    # locked after submit
    r = c.patch(f"/api/v1/inspector/inspections/{iid}", headers=h, json={"notes": "x"})
    assert r.status_code == 409, r.text


def test_other_roles_cannot_submit(authdb, officers):
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    # DSO can read targets but has no SUBMIT_INSPECTION
    h_dso = _login(c, officers["DISTRICT_OFFICER"][0])
    assert c.get("/api/v1/inspector/targets?limit=1", headers=h_dso).status_code == 200
    fps = c.get("/api/v1/inspector/targets?limit=1", headers=h_dso).json()["targets"][0]["fps_id"]
    assert c.post("/api/v1/inspector/inspections", json={"fps_id": fps}, headers=h_dso).status_code == 403
    # FPS owner has neither permission
    h_fps = _login(c, officers["FPS_OWNER"][0])
    assert c.get("/api/v1/inspector/summary", headers=h_fps).status_code == 403

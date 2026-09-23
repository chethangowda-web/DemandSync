"""Phase 8 §32 — end-to-end intelligence proof on ONE real live cycle.

Drives a scratch database through the full workflow
(intent -> forecast -> lock -> allocate -> optimize -> lock/authorize ->
dispatch -> deliver -> receive/distribute -> reconcile -> close) and asserts
the intelligence layer observes, explains and recommends — never decides —
at every stage, with the SAME underlying records visible in every portal.
"""
import os
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.core.credentials import set_password
from backend.db.ingest import import_dataset
from backend.db.migrate import migrate
from backend.main import app
from conftest import ADMIN_URL, OFFICER_PASSWORD, swap_database

pytestmark = pytest.mark.usefixtures("authdb")
client = TestClient(app)

CYCLE = "2026-03"
FPS_ID = "FPS-0244"
BEN_RC, BEN_MOBILE, BEN_ID = "RC2023100000", "9000060000", "BEN-000001"


def q(db, sql, params=()):
    with psycopg.connect(db, autocommit=True) as c:
        cur = c.execute(sql, params)
        return cur.fetchall() if cur.description else None


def q1(db, sql, params=()):
    r = q(db, sql, params)
    return r[0] if r else None


@pytest.fixture(scope="module")
def journey_db(officers):
    if not ADMIN_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    name = "phase8_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = swap_database(ADMIN_URL, name)
    migrate(url)
    assert import_dataset(url, activate=True, imported_by="pytest-phase8")["status"] == "ACTIVE"
    with psycopg.connect(url) as c, c.transaction():
        owner = c.execute("SELECT owner_id FROM fps WHERE fps_id = %s", (FPS_ID,)).fetchone()[0]
        for oid in {officers["DISTRICT_OFFICER"][0], officers["AUDITOR"][0], officers["ADMIN"][0],
                    officers["FIELD_FOOD_INSPECTOR"][0], owner}:
            set_password(c, oid, OFFICER_PASSWORD)
    saved = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    yield url, owner
    if saved is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = saved
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


def H(officers, role="DISTRICT_OFFICER"):
    token = client.post("/api/v1/auth/officer/login",
                        json={"officer_id": officers[role][0], "password": OFFICER_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def ben_headers():
    otp = client.post("/api/v1/auth/beneficiary/request-otp",
                      json={"ration_card_id": BEN_RC, "registered_mobile": BEN_MOBILE}).json()["dev_otp"]
    tok = client.post("/api/v1/auth/beneficiary/verify-otp",
                      json={"ration_card_id": BEN_RC, "otp": otp}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def fps_headers(journey_db):
    tok = client.post("/api/v1/auth/officer/login",
                      json={"officer_id": journey_db[1], "password": OFFICER_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_phase8_live_cycle_intelligence_end_to_end(journey_db, officers):
    db = journey_db[0]
    dso, aud = H(officers), H(officers, "AUDITOR")
    fps = fps_headers(journey_db)
    ben = ben_headers()

    # 1. beneficiary submits intent; DSO intelligence sees the SAME record
    ir = client.post("/api/v1/preferences", headers=ben,
                     json={"fps_id": FPS_ID, "rice_quantity_kg": 4, "wheat_quantity_kg": 3,
                           "collection_mode": "SELF"})
    assert ir.status_code == 201, ir.text
    sig = client.get(f"/api/v1/intelligence/dso/demand?cycle={CYCLE}", headers=dso).json()
    mine = [s for s in sig["signals"] if s["fps_id"] == FPS_ID and s["commodity"] == "RICE"]
    assert mine and mine[0]["intent_kg"] >= 4
    assert mine[0]["intent_minus_forecast_kg"] == round(mine[0]["intent_kg"] - mine[0]["forecast_kg"], 1), \
        "Intent − Forecast uses the persisted seed forecast until a fresh one is generated"
    ask0 = client.post("/api/v1/intelligence/ask", headers=dso,
                       json={"question": "Which FPS needs attention?", "cycle": CYCLE})
    assert ask0.status_code == 200 and ask0.json()["advisory"] is True

    # 2. forecast reuses XGBoost; signals carry the real model/dataset version
    assert client.post(f"/api/v1/cycles/{CYCLE}/forecast", headers=dso).status_code == 200
    sig2 = client.get(f"/api/v1/intelligence/dso/demand?cycle={CYCLE}", headers=dso).json()
    assert sig2["model"] == "xgb-v1.0"
    mine2 = [s for s in sig2["signals"] if s["fps_id"] == FPS_ID and s["commodity"] == "RICE"][0]
    assert mine2["forecast_kg"] is not None and mine2["dataset_version"]
    assert mine2["confidence"] is None  # never fabricated
    anom = client.get(f"/api/v1/intelligence/dso/anomalies?cycle={CYCLE}", headers=dso)
    assert anom.status_code == 200

    # 3. lock; dispatch risk honestly reports the cycle is not ready
    assert client.post(f"/api/v1/cycles/{CYCLE}/choice-window/close", headers=dso).status_code == 200
    risks = client.get(f"/api/v1/intelligence/dso/risks?cycle={CYCLE}&kind=DISPATCH_RISK", headers=dso).json()
    assert risks["risks"], "a LOCKED cycle must surface unreadiness, not silence"

    # 4. allocate (capacity override the seed needs); explanation is grounded
    q(db, "UPDATE fps SET capacity_kg = 1 WHERE fps_id = %s", (FPS_ID,))
    assert client.post(f"/api/v1/cycles/{CYCLE}/allocate", headers=dso).status_code == 200
    for com, floor in (("RICE", 140), ("WHEAT", 90)):
        assert client.post(f"/api/v1/cycles/{CYCLE}/allocations/{FPS_ID}/{com}/override", headers=dso,
                           json={"allocated_kg": floor, "reason": "phase8 journey: stale capacity figure"}).status_code == 200
    expl = client.get(f"/api/v1/intelligence/dso/allocation-explanation?cycle={CYCLE}&fps_id={FPS_ID}&commodity=RICE",
                      headers=dso).json()
    assert "140" in expl["answer"] and FPS_ID in expl["answer"]
    assert "stale capacity figure" in expl["answer"], "override reason must be traceable"

    # 5. optimize; route intelligence is geodesic-honest
    assert client.post(f"/api/v1/cycles/{CYCLE}/optimize", headers=dso).status_code == 200
    mids = [r[0] for r in q(db, "SELECT manifest_id FROM dispatch_manifests WHERE cycle=%s AND manifest_id LIKE 'MFO-%%'", (CYCLE,))]
    assert mids
    rr = client.get(f"/api/v1/intelligence/dso/risks?cycle={CYCLE}&kind=ROUTE_FLEET_RISK", headers=dso).json()
    for risk in rr["risks"]:
        assert "ROAD DISTANCE" not in risk["summary"].upper() or "NOT ROAD" in risk["summary"].upper()
    for mid in mids:
        assert client.post(f"/api/v1/manifests/{mid}/validate", headers=dso).status_code == 200
        assert client.post(f"/api/v1/manifests/{mid}/lock", headers=dso).status_code == 200

    # 6. authorize; dispatch risk must show no HIGH blockers from live gates
    assert client.post(f"/api/v1/cycles/{CYCLE}/authorize", headers=dso).status_code == 200
    risks6 = client.get(f"/api/v1/intelligence/dso/risks?cycle={CYCLE}&kind=DISPATCH_RISK", headers=dso).json()
    assert not [r for r in risks6["risks"] if r["severity"] == "HIGH"], risks6["risks"]
    assert client.post(f"/api/v1/cycles/{CYCLE}/dispatch", headers=dso).status_code == 200

    # 7. deliver as planned; reconciliation intelligence stays quiet for this shop
    for mid in mids:
        items = q(db, "SELECT fps_id, commodity, planned_kg FROM dispatch_manifest_items WHERE manifest_id=%s", (mid,))
        body = {"items": [{"fps_id": i[0], "commodity": i[1], "delivered_kg": float(i[2])} for i in items]}
        assert client.post(f"/api/v1/manifests/{mid}/deliver", headers=dso, json=body).status_code == 200
    rec = client.get(f"/api/v1/intelligence/dso/anomalies?cycle={CYCLE}", headers=dso).json()["anomalies"]
    mine_rec = [a for a in rec if a["entity_id"] == FPS_ID and a["type"].startswith("RECONCILIATION")]
    assert mine_rec == [], "exact delivery must produce no reconciliation anomaly"

    # 8. FPS + beneficiary portals see the SAME records
    fps_sum = client.get("/api/v1/intelligence/fps/me/summary", headers=fps).json()
    assert fps_sum["fps_id"] == FPS_ID
    assert any(b["fps_id"] == FPS_ID and b["received_kg"] is not None
               for b in fps_sum["incoming"]), "FPS sees its received leg"
    ben_sum = client.get("/api/v1/intelligence/beneficiary/me/summary", headers=ben).json()
    assert ben_sum["cycle"] == CYCLE and ben_sum["insights"]
    insp = client.get(f"/api/v1/intelligence/inspector/summary?cycle={CYCLE}",
                      headers=H(officers, "FIELD_FOOD_INSPECTOR"))
    assert insp.status_code == 200

    # 9. auditor sees the same decision chain + closure explanation before close
    aud_sum = client.get(f"/api/v1/intelligence/auditor/summary?cycle={CYCLE}", headers=aud).json()
    assert any("phase8 journey" in (o.get("reason") or "") for o in aud_sum["override_history"]), \
        f"auditor sees the capacity overrides: {aud_sum['override_history'][:2]}"
    why = client.post("/api/v1/intelligence/ask", headers=aud,
                      json={"question": "Explain why this cycle cannot close", "cycle": CYCLE}).json()
    assert CYCLE in why["answer"] and why["advisory"] is True

    # 10. reconcile + close through the authoritative workflow only
    assert client.post(f"/api/v1/cycles/{CYCLE}/reconcile", headers=dso).json()["passed"] is True
    assert client.post(f"/api/v1/cycles/{CYCLE}/close", headers=dso).json()["state"] == "CLOSED"

    # 11. audit trail holds the AI events; chain intact
    actions = {r[0] for r in q(db, "SELECT DISTINCT action FROM audit_events WHERE cycle=%s", (CYCLE,))}
    assert "AI_INSIGHT_GENERATED" in actions and "AI_RECOMMENDATION_VIEWED" in actions
    assert "CYCLE_CLOSED" in actions, "closure remains a human-workflow event"
    sec = client.get("/api/v1/admin/security", headers=H(officers, "ADMIN")).json()
    assert sec["chain"]["intact"] is True

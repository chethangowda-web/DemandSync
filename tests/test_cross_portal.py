"""Phase 7: cross-portal integration contracts — ONE backend, ONE source of truth.

A single journey drives the same persisted records through every portal (beneficiary
OTP + intent -> DSO forecast/lock/allocate/optimize/authorize/dispatch/deliver ->
FPS receive/distribute -> beneficiary collection -> auditor trace/recon -> admin
feed -> reconcile/close), asserting at each arrow that every role sees the SAME
ids, quantities, statuses and timestamps. No portal keeps authoritative state.
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
    name = "phase7_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = swap_database(ADMIN_URL, name)
    migrate(url)
    assert import_dataset(url, activate=True, imported_by="pytest-phase7")["status"] == "ACTIVE"
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


@pytest.fixture(scope="module")
def api(journey_db):
    return client


def H(api, officers, role="DISTRICT_OFFICER"):
    token = api.post("/api/v1/auth/officer/login",
                     json={"officer_id": officers[role][0], "password": OFFICER_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def ben_headers(api):
    otp = api.post("/api/v1/auth/beneficiary/request-otp",
                   json={"ration_card_id": BEN_RC, "registered_mobile": BEN_MOBILE}).json()["dev_otp"]
    tok = api.post("/api/v1/auth/beneficiary/verify-otp",
                   json={"ration_card_id": BEN_RC, "otp": otp}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def ben(api, journey_db):
    """One beneficiary session per module: OTP challenges are single-use with a resend
    cooldown, so the token is minted once and reused (JWTs are not consumed)."""
    return ben_headers(api)


def fps_headers(api, journey_db):
    tok = api.post("/api/v1/auth/officer/login",
                   json={"officer_id": journey_db[1], "password": OFFICER_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def mfo_ids(db):
    return [r[0] for r in q(db, "SELECT manifest_id FROM dispatch_manifests WHERE cycle=%s AND manifest_id LIKE 'MFO-%%'",
                            (CYCLE,))]


# ------------------------------------------------------------------ the journey

def test_phase7_full_journey_same_records_every_portal(api, journey_db, officers, ben):
    db = journey_db[0]
    dso, aud = H(api, officers), H(api, officers, "AUDITOR")
    fps = fps_headers(api, journey_db)

    # TEST 1 — beneficiary intent is the SAME record the DSO and auditor see
    ent = api.get("/api/v1/beneficiaries/me/entitlement", headers=ben).json()
    assert ent["rice_kg"] == 22 and ent["wheat_kg"] == 13
    ir = api.post("/api/v1/preferences", headers=ben,
                  json={"fps_id": FPS_ID, "rice_quantity_kg": 4, "wheat_quantity_kg": 3, "collection_mode": "SELF"})
    assert ir.status_code == 201, ir.text
    intent_id = ir.json()["reference"]
    d_rows = api.get(f"/api/v1/cycles/{CYCLE}/demand?view=intent", headers=dso).json()["rows"]
    mine = [r for r in d_rows if r["fps_id"] == FPS_ID and r["commodity"] == "RICE"]
    assert mine and mine[0]["intent_demand_kg"] >= 4
    a_dem = api.get(f"/api/v1/auditor/cycles/{CYCLE}/demand", headers=aud).json()
    assert a_dem["chain"][0]["intent_kg"] >= 4

    # TEST 2 — DSO locks demand; lock visible to auditor, intent still traceable
    assert api.post(f"/api/v1/cycles/{CYCLE}/forecast", headers=dso).status_code == 200
    assert api.post(f"/api/v1/cycles/{CYCLE}/choice-window/close", headers=dso).status_code == 200
    lock = api.get(f"/api/v1/cycles/{CYCLE}/demand-lock", headers=dso).json()
    assert len(lock["sha256_hash"]) == 64
    assert api.get(f"/api/v1/auditor/cycles/{CYCLE}/demand", headers=aud).json()["demand_lock"]["locked"] is True
    assert api.get(f"/api/v1/preferences/{intent_id}/receipt", headers=ben).status_code == 200

    # TEST 3 — allocation (with the capacity override the seed needs); auditor + FPS views agree
    q(db, "UPDATE fps SET capacity_kg = 1 WHERE fps_id = %s", (FPS_ID,))
    assert api.post(f"/api/v1/cycles/{CYCLE}/allocate", headers=dso).status_code == 200
    for com, floor in (("RICE", 140), ("WHEAT", 90)):
        assert api.post(f"/api/v1/cycles/{CYCLE}/allocations/{FPS_ID}/{com}/override", headers=dso,
                        json={"allocated_kg": floor, "reason": "phase7 journey: stale capacity figure"}).status_code == 200
    alloc = { (a["commodity"]): a["allocated_kg"] for a in
              api.get(f"/api/v1/cycles/{CYCLE}/allocations", headers=dso).json()["allocations"] if a["fps_id"] == FPS_ID }
    assert alloc == {"RICE": 140, "WHEAT": 90}
    a_alloc = [a for a in api.get(f"/api/v1/auditor/cycles/{CYCLE}/demand", headers=aud).json()["allocations"]
               if a["fps_id"] == FPS_ID]
    assert {(a["commodity"], a["allocated_kg"]) for a in a_alloc} == {("RICE", 140), ("WHEAT", 90)}
    inc0 = api.get("/api/v1/fps/me/incoming", headers=fps).json()
    assert inc0["fps_id"] == FPS_ID
    assert not any(i["manifest_id"].startswith("MFO-") for i in inc0["items"])

    # TEST 4 — optimize; SAME manifest_id + hash on DSO, inspector, auditor, FPS
    assert api.post(f"/api/v1/cycles/{CYCLE}/optimize", headers=dso).status_code == 200
    mids = mfo_ids(db)
    assert mids
    h_dso = api.get(f"/api/v1/manifests/{mids[0]}/lock-verification", headers=dso)
    assert h_dso.status_code == 409  # not locked yet: DRAFT has no seal to verify
    for mid in mids:
        assert api.post(f"/api/v1/manifests/{mid}/validate", headers=dso).status_code == 200
        assert api.post(f"/api/v1/manifests/{mid}/lock", headers=dso).status_code == 200
    h1 = api.get(f"/api/v1/manifests/{mids[0]}/lock-verification", headers=dso).json()
    h2 = api.get(f"/api/v1/auditor/manifests/{mids[0]}", headers=aud).json()["lock_verification"]
    assert h1["hash_verified"] is True and h2["hash_verified"] is True
    assert h1["sha256_hash"] == h2["sha256_hash"] and len(h1["sha256_hash"]) == 64
    insp = H(api, officers, "FIELD_FOOD_INSPECTOR")
    det = api.get(f"/api/v1/inspector/targets/{FPS_ID}", headers=insp).json()
    insp_mfo = {d["manifest_id"] for d in det["dispatch"]["items"] if d["manifest_id"].startswith("MFO-")}
    assert insp_mfo and insp_mfo <= set(mids)
    inc1 = api.get("/api/v1/fps/me/incoming", headers=fps).json()
    mfo_seen = {i["manifest_id"] for i in inc1["items"] if i["manifest_id"].startswith("MFO-")}
    assert mfo_seen and mfo_seen <= set(mids)
    assert insp_mfo == mfo_seen, "inspector and FPS owner must see the same dispatch records"

    # TEST 5 — authorize + dispatch; FPS + inspector see DISPATCHED, no fake ETA/GPS
    assert api.post(f"/api/v1/cycles/{CYCLE}/authorize", headers=dso).status_code == 200
    assert api.post(f"/api/v1/cycles/{CYCLE}/dispatch", headers=dso).status_code == 200
    inc2 = api.get("/api/v1/fps/me/incoming", headers=fps).json()
    assert any(i["manifest_status"] == "DISPATCHED" for i in inc2["items"])
    assert inc2["eta_note"].startswith("ETA UNAVAILABLE") and "LIVE LOCATION UNAVAILABLE" in inc2["location_note"]
    det2 = api.get(f"/api/v1/inspector/targets/{FPS_ID}", headers=insp).json()
    assert any(d["manifest_status"] == "DISPATCHED" for d in det2["dispatch"]["items"])

    # TEST 6 — deliver exactly as planned; FPS + beneficiary journey update
    for mid in mids:
        items = q(db, "SELECT fps_id, commodity, planned_kg FROM dispatch_manifest_items WHERE manifest_id=%s", (mid,))
        body = {"items": [{"fps_id": i[0], "commodity": i[1], "delivered_kg": float(i[2])} for i in items]}
        r = api.post(f"/api/v1/manifests/{mid}/deliver", headers=dso, json=body)
        assert r.status_code == 200 and all(it["status"] == "VERIFIED" for it in r.json()["items"])
    jr = api.get("/api/v1/tracking/me", headers=ben).json()
    by_key = {s["key"]: s["status"] for s in jr["steps"]}
    assert by_key["RECEIVED_AT_FPS"] == "DONE" and by_key["AVAILABLE_FOR_COLLECTION"] == "DONE"
    collected_before = api.get("/api/v1/beneficiaries/me/entitlement", headers=ben).json()["collected_total_kg"]
    inc3 = api.get("/api/v1/fps/me/incoming", headers=fps).json()
    mine244 = [i for i in inc3["items"] if i["manifest_id"] in mids]
    assert mine244 and all(i["delivery_status"] == "VERIFIED" for i in mine244)

    # TEST 7 — FPS receives, distributes; collection everywhere, recon includes it
    rice_got = sum(i["delivered_kg"] for i in mine244 if i["commodity"] == "RICE")
    rr = api.post("/api/v1/fps/me/stock/receive", headers=fps,
                  json={"commodity": "RICE", "quantity_kg": rice_got, "reason": "phase7 journey receipt", "reference": mids[0]})
    assert rr.status_code == 201, rr.text
    dr = api.post("/api/v1/fps/me/distribute", headers=fps,
                  json={"beneficiary_id": BEN_ID, "commodity": "RICE", "quantity_kg": 2, "client_ref": "P7-JOURNEY-001"})
    assert dr.status_code == 201, dr.text
    txn = dr.json()["transaction_id"]
    jr2 = api.get("/api/v1/tracking/me", headers=ben).json()
    assert {s["key"]: s["status"] for s in jr2["steps"]}["COLLECTED"] == "DONE"
    collected_after = api.get("/api/v1/beneficiaries/me/entitlement", headers=ben).json()["collected_total_kg"]
    assert collected_after == collected_before + 2
    hist = api.get("/api/v1/history/me?kind=collections", headers=ben).json()
    assert hist
    a_rec = api.get(f"/api/v1/auditor/cycles/{CYCLE}/reconciliation", headers=aud).json()
    rice_line = next(r for r in a_rec["flow"] if r["commodity"] == "RICE")
    assert rice_line["distributed_kg"] >= 2
    assert rice_line["variance_kg"] == round(rice_line["received_kg"] - rice_line["distributed_kg"], 1)

    # auditor trace holds the whole chain; admin feed holds the mutations
    trace = api.get(f"/api/v1/auditor/cycles/{CYCLE}/trace?limit=500", headers=aud).json()
    actions = {e["action"] for e in trace["events"]}
    assert {"PREFERENCE_SUBMITTED", "DEMAND_LOCKED", "CYCLE_ALLOCATED", "ALLOCATION_OVERRIDDEN",
            "CYCLE_OPTIMIZED", "MANIFEST_LOCKED", "CYCLE_AUTHORIZED", "CYCLE_DISPATCHED",
            "DISTRIBUTION_RECORDED"} <= actions
    adm = H(api, officers, "ADMIN")
    # admin role id for assertions below
    sec = api.get("/api/v1/admin/security", headers=adm).json()
    assert sec["chain"]["intact"] is True

    # TEST 8 — reconcile, close; every portal reads the same CLOSED state
    assert api.post(f"/api/v1/cycles/{CYCLE}/reconcile", headers=dso).json()["passed"] is True
    assert api.post(f"/api/v1/cycles/{CYCLE}/close", headers=dso).json()["state"] == "CLOSED"
    assert api.get(f"/api/v1/cycles/{CYCLE}", headers=dso).json()["state"] == "CLOSED"
    assert api.get(f"/api/v1/auditor/cycles/{CYCLE}/stages", headers=aud).json()["stages"][6]["status"] == "COMPLETED"
    assert q1(db, "SELECT state FROM cycles WHERE cycle=%s", (CYCLE,))[0] == "CLOSED"


# ------------------------------------------------------------------ RBAC isolation

def test_phase7_rbac_matrix(api, journey_db, officers, ben):
    dso, fps = H(api, officers), fps_headers(api, journey_db)
    insp = H(api, officers, "FIELD_FOOD_INSPECTOR")
    aud = H(api, officers, "AUDITOR")
    adm = H(api, officers, "ADMIN")
    assert api.get(f"/api/v1/cycles/{CYCLE}/demand", headers=ben).status_code == 403
    assert api.get("/api/v1/admin/overview", headers=dso).status_code == 403
    assert api.get("/api/v1/admin/security", headers=insp).status_code == 403
    assert api.post(f"/api/v1/cycles/{CYCLE}/allocate", headers=fps).status_code == 403
    assert api.post(f"/api/v1/cycles/{CYCLE}/allocate", headers=aud).status_code == 403
    assert api.post(f"/api/v1/cycles/{CYCLE}/authorize", headers=insp).status_code == 403
    assert api.post("/api/v1/fps/me/distribute", headers=adm,
                    json={"beneficiary_id": BEN_ID, "commodity": "RICE", "quantity_kg": 1}).status_code == 403
    assert api.post(f"/api/v1/inspector/inspections", headers=fps, json={"fps_id": FPS_ID}).status_code == 403
    assert api.get("/api/v1/auditor/cycles/2026-02/overview", headers=fps).status_code == 403


# ------------------------------------------------------------------ deterministic failures

def test_phase7_failures(api, journey_db, officers, ben):
    dso = H(api, officers)
    fps = fps_headers(api, journey_db)
    db = journey_db[0]
    q(db, "INSERT INTO cycles (cycle, state) VALUES ('2099-05', 'OPEN') ON CONFLICT DO NOTHING")
    q(db, """INSERT INTO inventory (inventory_id, location_type, location_id, commodity, opening_stock_kg,
              received_kg, dispatched_kg, distributed_kg, adjusted_kg, closing_stock_kg, cycle)
              VALUES ('INV-P7-R', 'FPS', %s, 'RICE', 1000, 0, 0, 0, 0, 1000, '2099-05'),
                     ('INV-P7-W', 'FPS', %s, 'WHEAT', 1, 0, 0, 0, 0, 1, '2099-05')
              ON CONFLICT DO NOTHING""", (FPS_ID, FPS_ID))
    # duplicate intent
    first = api.post("/api/v1/preferences?cycle=2099-05", headers=ben,
                     json={"fps_id": FPS_ID, "rice_quantity_kg": 1, "wheat_quantity_kg": 1, "collection_mode": "SELF", "cycle": "2099-05"})
    assert first.status_code == 201, first.text
    dup = api.post("/api/v1/preferences?cycle=2099-05", headers=ben,
                   json={"fps_id": FPS_ID, "rice_quantity_kg": 1, "wheat_quantity_kg": 1, "collection_mode": "SELF", "cycle": "2099-05"})
    assert dup.status_code == 409 and dup.json()["code"] == "INTENT_DUPLICATE"
    # invalid transition: authorize an OPEN cycle
    r = api.post("/api/v1/cycles/2099-05/authorize", headers=dso)
    assert r.status_code == 409
    # entitlement exceeded (rice remaining is 22 in 2099-05)
    r = api.post("/api/v1/fps/me/distribute", headers=fps,
                 json={"beneficiary_id": BEN_ID, "commodity": "RICE", "quantity_kg": 23, "cycle": "2099-05"})
    assert r.status_code == 422 and r.json()["code"] == "ENTITLEMENT_EXCEEDED"
    # insufficient stock (wheat closing is 1)
    r = api.post("/api/v1/fps/me/distribute", headers=fps,
                 json={"beneficiary_id": BEN_ID, "commodity": "WHEAT", "quantity_kg": 2, "cycle": "2099-05"})
    assert r.status_code == 422 and r.json()["code"] == "INSUFFICIENT_STOCK"
    # wrong shop
    other = q1(db, "SELECT beneficiary_id FROM beneficiaries WHERE current_fps_id <> %s LIMIT 1", (FPS_ID,))[0]
    r = api.post("/api/v1/fps/me/distribute", headers=fps,
                 json={"beneficiary_id": other, "commodity": "RICE", "quantity_kg": 1, "cycle": "2099-05"})
    assert r.status_code == 403
    # expired JWT
    from backend.core.security import create_access_token
    dead = create_access_token("OFF-00001", "DSO", minutes=-1)
    assert api.get(f"/api/v1/cycles/{CYCLE}", headers={"Authorization": f"Bearer {dead}"}).status_code == 401


# ------------------------------------------------------------------ mass balance on seeded history

def test_phase7_mass_balance_seeded_cycle(api, journey_db, officers):
    aud = H(api, officers, "AUDITOR")
    rec = api.get("/api/v1/auditor/cycles/2026-02/reconciliation?limit=1", headers=aud).json()
    for line in rec["flow"]:
        assert line["variance_kg"] == round(line["received_kg"] - line["distributed_kg"], 1)
        assert line["status"] in ("VERIFIED", "VARIANCE", "BLOCKED")

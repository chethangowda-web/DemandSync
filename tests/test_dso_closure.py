"""Phase 2 Slices 4 & 5: OPTIMIZED -> AUTHORIZED -> TRACKING -> DELIVERING -> RECONCILING -> AUDITING ->
CLOSED. Manifest validation, SHA256 sealing + QR, DSO authorization, dispatch, delivery recording, the 7
closure checks, and final close.

This is where the full Phase 2 acceptance criterion gets proven end to end: beneficiary submits intent ->
DSO sees it -> forecast -> demand locked -> constraint violation blocks allocation -> DSO overrides with
reason -> OR-Tools produces allocation/route -> manifest hashed and locked -> DSO authorizes -> delivery
reconciles -> cycle closes with a complete audit trail.
"""
import base64
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.core.audit import verify_chain
from backend.core.credentials import set_password
from backend.db.ingest import import_dataset
from backend.db.migrate import migrate
from backend.main import app
from conftest import ADMIN_URL, OFFICER_PASSWORD, swap_database

pytestmark = pytest.mark.usefixtures("authdb")
client = TestClient(app)

FPS_ID, WAREHOUSE_ID = "FPS-0244", "WH-019"
BEN_RC, BEN_MOBILE = "RC2023100000", "9000060000"  # BEN-000001, FPS-0244


def q(db, sql, params=()):
    with psycopg.connect(db, autocommit=True) as c:
        cur = c.execute(sql, params)
        return cur.fetchall() if cur.description else None


def q1(db, sql, params=()):
    r = q(db, sql, params)
    return r[0] if r else None


def H(officers) -> dict:
    token = client.post("/api/v1/auth/officer/login", json={"officer_id": officers["DISTRICT_OFFICER"][0],
                                                             "password": OFFICER_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def auditor_headers(officers) -> dict:
    token = client.post("/api/v1/auth/officer/login", json={"officer_id": officers["AUDITOR"][0],
                                                             "password": OFFICER_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fresh_db(officers):
    if not ADMIN_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    name = "close_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = swap_database(ADMIN_URL, name)
    migrate(url)
    assert import_dataset(url, activate=True, imported_by="pytest-close")["status"] == "ACTIVE"
    with psycopg.connect(url) as c, c.transaction():
        for role in ("DISTRICT_OFFICER", "AUDITOR"):
            set_password(c, officers[role][0], OFFICER_PASSWORD)
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture
def api(fresh_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db)
    return client


def my_manifests(fresh_db, cycle="2026-03") -> list[str]:
    return [r[0] for r in q(fresh_db, "SELECT manifest_id FROM dispatch_manifests WHERE cycle=%s AND manifest_id LIKE 'MFO-%%'", (cycle,))]


def lock_allocate_optimize(api, officers, cycle="2026-03") -> None:
    assert api.post(f"/api/v1/cycles/{cycle}/choice-window/close", headers=H(officers)).status_code == 200
    assert api.post(f"/api/v1/cycles/{cycle}/allocate", headers=H(officers)).status_code == 200
    assert api.post(f"/api/v1/cycles/{cycle}/optimize", headers=H(officers)).status_code == 200


def validate_and_lock_all(api, officers, fresh_db, cycle="2026-03") -> list[str]:
    mids = my_manifests(fresh_db, cycle)
    for mid in mids:
        assert api.post(f"/api/v1/manifests/{mid}/validate", headers=H(officers)).status_code == 200
        assert api.post(f"/api/v1/manifests/{mid}/lock", headers=H(officers)).status_code == 200
    return mids


# ------------------------------------------------------------------ RBAC

WRITE_ENDPOINTS_NEEDING_SETUP = ["choice-window/close", "allocate", "optimize", "authorize", "dispatch", "reconcile", "close"]


@pytest.mark.parametrize("action", WRITE_ENDPOINTS_NEEDING_SETUP)
def test_cycle_write_endpoints_require_manage_cycle(api, officers, action):
    path = f"/api/v1/cycles/2026-03/{action}"
    assert api.post(path).status_code == 401
    assert api.post(path, headers=auditor_headers(officers)).status_code == 403


# ------------------------------------------------------------------ the full acceptance-criterion chain

def test_full_lifecycle_intent_to_closed_with_complete_audit_trail(fresh_db, api, officers):
    # beneficiary submits intent -> DSO sees it -> forecast -> demand locked
    otp = client.post("/api/v1/auth/beneficiary/request-otp", json={"ration_card_id": BEN_RC, "registered_mobile": BEN_MOBILE}).json()["dev_otp"]
    ben_token = client.post("/api/v1/auth/beneficiary/verify-otp", json={"ration_card_id": BEN_RC, "otp": otp}).json()["access_token"]
    ir = client.post("/api/v1/preferences", headers={"Authorization": f"Bearer {ben_token}"},
                     json={"fps_id": FPS_ID, "rice_quantity_kg": 4, "wheat_quantity_kg": 3, "collection_mode": "SELF"})  # BEN-000001's entitlement caps rice at 4kg
    assert ir.status_code == 201, ir.text
    assert api.post("/api/v1/cycles/2026-03/forecast", headers=H(officers)).status_code == 200

    # -> constraint violation blocks allocation -> DSO overrides with reason
    q(fresh_db, "UPDATE fps SET capacity_kg = 1 WHERE fps_id = %s", (FPS_ID,))
    assert api.post("/api/v1/cycles/2026-03/choice-window/close", headers=H(officers)).status_code == 200
    assert api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers)).status_code == 200
    for commodity, floor_kg in (("RICE", 140), ("WHEAT", 90)):
        r = api.post(f"/api/v1/cycles/2026-03/allocations/{FPS_ID}/{commodity}/override", headers=H(officers),
                     json={"allocated_kg": floor_kg, "reason": "capacity figure stale; shop can hold this"})
        assert r.status_code == 200, r.text

    # -> OR-Tools produces allocation/route
    assert api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers)).status_code == 200
    mids = my_manifests(fresh_db)
    assert mids

    # -> manifest is hashed and locked
    for mid in mids:
        assert api.post(f"/api/v1/manifests/{mid}/validate", headers=H(officers)).status_code == 200
        r = api.post(f"/api/v1/manifests/{mid}/lock", headers=H(officers))
        assert r.status_code == 200 and len(r.json()["sha256_hash"]) == 64
        lv = api.get(f"/api/v1/manifests/{mid}/lock-verification", headers=H(officers))
        assert lv.status_code == 200 and lv.json()["hash_verified"] is True

    # -> DSO authorizes
    ar = api.post("/api/v1/cycles/2026-03/authorize", headers=H(officers))
    assert ar.status_code == 200 and ar.json()["state"] == "AUTHORIZED"

    # dispatch -> deliver exactly as planned (VERIFIED) -> reconcile -> close
    assert api.post("/api/v1/cycles/2026-03/dispatch", headers=H(officers)).status_code == 200
    for mid in mids:
        items = q(fresh_db, "SELECT fps_id, commodity, planned_kg FROM dispatch_manifest_items WHERE manifest_id=%s", (mid,))
        body = {"items": [{"fps_id": i[0], "commodity": i[1], "delivered_kg": float(i[2])} for i in items]}
        r = api.post(f"/api/v1/manifests/{mid}/deliver", headers=H(officers), json=body)
        assert r.status_code == 200, r.text
        assert all(it["status"] == "VERIFIED" for it in r.json()["items"])

    # -> delivery reconciles
    rr = api.post("/api/v1/cycles/2026-03/reconcile", headers=H(officers))
    assert rr.status_code == 200, rr.text
    body = rr.json()
    assert body["passed"] is True and body["state"] == "AUDITING"
    assert all(body["checks"].values())

    # -> cycle closes with complete audit trail
    cr = api.post("/api/v1/cycles/2026-03/close", headers=H(officers))
    assert cr.status_code == 200 and cr.json()["state"] == "CLOSED"
    final = q1(fresh_db, "SELECT state, closed_at FROM cycles WHERE cycle='2026-03'")
    assert final[0] == "CLOSED" and final[1] is not None

    # ALLOCATION_OVERRIDDEN's entity_id is the allocation_id, not the cycle -- filter by cycle alone
    actions = {a[0] for a in q(fresh_db, "SELECT action FROM audit_events WHERE cycle='2026-03'")}
    assert {"CHOICE_WINDOW_CLOSED", "DEMAND_LOCKED", "CYCLE_ALLOCATED", "ALLOCATION_OVERRIDDEN", "CYCLE_OPTIMIZED",
           "CYCLE_AUTHORIZED", "CYCLE_DISPATCHED", "CYCLE_RECONCILED", "CYCLE_CLOSED"} <= actions
    assert verify_chain(fresh_db)["intact"] is True


# ------------------------------------------------------------------ Slice 4: validation, sealing, authorization

def test_validate_requires_draft(fresh_db, api, officers):
    lock_allocate_optimize(api, officers)
    mid = my_manifests(fresh_db)[0]
    assert api.post(f"/api/v1/manifests/{mid}/validate", headers=H(officers)).status_code == 200
    again = api.post(f"/api/v1/manifests/{mid}/validate", headers=H(officers))
    assert again.status_code == 409 and again.json()["code"] == "MANIFEST_NOT_DRAFT"


def test_validate_catches_a_stale_allocation_after_an_override(fresh_db, api, officers):
    lock_allocate_optimize(api, officers)
    mid = my_manifests(fresh_db)[0]
    item = q1(fresh_db, "SELECT fps_id, commodity FROM dispatch_manifest_items WHERE manifest_id=%s LIMIT 1", (mid,))
    api.post(f"/api/v1/cycles/2026-03/allocations/{item[0]}/{item[1]}/override", headers=H(officers),
             json={"allocated_kg": 999, "reason": "changed after routing, for this test"})
    r = api.post(f"/api/v1/manifests/{mid}/validate", headers=H(officers))
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_FAILED"


def test_lock_requires_validated(fresh_db, api, officers):
    lock_allocate_optimize(api, officers)
    mid = my_manifests(fresh_db)[0]
    r = api.post(f"/api/v1/manifests/{mid}/lock", headers=H(officers))
    assert r.status_code == 409 and r.json()["code"] == "MANIFEST_NOT_VALIDATED"


def test_locked_manifest_content_is_immutable(fresh_db, api, officers):
    lock_allocate_optimize(api, officers)
    mid = my_manifests(fresh_db)[0]
    api.post(f"/api/v1/manifests/{mid}/validate", headers=H(officers))
    api.post(f"/api/v1/manifests/{mid}/lock", headers=H(officers))
    with pytest.raises(psycopg.errors.RestrictViolation):
        q(fresh_db, "UPDATE dispatch_manifests SET total_kg = total_kg + 1 WHERE manifest_id=%s", (mid,))


def test_qr_endpoint_returns_a_real_png(fresh_db, api, officers):
    lock_allocate_optimize(api, officers)
    mid = my_manifests(fresh_db)[0]
    api.post(f"/api/v1/manifests/{mid}/validate", headers=H(officers))
    api.post(f"/api/v1/manifests/{mid}/lock", headers=H(officers))
    r = api.get(f"/api/v1/manifests/{mid}/qr", headers=H(officers))
    assert r.status_code == 200
    png = base64.b64decode(r.json()["qr_png_base64"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_authorize_requires_every_manifest_locked(fresh_db, api, officers):
    lock_allocate_optimize(api, officers)
    r = api.post("/api/v1/cycles/2026-03/authorize", headers=H(officers))
    assert r.status_code == 409 and r.json()["code"] == "MANIFESTS_NOT_LOCKED"


# ------------------------------------------------------------------ Slice 5: dispatch, delivery, closure

def test_dispatch_requires_authorized(api, officers):
    lock_allocate_optimize(api, officers)
    r = api.post("/api/v1/cycles/2026-03/dispatch", headers=H(officers))
    assert r.status_code == 409 and r.json()["code"] == "CYCLE_NOT_AUTHORIZED"


def test_delivery_records_variance_and_rejected(fresh_db, api, officers):
    lock_allocate_optimize(api, officers)
    validate_and_lock_all(api, officers, fresh_db)
    api.post("/api/v1/cycles/2026-03/authorize", headers=H(officers))
    api.post("/api/v1/cycles/2026-03/dispatch", headers=H(officers))
    mid = my_manifests(fresh_db)[0]
    items = q(fresh_db, "SELECT fps_id, commodity, planned_kg FROM dispatch_manifest_items WHERE manifest_id=%s", (mid,))
    body = {"items": [{"fps_id": items[0][0], "commodity": items[0][1], "delivered_kg": 0}] +
                     [{"fps_id": i[0], "commodity": i[1], "delivered_kg": float(i[2]) * 2} for i in items[1:]]}
    r = api.post(f"/api/v1/manifests/{mid}/deliver", headers=H(officers), json=body)
    assert r.status_code == 200, r.text
    statuses = {(it["fps_id"], it["commodity"]): it["status"] for it in r.json()["items"]}
    key0 = (items[0][0], items[0][1])
    assert statuses[key0] == "REJECTED"
    assert any(s == "VARIANCE" for k, s in statuses.items() if k != key0)


def test_reconcile_fails_and_stays_reconciling_when_deliveries_are_incomplete(fresh_db, api, officers):
    lock_allocate_optimize(api, officers)
    validate_and_lock_all(api, officers, fresh_db)
    api.post("/api/v1/cycles/2026-03/authorize", headers=H(officers))
    api.post("/api/v1/cycles/2026-03/dispatch", headers=H(officers))
    # deliver nothing -> ALL_MANIFESTS_DELIVERED must fail; reconcile requires DELIVERING state, which
    # only starts once at least one delivery is recorded, so first record one to reach DELIVERING
    mids = my_manifests(fresh_db)
    items = q(fresh_db, "SELECT fps_id, commodity, planned_kg FROM dispatch_manifest_items WHERE manifest_id=%s", (mids[0],))
    api.post(f"/api/v1/manifests/{mids[0]}/deliver", headers=H(officers),
             json={"items": [{"fps_id": i[0], "commodity": i[1], "delivered_kg": float(i[2])} for i in items]})
    r = api.post("/api/v1/cycles/2026-03/reconcile", headers=H(officers))
    assert r.status_code == 200
    body = r.json()
    if len(mids) > 1:
        assert body["passed"] is False and body["state"] == "RECONCILING"
        assert body["checks"]["ALL_MANIFESTS_DELIVERED"] is False
        codes = {e[0] for e in q(fresh_db, "SELECT rule_code FROM exceptions WHERE cycle='2026-03' AND entity_type='CLOSURE'")}
        assert "ALL_MANIFESTS_DELIVERED" in codes


def test_close_requires_auditing(fresh_db, api, officers):
    lock_allocate_optimize(api, officers)
    validate_and_lock_all(api, officers, fresh_db)
    api.post("/api/v1/cycles/2026-03/authorize", headers=H(officers))
    r = api.post("/api/v1/cycles/2026-03/close", headers=H(officers))
    assert r.status_code == 409 and r.json()["code"] == "CYCLE_NOT_AUDITING"

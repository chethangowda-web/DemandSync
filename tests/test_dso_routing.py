"""Phase 2 Slice 3: ALLOCATED -> OPTIMIZED. OR-Tools CVRP over haversine distance, vehicle routes, and
DRAFT dispatch manifests.

Acceptance slice this proves: an unresolved blocking exception refuses optimization -> once resolved (or
the underlying allocation is naturally APPROVED), the engine plans real vehicle routes within real fleet
capacity -> a stop no available vehicle can reach is never silently dropped, it's a logged HIGH exception.
"""
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

FPS_ID, WAREHOUSE_ID = "FPS-0244", "WH-019"


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


def inspector_headers(officers) -> dict:
    token = client.post("/api/v1/auth/officer/login", json={"officer_id": officers["FIELD_FOOD_INSPECTOR"][0],
                                                             "password": OFFICER_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fresh_db(officers):
    if not ADMIN_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    name = "route_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = swap_database(ADMIN_URL, name)
    migrate(url)
    assert import_dataset(url, activate=True, imported_by="pytest-route")["status"] == "ACTIVE"
    with psycopg.connect(url) as c, c.transaction():
        for role in ("DISTRICT_OFFICER", "FIELD_FOOD_INSPECTOR"):
            set_password(c, officers[role][0], OFFICER_PASSWORD)
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture
def api(fresh_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db)
    return client


def lock_and_allocate(api, officers, cycle="2026-03") -> dict:
    r1 = api.post(f"/api/v1/cycles/{cycle}/choice-window/close", headers=H(officers))
    assert r1.status_code == 200, r1.text
    r2 = api.post(f"/api/v1/cycles/{cycle}/allocate", headers=H(officers))
    assert r2.status_code == 200, r2.text
    return r2.json()


# ------------------------------------------------------------------ RBAC

def test_optimize_requires_manage_cycle(api, officers):
    lock_and_allocate(api, officers)
    assert api.post("/api/v1/cycles/2026-03/optimize").status_code == 401
    assert api.post("/api/v1/cycles/2026-03/optimize", headers=inspector_headers(officers)).status_code == 403


def test_manifests_require_view_manifest(api, officers):
    lock_and_allocate(api, officers)
    api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))
    assert api.get("/api/v1/cycles/2026-03/manifests").status_code == 401
    assert api.get("/api/v1/cycles/2026-03/manifests", headers=inspector_headers(officers)).status_code == 403
    assert api.get("/api/v1/cycles/2026-03/manifests", headers=H(officers)).status_code == 200


# ------------------------------------------------------------------ state machine

def test_optimize_requires_an_allocated_cycle(api, officers):
    r = api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))  # 2026-03 is OPEN, never locked/allocated
    assert r.status_code == 409 and r.json()["code"] == "CYCLE_NOT_ALLOCATED"


def test_optimize_twice_is_rejected(api, officers):
    lock_and_allocate(api, officers)
    first = api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))
    assert first.status_code == 200, first.text
    again = api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))
    assert again.status_code == 409 and again.json()["code"] == "CYCLE_ALREADY_OPTIMIZED"


# Slice 3's manifest ids always start "MFO-"; the seeded dataset's own historical manifests use short
# numeric ids ("MAN-000275") and already reference the same allocation_id values Slice 2 upserts onto, so
# this prefix is how both the app and these tests isolate what the live workflow actually produced.
MY_MANIFEST = "m.manifest_id LIKE 'MFO-%%'"


def test_a_blocked_allocation_is_excluded_from_manifests_until_overridden(fresh_db, api, officers):
    """The per-item BLOCKED status (from Slice 2's gates) is what keeps a violation out of routing —
    scoped to that FPS, not a single switch that halts every other warehouse's dispatch."""
    q(fresh_db, "UPDATE fps SET capacity_kg = 1 WHERE fps_id = %s", (FPS_ID,))  # forces BLOCKED
    lock_and_allocate(api, officers)
    r = api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))
    assert r.status_code == 200, r.text
    assert r.json()["allocations_blocked"] >= 2  # FPS-0244's RICE + WHEAT

    assert not q(fresh_db, f"""SELECT 1 FROM dispatch_manifest_items mi JOIN dispatch_manifests m USING (manifest_id)
                               WHERE m.cycle='2026-03' AND mi.fps_id=%s AND {MY_MANIFEST}""", (FPS_ID,))


def test_overriding_before_optimize_lets_it_be_routed(fresh_db, api, officers):
    """FPS capacity is overridable (unlike the entitlement floor, which a DSO can never go below — see the
    FPS_CAPACITY_EXCEEDED case): the DSO can knowingly deliver the full entitlement floor anyway."""
    q(fresh_db, "UPDATE fps SET capacity_kg = 1 WHERE fps_id = %s", (FPS_ID,))
    lock_and_allocate(api, officers)
    for commodity, floor_kg in (("RICE", 140), ("WHEAT", 90)):
        r = api.post(f"/api/v1/cycles/2026-03/allocations/{FPS_ID}/{commodity}/override", headers=H(officers),
                     json={"allocated_kg": floor_kg, "reason": "capacity figure is stale; shop can actually hold this"})
        assert r.status_code == 200, r.text
    r = api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))
    assert r.status_code == 200, r.text

    item = q1(fresh_db, f"""SELECT mi.planned_kg FROM dispatch_manifest_items mi JOIN dispatch_manifests m USING (manifest_id)
                            WHERE m.cycle='2026-03' AND mi.fps_id=%s AND mi.commodity='RICE' AND {MY_MANIFEST}""", (FPS_ID,))
    assert item is not None and float(item[0]) == 140


# ------------------------------------------------------------------ real CVRP over the seeded dataset

def test_optimize_plans_real_routes_within_vehicle_capacity(fresh_db, api, officers):
    lock_and_allocate(api, officers)
    r = api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "OPTIMIZED" and body["manifests_created"] > 0

    assert q1(fresh_db, "SELECT state FROM cycles WHERE cycle='2026-03'")[0] == "OPTIMIZED"
    actions = {a[0] for a in q(fresh_db, "SELECT action FROM audit_events WHERE entity_id='2026-03' AND cycle='2026-03'")}
    assert "CYCLE_OPTIMIZED" in actions

    # every manifest this run created must respect its vehicle's real capacity
    over_capacity = q(fresh_db, f"""
        SELECT m.manifest_id FROM dispatch_manifests m JOIN vehicles v ON v.vehicle_id = m.vehicle_id
        WHERE m.cycle = '2026-03' AND {MY_MANIFEST} AND m.total_kg > v.capacity_kg""")
    assert not over_capacity

    # FPS-0244's allocation must now be on exactly one new manifest, planned for its real entitlement-floor kg
    item = q1(fresh_db, f"""SELECT mi.planned_kg, mi.commodity, m.constraint_status, m.route_distance_km
                           FROM dispatch_manifest_items mi JOIN dispatch_manifests m USING (manifest_id)
                           WHERE m.cycle='2026-03' AND mi.fps_id=%s AND mi.commodity='RICE' AND {MY_MANIFEST}""", (FPS_ID,))
    assert item is not None and float(item[0]) == 140 and item[2] == "READY"


def test_manifest_detail_labels_distance_as_haversine_and_has_sequential_stops(fresh_db, api, officers):
    lock_and_allocate(api, officers)
    api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))
    mid = q1(fresh_db, f"""SELECT m.manifest_id FROM dispatch_manifests m JOIN dispatch_manifest_items mi USING (manifest_id)
                          WHERE m.cycle='2026-03' AND mi.fps_id=%s AND {MY_MANIFEST} LIMIT 1""", (FPS_ID,))[0]
    r = client.get(f"/api/v1/manifests/{mid}", headers=H(officers))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "haversine" in body["distance_basis"].lower() and "not road distance" in body["distance_basis"].lower()
    seqs = [s["stop_sequence"] for s in body["route"]]
    assert seqs == list(range(1, len(seqs) + 1))


def test_manifest_not_found_is_a_clean_404(api, officers):
    lock_and_allocate(api, officers)
    r = client.get("/api/v1/manifests/MAN-DOES-NOT-EXIST", headers=H(officers))
    assert r.status_code == 404 and r.json()["code"] == "MANIFEST_NOT_FOUND"


def test_no_available_vehicle_is_a_logged_exception_not_a_silent_drop(fresh_db, api, officers):
    q(fresh_db, "UPDATE vehicles SET current_status = 'MAINTENANCE' WHERE warehouse_id = %s", (WAREHOUSE_ID,))
    lock_and_allocate(api, officers)
    r = api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))
    assert r.status_code == 200, r.text  # other warehouses still optimize fine
    assert r.json()["stops_unroutable"] > 0

    assert not q(fresh_db, f"""SELECT 1 FROM dispatch_manifest_items mi JOIN dispatch_manifests m USING (manifest_id)
                              WHERE m.cycle='2026-03' AND mi.fps_id=%s AND {MY_MANIFEST}""", (FPS_ID,))
    exc = q1(fresh_db, "SELECT rule_code, severity, status FROM exceptions WHERE cycle='2026-03' AND entity_id=%s AND rule_code='NO_VEHICLE_AVAILABLE'", (FPS_ID,))
    assert exc is not None and exc[1] == "HIGH" and exc[2] == "OPEN"


def test_insufficient_fleet_capacity_drops_the_heaviest_stop_and_logs_it(fresh_db, api, officers):
    q(fresh_db, "UPDATE vehicles SET capacity_kg = 5 WHERE warehouse_id = %s", (WAREHOUSE_ID,))
    lock_and_allocate(api, officers)
    r = api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers))
    assert r.status_code == 200, r.text
    assert r.json()["stops_unroutable"] > 0
    codes = {e[0] for e in q(fresh_db, "SELECT rule_code FROM exceptions WHERE cycle='2026-03' AND entity_id=%s", (FPS_ID,))}
    assert "INSUFFICIENT_FLEET_CAPACITY" in codes

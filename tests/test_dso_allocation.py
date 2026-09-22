"""Phase 2 Slice 2: LOCKED -> ALLOCATED. The 6-gate constraint engine, exceptions, allocation, and
audited DSO overrides.

Acceptance slice this proves: demand is locked -> the engine proposes an allocation per FPS+commodity,
clamped to real physical/legal constraints -> a violation is recorded as an exception and blocks that
allocation -> the DSO fixes it with a mandatory-reason, audited override, which resolves the exception.
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

# FPS-0244: capacity 1500kg, warehouse WH-019 (30328kg rice / 24982kg wheat stock), 12 active
# beneficiaries with a combined entitlement floor of 140kg rice / 90kg wheat (data/01_master).
FPS_ID, RICE_FLOOR, WHEAT_FLOOR, WAREHOUSE_ID = "FPS-0244", 140, 90, "WH-019"


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


def fps_owner_headers(officers) -> dict:
    token = client.post("/api/v1/auth/officer/login", json={"officer_id": officers["FPS_OWNER"][0],
                                                             "password": OFFICER_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def auditor_headers(officers) -> dict:
    token = client.post("/api/v1/auth/officer/login", json={"officer_id": officers["AUDITOR"][0],
                                                             "password": OFFICER_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ fixtures

@pytest.fixture
def fresh_db(officers):
    """A disposable database per test: allocate() writes allocations/exceptions that later tests in the
    same run must not see, and the underlying demand lock is immutable by trigger (see test_dso_demand.py)."""
    if not ADMIN_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    name = "alloc_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = swap_database(ADMIN_URL, name)
    migrate(url)
    assert import_dataset(url, activate=True, imported_by="pytest-alloc")["status"] == "ACTIVE"
    with psycopg.connect(url) as c, c.transaction():
        for role in ("DISTRICT_OFFICER", "AUDITOR", "FPS_OWNER"):
            set_password(c, officers[role][0], OFFICER_PASSWORD)
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture
def api(fresh_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db)
    return client


def lock_cycle(api, officers, cycle="2026-03") -> dict:
    r = api.post(f"/api/v1/cycles/{cycle}/choice-window/close", headers=H(officers))
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ RBAC

def test_allocate_requires_manage_cycle(api, officers):
    lock_cycle(api, officers)
    assert api.post("/api/v1/cycles/2026-03/allocate").status_code == 401
    assert api.post("/api/v1/cycles/2026-03/allocate", headers=auditor_headers(officers)).status_code == 403
    r = api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    assert r.status_code == 200, r.text


def test_view_allocations_and_exceptions_require_view_demand(api, officers):
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    for path in ("/api/v1/cycles/2026-03/allocations", "/api/v1/cycles/2026-03/exceptions",
                "/api/v1/cycles/2026-03/constraints/preview"):
        assert api.get(path).status_code == 401
        assert api.get(path, headers=fps_owner_headers(officers)).status_code == 403  # FPS_OWNER lacks VIEW_DEMAND
        assert api.get(path, headers=H(officers)).status_code == 200


def test_override_requires_manage_cycle(api, officers):
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    body = {"allocated_kg": RICE_FLOOR, "reason": "test"}
    path = f"/api/v1/cycles/2026-03/allocations/{FPS_ID}/RICE/override"
    assert api.post(path, json=body).status_code == 401
    assert api.post(path, json=body, headers=auditor_headers(officers)).status_code == 403


# ------------------------------------------------------------------ state machine

def test_allocate_requires_a_locked_cycle(api, officers):
    r = api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))  # 2026-03 is OPEN, never locked
    assert r.status_code == 409 and r.json()["code"] == "CYCLE_NOT_LOCKED"


def test_allocate_twice_is_rejected(api, officers):
    lock_cycle(api, officers)
    first = api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    assert first.status_code == 200
    again = api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    assert again.status_code == 409 and again.json()["code"] == "CYCLE_ALREADY_ALLOCATED"


def test_allocate_advances_cycle_state_and_audits(fresh_db, api, officers):
    lock_cycle(api, officers)
    r = api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    assert r.status_code == 200 and r.json()["state"] == "ALLOCATED"
    assert q1(fresh_db, "SELECT state FROM cycles WHERE cycle = '2026-03'")[0] == "ALLOCATED"
    actions = {a[0] for a in q(fresh_db, "SELECT action FROM audit_events WHERE entity_id = '2026-03' AND cycle = '2026-03'")}
    assert "CYCLE_ALLOCATED" in actions


# ------------------------------------------------------------------ the 6-gate engine, against real seeded data

def test_entitlement_floor_raises_allocation_above_zero_locked_demand(fresh_db, api, officers):
    """2026-03 has no seeded intent, so its locked demand is 0kg everywhere (see test_dso_demand.py). The
    engine must never leave FPS-0244's 12 active beneficiaries below their legal entitlement."""
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))

    rice = q1(fresh_db, "SELECT requested_kg, allocated_kg, status FROM allocations WHERE cycle='2026-03' AND fps_id=%s AND commodity='RICE'", (FPS_ID,))
    assert rice is not None, "FPS-0244/RICE should have an allocation row (its historical baseline makes it appear in the lock snapshot)"
    assert float(rice[0]) == 0  # locked demand was 0
    assert float(rice[1]) == RICE_FLOOR  # engine raised it to the entitlement floor
    assert rice[2] == "APPROVED"  # 1500kg capacity and 30328kg stock comfortably cover 140kg

    exc = q(fresh_db, "SELECT rule_code, severity, status FROM exceptions WHERE cycle='2026-03' AND entity_id=%s", (f"{FPS_ID}:RICE",))
    codes = {e[0] for e in exc}
    assert "BELOW_NFSA_ENTITLEMENT_FLOOR" in codes
    assert all(e[2] == "OPEN" for e in exc if e[0] == "BELOW_NFSA_ENTITLEMENT_FLOOR")


def test_fps_capacity_gate_clamps_and_flags_when_floor_exceeds_capacity(fresh_db, api, officers):
    """A physical ceiling wins over the legal floor when they conflict — that conflict is flagged HIGH,
    not silently resolved, because it is a real operational crisis for the DSO to act on."""
    q(fresh_db, "UPDATE fps SET capacity_kg = 50 WHERE fps_id = %s", (FPS_ID,))
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))

    rice = q1(fresh_db, "SELECT allocated_kg, status FROM allocations WHERE cycle='2026-03' AND fps_id=%s AND commodity='RICE'", (FPS_ID,))
    assert float(rice[0]) == 50  # clamped to the (reduced) capacity, below the 140kg floor
    assert rice[1] == "BLOCKED"

    codes = {e[0] for e in q(fresh_db, "SELECT rule_code FROM exceptions WHERE cycle='2026-03' AND entity_id=%s", (f"{FPS_ID}:RICE",))}
    assert {"BELOW_NFSA_ENTITLEMENT_FLOOR", "FPS_CAPACITY_EXCEEDED"} <= codes


def test_warehouse_stock_gate_clamps_when_stock_cannot_cover_the_floor(fresh_db, api, officers):
    """WH-019 serves other FPS too, all with the same entitlement-floor-driven demand this cycle, so
    FPS-0244 may see anywhere from 0 up to the 20kg left depending on processing order — what matters is
    it can never exceed the reduced stock, and the shortfall is flagged."""
    q(fresh_db, "UPDATE warehouses SET rice_stock_kg = 20 WHERE warehouse_id = %s", (WAREHOUSE_ID,))
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))

    rice = q1(fresh_db, "SELECT allocated_kg, status FROM allocations WHERE cycle='2026-03' AND fps_id=%s AND commodity='RICE'", (FPS_ID,))
    assert 0 <= float(rice[0]) <= 20
    assert rice[1] == "BLOCKED"
    codes = {e[0] for e in q(fresh_db, "SELECT rule_code FROM exceptions WHERE cycle='2026-03' AND entity_id=%s", (f"{FPS_ID}:RICE",))}
    assert "WAREHOUSE_STOCK_SHORTFALL" in codes


def test_inactive_fps_flags_route_not_feasible(fresh_db, api, officers):
    q(fresh_db, "UPDATE fps SET status = 'INACTIVE' WHERE fps_id = %s", (FPS_ID,))
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    codes = {e[0] for e in q(fresh_db, "SELECT rule_code FROM exceptions WHERE cycle='2026-03' AND entity_id=%s", (f"{FPS_ID}:RICE",))}
    assert "ROUTE_NOT_FEASIBLE" in codes


def test_constraints_preview_is_read_only(fresh_db, api, officers):
    """The dataset ships a placeholder allocations row and historical exceptions for every cycle
    (the same seeded-data pattern Slice 1 hit with demand_forecast) — preview must not touch either."""
    lock_cycle(api, officers)
    before_alloc = q1(fresh_db, "SELECT count(*) FROM allocations WHERE cycle='2026-03'")[0]
    before_exc = q1(fresh_db, "SELECT count(*) FROM exceptions WHERE cycle='2026-03'")[0]

    r = api.get("/api/v1/cycles/2026-03/constraints/preview", headers=H(officers))
    assert r.status_code == 200
    assert any(f["fps_id"] == FPS_ID for f in r.json()["findings"])

    assert q1(fresh_db, "SELECT count(*) FROM allocations WHERE cycle='2026-03'")[0] == before_alloc
    assert q1(fresh_db, "SELECT count(*) FROM exceptions WHERE cycle='2026-03'")[0] == before_exc


# ------------------------------------------------------------------ audited overrides

def test_override_requires_a_reason(api, officers):
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    r = api.post(f"/api/v1/cycles/2026-03/allocations/{FPS_ID}/RICE/override", headers=H(officers),
                json={"allocated_kg": 200, "reason": "   "})
    assert r.status_code == 422 and r.json()["code"] == "REASON_REQUIRED"


def test_override_cannot_go_below_entitlement_floor(api, officers):
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    r = api.post(f"/api/v1/cycles/2026-03/allocations/{FPS_ID}/RICE/override", headers=H(officers),
                json={"allocated_kg": RICE_FLOOR - 1, "reason": "trying to cut it"})
    assert r.status_code == 422 and r.json()["code"] == "BELOW_ENTITLEMENT_FLOOR"


def test_override_cannot_exceed_warehouse_stock(fresh_db, api, officers):
    q(fresh_db, "UPDATE warehouses SET rice_stock_kg = 200 WHERE warehouse_id = %s", (WAREHOUSE_ID,))
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    r = api.post(f"/api/v1/cycles/2026-03/allocations/{FPS_ID}/RICE/override", headers=H(officers),
                json={"allocated_kg": 500, "reason": "way over what the warehouse holds"})
    assert r.status_code == 422 and r.json()["code"] == "EXCEEDS_WAREHOUSE_STOCK"


def test_override_updates_allocation_resolves_exception_and_audits_before_after(fresh_db, api, officers):
    q(fresh_db, "UPDATE fps SET capacity_kg = 50 WHERE fps_id = %s", (FPS_ID,))  # forces a BLOCKED allocation
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    before = q1(fresh_db, "SELECT allocated_kg FROM allocations WHERE cycle='2026-03' AND fps_id=%s AND commodity='RICE'", (FPS_ID,))
    assert float(before[0]) == 50

    r = api.post(f"/api/v1/cycles/2026-03/allocations/{FPS_ID}/RICE/override", headers=H(officers),
                json={"allocated_kg": 150, "reason": "capacity figure was stale; shop was recently expanded"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["before_kg"] == 50 and body["after_kg"] == 150 and body["status"] == "APPROVED"

    row = q1(fresh_db, "SELECT allocated_kg, status, source FROM allocations WHERE cycle='2026-03' AND fps_id=%s AND commodity='RICE'", (FPS_ID,))
    assert float(row[0]) == 150 and row[1] == "APPROVED" and row[2] == "DSO_OVERRIDE"

    exc = q(fresh_db, "SELECT status, resolution FROM exceptions WHERE cycle='2026-03' AND entity_id=%s AND rule_code='FPS_CAPACITY_EXCEEDED'", (f"{FPS_ID}:RICE",))
    assert all(e[0] == "RESOLVED" and "capacity figure was stale" in e[1] for e in exc)

    audit = q1(fresh_db, "SELECT before_state, after_state, reason FROM audit_events WHERE action='ALLOCATION_OVERRIDDEN' AND cycle='2026-03'")
    assert audit[0] == "50" and audit[1] == "150" and "capacity figure was stale" in audit[2]


def test_override_unknown_allocation_is_a_clean_404(api, officers):
    lock_cycle(api, officers)
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    r = api.post("/api/v1/cycles/2026-03/allocations/FPS-9999/RICE/override", headers=H(officers),
                json={"allocated_kg": 10, "reason": "x"})
    assert r.status_code == 404 and r.json()["code"] == "ALLOCATION_NOT_FOUND"

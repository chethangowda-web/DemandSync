"""Read-only operational views behind the DSO Control Centre: summary, fleet, deliveries, tracking and
the closure gate.

These are additive views over Phase 2's own tables. What matters here is that they are genuinely
read-only (calling them never advances a cycle or writes a row), that they are scoped to this workflow's
data rather than the seeded dataset's synthetic history, and that they report absent data as null
instead of inventing a figure.
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

FPS_ID = "FPS-0244"
VIEWS = ["summary", "fleet", "deliveries", "tracking", "closure-checks"]


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


def beneficiary_headers() -> dict:
    otp = client.post("/api/v1/auth/beneficiary/request-otp",
                      json={"ration_card_id": "RC2023100000", "registered_mobile": "9000060000"}).json()["dev_otp"]
    tok = client.post("/api/v1/auth/beneficiary/verify-otp",
                      json={"ration_card_id": "RC2023100000", "otp": otp}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def fresh_db(officers):
    if not ADMIN_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    name = "ovw_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = swap_database(ADMIN_URL, name)
    migrate(url)
    assert import_dataset(url, activate=True, imported_by="pytest-overview")["status"] == "ACTIVE"
    with psycopg.connect(url) as c, c.transaction():
        set_password(c, officers["DISTRICT_OFFICER"][0], OFFICER_PASSWORD)
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture
def api(fresh_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db)
    return client


# ------------------------------------------------------------------ access control

@pytest.mark.parametrize("view", VIEWS)
def test_every_view_requires_an_authenticated_officer(api, view):
    assert api.get(f"/api/v1/cycles/2026-03/{view}").status_code == 401


@pytest.mark.parametrize("view", VIEWS)
def test_a_beneficiary_cannot_read_operational_views(api, view):
    assert api.get(f"/api/v1/cycles/2026-03/{view}", headers=beneficiary_headers()).status_code == 403


def test_summary_404s_for_an_unknown_cycle(api, officers):
    r = api.get("/api/v1/cycles/1999-01/summary", headers=H(officers))
    assert r.status_code == 404 and r.json()["code"] == "CYCLE_NOT_FOUND"


# ------------------------------------------------------------------ read-only guarantee

@pytest.mark.parametrize("view", VIEWS)
def test_views_never_mutate_the_cycle_or_write_rows(fresh_db, api, officers, view):
    headers = H(officers)  # log in FIRST: a successful login legitimately writes its own audit event
    before_state = q1(fresh_db, "SELECT state FROM cycles WHERE cycle='2026-03'")[0]
    before_counts = {t: q1(fresh_db, f"SELECT count(*) FROM {t}")[0]
                     for t in ("allocations", "exceptions", "dispatch_manifests", "delivery_history", "audit_events")}

    assert api.get(f"/api/v1/cycles/2026-03/{view}", headers=headers).status_code == 200

    assert q1(fresh_db, "SELECT state FROM cycles WHERE cycle='2026-03'")[0] == before_state
    for t, n in before_counts.items():
        assert q1(fresh_db, f"SELECT count(*) FROM {t}")[0] == n, f"{view} wrote to {t}"


# ------------------------------------------------------------------ the figures are real

def test_summary_reports_real_intent_and_honest_nulls_before_a_forecast_runs(fresh_db, api, officers):
    r = api.get("/api/v1/cycles/2026-03/summary", headers=H(officers))
    assert r.status_code == 200, r.text
    s = r.json()

    db_intent = q1(fresh_db, "SELECT count(*), COALESCE(sum(total_quantity_kg),0) FROM intent_signals WHERE cycle='2026-03' AND status='SUBMITTED'")
    assert s["intent"]["submissions"] == db_intent[0]
    assert float(s["intent"]["kg"]) == float(db_intent[1])

    # the dataset seeds demand_forecast for every cycle, so forecast figures are present and real
    db_forecast = q1(fresh_db, "SELECT COALESCE(sum(forecast_demand_kg),0) FROM demand_forecast WHERE cycle='2026-03'")
    assert float(s["forecast"]["kg"]) == float(db_forecast[0])

    # nothing has been locked or allocated yet on a fresh cycle -- reported as such, not as zero-with-confidence
    assert s["demand_lock"]["locked"] is False and s["demand_lock"]["sha256_hash"] is None
    assert s["state"] == "OPEN"


def test_summary_tracks_the_cycle_through_lock_and_allocation(fresh_db, api, officers):
    api.post("/api/v1/cycles/2026-03/choice-window/close", headers=H(officers))
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))

    s = api.get("/api/v1/cycles/2026-03/summary", headers=H(officers)).json()
    assert s["state"] == "ALLOCATED"
    assert s["demand_lock"]["locked"] is True and len(s["demand_lock"]["sha256_hash"]) == 64

    db = q1(fresh_db, "SELECT count(*), COALESCE(sum(allocated_kg),0), count(*) FILTER (WHERE status='BLOCKED') FROM allocations WHERE cycle='2026-03'")
    assert s["allocation"]["rows"] == db[0]
    assert float(s["allocation"]["allocated_kg"]) == float(db[1])
    assert s["allocation"]["blocked"] == db[2]

    # exception counts are scoped to this workflow's own gates, not the dataset's historical records
    live_open = q1(fresh_db, """SELECT count(*) FROM exceptions WHERE cycle='2026-03' AND status='OPEN'
                                AND entity_type IN ('ALLOCATION','ROUTING','CLOSURE')""")[0]
    assert s["exceptions"]["open_total"] == live_open
    all_open = q1(fresh_db, "SELECT count(*) FROM exceptions WHERE cycle='2026-03' AND status='OPEN'")[0]
    assert all_open > live_open, "the dataset should have unrelated historical exceptions that must NOT be counted"


def test_fleet_reports_real_vehicles_and_this_cycles_assignments(fresh_db, api, officers):
    r = api.get("/api/v1/cycles/2026-03/fleet", headers=H(officers))
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["totals"]["fleet_size"] == q1(fresh_db, "SELECT count(*) FROM vehicles")[0]
    assert f["totals"]["available"] == q1(fresh_db, "SELECT count(*) FROM vehicles WHERE current_status='AVAILABLE'")[0]
    assert f["totals"]["assigned_this_cycle"] == 0  # nothing routed yet
    assert all(v["manifest_id"] is None for v in f["vehicles"])


def test_deliveries_and_tracking_are_empty_before_dispatch_not_fabricated(api, officers):
    d = api.get("/api/v1/cycles/2026-03/deliveries", headers=H(officers)).json()
    assert d["deliveries"] == []
    t = api.get("/api/v1/cycles/2026-03/tracking", headers=H(officers)).json()
    assert t["planned_routes"] == [] and t["telemetry"] == []


def test_closure_checks_are_readable_before_reconcile_and_report_failures(api, officers):
    r = api.get("/api/v1/cycles/2026-03/closure-checks", headers=H(officers))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passed"] is False  # nothing delivered on a fresh cycle
    assert body["checks"]["ALL_MANIFESTS_DELIVERED"] is False
    assert len(body["checks"]) == 7


def test_fleet_and_tracking_reflect_a_real_optimised_cycle(fresh_db, api, officers):
    api.post("/api/v1/cycles/2026-03/choice-window/close", headers=H(officers))
    api.post("/api/v1/cycles/2026-03/allocate", headers=H(officers))
    assert api.post("/api/v1/cycles/2026-03/optimize", headers=H(officers)).status_code == 200

    f = api.get("/api/v1/cycles/2026-03/fleet", headers=H(officers)).json()
    assigned = [v for v in f["vehicles"] if v["manifest_id"]]
    assert assigned, "optimisation should have assigned vehicles"
    assert f["totals"]["assigned_this_cycle"] == len(assigned)
    for v in assigned:
        assert v["manifest_id"].startswith("MFO-")
        assert 0 < v["utilisation_pct"] <= 100, "a vehicle can never be loaded beyond its own capacity"

    t = api.get("/api/v1/cycles/2026-03/tracking", headers=H(officers)).json()
    assert t["planned_routes"], "routes exist once optimised"
    assert t["telemetry"] == [], "no telemetry until dispatch -- must not be invented from the planned route"
    seqs = [s["stop_sequence"] for s in t["planned_routes"] if s["manifest_id"] == t["planned_routes"][0]["manifest_id"]]
    assert seqs == sorted(seqs)

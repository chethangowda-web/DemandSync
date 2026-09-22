"""Phase 2 Slice 1: real demand aggregation, XGBoost forecast, and the demand lock.

Acceptance slice this proves: beneficiary submits intent -> DSO sees it in real aggregation ->
forecast is generated (or honestly falls back when history is short) -> demand is locked, immutably,
with a SHA256 seal and an audit trail. Downstream (constraints/allocation/optimize/manifest) is Slice 2+.
"""
import hashlib
import json
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
BEN_RC, BEN_MOBILE = "RC2023100000", "9000060000"  # BEN-000001, FPS-0244


def q(authdb, sql, params=()):
    with psycopg.connect(authdb, autocommit=True) as c:
        cur = c.execute(sql, params)
        return cur.fetchall() if cur.description else None


def q1(authdb, sql, params=()):
    r = q(authdb, sql, params)
    return r[0] if r else None


def dso_token(officers) -> str:
    oid = officers["DISTRICT_OFFICER"][0]
    return client.post("/api/v1/auth/officer/login", json={"officer_id": oid, "password": OFFICER_PASSWORD}).json()["access_token"]


def H(officers) -> dict:
    return {"Authorization": f"Bearer {dso_token(officers)}"}


def beneficiary_token() -> str:
    otp = client.post("/api/v1/auth/beneficiary/request-otp", json={"ration_card_id": BEN_RC, "registered_mobile": BEN_MOBILE}).json()["dev_otp"]
    return client.post("/api/v1/auth/beneficiary/verify-otp", json={"ration_card_id": BEN_RC, "otp": otp}).json()["access_token"]


def submit_intent(rice=4, wheat=7) -> dict:
    h = {"Authorization": f"Bearer {beneficiary_token()}"}
    r = client.post("/api/v1/preferences", headers=h, json={"fps_id": "FPS-0244", "rice_quantity_kg": rice, "wheat_quantity_kg": wheat, "collection_mode": "SELF"})
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ RBAC

# /cycles and /cycles/{cycle} need only VIEW_CYCLE (FPS_OWNER has it); the demand/forecast views need VIEW_DEMAND
# (FPS_OWNER does not) per backend/core/rbac.py.
ENDPOINTS_VIEW_CYCLE = ["/api/v1/cycles", "/api/v1/cycles/2026-03"]
ENDPOINTS_VIEW_DEMAND = ["/api/v1/cycles/2026-03/demand", "/api/v1/ai/forecast?cycle=2026-03&fps_id=FPS-0001&commodity=RICE"]
ENDPOINTS_POST = ["/api/v1/cycles/2026-03/forecast", "/api/v1/cycles/2026-03/choice-window/close"]


def _fps_owner_token(officers) -> str:
    return client.post("/api/v1/auth/officer/login", json={"officer_id": officers["FPS_OWNER"][0], "password": OFFICER_PASSWORD}).json()["access_token"]


@pytest.mark.parametrize("path", ENDPOINTS_VIEW_CYCLE)
def test_view_cycle_endpoints_require_auth_but_allow_any_officer_with_view_cycle(path, officers):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": f"Bearer {_fps_owner_token(officers)}"}).status_code == 200


@pytest.mark.parametrize("path", ENDPOINTS_VIEW_DEMAND)
def test_demand_endpoints_require_view_demand_permission(path, officers):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": f"Bearer {_fps_owner_token(officers)}"}).status_code == 403  # FPS_OWNER lacks VIEW_DEMAND


@pytest.mark.parametrize("path", ENDPOINTS_POST)
def test_write_endpoints_require_manage_cycle_permission(path, officers):
    assert client.post(path).status_code == 401
    auditor = client.post("/api/v1/auth/officer/login", json={"officer_id": officers["AUDITOR"][0], "password": OFFICER_PASSWORD}).json()["access_token"]
    r = client.post(path, headers={"Authorization": f"Bearer {auditor}"})
    assert r.status_code == 403  # AUDITOR can view demand but not manage the cycle
    ben = client.post(path, headers={"Authorization": f"Bearer {beneficiary_token()}"})
    assert ben.status_code == 403


def test_dso_can_read_and_write(officers):
    h = H(officers)
    assert client.get("/api/v1/cycles", headers=h).status_code == 200
    assert client.post("/api/v1/cycles/2026-03/forecast", headers=h).status_code == 200


# ------------------------------------------------------------------ aggregation is real

def test_intent_aggregation_reflects_a_real_submission(authdb, officers):
    h = H(officers)
    before = client.get("/api/v1/cycles/2026-03/demand", headers=h).json()
    row_before = next((r for r in before["rows"] if r["fps_id"] == "FPS-0244" and r["commodity"] == "RICE"), None)
    kg_before = row_before["intent_demand_kg"] if row_before else 0
    receipt = submit_intent(rice=4, wheat=7)
    after = client.get("/api/v1/cycles/2026-03/demand", headers=h).json()
    row_after = next(r for r in after["rows"] if r["fps_id"] == "FPS-0244" and r["commodity"] == "RICE")
    assert row_after["intent_demand_kg"] == kg_before + 4
    assert row_after["intent_count"] >= 1
    wheat_after = next(r for r in after["rows"] if r["fps_id"] == "FPS-0244" and r["commodity"] == "WHEAT")
    assert wheat_after["intent_demand_kg"] >= 7
    participation = after["participation"]
    assert participation["submitted"] >= 1 and 0 <= participation["participation_pct"] <= 100
    assert q1(authdb, "SELECT beneficiary_id FROM intent_signals WHERE intent_id = %s", (receipt["reference"],))[0] == "BEN-000001"


def test_baseline_matches_a_manual_average_of_the_last_three_cycles(authdb, officers):
    manual = q1(authdb, """SELECT round(avg(demand_kg), 1) AS kg, count(*) AS n FROM (
                              SELECT demand_kg FROM historical_demand WHERE fps_id = 'FPS-0001' AND commodity = 'RICE'
                              AND cycle < '2026-03' ORDER BY cycle DESC LIMIT 3) x""")
    rows_ = client.get("/api/v1/cycles/2026-03/demand", headers=H(officers)).json()["rows"]
    row = next(r for r in rows_ if r["fps_id"] == "FPS-0001" and r["commodity"] == "RICE")
    assert row["baseline_demand_kg"] == float(manual[0]) and row["baseline_cycles_used"] == manual[1] == 3


# ------------------------------------------------------------------ forecast

def test_forecast_run_writes_demand_forecast_and_is_idempotent(authdb, officers):
    h = H(officers)
    r1 = client.post("/api/v1/cycles/2026-03/forecast", headers=h)
    assert r1.status_code == 200
    body = r1.json()
    assert body["fps_commodity_pairs"] == 1200 and body["model_version"] == "xgb-v1.0"  # 600 fps x 2 commodities
    count1 = q1(authdb, "SELECT count(*) FROM demand_forecast WHERE cycle = '2026-03'")[0]
    assert count1 == 1200
    r2 = client.post("/api/v1/cycles/2026-03/forecast", headers=h)  # re-running upserts, never duplicates
    assert r2.status_code == 200
    assert q1(authdb, "SELECT count(*) FROM demand_forecast WHERE cycle = '2026-03'")[0] == 1200


def test_forecast_appears_in_the_demand_view_after_generation(authdb, officers):
    # the seeded dataset already ships synthetic forecast rows for every cycle (its own generator's numbers);
    # POSTing /forecast must overwrite them with our own model's live output, not merely add to what's there.
    h = H(officers)
    pre = client.get("/api/v1/cycles/2026-03/demand", headers=h).json()
    assert pre["forecast_generated"] is True  # seeded data is already there
    client.post("/api/v1/cycles/2026-03/forecast", headers=h)
    post = client.get("/api/v1/cycles/2026-03/demand", headers=h).json()
    row = next(r for r in post["rows"] if r["fps_id"] == "FPS-0001" and r["commodity"] == "RICE")
    assert isinstance(row["forecast_demand_kg"], (int, float))
    assert "intent_minus_forecast_kg" in row and "forecast_minus_baseline_kg" in row  # explicitly labelled diffs
    assert q1(authdb, "SELECT count(*) FROM demand_forecast WHERE fps_id = 'FPS-0001' AND cycle = '2026-03' AND commodity = 'RICE'")[0] == 1
    stored = q1(authdb, "SELECT forecast_demand_kg, model_version FROM demand_forecast WHERE fps_id = 'FPS-0001' AND cycle = '2026-03' AND commodity = 'RICE'")
    assert stored[1] == "xgb-v1.0" and float(stored[0]) == row["forecast_demand_kg"]


def test_ai_forecast_envelope_has_every_mandatory_field_and_is_logged(authdb, officers):
    r = client.get("/api/v1/ai/forecast?cycle=2026-03&fps_id=FPS-0001&commodity=RICE", headers=H(officers))
    assert r.status_code == 200
    e = r.json()
    for field in ("prediction", "confidence", "reason", "supporting_data", "model_version", "generated_at"):
        assert field in e and e[field] not in (None, ""), field
    assert 0 <= e["confidence"] <= 100
    assert e["supporting_data"]["fps_id"] == "FPS-0001" and e["supporting_data"]["commodity"] == "RICE"
    logged = q1(authdb, "SELECT service, entity_id, model_version FROM ai_predictions WHERE service = 'demand_forecast' "
                        "AND entity_type = 'FPS' AND entity_id = 'FPS-0001' ORDER BY generated_at DESC LIMIT 1")
    assert logged == ("demand_forecast", "FPS-0001", "xgb-v1.0")


def test_unknown_fps_or_commodity_or_cycle_is_a_clean_404(officers):
    h = H(officers)
    assert client.get("/api/v1/ai/forecast?cycle=2026-03&fps_id=FPS-NOPE&commodity=RICE", headers=h).status_code == 404
    assert client.get("/api/v1/ai/forecast?cycle=2026-03&fps_id=FPS-0001&commodity=SUGAR", headers=h).status_code == 422
    assert client.get("/api/v1/cycles/2099-01/demand", headers=h).status_code == 404
    assert client.post("/api/v1/cycles/2099-01/forecast", headers=h).status_code == 404


def test_insufficient_history_falls_back_to_baseline_never_a_fabricated_prediction(authdb, officers):
    with psycopg.connect(authdb) as _c:
        cols = [d.name for d in _c.execute("SELECT * FROM historical_demand LIMIT 0").description]
    saved = q(authdb, "SELECT * FROM historical_demand WHERE fps_id = 'FPS-0002' AND commodity = 'RICE' ORDER BY cycle")
    keep = saved[-2:]  # leave exactly 2 cycles of history: below the MIN_HISTORY_CYCLES=3 fallback threshold
    try:
        q(authdb, "DELETE FROM historical_demand WHERE fps_id = 'FPS-0002' AND commodity = 'RICE'")
        with psycopg.connect(authdb, autocommit=True) as conn:
            for r in keep:
                conn.execute(f"INSERT INTO historical_demand ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", list(r))
        h = H(officers)
        client.post("/api/v1/cycles/2026-03/forecast", headers=h)
        row = next(r for r in client.get("/api/v1/cycles/2026-03/demand", headers=h).json()["rows"]
                   if r["fps_id"] == "FPS-0002" and r["commodity"] == "RICE")
        assert row["forecast_demand_kg"] == row["baseline_demand_kg"] and row["baseline_cycles_used"] < 3
        e = client.get("/api/v1/ai/forecast?cycle=2026-03&fps_id=FPS-0002&commodity=RICE", headers=h).json()
        assert e["confidence"] <= 30 and "insufficient history" in e["reason"].lower()
        assert e["supporting_data"]["fallback"] is True
    finally:
        with psycopg.connect(authdb, autocommit=True) as conn:
            conn.execute("DELETE FROM historical_demand WHERE fps_id = 'FPS-0002' AND commodity = 'RICE'")
            for r in saved:
                conn.execute(f"INSERT INTO historical_demand ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", list(r))


# ------------------------------------------------------------------ demand lock
#
# demand_locks is immutable (migration 0002): once a cycle is locked, that row can never be updated or
# deleted, even for test cleanup. So every test that actually performs a lock gets its own disposable
# database (like tests/test_db.py's db_url fixture) rather than sharing the session-scoped `authdb`,
# which every other test in this file uses and must stay lockable.

@pytest.fixture
def fresh_db(officers):
    if not ADMIN_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    name = "lock_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = swap_database(ADMIN_URL, name)
    migrate(url)
    assert import_dataset(url, activate=True, imported_by="pytest-lock")["status"] == "ACTIVE"
    with psycopg.connect(url) as c, c.transaction():
        set_password(c, officers["DISTRICT_OFFICER"][0], OFFICER_PASSWORD)
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture
def locked_client(fresh_db, monkeypatch):
    """The API client wired to `fresh_db` for the duration of one test."""
    monkeypatch.setenv("DATABASE_URL", fresh_db)
    return client


def test_choice_window_close_locks_immutably_and_audits(fresh_db, locked_client, officers):
    h = H(officers)
    r = locked_client.post("/api/v1/cycles/2026-03/choice-window/close", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "LOCKED" and len(body["sha256_hash"]) == 64  # 2026-03 has no seeded intent; 0 kg is a valid real lock

    assert q1(fresh_db, "SELECT state FROM cycles WHERE cycle = '2026-03'")[0] == "LOCKED"
    row = q1(fresh_db, "SELECT locked_by, sha256_hash, snapshot FROM demand_locks WHERE cycle = '2026-03'")
    assert row[0] == officers["DISTRICT_OFFICER"][0]
    recomputed = hashlib.sha256(json.dumps(row[2], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert recomputed == row[1] == body["sha256_hash"]

    actions = {a[0] for a in q(fresh_db, "SELECT action FROM audit_events WHERE entity_id = '2026-03' AND cycle = '2026-03'")}
    assert {"CHOICE_WINDOW_CLOSED", "DEMAND_LOCKED"} <= actions

    with pytest.raises(psycopg.errors.RestrictViolation):
        q(fresh_db, "UPDATE demand_locks SET locked_by = 'someone-else' WHERE cycle = '2026-03'")
    with pytest.raises(psycopg.errors.RestrictViolation):
        q(fresh_db, "DELETE FROM demand_locks WHERE cycle = '2026-03'")


def test_locking_twice_is_rejected_and_does_not_change_the_seal(fresh_db, locked_client, officers):
    h = H(officers)
    first = locked_client.post("/api/v1/cycles/2026-03/choice-window/close", headers=h).json()
    again = locked_client.post("/api/v1/cycles/2026-03/choice-window/close", headers=h)
    assert again.status_code == 409 and again.json()["code"] == "CYCLE_NOT_OPEN"
    assert q1(fresh_db, "SELECT sha256_hash FROM demand_locks WHERE cycle = '2026-03'")[0] == first["sha256_hash"]


def test_locking_a_cycle_that_is_not_open_is_rejected(officers):
    r = client.post("/api/v1/cycles/2026-02/choice-window/close", headers=H(officers))  # 2026-02 is DELIVERING
    assert r.status_code == 409 and r.json()["code"] == "CYCLE_NOT_OPEN" and r.json()["params"]["state"] == "DELIVERING"


def test_demand_lock_endpoint_before_and_after_locking(fresh_db, locked_client, officers):
    h = H(officers)
    assert locked_client.get("/api/v1/cycles/2026-03/demand-lock", headers=h).status_code == 404
    locked_client.post("/api/v1/cycles/2026-03/choice-window/close", headers=h)
    r = locked_client.get("/api/v1/cycles/2026-03/demand-lock", headers=h)
    assert r.status_code == 200 and r.json()["hash_verified"] is True


def test_a_submission_after_lock_does_not_change_the_sealed_snapshot(fresh_db, locked_client, officers):
    h = H(officers)
    locked = locked_client.post("/api/v1/cycles/2026-03/choice-window/close", headers=h).json()
    # the choice window is now closed; Phase 1's own guard blocks new submissions for this cycle
    other = locked_client.post("/api/v1/preferences", headers={"Authorization": f"Bearer {beneficiary_token()}"},
                               json={"fps_id": "FPS-0244", "rice_quantity_kg": 1, "wheat_quantity_kg": 0, "collection_mode": "SELF"})
    assert other.status_code == 409 and other.json()["code"] == "CHOICE_WINDOW_CLOSED"
    assert q1(fresh_db, "SELECT sha256_hash FROM demand_locks WHERE cycle = '2026-03'")[0] == locked["sha256_hash"]

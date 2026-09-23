"""Phase 8 — AI + Cross-Portal Intelligence tests.

Proves the advisory intelligence layer against REAL persisted records:
forecast reuse, explainable anomalies, RBAC scoping, hallucination guards,
action safety (AI writes nothing authoritative), stale-data honesty, model
versioning, auditability, failure fallback, and cross-portal consistency.

Read-only except advisory ai_predictions rows + audit events (append-only;
never deleted, so the hash chain stays intact).
"""
import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from conftest import OFFICER_PASSWORD

pytestmark = pytest.mark.usefixtures("authdb")
client = TestClient(app)
BEN_RC, BEN_MOBILE = "RC2023100000", "9000060000"  # BEN-000001, FPS-0244
CYCLE = "2026-02"  # DELIVERING seed cycle with intent + allocations + history


def q(authdb, sql, params=()):
    with psycopg.connect(authdb, autocommit=True) as c:
        cur = c.execute(sql, params)
        return cur.fetchall() if cur.description else None


def login(officers, role) -> str:
    oid = officers[role][0]
    r = client.post("/api/v1/auth/officer/login", json={"officer_id": oid, "password": OFFICER_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def H(officers, role) -> dict:
    return {"Authorization": f"Bearer {login(officers, role)}"}


def beneficiary_headers() -> dict:
    otp = client.post("/api/v1/auth/beneficiary/request-otp",
                      json={"ration_card_id": BEN_RC, "registered_mobile": BEN_MOBILE}).json()["dev_otp"]
    tok = client.post("/api/v1/auth/beneficiary/verify-otp",
                      json={"ration_card_id": BEN_RC, "otp": otp}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def snapshot(authdb):
    tables = ["allocations", "dispatch_manifests", "dispatch_manifest_items", "inventory",
              "intent_signals", "cycles", "epos_transactions", "inspections"]
    out = {}
    for t in tables:
        if t == "cycles":
            out[t] = q(authdb, "SELECT cycle, state FROM cycles ORDER BY cycle")
        else:
            out[t] = q(authdb, f"SELECT count(*) AS n FROM {t}")[0][0]
    return out


# ------------------------------------------------------------------ A. forecast reuse

def test_demand_signals_reuse_persisted_forecast(officers, authdb):
    r = client.get(f"/api/v1/intelligence/dso/demand?cycle={CYCLE}", headers=H(officers, "DISTRICT_OFFICER"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"] == "xgb-v1.0"
    persisted = {f"{x[0]}:{x[1]}": x for x in
                 q(authdb, "SELECT fps_id, commodity, forecast_demand_kg, model_version FROM demand_forecast WHERE cycle = %s", (CYCLE,))}
    assert persisted, "seed must carry persisted forecasts"
    for s in body["signals"][:50]:
        p = persisted.get(f"{s['fps_id']}:{s['commodity']}")
        assert p is not None
        assert s["forecast_kg"] == float(p[2]), "signal must equal the persisted forecast"
        assert s["model_version"] == p[3]
        assert s["confidence"] is None, "persisted rows carry no confidence by design"
        if s["forecast_kg"] is not None and s["intent_kg"] is not None:
            assert s["intent_minus_forecast_kg"] == round(s["intent_kg"] - s["forecast_kg"], 1)


# ------------------------------------------------------------------ B. anomaly explainability

def test_anomalies_are_evidence_backed(officers):
    r = client.get(f"/api/v1/intelligence/dso/anomalies?cycle={CYCLE}", headers=H(officers, "DISTRICT_OFFICER"))
    assert r.status_code == 200, r.text
    for a in r.json()["anomalies"]:
        for key in ("anomaly_id", "type", "severity", "entity_type", "entity_id", "metric",
                    "observed_value", "expected_value", "difference", "detection_method",
                    "evidence", "detected_at"):
            assert key in a, f"missing {key}"
        assert a["detection_method"], "every signal must state what triggered it"
        assert "AI detected this" not in a["detection_method"]
        assert a["evidence"], "every anomaly must cite records"
        if a["type"] == "DEMAND_ZSCORE" and a["observed_value"] is not None and a["expected_value"] is not None:
            assert a["difference"] == round(a["observed_value"] - a["expected_value"], 3)


def test_normal_demand_does_not_trigger(officers, authdb):
    # FPS-0001/RICE per-capita intent (~12.3) sits inside its history band (~13.5±1.3):
    # it must not appear as an anomaly while genuinely deviating shops do surface.
    r = client.get(f"/api/v1/intelligence/dso/anomalies?cycle={CYCLE}", headers=H(officers, "DISTRICT_OFFICER"))
    ids = {(a["entity_id"], a.get("commodity")) for a in r.json()["anomalies"] if a["type"] == "DEMAND_ZSCORE"}
    assert ("FPS-0001", "RICE") not in ids


# ------------------------------------------------------------------ C. grounding

def test_allocation_explanation_uses_db_values(officers, authdb):
    row = q(authdb, "SELECT requested_kg, allocated_kg, status FROM allocations WHERE cycle=%s AND fps_id='FPS-0001' AND commodity='RICE'", (CYCLE,))[0]
    r = client.get(f"/api/v1/intelligence/dso/allocation-explanation?cycle={CYCLE}&fps_id=FPS-0001&commodity=RICE",
                   headers=H(officers, "DISTRICT_OFFICER"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["detail"]["requested_kg"] == float(row[0])
    assert body["detail"]["allocated_kg"] == float(row[1])
    assert body["detail"]["status"] == row[2]
    assert "FPS-0001" in body["answer"] and "13339" in body["answer"]
    assert body["advisory"] is True


def test_grounding_unknown_fps(officers):
    r = client.get(f"/api/v1/intelligence/dso/allocation-explanation?cycle={CYCLE}&fps_id=FPS-9999&commodity=RICE",
                   headers=H(officers, "DISTRICT_OFFICER"))
    assert r.status_code == 200, r.text
    assert r.json()["answer"] == "DATA NOT AVAILABLE"


# ------------------------------------------------------------------ D. RBAC (server-side scoping)

def test_beneficiary_cannot_reach_officer_intel():
    h = beneficiary_headers()
    for path in ("/api/v1/intelligence/dso/summary", "/api/v1/intelligence/auditor/summary",
                 "/api/v1/intelligence/admin/summary", "/api/v1/intelligence/inspector/summary"):
        r = client.get(path, headers=h)
        assert r.status_code == 403, (path, r.text)


def test_beneficiary_summary_is_own_data_only(authdb):
    h = beneficiary_headers()
    r = client.get("/api/v1/intelligence/beneficiary/me/summary", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    ben = q(authdb, "SELECT beneficiary_id FROM beneficiaries WHERE ration_card_id = %s", (BEN_RC,))[0][0]
    assert body["beneficiary_id"] == ben
    for card in body["insights"]:
        assert "BEN-" not in card["summary"] or ben in card["summary"] or "your" in card["summary"].lower()


def test_fps_owner_cannot_query_other_fps(officers, authdb):
    h = H(officers, "FPS_OWNER")
    me = client.get("/api/v1/intelligence/fps/me/summary", headers=h)
    assert me.status_code == 200, me.text
    own = me.json()["fps_id"]
    other = q(authdb, "SELECT fps_id FROM fps WHERE fps_id != %s LIMIT 1", (own,))[0][0]
    r = client.post("/api/v1/intelligence/ask", headers=h, json={"question": f"Why is {other} receiving less?"})
    assert r.status_code == 403, r.text


def test_role_summaries_require_permission(officers):
    # FPS owner has no VIEW_DEMAND / VIEW_AUDIT / VIEW_SYSTEM_HEALTH
    h = H(officers, "FPS_OWNER")
    assert client.get("/api/v1/intelligence/dso/summary", headers=h).status_code == 403
    assert client.get("/api/v1/intelligence/auditor/summary", headers=h).status_code == 403
    assert client.get("/api/v1/intelligence/admin/summary", headers=h).status_code == 403


# ------------------------------------------------------------------ E. hallucination guards

def test_ask_about_nonexistent_fps(officers):
    r = client.post("/api/v1/intelligence/ask", headers=H(officers, "DISTRICT_OFFICER"),
                    json={"question": "Why is FPS-9999 receiving less than requested?", "cycle": CYCLE})
    assert r.status_code == 200, r.text
    assert "DATA NOT AVAILABLE" in r.json()["answer"]
    assert r.json()["advisory"] is True


def test_ask_unknown_cycle(officers):
    r = client.post("/api/v1/intelligence/ask", headers=H(officers, "DISTRICT_OFFICER"),
                    json={"question": "Which FPS needs attention?", "cycle": "2099-99"})
    assert r.status_code == 404


# ------------------------------------------------------------------ F. action safety: AI changes nothing authoritative

def test_intelligence_is_read_only(officers, authdb):
    before = snapshot(authdb)
    h = H(officers, "DISTRICT_OFFICER")
    client.get(f"/api/v1/intelligence/dso/summary?cycle={CYCLE}", headers=h)
    client.get(f"/api/v1/intelligence/dso/risks?cycle={CYCLE}", headers=h)
    client.get(f"/api/v1/intelligence/dso/anomalies?cycle={CYCLE}", headers=h)
    client.post("/api/v1/intelligence/ask", headers=h,
                json={"question": "Which FPS needs attention?", "cycle": CYCLE})
    client.get("/api/v1/intelligence/auditor/summary?cycle=" + CYCLE, headers=h)
    client.get("/api/v1/intelligence/admin/summary", headers=H(officers, "ADMIN"))
    assert snapshot(authdb) == before


# ------------------------------------------------------------------ G/H. stale + versions

def test_model_and_dataset_versions_visible(officers):
    r = client.get(f"/api/v1/intelligence/dso/demand?cycle={CYCLE}", headers=H(officers, "DISTRICT_OFFICER"))
    sigs = [s for s in r.json()["signals"] if s["forecast_kg"] is not None]
    assert sigs
    assert all(s["model_version"] == "xgb-v1.0" for s in sigs[:20])
    assert all(s["dataset_version"] for s in sigs[:20])
    ask = client.post("/api/v1/intelligence/ask", headers=H(officers, "DISTRICT_OFFICER"),
                      json={"question": "Which FPS needs attention?", "cycle": CYCLE}).json()
    assert ask["model_version"] == "rule-intelligence-v1"


def test_stale_forecast_flagged(officers, authdb):
    # Order-independent honesty check: the staleness verdict must match the
    # actual newest forecast timestamp — stale when old, silent when fresh.
    from datetime import datetime, timezone
    r = client.get("/api/v1/intelligence/admin/summary", headers=H(officers, "ADMIN"))
    assert r.status_code == 200, r.text
    titles = [i["title"] for i in r.json()["insights"]]
    newest = q(authdb, "SELECT max(prediction_generated_at) AS ts FROM demand_forecast")[0][0]
    assert newest is not None
    age_days = (datetime.now(timezone.utc) - newest).total_seconds() / 86400
    if age_days > 30:
        assert any("stale" in t.lower() for t in titles), titles
    else:
        assert not any("stale" in t.lower() for t in titles), \
            f"fresh forecast ({age_days:.1f}d old) must not be called stale: {titles}"


# ------------------------------------------------------------------ I. auditability

def test_insight_generation_is_audited(officers, authdb):
    before = q(authdb, "SELECT count(*) AS n FROM audit_events WHERE action='AI_INSIGHT_GENERATED'")[0][0]
    client.get(f"/api/v1/intelligence/dso/summary?cycle={CYCLE}", headers=H(officers, "DISTRICT_OFFICER"))
    after = q(authdb, "SELECT count(*) AS n FROM audit_events WHERE action='AI_INSIGHT_GENERATED'")[0][0]
    assert after == before + 1
    row = q(authdb, "SELECT actor_role, entity_id FROM audit_events WHERE action='AI_INSIGHT_GENERATED' ORDER BY timestamp DESC LIMIT 1")[0]
    assert row[1] == CYCLE


# ------------------------------------------------------------------ J. failure fallback: no fake intelligence

def test_unknown_cycle_returns_404_not_fake(officers):
    for path in ("/api/v1/intelligence/dso/summary?cycle=2099-01",
                 "/api/v1/intelligence/dso/anomalies?cycle=2099-01",
                 "/api/v1/intelligence/dso/risks?cycle=2099-01"):
        r = client.get(path, headers=H(officers, "DISTRICT_OFFICER"))
        assert r.status_code == 404, (path, r.text)


# ------------------------------------------------------------------ K. cross-portal consistency + e2e proof hooks

def test_cross_portal_consistency(officers):
    h = H(officers, "DISTRICT_OFFICER")
    dso = client.get(f"/api/v1/intelligence/dso/summary?cycle={CYCLE}", headers=h).json()
    brief = client.get(f"/api/v1/intelligence/dso/brief?cycle={CYCLE}", headers=h).json()
    assert dso["brief"]["counts"] == brief["counts"], "summary and brief must count the same records"
    aud = client.get(f"/api/v1/intelligence/auditor/summary?cycle={CYCLE}",
                     headers=H(officers, "AUDITOR")).json()
    assert aud["cycle"] == CYCLE
    assert aud["closure_explanation"]["advisory"] is True
    insp = client.get(f"/api/v1/intelligence/inspector/summary?cycle={CYCLE}",
                      headers=H(officers, "FIELD_FOOD_INSPECTOR")).json()
    assert insp["cycle"] == CYCLE
    assert "Prioritisation only" in insp["note"]


def test_dispatch_risk_cites_only_live_gates(officers, authdb):
    """Seeded historical MANIFEST exceptions must never appear as dispatch blockers."""
    r = client.get(f"/api/v1/intelligence/dso/risks?cycle={CYCLE}&kind=DISPATCH_RISK",
                   headers=H(officers, "DISTRICT_OFFICER"))
    assert r.status_code == 200, r.text
    for risk in r.json()["risks"]:
        for e in risk["evidence"]:
            assert e["record"] != "exceptions" or "MANIFEST" not in str(e.get("field", "")), risk


def test_geodesic_honesty(officers):
    r = client.get(f"/api/v1/intelligence/dso/risks?cycle={CYCLE}&kind=ROUTE_FLEET_RISK",
                   headers=H(officers, "DISTRICT_OFFICER"))
    for risk in r.json()["risks"]:
        assert "ROAD DISTANCE" not in risk["summary"].upper() or "NOT ROAD" in risk["summary"].upper()
        assert "ETA" not in risk["summary"] or "geodesic" in risk["summary"].lower()

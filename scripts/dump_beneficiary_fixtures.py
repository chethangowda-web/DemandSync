"""Record real API responses from a seeded dev database as Flutter test fixtures.

  DATABASE_URL=postgresql://... OTP_PROVIDER=dev python scripts/dump_beneficiary_fixtures.py

The Flutter tests parse these files, so the app's models are checked against what the backend actually returns
(including error bodies), not against JSON written by hand. Temporary state changes (crafting an in-transit truck,
closing cycles) are reverted, and records created here are deleted, before the script exits.
"""
import json
import os
import sys
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.main import app  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "beneficiary-mobile" / "test" / "fixtures"
URL = os.environ["DATABASE_URL"]
client = TestClient(app)
_tokens: dict[str, str] = {}


def sql(query, params=()):
    with psycopg.connect(URL, autocommit=True) as c:
        cur = c.execute(query, params)
        return cur.fetchall() if cur.description else None


def token(beneficiary_id):
    if beneficiary_id not in _tokens:
        rc, mobile = sql("SELECT ration_card_id, registered_mobile FROM beneficiaries WHERE beneficiary_id = %s", (beneficiary_id,))[0]
        sql("DELETE FROM otp_challenges WHERE ration_card_id = %s", (rc,))
        otp = client.post("/api/v1/auth/beneficiary/request-otp", json={"ration_card_id": rc, "registered_mobile": mobile}).json()
        _tokens[beneficiary_id] = client.post("/api/v1/auth/beneficiary/verify-otp", json={"ration_card_id": rc, "otp": otp["dev_otp"]}).json()["access_token"]
        save("otp_request", otp | {"dev_otp": "123456"})  # the code itself is random; the shape is what matters
    return {"Authorization": f"Bearer {_tokens[beneficiary_id]}"}


def save(name, body):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(body, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print("wrote", name)


def get(name, path, ben="BEN-000001"):
    r = client.get(path, headers=token(ben))
    assert r.status_code < 300, (name, r.status_code, r.text)
    save(name, r.json())
    return r.json()


def post(name, path, body, ben="BEN-000001", expect=None):
    r = client.post(path, headers=token(ben), json=body)
    assert (r.status_code == expect) if expect else r.status_code < 300, (name, r.status_code, r.text)
    save(name, r.json())
    return r.json()


def cleanup():
    sql("DELETE FROM intent_signals WHERE intent_id ~ '^INT-[0-9]{4}-'")
    sql("DELETE FROM grievances WHERE grievance_id ~ '^GRV-1[0-9]{5}$'")
    sql("DELETE FROM ai_predictions WHERE service = 'beneficiary_assistant'")
    sql("UPDATE cycles SET state = 'OPEN' WHERE cycle = '2026-03'")
    sql("UPDATE cycles SET state = 'DELIVERING' WHERE cycle = '2026-02'")
    sql("UPDATE cycles SET state = 'AUDITING' WHERE cycle = '2026-01'")


def in_transit(name, with_telemetry):
    if with_telemetry:
        c = sql("""SELECT m.manifest_id, m.cycle, di.fps_id FROM dispatch_manifests m JOIN dispatch_manifest_items di USING (manifest_id)
                   JOIN vehicle_telemetry t ON t.manifest_id = m.manifest_id
                   JOIN delivery_history d ON d.manifest_id = m.manifest_id AND d.fps_id = di.fps_id
                   WHERE m.cycle = '2026-02' AND t.latitude IS NOT NULL ORDER BY 1, 3 LIMIT 1""")[0]
    else:
        c = sql("""SELECT m.manifest_id, m.cycle, di.fps_id FROM dispatch_manifests m JOIN dispatch_manifest_items di USING (manifest_id)
                   WHERE NOT EXISTS (SELECT 1 FROM delivery_history d WHERE d.manifest_id = m.manifest_id)
                     AND NOT EXISTS (SELECT 1 FROM vehicle_telemetry t WHERE t.manifest_id = m.manifest_id) ORDER BY 1 LIMIT 1""")[0]
    manifest, cycle, fps = c
    ben = sql("SELECT beneficiary_id FROM beneficiaries WHERE current_fps_id = %s AND status = 'ACTIVE' ORDER BY 1 LIMIT 1", (fps,))[0][0]
    status = sql("SELECT manifest_status FROM dispatch_manifests WHERE manifest_id = %s", (manifest,))[0][0]
    state = sql("SELECT state FROM cycles WHERE cycle = %s", (cycle,))[0][0]
    deliveries = sql("SELECT * FROM delivery_history WHERE manifest_id = %s AND fps_id = %s", (manifest, fps))
    cols = [d.name for d in psycopg.connect(URL).execute("SELECT * FROM delivery_history LIMIT 0").description]
    try:
        sql("UPDATE cycles SET state = 'TRACKING' WHERE cycle = %s", (cycle,))
        sql("UPDATE dispatch_manifests SET manifest_status = 'DISPATCHED' WHERE manifest_id = %s", (manifest,))
        sql("DELETE FROM delivery_history WHERE manifest_id = %s AND fps_id = %s", (manifest, fps))
        get(name, f"/api/v1/tracking/me?cycle={cycle}", ben)
    finally:
        sql("UPDATE cycles SET state = %s WHERE cycle = %s", (state, cycle))
        sql("UPDATE dispatch_manifests SET manifest_status = %s WHERE manifest_id = %s", (status, manifest))
        for row in deliveries:
            sql(f"INSERT INTO delivery_history ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", list(row))


def main():
    cleanup()
    try:
        get("home_open", "/api/v1/beneficiaries/me/home")
        get("entitlement", "/api/v1/beneficiaries/me/entitlement")
        get("fps_eligible", "/api/v1/fps/eligible?limit=6")
        get("tracking_open", "/api/v1/tracking/me")
        get("history_collections", "/api/v1/history/me?kind=collections")
        get("history_transactions", "/api/v1/history/me?kind=transactions")
        get("history_intents", "/api/v1/history/me?kind=intents")
        txn = sql("SELECT transaction_id FROM epos_transactions WHERE beneficiary_id = 'BEN-000001' AND status = 'SUCCESS' AND commodity = 'RICE'")[0][0]
        get("digital_receipt", f"/api/v1/transactions/{txn}/receipt")
        # a beneficiary whose own shop is suspended
        b = sql("SELECT b.beneficiary_id FROM beneficiaries b JOIN fps f ON f.fps_id = b.current_fps_id WHERE f.status = 'SUSPENDED' AND b.status = 'ACTIVE' ORDER BY 1 LIMIT 1")[0][0]
        get("home_fps_suspended", "/api/v1/beneficiaries/me/home", b)
        get("fps_eligible_suspended_home", "/api/v1/fps/eligible?limit=4", b)
        # a delivered cycle
        d = sql("""SELECT i.beneficiary_id FROM intent_signals i JOIN dispatch_manifest_items di ON di.fps_id = i.fps_id
                   JOIN dispatch_manifests m ON m.manifest_id = di.manifest_id AND m.cycle = '2026-02'
                   JOIN delivery_history dh ON dh.manifest_id = m.manifest_id AND dh.fps_id = i.fps_id AND dh.status = 'VERIFIED'
                   WHERE i.cycle = '2026-02' AND i.status = 'SUBMITTED' ORDER BY 1 LIMIT 1""")[0][0]
        get("tracking_delivered", "/api/v1/tracking/me?cycle=2026-02", d)
        in_transit("tracking_in_transit_gps", True)
        in_transit("tracking_in_transit_no_gps", False)
        # errors, as the backend really sends them
        post("error_exceeds", "/api/v1/preferences", {"fps_id": "FPS-0244", "rice_quantity_kg": 50, "wheat_quantity_kg": 0, "collection_mode": "SELF"}, expect=422)
        post("error_invalid_quantity", "/api/v1/preferences", {"fps_id": "FPS-0244", "rice_quantity_kg": -1, "wheat_quantity_kg": 0, "collection_mode": "SELF"}, expect=422)
        # the happy path: submit, duplicate, receipt, cancel
        rec = post("receipt_recorded", "/api/v1/preferences", {"fps_id": "FPS-0244", "rice_quantity_kg": 4, "wheat_quantity_kg": 7, "collection_mode": "SELF"}, expect=201)
        post("error_duplicate", "/api/v1/preferences", {"fps_id": "FPS-0244", "rice_quantity_kg": 1, "wheat_quantity_kg": 0, "collection_mode": "SELF"}, expect=409)
        get("home_intent", "/api/v1/beneficiaries/me/home")
        get("tracking_intent", "/api/v1/tracking/me")
        post("assistant_cant_submit", "/api/v1/ai/assistant", {"intent": "CANT_SUBMIT", "language": "en"})
        for lang in ("en", "hi", "kn"):
            post(f"assistant_entitlement_{lang}", "/api/v1/ai/assistant", {"intent": "ENTITLEMENT", "language": lang})
        post("cancelled", f"/api/v1/preferences/{rec['reference']}/cancel", {})
        post("error_notfound", "/api/v1/preferences/INT-NOPE/cancel", {}, expect=404)
        post("grievance_suggest", "/api/v1/ai/grievance-suggest", {"description": "The biometric machine failed and my transaction did not go through"})
        post("grievance_created", "/api/v1/grievances", {"category": "TRANSACTION_FAILURE", "description": "The biometric machine failed and my transaction did not go through"}, expect=201)
        get("grievances", "/api/v1/grievances/me")
        # window closed and no active cycle
        sql("UPDATE cycles SET state = 'LOCKED' WHERE cycle = '2026-03'")
        other = sql("SELECT beneficiary_id FROM beneficiaries WHERE district = 'BENGALURU_URBAN' AND status = 'ACTIVE' AND beneficiary_id <> 'BEN-000001' AND current_fps_id IN (SELECT fps_id FROM fps WHERE status = 'ACTIVE') ORDER BY 1 LIMIT 1")[0][0]
        post("error_window_closed", "/api/v1/preferences", {"fps_id": "FPS-0244", "rice_quantity_kg": 1, "wheat_quantity_kg": 0, "collection_mode": "SELF"}, ben=other, expect=409)
        get("home_window_closed", "/api/v1/beneficiaries/me/home", other)
        sql("UPDATE cycles SET state = 'CLOSED' WHERE state <> 'CLOSED'")
        get("home_no_cycle", "/api/v1/beneficiaries/me/home")
        client.post("/api/v1/auth/logout", headers=token("BEN-000001"))
        r = client.get("/api/v1/beneficiaries/me/home", headers=token("BEN-000001"))
        save("error_unauthorized", r.json())
    finally:
        cleanup()


if __name__ == "__main__":
    main()

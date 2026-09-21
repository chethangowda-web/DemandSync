from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_dataset_manifest_loads_from_repo_data():
    r = client.get("/api/v1/datasets/manifest")
    assert r.status_code == 200
    assert r.json()["row_counts"]["beneficiaries_master.csv"] == 10000


def test_protected_route_requires_token():
    assert client.get("/api/v1/auth/me").status_code == 401


def test_beneficiary_otp_login_and_entitlement():
    rc, mobile = "RC2023100000", "9000060000"  # BEN-000001 from data/01_master
    r = client.post("/api/v1/auth/beneficiary/request-otp", json={"ration_card_id": rc, "registered_mobile": mobile})
    assert r.status_code == 200
    otp = r.json()["dev_otp"]
    r = client.post("/api/v1/auth/beneficiary/verify-otp", json={"ration_card_id": rc, "otp": otp})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=h).json()["role"] == "BENEFICIARY"
    ent = client.get("/api/v1/beneficiaries/me/entitlement", headers=h).json()
    assert ent["total_entitlement_kg"] == 35 and ent["rice_entitlement_kg"] + ent["wheat_entitlement_kg"] == 35


def test_wrong_mobile_rejected():
    r = client.post("/api/v1/auth/beneficiary/request-otp", json={"ration_card_id": "RC2023100000", "registered_mobile": "0000000000"})
    assert r.status_code == 401

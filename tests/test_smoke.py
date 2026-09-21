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

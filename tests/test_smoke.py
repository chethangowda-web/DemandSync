from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["database"] in ("not_configured", "connected", "unavailable")


def test_dataset_manifest_loads_from_repo_data():
    r = client.get("/api/v1/datasets/manifest")
    assert r.status_code == 200
    assert r.json()["row_counts"]["beneficiaries_master.csv"] == 10000


def test_protected_routes_report_missing_database_not_a_fake_answer(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert client.get("/api/v1/auth/me").status_code == 503
    assert client.get("/api/v1/system/db-status").status_code == 503


def test_officer_web_is_served_with_spa_fallback_and_no_path_traversal(tmp_path, monkeypatch):
    app_dir = tmp_path / "officer"
    (app_dir / "assets").mkdir(parents=True)
    (app_dir / "index.html").write_text("<html>SPA</html>")
    (app_dir / "assets" / "x.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    monkeypatch.setenv("OFFICER_WEB_DIR", str(app_dir))
    assert "SPA" in client.get("/officer/").text
    assert "SPA" in client.get("/officer/dso").text  # deep link -> index.html
    js = client.get("/officer/assets/x.js")
    assert js.text == "console.log(1)" and "immutable" in js.headers["cache-control"]
    for evil in ("/officer/%2e%2e/secret.txt", "/officer/..%2fsecret.txt", "/officer/assets/..%2f..%2fsecret.txt"):
        assert "TOP SECRET" not in client.get(evil).text, evil
    assert client.get("/officer", follow_redirects=False).status_code in (307, 308)


def test_officer_web_absent_is_a_clean_404(monkeypatch, tmp_path):
    from backend import web
    monkeypatch.setattr(web, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("OFFICER_WEB_DIR", raising=False)
    assert client.get("/officer/").status_code == 404

"""One-time-only first-admin credential bootstrap: /api/v1/auth/officer/bootstrap-first-admin.

Exists so a freshly deployed instance (nobody has ever logged in) can be given its first officer password
without shell access to the host. It must be impossible to use once any officer_credentials row exists,
by any means -- that's the whole safety property this file proves.
"""
import re
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.core.credentials import set_password
from backend.db.ingest import import_dataset
from backend.db.migrate import migrate
from backend.main import app
from conftest import ADMIN_URL, OFFICER_PASSWORD

client = TestClient(app)


def swap(url: str, name: str) -> str:
    return re.sub(r"/[^/?]+(\?|$)", f"/{name}\\1", url, count=1)


@pytest.fixture
def virgin_db():
    """A disposable database with the dataset imported but NOT ONE officer_credentials row set -- the
    exact state bootstrap-first-admin is meant for."""
    if not ADMIN_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    name = "boot_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = swap(ADMIN_URL, name)
    migrate(url)
    assert import_dataset(url, activate=True, imported_by="pytest-bootstrap")["status"] == "ACTIVE"
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture
def api(virgin_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", virgin_db)
    return client


def test_bootstrap_sets_a_working_login_on_a_virgin_instance(api):
    r = api.post("/api/v1/auth/officer/bootstrap-first-admin", json={"officer_id": "OFF-00001", "password": "Correct-Horse-42"})
    assert r.status_code == 201, r.text
    assert r.json() == {"status": "ok", "officer_id": "OFF-00001", "must_change_password": True}

    login = api.post("/api/v1/auth/officer/login", json={"officer_id": "OFF-00001", "password": "Correct-Horse-42"})
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"] is True


def test_bootstrap_permanently_refuses_once_any_credential_exists(api, virgin_db):
    first = api.post("/api/v1/auth/officer/bootstrap-first-admin", json={"officer_id": "OFF-00001", "password": "Correct-Horse-42"})
    assert first.status_code == 201

    again = api.post("/api/v1/auth/officer/bootstrap-first-admin", json={"officer_id": "OFF-00002", "password": "Another-Horse-99"})
    assert again.status_code == 403

    # even a credential set through a completely different path (not this endpoint) locks it out
    with psycopg.connect(virgin_db, autocommit=True) as c:
        c.execute("DELETE FROM officer_credentials")  # reset, then set one via the normal internal path
    with psycopg.connect(virgin_db) as c, c.transaction():
        set_password(c, "OFF-00003", OFFICER_PASSWORD)
    blocked = api.post("/api/v1/auth/officer/bootstrap-first-admin", json={"officer_id": "OFF-00002", "password": "Another-Horse-99"})
    assert blocked.status_code == 403


def test_bootstrap_rejects_an_unknown_officer(api):
    r = api.post("/api/v1/auth/officer/bootstrap-first-admin", json={"officer_id": "OFF-99999", "password": "Correct-Horse-42"})
    assert r.status_code == 404


def test_bootstrap_enforces_the_password_policy(api):
    r = api.post("/api/v1/auth/officer/bootstrap-first-admin", json={"officer_id": "OFF-00001", "password": "weak"})
    assert r.status_code == 422
    assert not api.post("/api/v1/auth/officer/login", json={"officer_id": "OFF-00001", "password": "weak"}).json().get("access_token")

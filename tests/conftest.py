import os
import pathlib
import re
import sys
import uuid

import psycopg
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
OFFICER_PASSWORD = "Correct-Horse-42"


def swap_database(url: str, name: str) -> str:
    return re.sub(r"/[^/?]+(\?|$)", f"/{name}\\1", url, count=1)


@pytest.fixture(scope="session")
def authdb():
    """One migrated + fully seeded database shared by the auth/RBAC tests; DATABASE_URL points at it."""
    if not ADMIN_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    from backend.db.ingest import import_dataset
    from backend.db.migrate import migrate

    name = "auth_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = swap_database(ADMIN_URL, name)
    migrate(url)
    assert import_dataset(url, activate=True, imported_by="pytest")["status"] == "ACTIVE"
    saved = {k: os.environ.get(k) for k in ("DATABASE_URL", "OTP_PROVIDER")}
    os.environ["DATABASE_URL"], os.environ["OTP_PROVIDER"] = url, "dev"
    yield url
    for k, v in saved.items():
        os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture(scope="session")
def officers(authdb):
    """First officer of each dataset role, with a known password."""
    from backend.core.credentials import set_password

    picked = {}
    with psycopg.connect(authdb) as c:
        for role in ("DISTRICT_OFFICER", "FIELD_FOOD_INSPECTOR", "FPS_OWNER", "ADMIN", "AUDITOR"):
            picked[role] = [r[0] for r in c.execute(
                "SELECT officer_id FROM officers WHERE role = %s ORDER BY officer_id LIMIT 2", (role,))]
        for ids in picked.values():
            for oid in ids[:1]:
                set_password(c, oid, OFFICER_PASSWORD)
        c.commit()
    return picked


@pytest.fixture(autouse=True)
def _reset_auth_state(request):
    """Keep tests independent: clear OTPs, revocations and lockout counters after each auth test."""
    yield
    if "authdb" in request.fixturenames:
        url = request.getfixturevalue("authdb")
        with psycopg.connect(url, autocommit=True) as c:
            c.execute("DELETE FROM otp_challenges")
            c.execute("DELETE FROM revoked_tokens")
            c.execute("UPDATE officer_credentials SET failed_attempts = 0, locked_until = NULL, must_change_password = false")
            # records created through the beneficiary API, and any cycle state a test changed
            c.execute("DELETE FROM intent_signals WHERE intent_id ~ '^INT-[0-9]{4}-'")
            c.execute("DELETE FROM grievances WHERE grievance_id ~ '^GRV-1[0-9]{5}$'")
            c.execute("DELETE FROM ai_predictions WHERE service = 'beneficiary_assistant'")
            c.execute("DELETE FROM epos_transactions WHERE transaction_id LIKE 'TEST-%'")
            c.execute("UPDATE cycles SET state = 'OPEN' WHERE cycle = '2026-03'")
            c.execute("UPDATE cycles SET state = 'DELIVERING' WHERE cycle = '2026-02'")
            c.execute("UPDATE cycles SET state = 'AUDITING' WHERE cycle = '2026-01'")

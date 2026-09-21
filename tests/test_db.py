"""Phase B: migrations, ingestion pipeline and DB-level immutability.

Needs a Postgres server: set TEST_DATABASE_URL (any database on it; each test creates and drops its own).
  docker run -d -p 55432:5432 -e POSTGRES_USER=pds -e POSTGRES_PASSWORD=pds -e POSTGRES_DB=pds_test postgres:16
  TEST_DATABASE_URL=postgresql://pds:pds@localhost:55432/pds_test pytest tests/test_db.py
"""
import os
import re
import shutil
import uuid
from pathlib import Path

import pandas as pd
import psycopg
import pytest

from backend.core.config import DATA_DIR
from backend.db import ingest
from backend.db.conn import connect
from backend.db.ingest import ImportBlocked, import_dataset
from backend.db.migrate import MIGRATIONS_DIR, migrate

ADMIN_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def db_url():
    """A fresh, migrated database, dropped after the test."""
    name = "t_" + uuid.uuid4().hex[:10]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = re.sub(r"/[^/?]+(\?|$)", f"/{name}\\1", ADMIN_URL, count=1)
    migrate(url)
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {name} WITH (FORCE)")


@pytest.fixture
def data_copy(tmp_path) -> Path:
    dst = tmp_path / "data"
    shutil.copytree(DATA_DIR, dst)
    return dst


def edit(data_dir: Path, rel: str, fn) -> None:
    p = data_dir / rel
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    fn(df)
    df.to_csv(p, index=False)


def failed_names(summary) -> set[str]:
    return {f"{c['dataset']}.{c['name']}" for c in summary["report"]["checks"] if c["status"] == "FAIL"}


def table_counts(url, tables) -> dict:
    with connect(url) as c:
        return {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}


# ------------------------------------------------------------------ migrations

def test_migrations_apply_once_and_are_idempotent(db_url):
    assert migrate(db_url) == []  # fixture already applied everything
    with connect(db_url) as c:
        versions = [r[0] for r in c.execute("SELECT version FROM schema_migrations ORDER BY version")]
        assert versions == sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
        assert c.execute("SELECT count(*) FROM cycles").fetchone()[0] == 15


def test_editing_an_applied_migration_is_rejected(db_url, tmp_path):
    d = tmp_path / "m"
    shutil.copytree(MIGRATIONS_DIR, d)
    (d / "0003_seed_cycles.sql").write_text("-- tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="modified after being applied"):
        migrate(db_url, directory=d)


# ------------------------------------------------------------------ happy path

def test_dry_run_validates_real_dataset_and_writes_nothing(db_url):
    s = import_dataset(db_url, dry_run=True)
    assert s["passed"] and s["report"]["failed"] == 0 and s["report"]["total"] > 400
    assert set(table_counts(db_url, ingest.TABLES).values()) == {0}
    assert table_counts(db_url, ["dataset_imports"])["dataset_imports"] == 0


def test_full_import_matches_dataset_manifest(db_url):
    import json
    s = import_dataset(db_url, imported_by="pytest", activate=True)
    expected = json.loads((DATA_DIR / "07_generated" / "dataset_manifest.json").read_text())["row_counts"]
    assert s["status"] == "ACTIVE" and s["total_rows"] == sum(expected.values())
    counts = table_counts(db_url, ingest.TABLES)
    for table, rel, _ in ingest.DATASETS:
        assert counts[table] == expected[Path(rel).name], table
    with connect(db_url) as c:
        row = c.execute("SELECT status, imported_by, total_rows, checksum FROM dataset_imports").fetchone()
        assert row[0] == "ACTIVE" and row[1] == "pytest" and row[2] == sum(counts.values()) and len(row[3]) == 64
        # spot-check a real record end to end
        ben = c.execute("SELECT entitlement_kg, rice_entitlement_kg, wheat_entitlement_kg, current_fps_id "
                        "FROM beneficiaries WHERE ration_card_id = 'RC2023100000'").fetchone()
        assert (ben[0], ben[1], ben[2]) == (35, 22, 13) and ben[3] == "FPS-0244"
        # the one live-intent-per-beneficiary-per-cycle rule holds in stored data
        assert c.execute("""SELECT count(*) FROM (SELECT 1 FROM intent_signals WHERE status='SUBMITTED'
                            GROUP BY beneficiary_id, cycle HAVING count(*) > 1) x""").fetchone()[0] == 0


def test_reimport_is_blocked_unless_replace(db_url):
    import_dataset(db_url)
    before = table_counts(db_url, ["beneficiaries", "dataset_imports"])
    with pytest.raises(ImportBlocked):
        import_dataset(db_url)
    assert table_counts(db_url, ["beneficiaries", "dataset_imports"]) == before  # nothing half-written
    s = import_dataset(db_url, replace=True)
    assert s["status"] == "IMPORTED"
    assert table_counts(db_url, ["beneficiaries"])["beneficiaries"] == before["beneficiaries"]
    assert table_counts(db_url, ["dataset_imports"])["dataset_imports"] == 2  # history is kept


# ------------------------------------------------------------------ rejection

CORRUPTIONS = {
    "orphan_fps_reference": (
        "01_master/beneficiaries_master.csv", lambda d: d.__setitem__("current_fps_id", ["FPS-9999"] + list(d.current_fps_id[1:])),
        "beneficiaries.current_fps_id->fps.fps_id"),
    "negative_quantity": (
        "02_demand/allocations.csv", lambda d: d.__setitem__("allocated_kg", ["-5"] + list(d.allocated_kg[1:])),
        "allocations.allocated_kg_not_negative"),
    "duplicate_primary_key": (
        "01_master/warehouse_master.csv", lambda d: d.__setitem__("warehouse_id", [d.warehouse_id[0]] * 2 + list(d.warehouse_id[2:])),
        "warehouses.primary_key_unique(warehouse_id)"),
    "latitude_out_of_range": (
        "01_master/fps_master.csv", lambda d: d.__setitem__("latitude", ["123.4"] + list(d.latitude[1:])),
        "fps.latitude_in_range"),
    "entitlement_not_rice_plus_wheat": (
        "01_master/beneficiaries_master.csv", lambda d: d.__setitem__("entitlement_kg", ["999"] + list(d.entitlement_kg[1:])),
        "beneficiaries.entitlement_equals_rice_plus_wheat"),
    "non_numeric_quantity": (
        "03_operations/epos_transactions.csv", lambda d: d.__setitem__("quantity_kg", ["abc"] + list(d.quantity_kg[1:])),
        "epos_transactions.quantity_kg_numeric"),
    "missing_required_value": (
        "01_master/fps_master.csv", lambda d: d.__setitem__("capacity_kg", [""] + list(d.capacity_kg[1:])),
        "fps.capacity_kg_not_null"),
    "inventory_does_not_balance": (
        "03_operations/inventory.csv", lambda d: d.__setitem__("closing_stock_kg", ["1"] + list(d.closing_stock_kg[1:])),
        "inventory.closing_equals_opening_plus_received_minus_out"),
}


@pytest.mark.parametrize("case", CORRUPTIONS)
def test_bad_data_is_rejected_and_nothing_is_loaded(case, db_url, data_copy):
    rel, mutate, expected_check = CORRUPTIONS[case]
    edit(data_copy, rel, mutate)
    s = import_dataset(db_url, data_dir=data_copy, imported_by="pytest")
    assert not s["passed"] and s["status"] == "REJECTED"
    assert expected_check in failed_names(s)
    assert set(table_counts(db_url, ingest.TABLES).values()) == {0}  # atomic: no partial load
    with connect(db_url) as c:
        status, report = c.execute("SELECT status, validation_report FROM dataset_imports").fetchone()
    assert status == "REJECTED" and report["passed"] is False and expected_check in {
        f"{c['dataset']}.{c['name']}" for c in report["checks"] if c["status"] == "FAIL"}


def test_missing_column_is_a_schema_failure(db_url, data_copy):
    edit(data_copy, "01_master/fps_master.csv", lambda d: d.drop(columns=["capacity_kg"], inplace=True))
    s = import_dataset(db_url, data_dir=data_copy, dry_run=True)
    assert "fps.required_columns_present" in failed_names(s)


def test_duplicate_live_intent_and_over_entitlement_intent_are_caught(db_url, data_copy):
    def dup(d):
        live = d[d.status == "SUBMITTED"].iloc[0].copy()
        live["intent_id"] = "INT-DUPLICATE"
        d.loc[len(d)] = live

    edit(data_copy, "02_demand/intent_signals.csv", dup)
    assert "intent_signals.one_live_intent_per_beneficiary_cycle" in failed_names(
        import_dataset(db_url, data_dir=data_copy, dry_run=True))

    def over(d):
        i = d.index[d.status == "SUBMITTED"][0]
        d.loc[i, "rice_quantity_kg"] = "500"
        d.loc[i, "total_quantity_kg"] = str(500 + int(d.loc[i, "wheat_quantity_kg"]))

    shutil.copytree(DATA_DIR, data_copy, dirs_exist_ok=True)
    edit(data_copy, "02_demand/intent_signals.csv", over)
    assert "intent_signals.intent_within_entitlement" in failed_names(
        import_dataset(db_url, data_dir=data_copy, dry_run=True))


def test_locked_manifest_without_ready_constraints_is_caught(db_url, data_copy):
    def blocked_but_locked(d):
        i = d.index[d.manifest_status == "LOCKED"][0]
        d.loc[i, "constraint_status"] = "BLOCKED"

    edit(data_copy, "03_operations/dispatch_manifests.csv", blocked_but_locked)
    assert "dispatch_manifests.locked_only_if_constraints_ready" in failed_names(
        import_dataset(db_url, data_dir=data_copy, dry_run=True))


# ------------------------------------------------------------------ immutability (DB-enforced)

@pytest.fixture
def loaded(db_url):
    import_dataset(db_url, activate=True)
    return db_url


def test_demand_lock_is_immutable(loaded):
    with connect(loaded) as c:
        c.execute("INSERT INTO demand_locks (cycle, locked_by, snapshot, sha256_hash) VALUES ('2026-03','OFF-00001','{}','h')")
        c.commit()
        for sql in ("UPDATE demand_locks SET locked_by='x'", "DELETE FROM demand_locks"):
            with pytest.raises(psycopg.errors.RestrictViolation):
                c.execute(sql)
            c.rollback()
        with pytest.raises(psycopg.errors.UniqueViolation):  # one lock per cycle
            c.execute("INSERT INTO demand_locks (cycle, locked_by, snapshot, sha256_hash) VALUES ('2026-03','o','{}','h')")


def test_audit_events_are_append_only(loaded):
    with connect(loaded) as c:
        for sql in ("UPDATE audit_events SET result='X'", "DELETE FROM audit_events"):
            with pytest.raises(psycopg.errors.RestrictViolation):
                c.execute(sql)
            c.rollback()
        c.execute("""INSERT INTO audit_events (audit_event_id, cycle, actor_user_id, actor_role, action, entity_type,
                     entity_id, result, timestamp) VALUES ('AUD-T1','2026-03','OFF-00001','DSO','TEST','X','1','SUCCESS', now())""")
        c.commit()  # inserting is allowed


def test_sealed_manifest_content_cannot_change_but_status_can_advance(loaded):
    with connect(loaded) as c:
        mid = c.execute("SELECT manifest_id FROM dispatch_manifests WHERE manifest_status='LOCKED' LIMIT 1").fetchone()[0]
        for sql in ("UPDATE dispatch_manifests SET total_kg = total_kg + 1 WHERE manifest_id=%s",
                    "UPDATE dispatch_manifests SET sha256_hash = 'tampered' WHERE manifest_id=%s",
                    "DELETE FROM dispatch_manifests WHERE manifest_id=%s"):
            with pytest.raises(psycopg.errors.RestrictViolation):
                c.execute(sql, (mid,))
            c.rollback()
        c.execute("UPDATE dispatch_manifests SET manifest_status='DISPATCHED' WHERE manifest_id=%s", (mid,))
        c.commit()


def test_dataset_import_history_cannot_be_deleted(loaded):
    with connect(loaded) as c, pytest.raises(psycopg.errors.RestrictViolation):
        c.execute("DELETE FROM dataset_imports")


def test_database_rejects_second_live_intent_and_entitlement_mismatch(loaded):
    with connect(loaded) as c:
        b, cyc = c.execute("SELECT beneficiary_id, cycle FROM intent_signals WHERE status='SUBMITTED' LIMIT 1").fetchone()
        fps = c.execute("SELECT current_fps_id FROM beneficiaries WHERE beneficiary_id=%s", (b,)).fetchone()[0]
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("""INSERT INTO intent_signals VALUES ('INT-X', %s, %s, %s, 1, 1, 2, 'SELF', now(), 'SUBMITTED')""", (b, fps, cyc))
        c.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("UPDATE beneficiaries SET entitlement_kg = entitlement_kg + 1 WHERE beneficiary_id=%s", (b,))


def test_db_status_endpoint_reflects_real_database(loaded, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.core.security import create_access_token
    monkeypatch.setenv("DATABASE_URL", loaded)
    with connect(loaded) as c:
        admin = c.execute("SELECT officer_id FROM officers WHERE role = 'ADMIN' ORDER BY officer_id LIMIT 1").fetchone()[0]
    client = TestClient(app)
    assert client.get("/api/v1/system/db-status").status_code == 401  # not public any more
    r = client.get("/api/v1/system/db-status", headers={"Authorization": "Bearer " + create_access_token(admin, "SYSTEM_ADMIN")})
    assert r.status_code == 200
    body = r.json()
    assert body["latest_import"]["status"] == "ACTIVE" and body["latest_import"]["checks_failed"] == 0
    assert body["row_counts"]["beneficiaries"] == 10000 and body["total_rows"] == 83763
    assert body["migrations"][0] == "0001_schema.sql"


def test_if_empty_seeds_once_and_never_overwrites(db_url):
    first = import_dataset(db_url, activate=True, if_empty=True, imported_by="bootstrap")
    assert first["status"] == "ACTIVE"
    before = table_counts(db_url, ["beneficiaries", "dataset_imports"])
    again = import_dataset(db_url, activate=True, if_empty=True)
    assert again["status"] == "SKIPPED"
    assert table_counts(db_url, ["beneficiaries", "dataset_imports"]) == before


def test_if_empty_skips_when_only_import_history_exists(db_url, data_copy):
    edit(data_copy, "01_master/fps_master.csv", lambda d: d.__setitem__("capacity_kg", [""] + list(d.capacity_kg[1:])))
    assert import_dataset(db_url, data_dir=data_copy)["status"] == "REJECTED"  # leaves a REJECTED history row
    assert import_dataset(db_url, if_empty=True)["status"] == "SKIPPED"  # not blindly re-seeded over history


# ------------------------------------------------------------------ audit hash chain

def test_audit_chain_detects_a_forged_event(db_url):
    from backend.core.audit import verify_chain, write_audit
    for i in range(3):
        write_audit(f"u{i}", "TEST", "ACTION", "SUCCESS", url=db_url)
    assert verify_chain(db_url) == {"checked": 3, "broken": [], "intact": True}
    with connect(db_url) as c:  # inserting is allowed (append-only), but a forged hash is detectable
        c.execute("""INSERT INTO audit_events (audit_event_id, actor_user_id, actor_role, action, entity_type, entity_id,
                     result, timestamp, hash) VALUES ('AUD-FORGED000001','x','x','A','U','x','SUCCESS', now(), 'bad')""")
        c.commit()
    r = verify_chain(db_url)
    assert not r["intact"] and r["broken"] == ["AUD-FORGED000001"]


def test_audit_chain_survives_concurrent_writers(db_url):
    from concurrent.futures import ThreadPoolExecutor
    from backend.core.audit import verify_chain, write_audit
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda i: write_audit(f"u{i}", "TEST", "PARALLEL", "SUCCESS", url=db_url), range(24)))
    r = verify_chain(db_url)
    assert r["checked"] == 24 and r["intact"], r

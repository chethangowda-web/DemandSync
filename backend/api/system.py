"""System status endpoints (read-only). Access will be restricted to SYSTEM_ADMIN once DB-backed RBAC lands."""
import os

from fastapi import APIRouter, HTTPException

from backend.db.conn import connect
from backend.db.ingest import TABLES

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/db-status")
def db_status():
    """Migration state, latest dataset import and per-table row counts, straight from the database."""
    if not os.getenv("DATABASE_URL"):
        raise HTTPException(503, "DATABASE_URL is not configured")
    try:
        with connect() as c:
            migrations = [r[0] for r in c.execute("SELECT version FROM schema_migrations ORDER BY version")]
            imp = c.execute(
                """SELECT import_id, dataset_name, version, status, total_rows, checksum, imported_by, created_at,
                          validation_report->'total', validation_report->'failed'
                   FROM dataset_imports ORDER BY created_at DESC LIMIT 1""").fetchone()
            counts = {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
            cycles = [dict(zip(("cycle", "state"), r)) for r in c.execute("SELECT cycle, state FROM cycles ORDER BY cycle")]
    except Exception as e:
        raise HTTPException(503, f"database unavailable: {type(e).__name__}")
    latest = None
    if imp:
        latest = {"import_id": imp[0], "dataset": imp[1], "version": imp[2], "status": imp[3], "total_rows": imp[4],
                  "checksum": imp[5], "imported_by": imp[6], "imported_at": imp[7].isoformat(),
                  "checks_total": imp[8], "checks_failed": imp[9]}
    return {"database": "postgresql", "migrations": migrations, "latest_import": latest,
            "row_counts": counts, "total_rows": sum(counts.values()), "cycles": cycles}

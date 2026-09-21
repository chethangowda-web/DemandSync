"""Forward-only SQL migration runner.

Each file in database/migrations runs once, in filename order, inside its own transaction.
Applied files are checksummed: editing an applied migration is an error, not a silent no-op.

Usage: python -m backend.db.migrate
"""
import hashlib
import sys
from pathlib import Path

from backend.core.config import REPO_ROOT
from backend.db.conn import connect

MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"

_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  checksum TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def migrate(url: str | None = None, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations. Returns the versions applied by this call."""
    files = sorted(directory.glob("*.sql"))
    applied_now: list[str] = []
    with connect(url) as conn:
        conn.execute(_BOOTSTRAP)
        conn.commit()
        done = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())
        for f in files:
            digest = _checksum(f)
            if f.name in done:
                if done[f.name] != digest:
                    raise RuntimeError(f"migration {f.name} was modified after being applied")
                continue
            with conn.transaction():
                conn.execute(f.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)", (f.name, digest))
            applied_now.append(f.name)
    return applied_now


if __name__ == "__main__":
    applied = migrate()
    print("applied:", ", ".join(applied) if applied else "nothing (up to date)")
    sys.exit(0)

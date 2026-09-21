"""Officer credential management (no default or hardcoded passwords anywhere in the code).

  python -m backend.core.credentials bootstrap            # from BOOTSTRAP_ACCOUNTS="OFF-00667=pw;OFF-00001=pw"
  NEW_PASSWORD=... python -m backend.core.credentials set-password OFF-00001
  python -m backend.core.credentials seed-dev             # every officer, dev/test only (refused in production)

bootstrap is idempotent: it only creates credentials for officers that have none, so re-running on every
deploy never resets a password someone has changed.
"""
import getpass
import os
import sys

import psycopg

from backend.core.audit import write_audit
from backend.core.security import APP_ENV, hash_password, password_policy_error
from backend.db.conn import connect


def set_password(conn: psycopg.Connection, officer_id: str, password: str, must_change: bool = False) -> None:
    if not conn.execute("SELECT 1 FROM officers WHERE officer_id = %s", (officer_id,)).fetchone():
        raise ValueError(f"unknown officer {officer_id}")
    problem = password_policy_error(password, officer_id)
    if problem:
        raise ValueError(f"{officer_id}: {problem}")
    conn.execute(
        """INSERT INTO officer_credentials (officer_id, password_hash, must_change_password)
           VALUES (%s, %s, %s)
           ON CONFLICT (officer_id) DO UPDATE SET password_hash = EXCLUDED.password_hash,
               must_change_password = EXCLUDED.must_change_password, failed_attempts = 0, locked_until = NULL,
               password_changed_at = now()""",
        (officer_id, hash_password(password), must_change))


def parse_accounts(spec: str) -> dict[str, str]:
    accounts = {}
    for part in filter(None, (p.strip() for p in spec.split(";"))):
        officer_id, sep, password = part.partition("=")
        if not sep or not officer_id or not password:
            raise ValueError("BOOTSTRAP_ACCOUNTS entries must look like OFFICER_ID=password, separated by ';'")
        accounts[officer_id.strip()] = password
    return accounts


def bootstrap(url: str | None = None, spec: str | None = None) -> list[str]:
    """Create credentials for officers that have none. Returns the officer ids created."""
    accounts = parse_accounts(spec if spec is not None else os.getenv("BOOTSTRAP_ACCOUNTS", ""))
    created: list[str] = []
    with connect(url) as conn:
        for officer_id, password in accounts.items():
            if conn.execute("SELECT 1 FROM officer_credentials WHERE officer_id = %s", (officer_id,)).fetchone():
                continue
            with conn.transaction():
                set_password(conn, officer_id, password)
            created.append(officer_id)
    for officer_id in created:  # never log the password itself
        write_audit("system", "SYSTEM", "CREDENTIAL_CREATED", "SUCCESS", "bootstrap", "USER", officer_id, url=url)
    return created


def seed_dev(url: str | None = None) -> int:
    """Give every officer the password '<OFFICER_ID>@Test123'. Development and test databases only."""
    if APP_ENV == "production":
        raise RuntimeError("seed-dev is refused when APP_ENV=production")
    with connect(url) as conn, conn.transaction():
        ids = [r[0] for r in conn.execute("SELECT officer_id FROM officers ORDER BY officer_id")]
        for oid in ids:
            set_password(conn, oid, f"{oid}@Test123")
    return len(ids)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "bootstrap":
        created = bootstrap()
        print(f"credentials created for {len(created)} officer(s): {', '.join(created) or 'none (already set)'}")
    elif cmd == "set-password" and len(argv) == 2:
        pw = os.getenv("NEW_PASSWORD") or getpass.getpass("New password: ")
        with connect() as conn, conn.transaction():
            set_password(conn, argv[1], pw)
        write_audit("cli", "SYSTEM", "PASSWORD_SET", "SUCCESS", "set-password command", "USER", argv[1])
        print(f"password set for {argv[1]}")
    elif cmd == "seed-dev":
        print(f"dev credentials set for {seed_dev()} officers")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

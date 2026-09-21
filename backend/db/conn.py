"""Database connection helper. The database URL always comes from the environment."""
import os

import psycopg


def database_url(url: str | None = None) -> str:
    url = url or os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # some providers emit the legacy scheme
    return url.replace("postgres://", "postgresql://", 1) if url.startswith("postgres://") else url


def connect(url: str | None = None, **kwargs) -> psycopg.Connection:
    conn = psycopg.connect(database_url(url), **kwargs)
    conn.execute("SET TIME ZONE 'UTC'")
    conn.commit()
    return conn


def get_db():
    """FastAPI dependency: one connection per request; commits on success, rolls back on error.

    Code that must persist state before raising an HTTPException (failed OTP attempts, lockout counters)
    calls conn.commit() itself first.
    """
    from fastapi import HTTPException  # local import keeps this module usable from CLI scripts

    try:
        conn = connect()
    except RuntimeError:  # DATABASE_URL not set
        raise HTTPException(503, "Database is not configured")
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

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

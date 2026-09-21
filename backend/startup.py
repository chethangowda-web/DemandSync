"""Container start-up tasks, each idempotent, run before the web server:

1. apply pending database migrations
2. SEED_ON_START=1      -> import the dataset, only into a completely empty database
3. BOOTSTRAP_ACCOUNTS   -> create officer credentials that do not exist yet ("OFFICER_ID=password;...")
"""
import os
import sys

from backend.core.credentials import bootstrap
from backend.db.ingest import import_dataset
from backend.db.migrate import migrate


def run(url: str | None = None) -> dict:
    result = {"migrations": migrate(url)}
    if os.getenv("SEED_ON_START") == "1":
        result["seed"] = import_dataset(url, activate=True, if_empty=True, imported_by="bootstrap")["status"]
    if os.getenv("BOOTSTRAP_ACCOUNTS"):
        result["credentials_created"] = bootstrap(url)
    return result


if __name__ == "__main__":
    if not os.getenv("DATABASE_URL"):
        print("startup: DATABASE_URL not set, skipping database tasks")
        sys.exit(0)
    print("startup:", run())

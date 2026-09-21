"""Central configuration. All paths and secrets come from the environment."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", REPO_ROOT / "data"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
APP_ENV = os.getenv("APP_ENV", "development")

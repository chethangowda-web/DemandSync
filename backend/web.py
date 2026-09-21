"""Serves the built officer web app (a single-page app) from the API at /officer/."""
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from backend.core.config import REPO_ROOT

router = APIRouter(include_in_schema=False)


def web_root() -> Path | None:
    """OFFICER_WEB_DIR, else a locally built app. Read per request so it can be configured without a restart."""
    candidates = [os.getenv("OFFICER_WEB_DIR"), REPO_ROOT / "static" / "officer", REPO_ROOT / "frontend" / "officer-web" / "dist"]
    for c in candidates:
        if c and (Path(c) / "index.html").is_file():
            return Path(c).resolve()
    return None


@router.get("/officer")
def officer_redirect():
    return RedirectResponse("/officer/")


@router.get("/officer/{path:path}")
def officer_app(path: str):
    root = web_root()
    if root is None:
        raise HTTPException(404, "The officer web app has not been built")
    target = (root / path).resolve()
    if path and target.is_file() and target.is_relative_to(root):  # never serve anything outside the app directory
        headers = {"Cache-Control": "public, max-age=31536000, immutable"} if "/assets/" in f"/{path}" else {}
        return FileResponse(target, headers=headers)
    return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})  # client-side routes

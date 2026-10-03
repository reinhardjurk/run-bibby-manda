"""Serves the built frontend (SPA) from the same container when BIBBY_STATIC_DIR exists.

API routes keep precedence; unknown paths fall back to index.html for client-side routing.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI) -> None:
    static_dir = Path(os.environ.get("BIBBY_STATIC_DIR", "/app/static"))
    index = static_dir / "index.html"
    if not index.is_file():
        return
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str, request: Request):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Nicht gefunden."}, status_code=404)
        candidate = static_dir / full_path
        if (
            full_path
            and candidate.is_file()
            and candidate.resolve().is_relative_to(static_dir.resolve())
        ):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

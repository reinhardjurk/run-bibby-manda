"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.router import router as auth_router
from app.config import get_settings
from app.db.session import get_sessionmaker
from app.events.router import router as events_router
from app.platform.router import router as platform_router
from app.platform.service import bootstrap_platform_admin
from app.registrations.router_public import router as public_router
from app.registrations.router_team import router as registrations_team_router
from app.results.router import router as results_router
from app.sepa.router import router as sepa_router
from app.settings.router import router as settings_router
from app.sponsors.router import router as sponsors_router
from app.static import mount_frontend
from app.stats.router import router as stats_router
from app.timing.router import router as timing_router
from app.timing.router import team as timing_team_router
from app.users.router import router as users_router

log = logging.getLogger("bibby")


class ErrorCorsMiddleware(BaseHTTPMiddleware):
    """Turns unhandled exceptions into JSON 500s that still carry CORS headers."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:  # noqa: BLE001 - last-resort handler, logged with traceback
            log.exception("unhandled error on %s %s", request.method, request.url.path)
            origin = request.headers.get("origin")
            headers = {}
            if origin and origin in get_settings().cors_origins:
                headers = {
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                    "Vary": "Origin",
                }
            return JSONResponse({"detail": "Interner Fehler."}, status_code=500, headers=headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations never run here (separate CI step); only the idempotent platform-admin bootstrap.
    try:
        async with get_sessionmaker()() as db:
            await bootstrap_platform_admin(db)
    except Exception:  # noqa: BLE001 - startup must not crash on a cold database (health stays up)
        log.exception("platform admin bootstrap skipped")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Bibby Multi-Org",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(ErrorCorsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Device-Token"],
        expose_headers=["X-Certificate-Count", "X-Row-Count", "Content-Disposition"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/version")
    async def version() -> dict:
        schema = None
        try:
            async with get_sessionmaker()() as db:
                schema = (
                    await db.execute(text("SELECT version_num FROM alembic_version"))
                ).scalar_one_or_none()
        except Exception:  # noqa: BLE001 - version endpoint must answer even without a DB
            schema = None
        return {"backend": s.git_sha, "db_schema": schema}

    for r in (
        platform_router,
        auth_router,
        public_router,
        registrations_team_router,
        events_router,
        timing_router,
        timing_team_router,
        results_router,
        sponsors_router,
        stats_router,
        sepa_router,
        settings_router,
        users_router,
    ):
        app.include_router(r)
    mount_frontend(app)
    return app


app = create_app()

"""Organization login/logout (httpOnly session cookie + CSRF cookie)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import delete, select

from app.config import get_settings
from app.core.cookies import clear_session_cookies, set_session_cookies
from app.core.deps import DB, SESSION_COOKIE, CurrentPrincipal
from app.core.errors import Unauthorized
from app.core.ratelimit import limiter
from app.core.security import dummy_password_check, hash_token, new_token, verify_password
from app.db.models import AppUser, AuthToken, Organization

router = APIRouter(prefix="/api/{slug}/auth", tags=["auth"])

LOGIN_FAILED = "Anmeldung fehlgeschlagen."


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    email: str
    display_name: str
    roles: list[str]
    organization: dict
    is_platform_admin: bool
    csrf_token: str | None = None


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else None) or (
        request.client.host if request.client else "?"
    )


@router.post("/login", response_model=MeResponse)
async def login(
    slug: str, data: LoginRequest, request: Request, response: Response, db: DB
) -> MeResponse:
    s = get_settings()
    ip = client_ip(request)
    account_key = f"{slug}:{data.email.lower()}"
    limiter.check("login-ip", ip, s.login_ip_limit, s.login_ip_window_seconds)
    limiter.check(
        "login-account", account_key, s.login_account_limit, s.login_account_window_seconds
    )
    limiter.check_backoff("login-account", account_key)

    org = (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    user = None
    if org is not None and org.status == "active":
        user = (
            await db.execute(
                select(AppUser)
                .where(AppUser.organization_id == org.id)
                .where(AppUser.email == data.email.lower())
                .where(AppUser.is_active.is_(True))
            )
        ).scalar_one_or_none()
    if user is None:
        dummy_password_check()
        limiter.record_failure("login-account", account_key)
        raise Unauthorized(LOGIN_FAILED)
    if not verify_password(data.password, user.password_hash):
        limiter.record_failure("login-account", account_key)
        raise Unauthorized(LOGIN_FAILED)
    assert org is not None
    limiter.record_success("login-account", account_key)
    token = new_token()
    db.add(
        AuthToken(
            organization_id=org.id,
            user_id=user.id,
            token_hash=hash_token(token, "session"),
            expires_at=datetime.now(UTC) + timedelta(hours=s.session_ttl_hours),
        )
    )
    await db.commit()
    csrf = set_session_cookies(response, token)
    return MeResponse(
        email=user.email,
        display_name=user.display_name,
        roles=sorted(r.role for r in user.roles),
        organization={"id": str(org.id), "slug": org.slug, "name": org.name},
        is_platform_admin=False,
        csrf_token=csrf,
    )


@router.post("/logout")
async def logout(request: Request, response: Response, db: DB) -> dict:
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        await db.execute(
            delete(AuthToken).where(AuthToken.token_hash == hash_token(raw, "session"))
        )
        await db.commit()
    clear_session_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(principal: CurrentPrincipal, db: DB, request: Request) -> MeResponse:
    org = (
        await db.execute(select(Organization).where(Organization.id == principal.organization_id))
    ).scalar_one()
    return MeResponse(
        email=principal.email,
        display_name=principal.display_name,
        roles=sorted(principal.roles),
        organization={"id": str(org.id), "slug": org.slug, "name": org.name},
        is_platform_admin=principal.is_platform_admin,
        csrf_token=request.cookies.get("bibby_csrf"),
    )

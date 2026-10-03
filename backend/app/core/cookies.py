"""Cookie helpers for the httpOnly session cookie and the CSRF double-submit cookie."""

from __future__ import annotations

import secrets

from fastapi import Response

from app.config import get_settings
from app.core.deps import CSRF_COOKIE, PLATFORM_COOKIE, SESSION_COOKIE


def set_session_cookies(response: Response, token: str, platform: bool = False) -> str:
    s = get_settings()
    max_age = s.session_ttl_hours * 3600
    name = PLATFORM_COOKIE if platform else SESSION_COOKIE
    response.set_cookie(
        name,
        token,
        max_age=max_age,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        domain=s.cookie_domain,
        path="/",
    )
    csrf = secrets.token_urlsafe(24)
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        httponly=False,
        secure=s.cookie_secure,
        samesite="lax",
        domain=s.cookie_domain,
        path="/",
    )
    return csrf


def clear_session_cookies(response: Response, platform: bool = False) -> None:
    s = get_settings()
    name = PLATFORM_COOKIE if platform else SESSION_COOKIE
    response.delete_cookie(name, path="/", domain=s.cookie_domain)
    if not platform:
        response.delete_cookie(CSRF_COOKIE, path="/", domain=s.cookie_domain)

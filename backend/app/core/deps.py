"""FastAPI dependencies: database session, organization resolution, authentication, roles.

Organizations are resolved **server-side only** – from the URL slug (public endpoints) or from
the session (team endpoints). No endpoint accepts a client-chosen organization id.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, NotFound, Unauthorized
from app.core.security import hash_token
from app.db.models import (
    AppUser,
    AuditLog,
    AuthToken,
    DeviceToken,
    Organization,
    PlatformAdmin,
    PlatformSession,
)
from app.db.session import get_sessionmaker

SESSION_COOKIE = "bibby_session"
PLATFORM_COOKIE = "bibby_platform_session"
CSRF_COOKIE = "bibby_csrf"
CSRF_HEADER = "x-csrf-token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ALL_ROLES = ("admin", "race_office", "timing", "sponsor_management", "sepa", "viewer")


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        try:
            yield session
        finally:
            # Defense in depth: clear the RLS tenant setting before the connection is pooled again.
            try:
                await session.execute(text("RESET app.organization_id"))
            except Exception:  # noqa: BLE001 - connection may already be invalid; nothing to do.
                pass


DB = Annotated[AsyncSession, Depends(get_db)]


async def _bind_tenant(db: AsyncSession, organization_id: uuid.UUID) -> None:
    """Publishes the tenant id to PostgreSQL (`app.organization_id`) for row-level security."""
    await db.execute(
        text("SELECT set_config('app.organization_id', :oid, false)"),
        {"oid": str(organization_id)},
    )


async def get_org_by_slug(slug: str, db: DB) -> Organization:
    """Public endpoints: resolve the tenant from the URL slug. Suspended tenants → 423."""
    org = (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if org is None:
        raise NotFound("Diese Seite existiert nicht.")
    if org.status != "active":
        from fastapi import HTTPException

        raise HTTPException(423, "Diese Organisation ist derzeit nicht verfügbar.")
    await _bind_tenant(db, org.id)
    return org


PublicOrg = Annotated[Organization, Depends(get_org_by_slug)]


@dataclass
class Principal:
    organization_id: uuid.UUID
    roles: set[str]
    user_id: uuid.UUID | None = None
    email: str = ""
    display_name: str = ""
    platform_admin_id: uuid.UUID | None = None
    platform_admin_email: str | None = None

    @property
    def is_platform_admin(self) -> bool:
        return self.platform_admin_id is not None

    def has_role(self, *roles: str) -> bool:
        return "admin" in self.roles or any(r in self.roles for r in roles)


def _check_csrf(request: Request) -> None:
    if request.method not in UNSAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or cookie != header:
        raise Forbidden("CSRF-Prüfung fehlgeschlagen. Bitte Seite neu laden.")


async def _audit(
    principal: Principal, request: Request, action: str, detail: dict | None = None
) -> None:
    """Super-admin actions inside an organization are always audited (own transaction)."""
    async with get_sessionmaker()() as s:
        s.add(
            AuditLog(
                platform_admin_id=principal.platform_admin_id,
                platform_admin_email=principal.platform_admin_email,
                organization_id=principal.organization_id,
                action=action,
                method=request.method,
                path=str(request.url.path),
                detail=detail,
            )
        )
        await s.commit()


async def _platform_principal_for_org(
    request: Request, db: AsyncSession, org: Organization
) -> Principal | None:
    raw = request.cookies.get(PLATFORM_COOKIE)
    if not raw:
        return None
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(PlatformSession, PlatformAdmin)
            .join(PlatformAdmin, PlatformAdmin.id == PlatformSession.platform_admin_id)
            .where(PlatformSession.token_hash == hash_token(raw, "platform"))
            .where(PlatformSession.expires_at > now)
            .where(PlatformAdmin.is_active.is_(True))
        )
    ).first()
    if row is None:
        return None
    sess, admin = row
    if sess.acting_organization_id != org.id:
        return None
    return Principal(
        organization_id=org.id,
        roles=set(ALL_ROLES),
        user_id=None,
        email=admin.email,
        display_name=f"Super-Admin ({admin.email})",
        platform_admin_id=admin.id,
        platform_admin_email=admin.email,
    )


async def get_current_principal(slug: str, request: Request, db: DB) -> Principal:
    """Team endpoints: organization from slug, identity from the httpOnly session cookie.

    The session must belong to exactly this organization (or be a super admin acting as it).
    """
    org = (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if org is None:
        raise NotFound("Diese Seite existiert nicht.")
    if org.status != "active":
        raise Unauthorized("Diese Organisation ist derzeit gesperrt.")

    principal: Principal | None = None
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        now = datetime.now(UTC)
        row = (
            await db.execute(
                select(AuthToken, AppUser)
                .join(AppUser, AppUser.id == AuthToken.user_id)
                .where(AuthToken.token_hash == hash_token(raw, "session"))
                .where(AuthToken.expires_at > now)
                .where(AuthToken.organization_id == org.id)
                .where(AppUser.organization_id == org.id)
                .where(AppUser.is_active.is_(True))
            )
        ).first()
        if row is not None:
            _tok, user = row
            principal = Principal(
                organization_id=org.id,
                roles={r.role for r in user.roles},
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
            )
    if principal is None:
        principal = await _platform_principal_for_org(request, db, org)
    if principal is None:
        raise Unauthorized("Bitte anmelden.")

    _check_csrf(request)
    await _bind_tenant(db, org.id)
    if principal.is_platform_admin and request.method in UNSAFE_METHODS:
        await _audit(principal, request, "org.write")
    request.state.principal = principal
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_roles(*roles: str) -> Callable[..., Awaitable[Principal]]:
    async def _dep(principal: CurrentPrincipal) -> Principal:
        if not principal.has_role(*roles):
            raise Forbidden("Diese Funktion ist für Ihre Rolle nicht freigeschaltet.")
        return principal

    return _dep


async def get_platform_admin(request: Request, db: DB) -> PlatformAdmin:
    raw = request.cookies.get(PLATFORM_COOKIE)
    if not raw:
        raise Unauthorized("Bitte als Super-Admin anmelden.")
    row = (
        await db.execute(
            select(PlatformSession, PlatformAdmin)
            .join(PlatformAdmin, PlatformAdmin.id == PlatformSession.platform_admin_id)
            .where(PlatformSession.token_hash == hash_token(raw, "platform"))
            .where(PlatformSession.expires_at > datetime.now(UTC))
            .where(PlatformAdmin.is_active.is_(True))
        )
    ).first()
    if row is None:
        raise Unauthorized("Bitte als Super-Admin anmelden.")
    _check_csrf(request)
    request.state.platform_session = row[0]
    return row[1]


CurrentPlatformAdmin = Annotated[PlatformAdmin, Depends(get_platform_admin)]


@dataclass
class DeviceContext:
    organization_id: uuid.UUID
    token: DeviceToken | None = None
    principal: Principal | None = None
    label: str = field(default="")

    @property
    def offset_seconds(self) -> int:
        return self.token.time_offset_seconds if self.token else 0


async def get_timing_actor(
    slug: str,
    request: Request,
    db: DB,
    x_device_token: Annotated[str | None, Header()] = None,
) -> DeviceContext:
    """Timing endpoints accept either a device token header or a logged-in timing user."""
    if x_device_token:
        org = (
            await db.execute(select(Organization).where(Organization.slug == slug))
        ).scalar_one_or_none()
        if org is None:
            raise NotFound("Diese Seite existiert nicht.")
        if org.status != "active":
            raise Unauthorized("Diese Organisation ist derzeit gesperrt.")
        tok = (
            await db.execute(
                select(DeviceToken)
                .where(DeviceToken.organization_id == org.id)
                .where(DeviceToken.token_hash == hash_token(x_device_token, "device"))
                .where(DeviceToken.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if tok is None:
            raise Unauthorized("Geräte-Token ungültig oder gesperrt.")
        tok.last_used_at = datetime.now(UTC)
        await db.commit()
        await _bind_tenant(db, org.id)
        return DeviceContext(organization_id=org.id, token=tok, label=tok.label)
    principal = await get_current_principal(slug, request, db)
    if not principal.has_role("timing", "race_office"):
        raise Forbidden("Diese Funktion ist für Ihre Rolle nicht freigeschaltet.")
    return DeviceContext(
        organization_id=principal.organization_id,
        principal=principal,
        label=principal.display_name or principal.email,
    )


TimingActor = Annotated[DeviceContext, Depends(get_timing_actor)]

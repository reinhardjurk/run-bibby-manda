"""Super-admin endpoints: platform login, organizations, first org admin, overview, audit,
'act as organization'."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.core.cookies import clear_session_cookies, set_session_cookies
from app.core.deps import DB, PLATFORM_COOKIE, CurrentPlatformAdmin
from app.core.errors import BadRequest, Conflict, NotFound, Unauthorized
from app.core.ratelimit import limiter
from app.core.security import (
    dummy_password_check,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)
from app.db.models import (
    AppUser,
    AuditLog,
    AuthToken,
    Organization,
    PlatformAdmin,
    PlatformSession,
    UserRole,
)
from app.db.models.users import ROLES
from app.platform import service
from app.platform.schemas import (
    OrgAdminCreate,
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
    PasswordReset,
    PlatformAdminCreate,
    PlatformLogin,
)

router = APIRouter(prefix="/api/platform", tags=["platform"])


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else None) or (
        request.client.host if request.client else "?"
    )


@router.post("/auth/login")
async def login(data: PlatformLogin, request: Request, response: Response, db: DB) -> dict:
    s = get_settings()
    key = f"platform:{data.email.lower()}"
    limiter.check("login-ip", _ip(request), s.login_ip_limit, s.login_ip_window_seconds)
    limiter.check("login-account", key, s.login_account_limit, s.login_account_window_seconds)
    limiter.check_backoff("login-account", key)
    admin = (
        await db.execute(
            select(PlatformAdmin).where(
                PlatformAdmin.email == data.email.lower(), PlatformAdmin.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if admin is None:
        dummy_password_check()
        limiter.record_failure("login-account", key)
        raise Unauthorized("Anmeldung fehlgeschlagen.")
    if not verify_password(data.password, admin.password_hash):
        limiter.record_failure("login-account", key)
        raise Unauthorized("Anmeldung fehlgeschlagen.")
    limiter.record_success("login-account", key)
    token = new_token()
    db.add(
        PlatformSession(
            platform_admin_id=admin.id,
            token_hash=hash_token(token, "platform"),
            expires_at=datetime.now(UTC) + timedelta(hours=s.session_ttl_hours),
        )
    )
    await service.audit(db, admin, "platform.login")
    await db.commit()
    csrf = set_session_cookies(response, token, platform=True)
    return {"email": admin.email, "csrf_token": csrf, "acting_organization": None}


@router.post("/auth/logout")
async def logout(request: Request, response: Response, db: DB) -> dict:
    raw = request.cookies.get(PLATFORM_COOKIE)
    if raw:
        await db.execute(
            delete(PlatformSession).where(PlatformSession.token_hash == hash_token(raw, "platform"))
        )
        await db.commit()
    clear_session_cookies(response, platform=True)
    return {"ok": True}


@router.get("/auth/me")
async def me(admin: CurrentPlatformAdmin, request: Request, db: DB) -> dict:
    sess: PlatformSession = request.state.platform_session
    acting = None
    if sess.acting_organization_id:
        org = (
            await db.execute(
                select(Organization).where(Organization.id == sess.acting_organization_id)
            )
        ).scalar_one_or_none()
        if org:
            acting = {"id": str(org.id), "slug": org.slug, "name": org.name}
    return {
        "email": admin.email,
        "csrf_token": request.cookies.get("bibby_csrf"),
        "acting_organization": acting,
    }


# ---- organizations ----


@router.get("/organizations", response_model=list[OrganizationOut])
async def list_orgs(admin: CurrentPlatformAdmin, db: DB) -> list[OrganizationOut]:
    orgs = (await db.execute(select(Organization).order_by(Organization.created_at))).scalars()
    numbers = await service.org_overview(db)
    return [
        OrganizationOut(
            id=o.id,
            slug=o.slug,
            name=o.name,
            status=o.status,
            contact_email=o.contact_email,
            created_at=o.created_at,
            **numbers.get(o.id, {}),
        )
        for o in orgs
    ]


@router.post("/organizations", response_model=OrganizationOut, status_code=201)
async def create_org(
    admin: CurrentPlatformAdmin, db: DB, data: OrganizationCreate, request: Request
) -> OrganizationOut:
    org = Organization(slug=data.slug, name=data.name, contact_email=data.contact_email)
    db.add(org)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict("Dieser Slug ist bereits vergeben.") from exc
    if data.admin_email and data.admin_password:
        user = AppUser(
            organization_id=org.id,
            email=str(data.admin_email).lower(),
            display_name="Admin",
            password_hash=hash_password(data.admin_password),
        )
        user.roles = [UserRole(organization_id=org.id, role="admin")]
        db.add(user)
    await service.audit(
        db,
        admin,
        "organization.create",
        org.id,
        {"slug": org.slug},
        request.method,
        request.url.path,
    )
    await db.commit()
    await db.refresh(org)
    return OrganizationOut(
        id=org.id,
        slug=org.slug,
        name=org.name,
        status=org.status,
        contact_email=org.contact_email,
        created_at=org.created_at,
    )


async def _org(db, org_id: str) -> Organization:
    try:
        oid = uuid.UUID(org_id)
    except ValueError as exc:
        raise NotFound("Organisation nicht gefunden.") from exc
    org = (
        await db.execute(select(Organization).where(Organization.id == oid))
    ).scalar_one_or_none()
    if org is None:
        raise NotFound("Organisation nicht gefunden.")
    return org


@router.patch("/organizations/{org_id}", response_model=OrganizationOut)
async def update_org(
    admin: CurrentPlatformAdmin, db: DB, org_id: str, data: OrganizationUpdate, request: Request
) -> OrganizationOut:
    org = await _org(db, org_id)
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        if v is not None:
            setattr(org, k, v)
    if changes.get("status") == "suspended":
        await db.execute(delete(AuthToken).where(AuthToken.organization_id == org.id))
    await service.audit(
        db, admin, "organization.update", org.id, changes, request.method, request.url.path
    )
    await db.commit()
    await db.refresh(org)
    numbers = (await service.org_overview(db)).get(org.id, {})
    return OrganizationOut(
        id=org.id,
        slug=org.slug,
        name=org.name,
        status=org.status,
        contact_email=org.contact_email,
        created_at=org.created_at,
        **numbers,
    )


@router.delete("/organizations/{org_id}", status_code=204, response_model=None)
async def delete_org(
    admin: CurrentPlatformAdmin, db: DB, org_id: str, request: Request, confirm_slug: str = ""
) -> None:
    org = await _org(db, org_id)
    if confirm_slug != org.slug:
        raise BadRequest("Zum Löschen muss der Slug der Organisation bestätigt werden.")
    await service.audit(
        db,
        admin,
        "organization.delete",
        None,
        {"slug": org.slug, "id": str(org.id)},
        request.method,
        request.url.path,
    )
    await db.delete(org)
    await db.commit()


@router.get("/organizations/{org_id}/users")
async def org_users(admin: CurrentPlatformAdmin, db: DB, org_id: str) -> list[dict]:
    org = await _org(db, org_id)
    users = (
        await db.execute(
            select(AppUser).where(AppUser.organization_id == org.id).order_by(AppUser.email)
        )
    ).scalars()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "display_name": u.display_name,
            "is_active": u.is_active,
            "roles": sorted(r.role for r in u.roles),
        }
        for u in users
    ]


@router.post("/organizations/{org_id}/admins", status_code=201)
async def create_org_admin(
    admin: CurrentPlatformAdmin, db: DB, org_id: str, data: OrgAdminCreate, request: Request
) -> dict:
    org = await _org(db, org_id)
    user = AppUser(
        organization_id=org.id,
        email=str(data.email).lower(),
        display_name=data.display_name or "Admin",
        password_hash=hash_password(data.password),
    )
    user.roles = [UserRole(organization_id=org.id, role=r) for r in ("admin",)]
    db.add(user)
    await service.audit(
        db,
        admin,
        "organization.admin.create",
        org.id,
        {"email": user.email},
        request.method,
        request.url.path,
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict(
            "Ein Benutzer mit dieser E-Mail existiert in dieser Organisation bereits."
        ) from exc
    return {"id": str(user.id), "email": user.email, "roles": list(ROLES[:1])}


@router.post("/organizations/{org_id}/reset-password")
async def reset_password(
    admin: CurrentPlatformAdmin, db: DB, org_id: str, data: PasswordReset, request: Request
) -> dict:
    org = await _org(db, org_id)
    user = (
        await db.execute(
            select(AppUser).where(AppUser.id == data.user_id, AppUser.organization_id == org.id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFound("Benutzer nicht gefunden.")
    user.password_hash = hash_password(data.password)
    await db.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    await service.audit(
        db,
        admin,
        "organization.user.reset_password",
        org.id,
        {"user_id": str(user.id)},
        request.method,
        request.url.path,
    )
    await db.commit()
    return {"ok": True}


# ---- act as organization ----


@router.post("/organizations/{org_id}/enter")
async def enter_org(admin: CurrentPlatformAdmin, db: DB, org_id: str, request: Request) -> dict:
    org = await _org(db, org_id)
    sess: PlatformSession = request.state.platform_session
    sess.acting_organization_id = org.id
    await service.audit(
        db, admin, "organization.enter", org.id, None, request.method, request.url.path
    )
    await db.commit()
    return {"acting_organization": {"id": str(org.id), "slug": org.slug, "name": org.name}}


@router.post("/leave")
async def leave_org(admin: CurrentPlatformAdmin, db: DB, request: Request) -> dict:
    sess: PlatformSession = request.state.platform_session
    if sess.acting_organization_id:
        await service.audit(
            db,
            admin,
            "organization.leave",
            sess.acting_organization_id,
            None,
            request.method,
            request.url.path,
        )
    sess.acting_organization_id = None
    await db.commit()
    return {"acting_organization": None}


# ---- overview, audit, platform admins ----


@router.get("/overview")
async def overview(admin: CurrentPlatformAdmin, db: DB) -> dict:
    numbers = await service.org_overview(db)
    return {
        "organizations": (
            await db.execute(select(func.count()).select_from(Organization))
        ).scalar_one(),
        "events": sum(n.get("events", 0) for n in numbers.values()),
        "registrations": sum(n.get("registrations", 0) for n in numbers.values()),
        "storage_bytes": sum(n.get("storage_bytes", 0) for n in numbers.values()),
        "db_size_bytes": (
            await db.execute(select(func.pg_database_size(func.current_database())))
        ).scalar_one(),
    }


@router.get("/audit")
async def audit_log(
    admin: CurrentPlatformAdmin, db: DB, limit: int = 200, organization_id: uuid.UUID | None = None
) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 1000))
    if organization_id:
        stmt = stmt.where(AuditLog.organization_id == organization_id)
    rows = (await db.execute(stmt)).scalars()
    return [
        {
            "id": str(a.id),
            "admin": a.platform_admin_email,
            "organization_id": str(a.organization_id) if a.organization_id else None,
            "action": a.action,
            "method": a.method,
            "path": a.path,
            "detail": a.detail,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]


@router.get("/admins")
async def list_admins(admin: CurrentPlatformAdmin, db: DB) -> list[dict]:
    rows = (await db.execute(select(PlatformAdmin).order_by(PlatformAdmin.created_at))).scalars()
    return [
        {"id": str(a.id), "email": a.email, "is_active": a.is_active, "is_self": a.id == admin.id}
        for a in rows
    ]


@router.post("/admins", status_code=201)
async def create_admin(
    admin: CurrentPlatformAdmin, db: DB, data: PlatformAdminCreate, request: Request
) -> dict:
    new = PlatformAdmin(email=str(data.email).lower(), password_hash=hash_password(data.password))
    db.add(new)
    await service.audit(
        db,
        admin,
        "platform.admin.create",
        None,
        {"email": new.email},
        request.method,
        request.url.path,
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict("Ein Super-Admin mit dieser E-Mail existiert bereits.") from exc
    return {"id": str(new.id), "email": new.email}


@router.delete("/admins/{admin_id}", status_code=204, response_model=None)
async def delete_admin(
    admin: CurrentPlatformAdmin, db: DB, admin_id: str, request: Request
) -> None:
    """A super admin can never delete or deactivate itself; at least one must remain."""
    if str(admin.id) == admin_id:
        raise BadRequest("Das eigene Super-Admin-Konto kann nicht gelöscht werden.")
    target = (
        await db.execute(select(PlatformAdmin).where(PlatformAdmin.id == uuid.UUID(admin_id)))
    ).scalar_one_or_none()
    if target is None:
        raise NotFound("Super-Admin nicht gefunden.")
    if await service.active_admin_count(db) <= 1:
        raise BadRequest("Es muss mindestens ein Super-Admin bestehen bleiben.")
    await service.audit(
        db,
        admin,
        "platform.admin.delete",
        None,
        {"email": target.email},
        request.method,
        request.url.path,
    )
    await db.delete(target)
    await db.commit()


@router.get("/settings")
async def platform_settings(admin: CurrentPlatformAdmin) -> dict:
    s = get_settings()
    return {
        "env": s.env,
        "public_base_url": s.public_base_url,
        "payment_provider": s.payment_provider,
        "mail_configured": bool(s.mail_api_key and s.mail_project_id),
        "mail_test_recipient": s.mail_test_recipient,
        "ratelimit_enabled": s.ratelimit_enabled,
        "session_ttl_hours": s.session_ttl_hours,
        "login_ip_limit": s.login_ip_limit,
        "registration_limit": s.registration_limit,
    }

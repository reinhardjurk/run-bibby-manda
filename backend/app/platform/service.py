"""Platform service: overview numbers, audit helper, bootstrap of the first super admin."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_password
from app.db.models import (
    AppUser,
    AuditLog,
    Event,
    PlatformAdmin,
    Registration,
    Sponsor,
)

log = logging.getLogger("bibby.platform")


async def audit(
    db: AsyncSession,
    admin: PlatformAdmin,
    action: str,
    organization_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
    method: str | None = None,
    path: str | None = None,
) -> None:
    db.add(
        AuditLog(
            platform_admin_id=admin.id,
            platform_admin_email=admin.email,
            organization_id=organization_id,
            action=action,
            detail=detail,
            method=method,
            path=path,
        )
    )


async def org_overview(db: AsyncSession) -> dict[uuid.UUID, dict[str, int]]:
    out: dict[uuid.UUID, dict[str, int]] = {}
    for model, key in ((Event, "events"), (Registration, "registrations"), (AppUser, "users")):
        rows = await db.execute(
            select(model.organization_id, func.count()).group_by(model.organization_id)
        )  # type: ignore[attr-defined]
        for oid, n in rows:
            out.setdefault(oid, {})[key] = n
    storage = await db.execute(
        select(
            Sponsor.organization_id, func.coalesce(func.sum(func.length(Sponsor.image)), 0)
        ).group_by(Sponsor.organization_id)
    )
    for oid, n in storage:
        out.setdefault(oid, {})["storage_bytes"] = int(n)
    ev_storage = await db.execute(
        select(
            Event.organization_id,
            func.coalesce(
                func.sum(
                    func.coalesce(func.length(Event.certificate_background), 0)
                    + func.coalesce(func.length(Event.bib_background), 0)
                ),
                0,
            ),
        ).group_by(Event.organization_id)
    )
    for oid, n in ev_storage:
        out.setdefault(oid, {})["storage_bytes"] = out.get(oid, {}).get("storage_bytes", 0) + int(n)
    return out


async def bootstrap_platform_admin(db: AsyncSession) -> None:
    """Creates the first super admin from env vars if none exists (idempotent)."""
    s = get_settings()
    count = (await db.execute(select(func.count()).select_from(PlatformAdmin))).scalar_one()
    if count:
        return
    if not s.bootstrap_platform_admin_email or not s.bootstrap_platform_admin_password:
        log.warning("no platform admin exists and no bootstrap credentials configured")
        return
    db.add(
        PlatformAdmin(
            email=s.bootstrap_platform_admin_email.lower(),
            password_hash=hash_password(s.bootstrap_platform_admin_password),
        )
    )
    await db.commit()
    log.info("bootstrapped platform admin %s", s.bootstrap_platform_admin_email)


async def active_admin_count(db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(PlatformAdmin).where(PlatformAdmin.is_active.is_(True))
        )
    ).scalar_one()

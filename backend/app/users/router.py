"""Organization user management (org admin only, with self-lockout protection)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.core.deps import DB, Principal, require_roles
from app.core.errors import BadRequest, Conflict
from app.core.scoping import get_tenant_or_404, tenant_select
from app.core.security import hash_password
from app.db.models import AppUser, UserRole
from app.db.models.users import ROLES

router = APIRouter(prefix="/api/{slug}/team/users", tags=["users"])
Admin = Annotated[Principal, Depends(require_roles("admin"))]


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    roles: list[str]


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = ""
    password: str = Field(min_length=10, max_length=200)
    roles: list[str] = []


class UserUpdate(BaseModel):
    display_name: str | None = None
    password: str | None = Field(default=None, min_length=10, max_length=200)
    roles: list[str] | None = None
    is_active: bool | None = None


def _out(u: AppUser) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        is_active=u.is_active,
        roles=sorted(r.role for r in u.roles),
    )


def _validate_roles(roles: list[str]) -> list[str]:
    bad = [r for r in roles if r not in ROLES]
    if bad:
        raise BadRequest(f"Unbekannte Rolle: {', '.join(bad)}")
    return sorted(set(roles))


@router.get("", response_model=list[UserOut])
async def list_users(principal: Admin, db: DB) -> list[UserOut]:
    rows = (
        await db.execute(tenant_select(AppUser, principal.organization_id).order_by(AppUser.email))
    ).scalars()
    return [_out(u) for u in rows]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(principal: Admin, db: DB, data: UserCreate) -> UserOut:
    roles = _validate_roles(data.roles)
    user = AppUser(
        organization_id=principal.organization_id,
        email=str(data.email).lower(),
        display_name=data.display_name,
        password_hash=hash_password(data.password),
    )
    user.roles = [UserRole(organization_id=principal.organization_id, role=r) for r in roles]
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict("Ein Benutzer mit dieser E-Mail existiert bereits.") from exc
    await db.refresh(user)
    return _out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(principal: Admin, db: DB, user_id: str, data: UserUpdate) -> UserOut:
    user = await get_tenant_or_404(
        db, AppUser, principal.organization_id, user_id, "Benutzer nicht gefunden."
    )
    is_self = principal.user_id == user.id
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.password:
        user.password_hash = hash_password(data.password)
    if data.is_active is not None:
        if is_self and not data.is_active:
            raise BadRequest("Sie können sich nicht selbst deaktivieren.")
        user.is_active = data.is_active
    if data.roles is not None:
        roles = _validate_roles(data.roles)
        if is_self and "admin" not in roles:
            raise BadRequest("Sie können sich die Admin-Rolle nicht selbst entziehen.")
        # Remove the old role rows first: the unit of work would otherwise INSERT the new rows
        # before DELETING the old ones and trip over uq_user_role for every role that is kept.
        await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        await db.flush()
        user.roles = [UserRole(organization_id=principal.organization_id, role=r) for r in roles]
    await db.commit()
    await db.refresh(user)
    return _out(user)


@router.delete("/{user_id}", status_code=204, response_model=None)
async def delete_user(principal: Admin, db: DB, user_id: str) -> None:
    user = await get_tenant_or_404(
        db, AppUser, principal.organization_id, user_id, "Benutzer nicht gefunden."
    )
    if principal.user_id == user.id:
        raise BadRequest("Sie können sich nicht selbst löschen.")
    await db.delete(user)
    await db.commit()

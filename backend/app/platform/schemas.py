from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class PlatformLogin(BaseModel):
    email: EmailStr
    password: str


class OrganizationCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
    name: str = Field(min_length=1, max_length=200)
    contact_email: EmailStr | None = None
    admin_email: EmailStr | None = None
    admin_password: str | None = Field(default=None, min_length=10, max_length=200)

    @field_validator("slug")
    @classmethod
    def _reserved(cls, v: str) -> str:
        if v in {"api", "platform", "health", "version", "assets", "static", "team", "manage"}:
            raise ValueError("Dieser Slug ist reserviert.")
        return v


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_email: EmailStr | None = None
    status: Literal["active", "suspended"] | None = None


class OrganizationOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    status: str
    contact_email: str | None
    created_at: datetime
    events: int = 0
    registrations: int = 0
    users: int = 0
    storage_bytes: int = 0


class OrgAdminCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str = ""


class PasswordReset(BaseModel):
    user_id: uuid.UUID
    password: str = Field(min_length=10, max_length=200)


class PlatformAdminCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)


class PlatformSettingsUpdate(BaseModel):
    values: dict[str, str]

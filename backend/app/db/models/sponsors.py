"""Sponsors, site assets (logo) and per-organization key/value settings."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, org_fk, uuid_pk


class Sponsor(Base):
    __tablename__ = "sponsor"
    __table_args__ = (CheckConstraint("tier BETWEEN 1 AND 5", name="ck_sponsor_tier"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    name: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(Text)
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mime: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class SiteAsset(Base):
    __tablename__ = "site_asset"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_site_asset_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mime: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class OrgSetting(Base):
    __tablename__ = "org_setting"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_org_setting_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")

"""Timing: device tokens and finish-line records (no laps – one crossing, many recorders)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, org_fk, uuid_pk

TIMING_STATUSES = ("valid", "ignored", "duplicate", "manual")


class DeviceToken(Base):
    __tablename__ = "device_token"
    __table_args__ = (UniqueConstraint("organization_id", "label", name="uq_device_token_label"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    time_offset_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class TimingRecord(Base):
    __tablename__ = "timing_record"
    __table_args__ = (
        UniqueConstraint("event_id", "dedup_key", name="uq_timing_event_dedup"),
        CheckConstraint(
            "status IN ('valid','ignored','duplicate','manual')", name="ck_timing_status"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bib_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    absolute_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("device_token.id", ondelete="SET NULL")
    )
    source_label: Mapped[str | None] = mapped_column(String(100))
    dedup_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="valid")
    created_at: Mapped[datetime] = created_at_col()

"""Participants, registrations, bib assignments."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_col, org_fk, uuid_pk

if TYPE_CHECKING:
    from app.db.models.payments import Payment

REGISTRATION_STATUSES = ("pending", "confirmed", "cancelled")
GENDERS = ("f", "m", "x")
HEARD_ABOUT_OPTIONS = (
    "friends",
    "club",
    "poster",
    "newspaper",
    "social_media",
    "website",
    "previous_participation",
    "other",
)


class Participant(Base):
    __tablename__ = "participant"
    __table_args__ = (
        UniqueConstraint("organization_id", "match_key", name="uq_participant_org_match"),
        CheckConstraint("gender IN ('f','m','x')", name="ck_participant_gender"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)
    match_key: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class Registration(Base):
    __tablename__ = "registration"
    __table_args__ = (
        UniqueConstraint("event_id", "participant_id", name="uq_registration_event_participant"),
        CheckConstraint("status IN ('pending','confirmed','cancelled')", name="ck_reg_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True
    )
    competition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competition.id", ondelete="RESTRICT"), nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participant.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed")
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False, default="de")
    team_name: Mapped[str | None] = mapped_column(String(120))
    tshirt_size: Mapped[str | None] = mapped_column(String(40))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    heard_about: Mapped[str | None] = mapped_column(String(40))
    consent_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_publish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    manage_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    finish_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    relay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    participant: Mapped[Participant] = relationship("Participant", lazy="joined")
    bib: Mapped[BibAssignment | None] = relationship(
        "BibAssignment", uselist=False, lazy="joined", cascade="all, delete-orphan"
    )
    payment: Mapped[Payment | None] = relationship(
        "Payment", uselist=False, lazy="joined", cascade="all, delete-orphan"
    )

    @property
    def bib_number(self) -> int | None:
        return self.bib.bib_number if self.bib else None

    @property
    def is_frozen(self) -> bool:
        return self.finish_seconds is not None


class BibAssignment(Base):
    __tablename__ = "bib_assignment"
    __table_args__ = (
        UniqueConstraint("event_id", "bib_number", name="uq_bib_event_number"),
        UniqueConstraint("registration_id", name="uq_bib_registration"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True
    )
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("registration.id", ondelete="CASCADE"), nullable=False
    )
    bib_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_at_col()

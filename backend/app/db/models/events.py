"""Events and competitions (Strecken). No lap concept exists in this application."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_col, org_fk, uuid_pk

AGE_CLASS_SCHEMES = ("five", "one", "none")


class Event(Base):
    __tablename__ = "event"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    event_date: Mapped[date | None] = mapped_column(Date)
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    default_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tshirt_options: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tshirt_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    youth_cutoff_date: Mapped[date | None] = mapped_column(Date)
    venue_postal_code: Mapped[str | None] = mapped_column(String(10))
    bib_start_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    certificate_offset_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    certificate_background: Mapped[bytes | None] = mapped_column(LargeBinary)
    certificate_background_mime: Mapped[str | None] = mapped_column(String(64))
    bib_background: Mapped[bytes | None] = mapped_column(LargeBinary)
    bib_background_mime: Mapped[str | None] = mapped_column(String(64))
    photo_base_url: Mapped[str | None] = mapped_column(Text)
    photo_hmac_seed: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = created_at_col()

    competitions: Mapped[list[Competition]] = relationship(
        "Competition",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Competition.sort_order",
    )

    @property
    def tshirt_option_list(self) -> list[str]:
        return [o.strip() for o in self.tshirt_options.splitlines() if o.strip()]


class Competition(Base):
    __tablename__ = "competition"
    __table_args__ = (
        CheckConstraint("age_class_scheme IN ('five','one','none')", name="ck_comp_scheme"),
        CheckConstraint(
            "(bib_range_start IS NULL AND bib_range_end IS NULL) OR "
            "(bib_range_start IS NOT NULL AND bib_range_end IS NOT NULL "
            "AND bib_range_start <= bib_range_end)",
            name="ck_comp_bib_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title_de: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_adult_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_youth_cents: Mapped[int | None] = mapped_column(Integer)
    age_class_scheme: Mapped[str] = mapped_column(String(8), nullable=False, default="five")
    gender_scoring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    relay_scoring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bib_range_start: Mapped[int | None] = mapped_column(Integer)
    bib_range_end: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

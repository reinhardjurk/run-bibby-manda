"""Payments: SEPA direct debit, on-site cash, SumUp online checkout."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_col, org_fk, uuid_pk

PAYMENT_METHODS = ("sepa_debit", "on_site", "sumup")
PAYMENT_STATUSES = ("pending", "paid", "cancelled")


class Payment(Base):
    __tablename__ = "payment"
    __table_args__ = (
        UniqueConstraint("registration_id", name="uq_payment_registration"),
        UniqueConstraint("organization_id", "mandate_reference", name="uq_payment_org_mandate"),
        CheckConstraint("method IN ('sepa_debit','on_site','sumup')", name="ck_payment_method"),
        CheckConstraint("status IN ('pending','paid','cancelled')", name="ck_payment_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("registration.id", ondelete="CASCADE"), nullable=False
    )
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    iban_encrypted: Mapped[str | None] = mapped_column(Text)
    iban_masked: Mapped[str | None] = mapped_column(String(40))
    account_holder: Mapped[str | None] = mapped_column(String(200))
    mandate_reference: Mapped[str | None] = mapped_column(String(35))
    sepa_exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_checkout_id: Mapped[str | None] = mapped_column(String(120))
    provider_checkout_reference: Mapped[str | None] = mapped_column(String(120))
    provider_transaction_code: Mapped[str | None] = mapped_column(String(120))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()

"""Pydantic schemas for public registration, the manage page and team-side editing."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.db.models.registrations import HEARD_ABOUT_OPTIONS

Gender = Literal["f", "m", "x"]
PaymentMethod = Literal["sepa_debit", "on_site", "sumup"]


class RegistrationCreate(BaseModel):
    event_id: uuid.UUID
    competition_id: uuid.UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: date
    gender: Gender
    email: EmailStr
    language: Literal["de", "en"] = "de"
    team_name: str | None = Field(default=None, max_length=120)
    tshirt_size: str | None = Field(default=None, max_length=40)
    postal_code: str | None = Field(default=None, max_length=10)
    heard_about: str | None = None
    consent_data: bool
    consent_publish: bool = False
    payment_method: PaymentMethod
    iban: str | None = None
    account_holder: str | None = Field(default=None, max_length=200)

    @field_validator("heard_about")
    @classmethod
    def _heard(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if v not in HEARD_ABOUT_OPTIONS:
            raise ValueError("Ungültige Auswahl bei 'Wie haben Sie von uns erfahren?'.")
        return v

    @field_validator("first_name", "last_name", "team_name", "postal_code", "account_holder")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class PaymentView(BaseModel):
    method: str
    status: str
    amount_cents: int
    iban_masked: str | None = None
    account_holder: str | None = None
    mandate_reference: str | None = None
    provider_transaction_code: str | None = None
    paid_at: datetime | None = None
    sepa_exported_at: datetime | None = None


class RegistrationCreated(BaseModel):
    registration_id: uuid.UUID
    bib_number: int
    manage_url: str
    checkout_url: str | None = None
    payment: PaymentView


class ManageView(BaseModel):
    registration_id: uuid.UUID
    status: str
    event_id: uuid.UUID
    event_name: str
    event_year: int
    competition_id: uuid.UUID
    competition_title: str
    first_name: str
    last_name: str
    birth_date: date
    gender: str
    email: str
    language: str
    team_name: str | None
    tshirt_size: str | None
    bib_number: int | None
    finish_seconds: Decimal | None
    frozen: bool
    payment: PaymentView
    checkout_url: str | None = None
    photo_url: str | None = None
    mandate_text: str | None = None
    tshirt_options: list[str]
    competitions: list[dict]


class ManageUpdate(BaseModel):
    email: EmailStr | None = None
    competition_id: uuid.UUID | None = None
    team_name: str | None = Field(default=None, max_length=120)
    tshirt_size: str | None = Field(default=None, max_length=40)


class RegistrationListItem(BaseModel):
    id: uuid.UUID
    bib_number: int | None
    first_name: str
    last_name: str
    birth_date: date
    gender: str
    competition_id: uuid.UUID
    competition_title: str
    team_name: str | None
    status: str
    finish_seconds: Decimal | None
    payment_method: str | None
    payment_status: str | None
    amount_cents: int | None
    email: str


class RegistrationDetail(RegistrationListItem):
    event_id: uuid.UUID
    participant_id: uuid.UUID
    language: str
    tshirt_size: str | None
    postal_code: str | None
    heard_about: str | None
    consent_data: bool
    consent_publish: bool
    relay_id: uuid.UUID | None
    created_at: datetime
    payment: PaymentView | None


class RegistrationAdminUpdate(BaseModel):
    """Race office may change every field. Bib numbers never change implicitly – only via
    `bib_number` (manual re-assignment)."""

    status: Literal["pending", "confirmed", "cancelled"] | None = None
    bib_number: int | None = Field(default=None, ge=1)
    competition_id: uuid.UUID | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    birth_date: date | None = None
    gender: Gender | None = None
    email: EmailStr | None = None
    language: Literal["de", "en"] | None = None
    team_name: str | None = Field(default=None, max_length=120)
    tshirt_size: str | None = Field(default=None, max_length=40)
    postal_code: str | None = Field(default=None, max_length=10)
    heard_about: str | None = None
    consent_data: bool | None = None
    consent_publish: bool | None = None
    finish_seconds: Decimal | None = None
    clear_finish: bool = False
    payment_method: PaymentMethod | None = None
    payment_status: Literal["pending", "paid", "cancelled"] | None = None
    amount_cents: int | None = Field(default=None, ge=0)
    account_holder: str | None = None
    iban: str | None = None


class OfficeRegistrationCreate(RegistrationCreate):
    """Registration entered by the race office (consent collected on paper)."""

    consent_data: bool = True
    status: Literal["pending", "confirmed"] = "confirmed"


class MergeParticipants(BaseModel):
    source_participant_id: uuid.UUID
    target_participant_id: uuid.UUID


class PagedRegistrations(BaseModel):
    items: list[RegistrationListItem]
    total: int
    page: int
    page_size: int

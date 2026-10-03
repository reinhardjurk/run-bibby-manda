from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Scheme = Literal["five", "one", "none"]


class CompetitionIn(BaseModel):
    title_de: str = Field(min_length=1, max_length=200)
    title_en: str = Field(default="", max_length=200)
    start_time: datetime | None = None
    price_adult_cents: int = Field(default=0, ge=0)
    price_youth_cents: int | None = Field(default=None, ge=0)
    age_class_scheme: Scheme = "five"
    gender_scoring: bool = True
    relay_scoring: bool = False
    bib_range_start: int | None = Field(default=None, ge=1)
    bib_range_end: int | None = Field(default=None, ge=1)
    sort_order: int = 0

    @model_validator(mode="after")
    def _range(self) -> CompetitionIn:
        a, b = self.bib_range_start, self.bib_range_end
        if (a is None) != (b is None):
            raise ValueError(
                "Startnummernkreis: 'von' und 'bis' müssen beide gesetzt oder beide leer sein."
            )
        if a is not None and b is not None and a > b:
            raise ValueError("Startnummernkreis: 'von' muss kleiner oder gleich 'bis' sein.")
        return self


class CompetitionOut(CompetitionIn):
    id: uuid.UUID
    event_id: uuid.UUID


class EventIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    year: int = Field(ge=1900, le=2200)
    event_date: date | None = None
    registration_deadline: datetime | None = None
    default_start_time: datetime | None = None
    tshirt_options: str = ""
    tshirt_included: bool = False
    youth_cutoff_date: date | None = None
    venue_postal_code: str | None = Field(default=None, max_length=10)
    bib_start_number: int = Field(default=1, ge=1)
    certificate_offset_lines: int = Field(default=0, ge=-30, le=30)
    photo_base_url: str | None = None
    photo_hmac_seed: str | None = Field(default=None, max_length=128)


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    year: int | None = Field(default=None, ge=1900, le=2200)
    event_date: date | None = None
    registration_deadline: datetime | None = None
    default_start_time: datetime | None = None
    tshirt_options: str | None = None
    tshirt_included: bool | None = None
    youth_cutoff_date: date | None = None
    venue_postal_code: str | None = None
    bib_start_number: int | None = Field(default=None, ge=1)
    certificate_offset_lines: int | None = Field(default=None, ge=-30, le=30)
    photo_base_url: str | None = None
    photo_hmac_seed: str | None = None
    clear_fields: list[str] = []


class EventOut(BaseModel):
    id: uuid.UUID
    name: str
    year: int
    event_date: date | None
    registration_deadline: datetime | None
    default_start_time: datetime | None
    tshirt_options: str
    tshirt_included: bool
    youth_cutoff_date: date | None
    venue_postal_code: str | None
    bib_start_number: int
    certificate_offset_lines: int
    photo_base_url: str | None
    photo_seed_set: bool
    has_certificate_background: bool
    has_bib_background: bool
    registration_count: int = 0
    competitions: list[CompetitionOut]


class EventTemplate(BaseModel):
    """Exported configuration – deliberately without year/date/start times."""

    template_version: int = 1
    name: str
    tshirt_options: str = ""
    tshirt_included: bool = False
    venue_postal_code: str | None = None
    bib_start_number: int = 1
    certificate_offset_lines: int = 0
    competitions: list[CompetitionIn] = []

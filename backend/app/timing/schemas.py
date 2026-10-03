from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TimingStatus = Literal["valid", "ignored", "duplicate", "manual"]


class DeviceTokenCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    time_offset_seconds: int = 0


class DeviceTokenOut(BaseModel):
    id: uuid.UUID
    label: str
    time_offset_seconds: int
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime


class DeviceTokenIssued(DeviceTokenOut):
    token: str  # plaintext – shown exactly once
    kiosk_url: str


class RecordIn(BaseModel):
    bib_number: int = Field(ge=0, le=999999)
    absolute_time: datetime
    dedup_key: str = Field(min_length=8, max_length=120)


class RecordBatch(BaseModel):
    event_id: uuid.UUID
    records: list[RecordIn] = Field(max_length=500)


class RecordOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    bib_number: int
    absolute_time: datetime
    source_label: str | None
    status: str
    dedup_key: str
    created_at: datetime


class RecordUpdate(BaseModel):
    bib_number: int | None = Field(default=None, ge=0, le=999999)
    absolute_time: datetime | None = None
    status: TimingStatus | None = None


class ManualRecord(BaseModel):
    event_id: uuid.UUID
    bib_number: int = Field(ge=0, le=999999)
    absolute_time: datetime


class ComputeResult(BaseModel):
    computed: int
    without_start_time: int
    relays_formed: int


class PlausibilityEntry(BaseModel):
    bib_number: int
    spread_seconds: float
    timestamps: list[datetime]


class PlausibilityResult(BaseModel):
    threshold_seconds: float
    entries: list[PlausibilityEntry]

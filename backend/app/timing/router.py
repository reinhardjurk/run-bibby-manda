"""Timing endpoints: device tokens (hash only), record ingest (device or user), race ops."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.core.deps import DB, Principal, TimingActor, require_roles
from app.core.errors import BadRequest, Conflict
from app.core.scoping import get_tenant_or_404, tenant_select
from app.core.security import hash_token, new_token
from app.db.models import DeviceToken, Event, Organization, TimingRecord
from app.results.service import event_results, row_to_public
from app.settings import service as settings_service
from app.timing import service
from app.timing.schemas import (
    ComputeResult,
    DeviceTokenCreate,
    DeviceTokenIssued,
    DeviceTokenOut,
    ManualRecord,
    PlausibilityEntry,
    PlausibilityResult,
    RecordBatch,
    RecordOut,
    RecordUpdate,
)

router = APIRouter(prefix="/api/{slug}/timing", tags=["timing"])
team = APIRouter(prefix="/api/{slug}/team/timing", tags=["timing-team"])
Timer = Annotated[Principal, Depends(require_roles("timing", "race_office"))]
Office = Annotated[Principal, Depends(require_roles("race_office"))]


def _tok_out(t: DeviceToken) -> DeviceTokenOut:
    return DeviceTokenOut(
        id=t.id,
        label=t.label,
        time_offset_seconds=t.time_offset_seconds,
        is_active=t.is_active,
        last_used_at=t.last_used_at,
        created_at=t.created_at,
    )


def _rec_out(r: TimingRecord) -> RecordOut:
    return RecordOut(
        id=r.id,
        event_id=r.event_id,
        bib_number=r.bib_number,
        absolute_time=r.absolute_time,
        source_label=r.source_label,
        status=r.status,
        dedup_key=r.dedup_key,
        created_at=r.created_at,
    )


# ---- device / recorder endpoints (device token header OR timing user session) ----


@router.get("/context")
async def timing_context(actor: TimingActor, db: DB) -> dict:
    """What a recorder needs: the organization's events with competitions and the actor label."""
    events = (
        await db.execute(
            tenant_select(Event, actor.organization_id).order_by(
                Event.event_date.desc().nullslast()
            )
        )
    ).scalars()
    org = (
        await db.execute(select(Organization).where(Organization.id == actor.organization_id))
    ).scalar_one()
    return {
        "organization": {"name": org.name, "slug": org.slug},
        "actor": actor.label,
        "device": actor.token is not None,
        "offset_seconds": actor.offset_seconds,
        "events": [
            {
                "id": str(e.id),
                "name": e.name,
                "year": e.year,
                "competitions": [
                    {
                        "id": str(c.id),
                        "title_de": c.title_de,
                        "start_time": c.start_time.isoformat() if c.start_time else None,
                    }
                    for c in e.competitions
                ],
            }
            for e in events
        ],
    }


@router.post("/records")
async def upload_records(actor: TimingActor, db: DB, batch: RecordBatch) -> dict:
    event = await get_tenant_or_404(
        db, Event, actor.organization_id, batch.event_id, "Veranstaltung nicht gefunden."
    )
    inserted, dup = await service.ingest_records(db, actor, event, batch.records)
    return {"inserted": inserted, "duplicates": dup}


# ---- team endpoints ----


@team.get("/devices", response_model=list[DeviceTokenOut])
async def list_devices(principal: Timer, db: DB) -> list[DeviceTokenOut]:
    rows = (
        await db.execute(
            tenant_select(DeviceToken, principal.organization_id).order_by(DeviceToken.created_at)
        )
    ).scalars()
    return [_tok_out(t) for t in rows]


def _kiosk_url(slug: str, token: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/{slug}/timing?device={token}"


@team.post("/devices", response_model=DeviceTokenIssued, status_code=201)
async def create_device(
    principal: Timer, db: DB, slug: str, data: DeviceTokenCreate
) -> DeviceTokenIssued:
    plain = new_token()
    tok = DeviceToken(
        organization_id=principal.organization_id,
        label=data.label.strip(),
        token_hash=hash_token(plain, "device"),
        time_offset_seconds=data.time_offset_seconds,
    )
    db.add(tok)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict("Ein Geräte-Token mit diesem Label existiert bereits.") from exc
    await db.refresh(tok)
    return DeviceTokenIssued(
        **_tok_out(tok).model_dump(), token=plain, kiosk_url=_kiosk_url(slug, plain)
    )


@team.post("/devices/{token_id}/reissue", response_model=DeviceTokenIssued)
async def reissue_device(principal: Timer, db: DB, slug: str, token_id: str) -> DeviceTokenIssued:
    """Issues a fresh token; the previous one becomes invalid immediately."""
    tok = await get_tenant_or_404(
        db, DeviceToken, principal.organization_id, token_id, "Geräte-Token nicht gefunden."
    )
    plain = new_token()
    tok.token_hash = hash_token(plain, "device")
    tok.is_active = True
    await db.commit()
    await db.refresh(tok)
    return DeviceTokenIssued(
        **_tok_out(tok).model_dump(), token=plain, kiosk_url=_kiosk_url(slug, plain)
    )


@team.patch("/devices/{token_id}", response_model=DeviceTokenOut)
async def update_device(principal: Timer, db: DB, token_id: str, data: dict) -> DeviceTokenOut:
    tok = await get_tenant_or_404(
        db, DeviceToken, principal.organization_id, token_id, "Geräte-Token nicht gefunden."
    )
    if "is_active" in data:
        tok.is_active = bool(data["is_active"])
    if "time_offset_seconds" in data:
        tok.time_offset_seconds = int(data["time_offset_seconds"])
    if "label" in data and str(data["label"]).strip():
        tok.label = str(data["label"]).strip()
    await db.commit()
    await db.refresh(tok)
    return _tok_out(tok)


@team.delete("/devices/{token_id}", status_code=204, response_model=None)
async def delete_device(principal: Timer, db: DB, token_id: str) -> None:
    tok = await get_tenant_or_404(
        db, DeviceToken, principal.organization_id, token_id, "Geräte-Token nicht gefunden."
    )
    await db.delete(tok)
    await db.commit()


@team.get("/records", response_model=list[RecordOut])
async def list_records(
    principal: Timer,
    db: DB,
    event_id: uuid.UUID,
    bib_number: int | None = None,
    limit: int = Query(200, ge=1, le=2000),
) -> list[RecordOut]:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    if bib_number is not None:
        return [
            _rec_out(r)
            for r in await service.records_for_bib(db, principal.organization_id, event, bib_number)
        ]
    rows = (
        await db.execute(
            tenant_select(TimingRecord, principal.organization_id)
            .where(TimingRecord.event_id == event.id)
            .order_by(TimingRecord.created_at.desc())
            .limit(limit)
        )
    ).scalars()
    return [_rec_out(r) for r in rows]


@team.get("/summary")
async def summary(principal: Timer, db: DB, event_id: uuid.UUID) -> dict:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    return await service.record_counts(db, principal.organization_id, event)


@team.post("/records/manual", response_model=RecordOut, status_code=201)
async def add_manual(principal: Office, db: DB, data: ManualRecord) -> RecordOut:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, data.event_id, "Veranstaltung nicht gefunden."
    )
    rec = TimingRecord(
        organization_id=principal.organization_id,
        event_id=event.id,
        bib_number=data.bib_number,
        absolute_time=data.absolute_time,
        source_label=principal.display_name or principal.email,
        dedup_key=f"manual-{uuid.uuid4()}",
        status="manual",
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return _rec_out(rec)


@team.patch("/records/{record_id}", response_model=RecordOut)
async def update_record(principal: Office, db: DB, record_id: str, data: RecordUpdate) -> RecordOut:
    rec = await get_tenant_or_404(
        db, TimingRecord, principal.organization_id, record_id, "Erfassung nicht gefunden."
    )
    if data.bib_number is not None:
        rec.bib_number = data.bib_number
    if data.absolute_time is not None:
        rec.absolute_time = data.absolute_time
    if data.status is not None:
        rec.status = data.status
    await db.commit()
    await db.refresh(rec)
    return _rec_out(rec)


@team.delete("/records/{record_id}", status_code=204, response_model=None)
async def delete_record(principal: Office, db: DB, record_id: str) -> None:
    rec = await get_tenant_or_404(
        db, TimingRecord, principal.organization_id, record_id, "Erfassung nicht gefunden."
    )
    await db.delete(rec)
    await db.commit()


@team.post("/compute", response_model=ComputeResult)
async def compute(principal: Office, db: DB, event_id: uuid.UUID) -> ComputeResult:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    computed, no_start, relays = await service.compute_all(db, principal.organization_id, event)
    return ComputeResult(computed=computed, without_start_time=no_start, relays_formed=relays)


@team.get("/plausibility", response_model=PlausibilityResult)
async def plausibility_check(
    principal: Office, db: DB, event_id: uuid.UUID, threshold_seconds: float | None = None
) -> PlausibilityResult:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    if threshold_seconds is None:
        threshold_seconds = float(
            await settings_service.get(
                db, principal.organization_id, "plausibility_threshold_seconds"
            )
            or 3
        )
    if threshold_seconds < 0:
        raise BadRequest("Schwelle muss positiv sein.")
    entries = await service.plausibility(db, principal.organization_id, event, threshold_seconds)
    return PlausibilityResult(
        threshold_seconds=threshold_seconds,
        entries=[
            PlausibilityEntry(bib_number=b, spread_seconds=s, timestamps=t) for b, s, t in entries
        ],
    )


@team.get("/internal-results")
async def internal_results(principal: Timer, db: DB, event_id: uuid.UUID) -> dict:
    """Complete result list including participants without publication consent."""
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    results = await event_results(db, principal.organization_id, event)
    return {
        "event": {"id": str(event.id), "name": event.name, "year": event.year},
        "competitions": [
            {
                "competition": {
                    "id": str(cr.competition.id),
                    "title_de": cr.competition.title_de,
                    "relay_scoring": cr.competition.relay_scoring,
                },
                "rows": [
                    {
                        **row_to_public(r),
                        "consent_publish": r.consent_publish,
                        "registration_id": r.registration_id,
                    }
                    for r in cr.rows
                    if r.finish_seconds is not None
                ],
                "unfinished": sum(1 for r in cr.rows if r.finish_seconds is None),
                "relays": [
                    {
                        "relay_id": str(rel.relay_id),
                        "team_name": rel.team_name,
                        "place": rel.place,
                        "total_scored": rel.total_scored,
                        "complete": rel.complete,
                        "total_seconds": float(rel.total_seconds)
                        if rel.total_seconds is not None
                        else None,
                    }
                    for rel in cr.relays
                ],
            }
            for cr in results
        ],
    }

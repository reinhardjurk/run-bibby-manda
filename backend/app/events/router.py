"""Events & competitions (race office), templates, background uploads."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy import delete, func, select

from app.core.deps import DB, Principal, require_roles
from app.core.errors import BadRequest
from app.core.scoping import get_tenant_or_404, tenant_select
from app.db.models import Competition, Event, Registration
from app.events.schemas import (
    CompetitionIn,
    CompetitionOut,
    EventIn,
    EventOut,
    EventTemplate,
    EventUpdate,
)

router = APIRouter(prefix="/api/{slug}/team/events", tags=["events"])
Office = Annotated[Principal, Depends(require_roles("race_office"))]
Admin = Annotated[Principal, Depends(require_roles("admin"))]
Reader = Annotated[
    Principal,
    Depends(require_roles("race_office", "timing", "viewer", "sepa", "sponsor_management")),
]


def _comp_out(c: Competition) -> CompetitionOut:
    return CompetitionOut(
        id=c.id,
        event_id=c.event_id,
        title_de=c.title_de,
        title_en=c.title_en,
        start_time=c.start_time,
        price_adult_cents=c.price_adult_cents,
        price_youth_cents=c.price_youth_cents,
        age_class_scheme=c.age_class_scheme,
        gender_scoring=c.gender_scoring,
        relay_scoring=c.relay_scoring,
        bib_range_start=c.bib_range_start,
        bib_range_end=c.bib_range_end,
        sort_order=c.sort_order,
    )


def _event_out(e: Event, count: int = 0) -> EventOut:
    return EventOut(
        id=e.id,
        name=e.name,
        year=e.year,
        event_date=e.event_date,
        registration_deadline=e.registration_deadline,
        default_start_time=e.default_start_time,
        tshirt_options=e.tshirt_options,
        tshirt_included=e.tshirt_included,
        youth_cutoff_date=e.youth_cutoff_date,
        venue_postal_code=e.venue_postal_code,
        bib_start_number=e.bib_start_number,
        certificate_offset_lines=e.certificate_offset_lines,
        photo_base_url=e.photo_base_url,
        photo_seed_set=bool(e.photo_hmac_seed),
        has_certificate_background=e.certificate_background is not None,
        has_bib_background=e.bib_background is not None,
        registration_count=count,
        competitions=[_comp_out(c) for c in e.competitions],
    )


async def _counts(db: DB, org_id) -> dict:
    rows = await db.execute(
        select(Registration.event_id, func.count())
        .where(Registration.organization_id == org_id)
        .group_by(Registration.event_id)
    )
    return {eid: n for eid, n in rows}


@router.get("", response_model=list[EventOut])
async def list_events(principal: Reader, db: DB) -> list[EventOut]:
    events = (
        await db.execute(
            tenant_select(Event, principal.organization_id).order_by(
                Event.year.desc(), Event.event_date.desc().nullslast(), Event.created_at.desc()
            )
        )
    ).scalars()
    counts = await _counts(db, principal.organization_id)
    return [_event_out(e, counts.get(e.id, 0)) for e in events]


@router.post("", response_model=EventOut, status_code=201)
async def create_event(principal: Office, db: DB, data: EventIn) -> EventOut:
    event = Event(organization_id=principal.organization_id, **data.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return _event_out(event)


@router.get("/{event_id}", response_model=EventOut)
async def get_event(principal: Reader, db: DB, event_id: str) -> EventOut:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    counts = await _counts(db, principal.organization_id)
    return _event_out(event, counts.get(event.id, 0))


@router.patch("/{event_id}", response_model=EventOut)
async def update_event(principal: Office, db: DB, event_id: str, data: EventUpdate) -> EventOut:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    for key, value in data.model_dump(exclude_unset=True, exclude={"clear_fields"}).items():
        if value is not None:
            setattr(event, key, value)
    for key in data.clear_fields:
        if key in {
            "event_date",
            "registration_deadline",
            "default_start_time",
            "youth_cutoff_date",
            "venue_postal_code",
            "photo_base_url",
            "photo_hmac_seed",
        }:
            setattr(event, key, None)
        elif key == "certificate_background":
            event.certificate_background = event.certificate_background_mime = None
        elif key == "bib_background":
            event.bib_background = event.bib_background_mime = None
    await db.commit()
    await db.refresh(event)
    return _event_out(event)


@router.delete("/{event_id}", status_code=204, response_model=None)
async def delete_event(principal: Admin, db: DB, event_id: str) -> None:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    # Registrations reference competitions with ON DELETE RESTRICT (a single competition can
    # never be removed under running registrations). Deleting a whole event is allowed, so the
    # registrations (with bibs and payments, DB cascade) go first, then the event itself.
    await db.execute(
        delete(Registration).where(
            Registration.event_id == event.id,
            Registration.organization_id == principal.organization_id,
        )
    )
    await db.delete(event)
    await db.commit()


@router.post("/{event_id}/competitions", response_model=CompetitionOut, status_code=201)
async def add_competition(
    principal: Office, db: DB, event_id: str, data: CompetitionIn
) -> CompetitionOut:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    comp = Competition(
        organization_id=principal.organization_id, event_id=event.id, **data.model_dump()
    )
    if comp.start_time is None:
        comp.start_time = event.default_start_time
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return _comp_out(comp)


@router.patch("/{event_id}/competitions/{competition_id}", response_model=CompetitionOut)
async def update_competition(
    principal: Office, db: DB, event_id: str, competition_id: str, data: CompetitionIn
) -> CompetitionOut:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    comp = await get_tenant_or_404(
        db,
        Competition,
        principal.organization_id,
        competition_id,
        "Strecke nicht gefunden.",
        event_id=event.id,
    )
    for key, value in data.model_dump().items():
        setattr(comp, key, value)
    await db.commit()
    await db.refresh(comp)
    return _comp_out(comp)


@router.delete("/{event_id}/competitions/{competition_id}", status_code=204, response_model=None)
async def delete_competition(principal: Office, db: DB, event_id: str, competition_id: str) -> None:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    comp = await get_tenant_or_404(
        db,
        Competition,
        principal.organization_id,
        competition_id,
        "Strecke nicht gefunden.",
        event_id=event.id,
    )
    used = (
        await db.execute(select(func.count()).where(Registration.competition_id == comp.id))
    ).scalar_one()
    if used:
        raise BadRequest("Diese Strecke hat bereits Anmeldungen und kann nicht gelöscht werden.")
    await db.delete(comp)
    await db.commit()


@router.get("/{event_id}/template", response_model=EventTemplate)
async def export_template(principal: Office, db: DB, event_id: str) -> EventTemplate:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    return EventTemplate(
        name=event.name,
        tshirt_options=event.tshirt_options,
        tshirt_included=event.tshirt_included,
        venue_postal_code=event.venue_postal_code,
        bib_start_number=event.bib_start_number,
        certificate_offset_lines=event.certificate_offset_lines,
        competitions=[
            CompetitionIn(
                title_de=c.title_de,
                title_en=c.title_en,
                start_time=None,
                price_adult_cents=c.price_adult_cents,
                price_youth_cents=c.price_youth_cents,
                age_class_scheme=c.age_class_scheme,
                gender_scoring=c.gender_scoring,
                relay_scoring=c.relay_scoring,
                bib_range_start=c.bib_range_start,
                bib_range_end=c.bib_range_end,
                sort_order=c.sort_order,
            )
            for c in event.competitions
        ],
    )


class _ImportBody(EventIn):
    competitions: list[CompetitionIn] = []


@router.post("/import", response_model=EventOut, status_code=201)
async def import_template(principal: Office, db: DB, data: _ImportBody) -> EventOut:
    """Creates an event (with competitions) from a template plus year/date supplied by the form."""
    payload = data.model_dump(exclude={"competitions"})
    event = Event(organization_id=principal.organization_id, **payload)
    for c in data.competitions:
        comp = Competition(organization_id=principal.organization_id, **c.model_dump())
        if comp.start_time is None:
            comp.start_time = event.default_start_time
        event.competitions.append(comp)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return _event_out(event)


@router.post("/{event_id}/background/{kind}")
async def upload_background(
    principal: Office, db: DB, event_id: str, kind: str, file: UploadFile = File(...)
) -> dict:
    if kind not in ("certificate", "bib"):
        raise BadRequest("Unbekannter Hintergrundtyp.")
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise BadRequest("Das Bild ist zu groß (max. 8 MB).")
    data, mime = _normalize_background(raw)
    if kind == "certificate":
        event.certificate_background, event.certificate_background_mime = data, mime
    else:
        event.bib_background, event.bib_background_mime = data, mime
    await db.commit()
    return {"ok": True}


def _normalize_background(raw: bytes) -> tuple[bytes, str]:
    import io

    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise BadRequest("Die Datei ist kein lesbares Bild.") from exc
    img.thumbnail((2480, 2480))  # A4 @ 300 dpi long edge
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=88)
    return out.getvalue(), "image/jpeg"


@router.get("/{event_id}/background/{kind}")
async def get_background(principal: Reader, db: DB, event_id: str, kind: str) -> Response:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    data, mime = (
        (event.certificate_background, event.certificate_background_mime)
        if kind == "certificate"
        else (event.bib_background, event.bib_background_mime)
    )
    if not data:
        return Response(status_code=404)
    return Response(data, media_type=mime or "image/jpeg")

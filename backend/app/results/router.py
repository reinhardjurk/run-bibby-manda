"""Certificate printing (single, per age class × competition, whole competition)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import DB, Principal, require_roles
from app.core.errors import NotFound
from app.core.scoping import get_tenant_or_404
from app.db.models import Competition, Event
from app.results import pdf as pdfs
from app.results.placements import ResultRow
from app.results.service import competition_results, event_results

router = APIRouter(prefix="/api/{slug}/team/results", tags=["results"])
Office = Annotated[Principal, Depends(require_roles("race_office"))]


def _cert_pages(
    rows: list[ResultRow], comp: Competition, event: Event, print_background: bool
) -> list[str]:
    return [
        pdfs.certificate_html(
            r,
            comp.title_de,
            event.name,
            event.year,
            gender_scoring=comp.gender_scoring,
            scheme=comp.age_class_scheme,
            offset_lines=event.certificate_offset_lines,
            background=event.certificate_background,
            bg_mime=event.certificate_background_mime,
            print_background=print_background,
        )
        for r in rows
    ]


def _filter(rows: list[ResultRow], age_class: str | None, gender: str | None) -> list[ResultRow]:
    out = [r for r in rows if r.finish_seconds is not None]
    if age_class:
        out = [r for r in out if r.age_class == age_class]
    if gender:
        out = [r for r in out if r.gender == gender]
    return sorted(out, key=lambda r: (r.place_overall or 0))


@router.get("/overview")
async def overview(principal: Office, db: DB, event_id: uuid.UUID) -> dict:
    """Counts per competition × age class × gender – shows how many certificates a batch holds."""
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    results = await event_results(db, principal.organization_id, event)
    out = []
    for cr in results:
        finished = [r for r in cr.rows if r.finish_seconds is not None]
        classes: dict[str, dict[str, int]] = {}
        for r in finished:
            classes.setdefault(r.age_class or "–", {}).setdefault(r.gender, 0)
            classes[r.age_class or "–"][r.gender] += 1
        out.append(
            {
                "competition": {
                    "id": str(cr.competition.id),
                    "title_de": cr.competition.title_de,
                    "age_class_scheme": cr.competition.age_class_scheme,
                    "gender_scoring": cr.competition.gender_scoring,
                },
                "finished": len(finished),
                "age_classes": [
                    {"age_class": k, "counts": v, "total": sum(v.values())}
                    for k, v in sorted(classes.items())
                ],
            }
        )
    return {
        "event": {"id": str(event.id), "name": event.name, "year": event.year},
        "competitions": out,
    }


@router.get("/certificate.pdf")
async def certificate_single(
    principal: Office, db: DB, event_id: uuid.UUID, bib_number: int, print_background: bool = True
) -> Response:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    results = await event_results(db, principal.organization_id, event)
    await db.commit()
    for cr in results:
        row = next((r for r in cr.rows if r.bib_number == bib_number), None)
        if row is not None:
            if row.finish_seconds is None:
                raise NotFound("Für diese Startnummer ist noch keine Zeit berechnet.")
            html_doc = _cert_pages([row], cr.competition, event, print_background)[0]
            return Response(await pdfs.render_pdf(html_doc), media_type="application/pdf")
    raise NotFound("Startnummer nicht gefunden.")


@router.get("/certificates.pdf")
async def certificates_batch(
    principal: Office,
    db: DB,
    event_id: uuid.UUID,
    competition_id: uuid.UUID,
    age_class: str | None = Query(None),
    gender: str | None = Query(None),
    print_background: bool = True,
) -> Response:
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
    results = await competition_results(db, principal.organization_id, event, comp)
    await db.commit()
    rows = _filter(results.rows, age_class, gender)
    if not rows:
        raise NotFound("Keine Urkunden für diese Auswahl.")
    html_doc = pdfs.combine_pages(_cert_pages(rows, comp, event, print_background))
    pdf = await pdfs.render_pdf(html_doc)  # runs in the bounded PDF pool
    return Response(
        pdf, media_type="application/pdf", headers={"X-Certificate-Count": str(len(rows))}
    )

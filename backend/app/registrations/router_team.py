"""Team endpoints for registrations: search, paging, full edit, mark paid, merge, office entry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import DB, Principal, require_roles
from app.core.errors import BadRequest, Conflict
from app.core.scoping import get_tenant_or_404, tenant_select
from app.core.security import encrypt_field
from app.db.models import (
    BibAssignment,
    Competition,
    Event,
    Organization,
    Participant,
    Payment,
    Registration,
)
from app.mail.service import send_confirmation_mail
from app.payments.iban import is_valid_iban, mask_iban, normalize_iban
from app.registrations import service
from app.registrations.identity import match_key
from app.registrations.schemas import (
    MergeParticipants,
    OfficeRegistrationCreate,
    PagedRegistrations,
    PaymentView,
    RegistrationAdminUpdate,
    RegistrationCreated,
    RegistrationDetail,
    RegistrationListItem,
)
from app.results import pdf as pdfs

router = APIRouter(prefix="/api/{slug}/team/registrations", tags=["registrations-team"])
Office = Annotated[Principal, Depends(require_roles("race_office"))]


def _pay_view(p: Payment | None) -> PaymentView | None:
    if p is None:
        return None
    return PaymentView(
        method=p.method,
        status=p.status,
        amount_cents=p.amount_cents,
        iban_masked=p.iban_masked,
        account_holder=p.account_holder,
        mandate_reference=p.mandate_reference,
        provider_transaction_code=p.provider_transaction_code,
        paid_at=p.paid_at,
        sepa_exported_at=p.sepa_exported_at,
    )


def _item(r: Registration, comp_titles: dict[uuid.UUID, str]) -> RegistrationListItem:
    return RegistrationListItem(
        id=r.id,
        bib_number=r.bib_number,
        first_name=r.participant.first_name,
        last_name=r.participant.last_name,
        birth_date=r.participant.birth_date,
        gender=r.participant.gender,
        competition_id=r.competition_id,
        competition_title=comp_titles.get(r.competition_id, ""),
        team_name=r.team_name,
        status=r.status,
        finish_seconds=r.finish_seconds,
        payment_method=r.payment.method if r.payment else None,
        payment_status=r.payment.status if r.payment else None,
        amount_cents=r.payment.amount_cents if r.payment else None,
        email=r.email,
    )


def _detail(r: Registration, comp_titles: dict[uuid.UUID, str]) -> RegistrationDetail:
    base = _item(r, comp_titles).model_dump()
    return RegistrationDetail(
        **base,
        event_id=r.event_id,
        participant_id=r.participant_id,
        language=r.language,
        tshirt_size=r.tshirt_size,
        postal_code=r.postal_code,
        heard_about=r.heard_about,
        consent_data=r.consent_data,
        consent_publish=r.consent_publish,
        relay_id=r.relay_id,
        created_at=r.created_at,
        payment=_pay_view(r.payment),
    )


async def _comp_titles(db, org_id) -> dict[uuid.UUID, str]:
    rows = await db.execute(
        select(Competition.id, Competition.title_de).where(Competition.organization_id == org_id)
    )
    return {cid: title for cid, title in rows}


@router.get("", response_model=PagedRegistrations)
async def list_registrations(
    principal: Office,
    db: DB,
    event_id: uuid.UUID,
    q: str = Query("", max_length=80),
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> PagedRegistrations:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    stmt = (
        tenant_select(Registration, principal.organization_id)
        .join(Participant, Participant.id == Registration.participant_id)
        .outerjoin(BibAssignment, BibAssignment.registration_id == Registration.id)
        .where(Registration.event_id == event.id)
    )
    if status:
        stmt = stmt.where(Registration.status == status)
    if q.strip():
        term = q.strip()
        conds: list[Any] = [
            func.lower(Participant.first_name).like(f"%{term.lower()}%"),
            func.lower(Participant.last_name).like(f"%{term.lower()}%"),
            func.lower(func.concat(Participant.first_name, " ", Participant.last_name)).like(
                f"%{term.lower()}%"
            ),
        ]
        if term.isdigit():
            conds.append(BibAssignment.bib_number == int(term))
        stmt = stmt.where(or_(*conds))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(BibAssignment.bib_number.nullslast(), Participant.last_name)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .unique()
    )
    titles = await _comp_titles(db, principal.organization_id)
    return PagedRegistrations(
        items=[_item(r, titles) for r in rows], total=total, page=page, page_size=page_size
    )


@router.get("/by-bib/{bib_number}", response_model=RegistrationDetail)
async def by_bib(
    principal: Office, db: DB, bib_number: int, event_id: uuid.UUID
) -> RegistrationDetail:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    reg = (
        (
            await db.execute(
                tenant_select(Registration, principal.organization_id)
                .join(BibAssignment, BibAssignment.registration_id == Registration.id)
                .where(Registration.event_id == event.id, BibAssignment.bib_number == bib_number)
            )
        )
        .scalars()
        .unique()
        .one_or_none()
    )
    if reg is None:
        raise BadRequest("Zu dieser Startnummer existiert keine Anmeldung.")
    return _detail(reg, await _comp_titles(db, principal.organization_id))


@router.post("", response_model=RegistrationCreated, status_code=201)
async def office_create(
    principal: Office, db: DB, data: OfficeRegistrationCreate, background: BackgroundTasks
) -> RegistrationCreated:
    org_row = (
        await db.execute(select(Organization).where(Organization.id == principal.organization_id))
    ).scalar_one()
    reg, token, checkout_url = await service.create_registration(
        db, org_row, data, enforce_deadline=False, status=data.status
    )
    link = service.manage_url(org_row, token)
    background.add_task(send_confirmation_mail, org_row.id, reg.email, reg.language, link)
    return RegistrationCreated(
        registration_id=reg.id,
        bib_number=reg.bib_number or 0,
        manage_url=link,
        checkout_url=checkout_url,
        payment=_pay_view(reg.payment)
        or PaymentView(method="on_site", status="pending", amount_cents=0),
    )


@router.get("/{registration_id}", response_model=RegistrationDetail)
async def get_registration(principal: Office, db: DB, registration_id: str) -> RegistrationDetail:
    reg = await get_tenant_or_404(
        db, Registration, principal.organization_id, registration_id, "Anmeldung nicht gefunden."
    )
    return _detail(reg, await _comp_titles(db, principal.organization_id))


@router.post("/{registration_id}/mark-paid", response_model=RegistrationDetail)
async def mark_paid(principal: Office, db: DB, registration_id: str) -> RegistrationDetail:
    reg = await get_tenant_or_404(
        db, Registration, principal.organization_id, registration_id, "Anmeldung nicht gefunden."
    )
    if reg.payment is None:
        raise BadRequest("Keine Zahlung vorhanden.")
    reg.payment.status = "paid"
    reg.payment.paid_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(reg)
    return _detail(reg, await _comp_titles(db, principal.organization_id))


@router.patch("/{registration_id}", response_model=RegistrationDetail)
async def update_registration(
    principal: Office, db: DB, registration_id: str, data: RegistrationAdminUpdate
) -> RegistrationDetail:
    org_id = principal.organization_id
    reg = await get_tenant_or_404(
        db, Registration, org_id, registration_id, "Anmeldung nicht gefunden."
    )
    event = await get_tenant_or_404(db, Event, org_id, reg.event_id)
    p = reg.participant
    fields = data.model_dump(exclude_unset=True)

    for key in (
        "status",
        "email",
        "language",
        "team_name",
        "tshirt_size",
        "postal_code",
        "heard_about",
        "consent_data",
        "consent_publish",
    ):
        if key in fields:
            setattr(reg, key, fields[key])
    if "competition_id" in fields and fields["competition_id"] is not None:
        comp = await get_tenant_or_404(
            db,
            Competition,
            org_id,
            fields["competition_id"],
            "Strecke nicht gefunden.",
            event_id=event.id,
        )
        reg.competition_id = comp.id  # the bib number is kept
    if data.clear_finish:
        reg.finish_seconds = None
    elif "finish_seconds" in fields and fields["finish_seconds"] is not None:
        reg.finish_seconds = fields["finish_seconds"]

    identity_changed = any(k in fields for k in ("first_name", "last_name", "birth_date", "gender"))
    if identity_changed:
        for key in ("first_name", "last_name", "birth_date", "gender"):
            if key in fields and fields[key] is not None:
                setattr(p, key, fields[key])
        p.match_key = match_key(p.first_name, p.last_name, p.birth_date)

    if (
        "bib_number" in fields
        and fields["bib_number"] is not None
        and fields["bib_number"] != reg.bib_number
    ):
        if reg.bib is None:
            db.add(
                BibAssignment(
                    organization_id=org_id,
                    event_id=event.id,
                    registration_id=reg.id,
                    bib_number=fields["bib_number"],
                )
            )
        else:
            reg.bib.bib_number = fields["bib_number"]

    pay = reg.payment
    if pay is None and any(
        k in fields for k in ("payment_method", "payment_status", "amount_cents")
    ):
        pay = Payment(
            organization_id=org_id, registration_id=reg.id, method="on_site", amount_cents=0
        )
        reg.payment = pay
    if pay is not None:
        if "payment_method" in fields and fields["payment_method"]:
            pay.method = fields["payment_method"]
        if "amount_cents" in fields and fields["amount_cents"] is not None:
            pay.amount_cents = fields["amount_cents"]
        if "account_holder" in fields:
            pay.account_holder = fields["account_holder"]
        if "iban" in fields and fields["iban"]:
            if not is_valid_iban(fields["iban"]):
                raise BadRequest("Die IBAN ist ungültig.")
            iban = normalize_iban(fields["iban"])
            pay.iban_encrypted, pay.iban_masked = encrypt_field(iban), mask_iban(iban)
        if "payment_status" in fields and fields["payment_status"]:
            pay.status = fields["payment_status"]
            pay.paid_at = datetime.now(UTC) if pay.status == "paid" else None
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        msg = str(exc.orig)
        if "uq_bib_event_number" in msg:
            raise Conflict("Diese Startnummer ist in diesem Event bereits vergeben.") from exc
        if "uq_participant_org_match" in msg:
            raise Conflict(
                "Es existiert bereits eine Person mit diesem Namen und Geburtsdatum "
                "(Dubletten zusammenführen)."
            ) from exc
        raise
    await db.refresh(reg)
    return _detail(reg, await _comp_titles(db, org_id))


@router.delete("/{registration_id}", status_code=204, response_model=None)
async def delete_registration(principal: Office, db: DB, registration_id: str) -> None:
    reg = await get_tenant_or_404(
        db, Registration, principal.organization_id, registration_id, "Anmeldung nicht gefunden."
    )
    await db.delete(reg)
    await db.commit()


@router.post("/merge-participants")
async def merge_participants(principal: Office, db: DB, data: MergeParticipants) -> dict:
    org_id = principal.organization_id
    if data.source_participant_id == data.target_participant_id:
        raise BadRequest("Quelle und Ziel sind identisch.")
    source = await get_tenant_or_404(
        db, Participant, org_id, data.source_participant_id, "Teilnehmer nicht gefunden."
    )
    target = await get_tenant_or_404(
        db, Participant, org_id, data.target_participant_id, "Teilnehmer nicht gefunden."
    )
    regs = list(
        (
            await db.execute(
                tenant_select(Registration, org_id).where(Registration.participant_id == source.id)
            )
        )
        .scalars()
        .unique()
    )
    for r in regs:
        r.participant_id = target.id
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict(
            "Beide Personen sind im selben Event angemeldet – bitte zuerst eine Anmeldung löschen."
        ) from exc
    await db.delete(source)
    await db.commit()
    return {"moved": len(regs)}


@router.get("/{registration_id}/bib.pdf")
async def office_bib_pdf(principal: Office, db: DB, registration_id: str) -> Response:
    reg = await get_tenant_or_404(
        db, Registration, principal.organization_id, registration_id, "Anmeldung nicht gefunden."
    )
    event = await get_tenant_or_404(db, Event, principal.organization_id, reg.event_id)
    await db.commit()
    html_doc = pdfs.bib_html(
        reg.bib_number or 0,
        f"{reg.participant.first_name} {reg.participant.last_name}",
        f"{event.name} {event.year}",
        event.bib_background,
        event.bib_background_mime,
    )
    return Response(await pdfs.render_pdf(html_doc), media_type="application/pdf")

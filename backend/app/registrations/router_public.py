"""Public endpoints under /api/public/{slug}: info, registration, manage page, results."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response

from app.config import get_settings
from app.core.deps import DB, PublicOrg
from app.core.errors import NotFound
from app.core.ratelimit import limiter
from app.core.scoping import get_tenant_or_404, tenant_select
from app.core.security import hmac_hex
from app.db.models import Competition, Event, Payment, Registration, SiteAsset, Sponsor
from app.db.models.registrations import HEARD_ABOUT_OPTIONS
from app.mail.service import send_confirmation_mail
from app.payments import service as payments
from app.registrations import service
from app.registrations.schemas import (
    ManageUpdate,
    ManageView,
    PaymentView,
    RegistrationCreate,
    RegistrationCreated,
)
from app.results import pdf as pdfs
from app.results.service import competition_results, event_results, row_to_public
from app.settings import service as settings_service
from app.sponsors import service as sponsors

router = APIRouter(prefix="/api/public/{slug}", tags=["public"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else None) or (
        request.client.host if request.client else "?"
    )


def _payment_view(p: Payment | None) -> PaymentView:
    if p is None:
        return PaymentView(method="on_site", status="pending", amount_cents=0)
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


def _competition_public(c: Competition) -> dict:
    return {
        "id": str(c.id),
        "title_de": c.title_de,
        "title_en": c.title_en or c.title_de,
        "start_time": c.start_time.isoformat() if c.start_time else None,
        "price_adult_cents": c.price_adult_cents,
        "price_youth_cents": c.price_youth_cents,
        "relay_scoring": c.relay_scoring,
    }


@router.get("/info")
async def public_info(org: PublicOrg, db: DB) -> dict:
    values = await settings_service.get_all(db, org.id)
    now = datetime.now(UTC)
    events = (
        await db.execute(tenant_select(Event, org.id).order_by(Event.event_date.desc().nullslast()))
    ).scalars()
    sumup_available = bool(values.get("sumup_api_key")) and bool(values.get("sumup_merchant_code"))
    logo = (
        await db.execute(tenant_select(SiteAsset, org.id).where(SiteAsset.key == "logo"))
    ).scalar_one_or_none()
    return {
        "organization": {"name": org.name, "slug": org.slug},
        "logo_url": f"/api/public/{org.slug}/assets/logo" if logo else None,
        "payment_methods": ["on_site", "sepa_debit"] + (["sumup"] if sumup_available else []),
        "heard_about_options": list(HEARD_ABOUT_OPTIONS),
        "sepa_creditor": {
            "name": values.get("sepa_creditor_name", ""),
            "creditor_id": values.get("sepa_creditor_id", ""),
        },
        "sponsor_display": {
            "mode": values.get("sponsor_mode"),
            "marquee_seconds": int(values.get("sponsor_marquee_seconds") or 30),
            "tier_weights": values.get("sponsor_tier_weights"),
        },
        "events": [
            {
                "id": str(e.id),
                "name": e.name,
                "year": e.year,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "registration_deadline": (
                    e.registration_deadline.isoformat() if e.registration_deadline else None
                ),
                "registration_open": service.registration_open(e, now),
                "tshirt_options": e.tshirt_option_list,
                "tshirt_included": e.tshirt_included,
                "youth_cutoff_date": e.youth_cutoff_date.isoformat()
                if e.youth_cutoff_date
                else None,
                "photos_available": bool(e.photo_base_url and e.photo_hmac_seed),
                "competitions": [_competition_public(c) for c in e.competitions],
            }
            for e in events
        ],
    }


@router.get("/team-names")
async def team_names(org: PublicOrg, db: DB, q: str = Query("", max_length=60)) -> list[str]:
    return await service.team_names(db, org.id, q)


@router.post("/registrations", response_model=RegistrationCreated, status_code=201)
async def create_registration(
    org: PublicOrg, db: DB, data: RegistrationCreate, request: Request, background: BackgroundTasks
) -> RegistrationCreated:
    s = get_settings()
    limiter.check(
        "registration", _client_ip(request), s.registration_limit, s.registration_window_seconds
    )
    reg, token, checkout_url = await service.create_registration(db, org, data)
    link = service.manage_url(org, token)
    # Mail only after a successful commit, as a background task; failures are logged, not raised.
    background.add_task(send_confirmation_mail, org.id, reg.email, reg.language, link)
    return RegistrationCreated(
        registration_id=reg.id,
        bib_number=reg.bib_number or 0,
        manage_url=link,
        checkout_url=checkout_url,
        payment=_payment_view(reg.payment),
    )


async def _manage_view(
    db, org, reg: Registration, token: str, checkout_url: str | None
) -> ManageView:
    event = await get_tenant_or_404(db, Event, org.id, reg.event_id)
    comp = next((c for c in event.competitions if c.id == reg.competition_id), None)
    values = await settings_service.get_all(db, org.id)
    photo_url = None
    if event.photo_base_url and event.photo_hmac_seed and reg.bib_number is not None:
        folder = hmac_hex(event.photo_hmac_seed, str(reg.bib_number))
        photo_url = f"{event.photo_base_url.rstrip('/')}/{folder}/index.html"
    mandate_text = None
    if reg.payment and reg.payment.method == "sepa_debit":
        mandate_text = (
            f"Ich ermächtige {values.get('sepa_creditor_name') or org.name} "
            f"(Gläubiger-ID {values.get('sepa_creditor_id') or '–'}), Zahlungen von meinem Konto "
            f"mittels Lastschrift einzuziehen. Mandatsreferenz: {reg.payment.mandate_reference}."
        )
    return ManageView(
        registration_id=reg.id,
        status=reg.status,
        event_id=event.id,
        event_name=event.name,
        event_year=event.year,
        competition_id=reg.competition_id,
        competition_title=comp.title_de if comp else "",
        first_name=reg.participant.first_name,
        last_name=reg.participant.last_name,
        birth_date=reg.participant.birth_date,
        gender=reg.participant.gender,
        email=reg.email,
        language=reg.language,
        team_name=reg.team_name,
        tshirt_size=reg.tshirt_size,
        bib_number=reg.bib_number,
        finish_seconds=reg.finish_seconds,
        frozen=reg.is_frozen,
        payment=_payment_view(reg.payment),
        checkout_url=checkout_url,
        photo_url=photo_url,
        mandate_text=mandate_text,
        tshirt_options=event.tshirt_option_list,
        competitions=[_competition_public(c) for c in event.competitions],
    )


@router.get("/manage", response_model=ManageView)
async def manage_get(org: PublicOrg, db: DB, token: str) -> ManageView:
    reg = await service.get_by_manage_token(db, org, token)
    if reg.payment is not None:
        await payments.verify_sumup_payment(db, org, reg.payment)
        reg = await service.get_by_manage_token(db, org, token)
    return await _manage_view(db, org, reg, token, None)


@router.patch("/manage", response_model=ManageView)
async def manage_update(org: PublicOrg, db: DB, token: str, data: ManageUpdate) -> ManageView:
    reg = await service.get_by_manage_token(db, org, token)
    reg = await service.apply_manage_update(db, org, reg, data)
    return await _manage_view(db, org, reg, token, None)


@router.post("/manage/checkout")
async def manage_checkout(org: PublicOrg, db: DB, token: str) -> dict:
    reg = await service.get_by_manage_token(db, org, token)
    if reg.payment and await payments.verify_sumup_payment(db, org, reg.payment):
        return {"checkout_url": None, "status": "paid"}
    reg = await service.get_by_manage_token(db, org, token)
    url = await payments.fresh_checkout_url(db, org, reg, token)
    if url is None:
        raise NotFound("Für diese Anmeldung ist keine Online-Zahlung offen.")
    return {"checkout_url": url, "status": "pending"}


@router.get("/manage/bib.pdf")
async def manage_bib_pdf(org: PublicOrg, db: DB, token: str) -> Response:
    reg = await service.get_by_manage_token(db, org, token)
    event = await get_tenant_or_404(db, Event, org.id, reg.event_id)
    await db.commit()
    html_doc = pdfs.bib_html(
        reg.bib_number or 0,
        f"{reg.participant.first_name} {reg.participant.last_name}",
        f"{event.name} {event.year}",
        event.bib_background,
        event.bib_background_mime,
    )
    data = await pdfs.render_pdf(html_doc)
    return Response(data, media_type="application/pdf")


@router.get("/manage/certificate.pdf")
async def manage_certificate_pdf(org: PublicOrg, db: DB, token: str) -> Response:
    reg = await service.get_by_manage_token(db, org, token)
    if not reg.is_frozen:
        raise NotFound("Die Urkunde ist erst nach der Zeitberechnung verfügbar.")
    event = await get_tenant_or_404(db, Event, org.id, reg.event_id)
    comp = await get_tenant_or_404(db, Competition, org.id, reg.competition_id)
    results = await competition_results(db, org.id, event, comp)
    await db.commit()
    row = next((r for r in results.rows if r.registration_id == str(reg.id)), None)
    if row is None:
        raise NotFound("Kein Ergebnis vorhanden.")
    html_doc = pdfs.certificate_html(
        row,
        comp.title_de,
        event.name,
        event.year,
        gender_scoring=comp.gender_scoring,
        scheme=comp.age_class_scheme,
        offset_lines=event.certificate_offset_lines,
        background=event.certificate_background,
        bg_mime=event.certificate_background_mime,
    )
    return Response(await pdfs.render_pdf(html_doc), media_type="application/pdf")


@router.get("/results")
async def public_results(org: PublicOrg, db: DB, event_id: uuid.UUID | None = None) -> dict:
    stmt = tenant_select(Event, org.id).order_by(Event.event_date.desc().nullslast())
    events = list((await db.execute(stmt)).scalars())
    event = next((e for e in events if event_id is None or e.id == event_id), None)
    if event is None:
        if event_id is not None:
            raise NotFound("Veranstaltung nicht gefunden.")
        return {"events": [], "event": None, "competitions": []}
    results = await event_results(db, org.id, event)
    return {
        "events": [{"id": str(e.id), "name": e.name, "year": e.year} for e in events],
        "event": {"id": str(event.id), "name": event.name, "year": event.year},
        "competitions": [
            {
                "competition": _competition_public(cr.competition),
                "rows": [
                    row_to_public(r)
                    for r in cr.rows
                    if r.consent_publish and r.finish_seconds is not None
                ],
            }
            for cr in results
        ],
    }


@router.get("/sponsors")
async def public_sponsors(org: PublicOrg, db: DB) -> list[dict]:
    bucket = await settings_service.get(db, org.id, "sponsor_bucket_url")
    await db.commit()
    return await sponsors.public_sponsors(db, org.id, org.slug, bucket)


@router.get("/sponsors/{sponsor_id}/image")
async def sponsor_image(org: PublicOrg, db: DB, sponsor_id: str) -> Response:
    s = await get_tenant_or_404(db, Sponsor, org.id, sponsor_id)
    return Response(s.image, media_type=s.mime, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/assets/{key}")
async def site_asset(org: PublicOrg, db: DB, key: str) -> Response:
    asset = (
        await db.execute(tenant_select(SiteAsset, org.id).where(SiteAsset.key == key))
    ).scalar_one_or_none()
    if asset is None:
        raise NotFound()
    return Response(
        asset.data, media_type=asset.mime, headers={"Cache-Control": "public, max-age=3600"}
    )


@router.get("/events/{event_id}/competitions")
async def event_competitions(org: PublicOrg, db: DB, event_id: str) -> list[dict]:
    event = await get_tenant_or_404(db, Event, org.id, event_id, "Veranstaltung nicht gefunden.")
    return [_competition_public(c) for c in event.competitions]


@router.post("/payments/webhook")
async def sumup_webhook(org: PublicOrg, db: DB, request: Request) -> dict:
    """Provider webhook. The payload is **not** trusted: we only read an identifier and ask the
    provider for the real status."""
    s = get_settings()
    limiter.check("webhook", _client_ip(request), s.webhook_limit, s.webhook_window_seconds)
    try:
        payload = await request.json()
    except ValueError:
        payload = {}
    checkout_id = str(payload.get("id") or payload.get("checkout_id") or "") or None
    reference = str(payload.get("checkout_reference") or "") or None
    payment = await payments.find_payment_by_checkout(db, org, checkout_id, reference)
    if payment is None:
        return {"ok": True, "handled": False}
    paid = await payments.verify_sumup_payment(db, org, payment)
    return {"ok": True, "handled": True, "paid": paid}

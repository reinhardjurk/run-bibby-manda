"""Registration domain service: create (public/office), bib allocation, manage updates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import BadRequest, Conflict, NotFound, ServiceUnavailable
from app.core.scoping import get_tenant_or_404, tenant_select
from app.core.security import encrypt_field, hash_token, new_token
from app.db.models import (
    BibAssignment,
    Competition,
    Event,
    Organization,
    Participant,
    Payment,
    Registration,
)
from app.payments.iban import is_valid_iban, mask_iban, new_mandate_reference, normalize_iban
from app.payments.sumup import PaymentProviderError, make_client
from app.registrations.bibs import BibRangeFull, next_bib_in_range, next_bib_outside_ranges
from app.registrations.identity import match_key
from app.registrations.pricing import price_cents
from app.registrations.schemas import ManageUpdate, RegistrationCreate
from app.settings import service as settings_service


def manage_url(org: Organization, token: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/{org.slug}/manage?token={token}"


def registration_open(event: Event, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return event.registration_deadline is None or now <= event.registration_deadline


async def load_event_competition(
    db: AsyncSession, org_id: uuid.UUID, event_id: uuid.UUID, competition_id: uuid.UUID
) -> tuple[Event, Competition]:
    event = await get_tenant_or_404(db, Event, org_id, event_id, "Veranstaltung nicht gefunden.")
    comp = await get_tenant_or_404(
        db, Competition, org_id, competition_id, "Strecke nicht gefunden.", event_id=event.id
    )
    return event, comp


async def assign_bib(
    db: AsyncSession, event: Event, competition: Competition, reg: Registration
) -> int:
    """Allocates the next bib number under a transaction-bound advisory lock per event.

    Must be the **last** step before commit; no external call may happen while the lock is held.
    """
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:eid))"), {"eid": str(event.id)})
    assigned = set(
        (
            await db.execute(
                select(BibAssignment.bib_number).where(BibAssignment.event_id == event.id)
            )
        ).scalars()
    )
    ranges = [
        (c.bib_range_start, c.bib_range_end)
        for c in event.competitions
        if c.bib_range_start is not None and c.bib_range_end is not None
    ]
    try:
        if competition.bib_range_start is not None and competition.bib_range_end is not None:
            number = next_bib_in_range(
                assigned, competition.bib_range_start, competition.bib_range_end
            )
        else:
            number = next_bib_outside_ranges(assigned, event.bib_start_number, ranges)
    except BibRangeFull as exc:
        raise Conflict(
            "Der Startnummernkreis dieser Strecke ist voll. Bitte wenden Sie sich an das "
            "Wettkampfbüro."
        ) from exc
    db.add(
        BibAssignment(
            organization_id=event.organization_id,
            event_id=event.id,
            registration_id=reg.id,
            bib_number=number,
        )
    )
    return number


async def get_or_create_participant(
    db: AsyncSession, org_id: uuid.UUID, data: RegistrationCreate
) -> Participant:
    key = match_key(data.first_name, data.last_name, data.birth_date)
    existing = (
        await db.execute(tenant_select(Participant, org_id).where(Participant.match_key == key))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    p = Participant(
        organization_id=org_id,
        first_name=data.first_name,
        last_name=data.last_name,
        birth_date=data.birth_date,
        gender=data.gender,
        match_key=key,
    )
    db.add(p)
    return p


async def build_payment(
    db: AsyncSession, org: Organization, event: Event, data: RegistrationCreate, amount: int
) -> Payment:
    payment = Payment(
        id=uuid.uuid4(), organization_id=org.id, method=data.payment_method, amount_cents=amount
    )
    if data.payment_method == "sepa_debit":
        if not data.iban or not is_valid_iban(data.iban):
            raise BadRequest("Die IBAN ist ungültig.")
        iban = normalize_iban(data.iban)
        payment.iban_encrypted = encrypt_field(iban)
        payment.iban_masked = mask_iban(iban)
        payment.account_holder = data.account_holder or f"{data.first_name} {data.last_name}"
        prefix = await settings_service.get(db, org.id, "sepa_mandate_prefix")
        payment.mandate_reference = new_mandate_reference(prefix, event.year)
    if amount == 0:
        payment.status = "paid"
        payment.paid_at = datetime.now(UTC)
    return payment


async def sumup_credentials(db: AsyncSession, org_id: uuid.UUID) -> tuple[str, str] | None:
    key = await settings_service.get_secret(db, org_id, "sumup_api_key")
    merchant = await settings_service.get(db, org_id, "sumup_merchant_code")
    if key and merchant:
        return key, merchant
    return None


async def start_checkout(
    db: AsyncSession, org: Organization, event: Event, payment: Payment, token: str
) -> str:
    """Creates a hosted checkout. Called **outside** any DB transaction / lock."""
    creds = await sumup_credentials(db, org.id)
    if creds is None:
        raise BadRequest("Online-Zahlung ist für diese Veranstaltung nicht verfügbar.")
    client = make_client(*creds)
    reference = f"{payment.id}-{new_token(4)}"
    try:
        result = await client.create_checkout(
            amount_cents=payment.amount_cents,
            reference=reference,
            description=f"Startgeld {event.name} {event.year}",
            redirect_url=manage_url(org, token),
        )
    except PaymentProviderError as exc:
        raise ServiceUnavailable(
            "Der Zahlungsanbieter ist derzeit nicht erreichbar. Die Anmeldung wurde nicht "
            "gespeichert – bitte versuchen Sie es später erneut oder wählen Sie eine andere "
            "Zahlart."
        ) from exc
    payment.provider_checkout_id = result.checkout_id
    payment.provider_checkout_reference = reference
    return result.hosted_url


async def create_registration(
    db: AsyncSession,
    org: Organization,
    data: RegistrationCreate,
    *,
    enforce_deadline: bool = True,
    status: str = "confirmed",
) -> tuple[Registration, str, str | None]:
    """Returns (registration, plaintext manage token, checkout url). Commits on success."""
    event, comp = await load_event_competition(db, org.id, data.event_id, data.competition_id)
    if enforce_deadline and not registration_open(event):
        raise BadRequest("Der Meldeschluss ist bereits verstrichen.")
    if not data.consent_data:
        raise BadRequest("Die Einwilligung zur Datenverarbeitung ist erforderlich.")
    options = event.tshirt_option_list
    if options and data.tshirt_size and data.tshirt_size not in options:
        raise BadRequest("Ungültige T-Shirt-Größe.")
    amount = price_cents(
        data.birth_date, event.youth_cutoff_date, comp.price_adult_cents, comp.price_youth_cents
    )
    token = new_token()
    payment = await build_payment(db, org, event, data, amount)

    checkout_url: str | None = None
    if data.payment_method == "sumup" and amount > 0:
        # End the read-only transaction first: the provider call happens with no DB
        # transaction open and no lock held (expire_on_commit=False keeps objects usable).
        await db.commit()
        checkout_url = await start_checkout(db, org, event, payment, token)

    participant = await get_or_create_participant(db, org.id, data)
    reg = Registration(
        organization_id=org.id,
        event_id=event.id,
        competition_id=comp.id,
        status=status,
        email=str(data.email),
        language=data.language,
        team_name=data.team_name,
        tshirt_size=data.tshirt_size,
        postal_code=data.postal_code,
        heard_about=data.heard_about,
        consent_data=data.consent_data,
        consent_publish=data.consent_publish,
        manage_token_hash=hash_token(token, "manage"),
    )
    reg.participant = participant
    payment.registration_id = reg.id
    reg.payment = payment
    db.add(reg)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        constraint = getattr(getattr(exc, "orig", None), "__cause__", None)
        name = getattr(constraint, "constraint_name", "") or str(exc.orig)
        if "uq_registration_event_participant" in name or "uq_participant_org_match" in name:
            raise Conflict("Diese Person ist für diese Veranstaltung bereits angemeldet.") from exc
        raise
    try:
        await assign_bib(db, event, comp, reg)  # last step: lock held only until commit
        await db.commit()
    except IntegrityError as exc:  # pragma: no cover - lock makes this unreachable
        await db.rollback()
        raise Conflict("Startnummernvergabe fehlgeschlagen, bitte erneut versuchen.") from exc
    await db.refresh(reg)
    return reg, token, checkout_url


async def get_by_manage_token(db: AsyncSession, org: Organization, token: str) -> Registration:
    reg = (
        await db.execute(
            tenant_select(Registration, org.id).where(
                Registration.manage_token_hash == hash_token(token, "manage")
            )
        )
    ).scalar_one_or_none()
    if reg is None:
        raise NotFound("Dieser Verwaltungslink ist ungültig.")
    return reg


async def apply_manage_update(
    db: AsyncSession, org: Organization, reg: Registration, data: ManageUpdate
) -> Registration:
    if reg.is_frozen:
        raise Conflict("Die Laufzeit ist bereits berechnet – Änderungen sind nicht mehr möglich.")
    event = await get_tenant_or_404(db, Event, org.id, reg.event_id)
    if data.email is not None:
        reg.email = str(data.email)
    if data.team_name is not None:
        reg.team_name = data.team_name.strip() or None
    if data.tshirt_size is not None:
        options = event.tshirt_option_list
        if options and data.tshirt_size and data.tshirt_size not in options:
            raise BadRequest("Ungültige T-Shirt-Größe.")
        reg.tshirt_size = data.tshirt_size or None
    if data.competition_id is not None and data.competition_id != reg.competition_id:
        comp = await get_tenant_or_404(
            db,
            Competition,
            org.id,
            data.competition_id,
            "Strecke nicht gefunden.",
            event_id=event.id,
        )
        reg.competition_id = comp.id  # bib number never changes on a competition change
        if reg.payment and reg.payment.status == "pending":
            reg.payment.amount_cents = price_cents(
                reg.participant.birth_date,
                event.youth_cutoff_date,
                comp.price_adult_cents,
                comp.price_youth_cents,
            )
    await db.commit()
    await db.refresh(reg)
    return reg


async def team_names(db: AsyncSession, org_id: uuid.UUID, query: str) -> list[str]:
    stmt = (
        select(Registration.team_name)
        .where(Registration.organization_id == org_id)
        .where(Registration.team_name.is_not(None))
        .where(func.lower(Registration.team_name).like(f"%{query.lower()}%"))
        .distinct()
        .order_by(Registration.team_name)
        .limit(20)
    )
    return [t for t in (await db.execute(stmt)).scalars() if t]

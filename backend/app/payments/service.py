"""Payment status synchronisation with the provider (server-side verification only)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoping import tenant_select
from app.db.models import Event, Organization, Payment, Registration
from app.payments.sumup import PaymentProviderError, make_client
from app.registrations.service import start_checkout, sumup_credentials

log = logging.getLogger("bibby.payments")


async def verify_sumup_payment(db: AsyncSession, org: Organization, payment: Payment) -> bool:
    """Asks the provider for the checkout status and marks the payment paid on success.

    Returns True when the payment is (now) paid. Never trusts client-provided state.
    """
    if payment.method != "sumup" or payment.status == "paid" or not payment.provider_checkout_id:
        return payment.status == "paid"
    creds = await sumup_credentials(db, org.id)
    if creds is None:
        return False
    # No transaction is held open during the provider call.
    await db.commit()
    try:
        status = await make_client(*creds).get_checkout(payment.provider_checkout_id)
    except PaymentProviderError as exc:
        log.warning("payment verification unavailable for %s: %s", payment.id, exc)
        return False
    if status.status == "PAID":
        payment.status = "paid"
        payment.paid_at = datetime.now(UTC)
        payment.provider_transaction_code = status.transaction_code
        await db.commit()
        return True
    return False


async def fresh_checkout_url(
    db: AsyncSession, org: Organization, reg: Registration, token: str
) -> str | None:
    """A new hosted checkout for a still-open online payment (hosted pages expire)."""
    payment = reg.payment
    if payment is None or payment.method != "sumup" or payment.status != "pending":
        return None
    event = (
        await db.execute(tenant_select(Event, org.id).where(Event.id == reg.event_id))
    ).scalar_one()
    await db.commit()
    url = await start_checkout(db, org, event, payment, token)
    await db.commit()
    return url


async def find_payment_by_checkout(
    db: AsyncSession, org: Organization, checkout_id: str | None, reference: str | None
) -> Payment | None:
    stmt = tenant_select(Payment, org.id)
    if checkout_id:
        stmt = stmt.where(Payment.provider_checkout_id == checkout_id)
    elif reference:
        stmt = stmt.where(Payment.provider_checkout_reference == reference)
    else:
        return None
    return (await db.execute(stmt)).scalar_one_or_none()


def payment_id_from_reference(reference: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(reference.rsplit("-", 1)[0])
    except ValueError:
        return None

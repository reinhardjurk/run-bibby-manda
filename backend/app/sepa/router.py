"""SEPA direct debit CSV export."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select

from app.core.deps import DB, Principal, require_roles
from app.core.scoping import get_tenant_or_404, tenant_select
from app.core.security import decrypt_field
from app.db.models import Event, Payment, Registration
from app.settings import service as settings_service

router = APIRouter(prefix="/api/{slug}/team/sepa", tags=["sepa"])
Sepa = Annotated[Principal, Depends(require_roles("sepa"))]


async def _pending(db, org_id, event: Event, include_exported: bool) -> list[Registration]:
    stmt = (
        tenant_select(Registration, org_id)
        .join(Payment, Payment.registration_id == Registration.id)
        .where(Registration.event_id == event.id, Registration.status != "cancelled")
        .where(Payment.method == "sepa_debit", Payment.status != "cancelled")
    )
    if not include_exported:
        stmt = stmt.where(Payment.sepa_exported_at.is_(None))
    return list((await db.execute(stmt)).scalars().unique())


@router.get("/summary")
async def sepa_summary(principal: Sepa, db: DB, event_id: uuid.UUID) -> dict:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    rows = await db.execute(
        select(
            Payment.sepa_exported_at.is_(None),
            func.count(),
            func.coalesce(func.sum(Payment.amount_cents), 0),
        )
        .join(Registration, Registration.id == Payment.registration_id)
        .where(
            Payment.organization_id == principal.organization_id, Registration.event_id == event.id
        )
        .where(Payment.method == "sepa_debit", Payment.status != "cancelled")
        .group_by(Payment.sepa_exported_at.is_(None))
    )
    out = {"open": {"count": 0, "amount_cents": 0}, "exported": {"count": 0, "amount_cents": 0}}
    for is_open, n, amount in rows:
        out["open" if is_open else "exported"] = {"count": n, "amount_cents": int(amount)}
    values = await settings_service.get_all(db, principal.organization_id)
    return {
        **out,
        "creditor_name": values["sepa_creditor_name"],
        "creditor_id": values["sepa_creditor_id"],
    }


@router.post("/export.csv")
async def sepa_export(
    principal: Sepa, db: DB, event_id: uuid.UUID, include_exported: bool = False
) -> Response:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    regs = await _pending(db, principal.organization_id, event, include_exported)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        [
            "Name",
            "Kontoinhaber",
            "IBAN",
            "Mandatsreferenz",
            "Betrag",
            "Verwendungszweck",
            "Startnummer",
            "E-Mail",
        ]
    )
    now = datetime.now(UTC)
    for r in regs:
        p = r.payment
        assert p is not None
        iban = decrypt_field(p.iban_encrypted) if p.iban_encrypted else None
        name = f"{r.participant.first_name} {r.participant.last_name}"
        w.writerow(
            [
                name,
                p.account_holder or name,
                iban or "IBAN-NICHT-ENTSCHLUESSELBAR",
                p.mandate_reference or "",
                f"{p.amount_cents / 100:.2f}".replace(".", ","),
                f"Startgeld {event.name} {event.year} - {name}",
                r.bib_number or "",
                r.email,
            ]
        )
        if p.sepa_exported_at is None:
            p.sepa_exported_at = now
    await db.commit()
    filename = f"sepa_{event.year}_{event.name.replace(' ', '_')}.csv"
    return Response(
        "﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Row-Count": str(len(regs)),
        },
    )

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import DB, Principal, require_roles
from app.core.scoping import get_tenant_or_404
from app.db.models import Event
from app.stats.service import event_statistics

router = APIRouter(prefix="/api/{slug}/team/stats", tags=["stats"])
Viewer = Annotated[Principal, Depends(require_roles("viewer", "race_office"))]


@router.get("")
async def stats(principal: Viewer, db: DB, event_id: uuid.UUID) -> dict:
    event = await get_tenant_or_404(
        db, Event, principal.organization_id, event_id, "Veranstaltung nicht gefunden."
    )
    return await event_statistics(db, principal.organization_id, event)

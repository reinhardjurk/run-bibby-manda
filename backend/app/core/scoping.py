"""Central tenant scoping layer.

Every tenant query goes through these helpers so that the `organization_id` filter is enforced
in one tested place instead of scattered WHERE clauses. Foreign IDs resolve to 404 (never 403)
so that no endpoint acts as an existence oracle.
"""

from __future__ import annotations

import uuid
from typing import Any, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.db.base import Base

M = TypeVar("M", bound=Base)


def tenant_select(model: type[M], organization_id: uuid.UUID) -> Select[tuple[M]]:
    """`SELECT ... FROM model WHERE model.organization_id = :org`."""
    return select(model).where(model.organization_id == organization_id)  # type: ignore[attr-defined]


async def get_tenant_or_404(
    db: AsyncSession,
    model: type[M],
    organization_id: uuid.UUID,
    obj_id: uuid.UUID | str | None,
    detail: str = "Nicht gefunden.",
    **extra: Any,
) -> M:
    """Loads a tenant-owned row by id; a foreign or unknown id yields 404."""
    try:
        parsed = uuid.UUID(str(obj_id))
    except (ValueError, TypeError) as exc:
        raise NotFound(detail) from exc
    stmt = tenant_select(model, organization_id).where(model.id == parsed)  # type: ignore[attr-defined]
    for key, value in extra.items():
        stmt = stmt.where(getattr(model, key) == value)
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        raise NotFound(detail)
    return obj

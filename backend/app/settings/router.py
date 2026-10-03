"""Organization settings: mail mode/templates, SEPA creditor data, SumUp credentials, logo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.core.deps import DB, Principal, require_roles
from app.core.errors import BadRequest, Forbidden
from app.core.scoping import tenant_select
from app.db.models import SiteAsset
from app.settings import service
from app.settings.service import ADMIN_ONLY_KEYS, DEFAULTS, SECRET_KEYS
from app.sponsors.service import normalize_logo

router = APIRouter(prefix="/api/{slug}/team/settings", tags=["settings"])
Office = Annotated[Principal, Depends(require_roles("race_office", "admin"))]


class SettingsUpdate(BaseModel):
    values: dict[str, str]
    confirm_live_mail: bool = False


@router.get("")
async def get_settings_view(principal: Office, db: DB) -> dict:
    return service.masked_view(await service.get_all(db, principal.organization_id))


@router.put("")
async def update_settings(principal: Office, db: DB, data: SettingsUpdate) -> dict:
    for key, value in data.values.items():
        if key not in DEFAULTS:
            raise BadRequest(f"Unbekannte Einstellung: {key}")
        if key in ADMIN_ONLY_KEYS and not principal.has_role("admin"):
            raise Forbidden("Diese Einstellung darf nur ein Org-Admin ändern.")
        if key == "mail_mode":
            if value not in ("live", "test", "off"):
                raise BadRequest("Mailmodus muss live, test oder off sein.")
            if value == "live" and not data.confirm_live_mail:
                raise BadRequest("Umschalten auf 'live' erfordert eine Bestätigung.")
        if key == "sponsor_mode" and value not in ("rotation", "marquee"):
            raise BadRequest("Sponsorenmodus muss rotation oder marquee sein.")
        if key == "sponsor_marquee_seconds":
            try:
                secs = int(value)
            except ValueError as exc:
                raise BadRequest("Laufbanddauer muss eine Zahl sein.") from exc
            if not 5 <= secs <= 300:
                raise BadRequest("Laufbanddauer muss zwischen 5 und 300 Sekunden liegen.")
        if key in SECRET_KEYS and value == "":
            continue  # empty secret in the form = keep existing value
        await service.set_value(db, principal.organization_id, key, value)
    await db.commit()
    return service.masked_view(await service.get_all(db, principal.organization_id))


@router.delete("/secret/{key}")
async def clear_secret(principal: Office, db: DB, key: str) -> dict:
    if key not in SECRET_KEYS or not principal.has_role("admin"):
        raise Forbidden("Diese Einstellung darf nur ein Org-Admin ändern.")
    await service.set_value(db, principal.organization_id, key, "")
    await db.commit()
    return service.masked_view(await service.get_all(db, principal.organization_id))


@router.post("/logo")
async def upload_logo(principal: Office, db: DB, file: UploadFile = File(...)) -> dict:
    data, mime = normalize_logo(await file.read())
    existing = (
        await db.execute(
            tenant_select(SiteAsset, principal.organization_id).where(SiteAsset.key == "logo")
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            SiteAsset(organization_id=principal.organization_id, key="logo", data=data, mime=mime)
        )
    else:
        existing.data, existing.mime = data, mime
    await db.commit()
    return {"ok": True}


@router.delete("/logo", status_code=204, response_model=None)
async def delete_logo(principal: Office, db: DB) -> None:
    existing = (
        await db.execute(
            tenant_select(SiteAsset, principal.organization_id).where(SiteAsset.key == "logo")
        )
    ).scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.commit()

"""Sponsor administration: uploads, tiers, display settings, S3 bucket mode."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from app.core.deps import DB, Principal, require_roles
from app.core.errors import BadRequest
from app.core.scoping import get_tenant_or_404, tenant_select
from app.db.models import Sponsor
from app.settings import service as settings_service
from app.sponsors import service

router = APIRouter(prefix="/api/{slug}/team/sponsors", tags=["sponsors"])
Manager = Annotated[Principal, Depends(require_roles("sponsor_management"))]


class SponsorOut(BaseModel):
    id: uuid.UUID
    tier: int
    name: str | None
    url: str | None
    image_url: str


def _out(s: Sponsor, slug: str) -> SponsorOut:
    return SponsorOut(
        id=s.id,
        tier=s.tier,
        name=s.name,
        url=s.url,
        image_url=f"/api/public/{slug}/sponsors/{s.id}/image",
    )


@router.get("", response_model=list[SponsorOut])
async def list_sponsors(principal: Manager, db: DB, slug: str) -> list[SponsorOut]:
    rows = (
        await db.execute(
            tenant_select(Sponsor, principal.organization_id).order_by(
                Sponsor.tier, Sponsor.created_at
            )
        )
    ).scalars()
    return [_out(s, slug) for s in rows]


@router.post("", response_model=SponsorOut, status_code=201)
async def upload_sponsor(
    principal: Manager,
    db: DB,
    slug: str,
    file: UploadFile = File(...),
    tier: int = Form(3),
    name: str = Form(""),
    url: str = Form(""),
) -> SponsorOut:
    if not 1 <= tier <= 5:
        raise BadRequest("Klasse muss zwischen 1 und 5 liegen.")
    data, mime = service.normalize_logo(await file.read())
    s = Sponsor(
        organization_id=principal.organization_id,
        tier=tier,
        name=name.strip() or None,
        url=url.strip() or None,
        image=data,
        mime=mime,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _out(s, slug)


class SponsorUpdate(BaseModel):
    tier: int | None = None
    name: str | None = None
    url: str | None = None


@router.patch("/{sponsor_id}", response_model=SponsorOut)
async def update_sponsor(
    principal: Manager, db: DB, slug: str, sponsor_id: str, data: SponsorUpdate
) -> SponsorOut:
    s = await get_tenant_or_404(
        db, Sponsor, principal.organization_id, sponsor_id, "Sponsor nicht gefunden."
    )
    if data.tier is not None:
        if not 1 <= data.tier <= 5:
            raise BadRequest("Klasse muss zwischen 1 und 5 liegen.")
        s.tier = data.tier
    if data.name is not None:
        s.name = data.name.strip() or None
    if data.url is not None:
        s.url = data.url.strip() or None
    await db.commit()
    await db.refresh(s)
    return _out(s, slug)


@router.delete("/{sponsor_id}", status_code=204, response_model=None)
async def delete_sponsor(principal: Manager, db: DB, sponsor_id: str) -> None:
    s = await get_tenant_or_404(
        db, Sponsor, principal.organization_id, sponsor_id, "Sponsor nicht gefunden."
    )
    await db.delete(s)
    await db.commit()


class DisplaySettings(BaseModel):
    sponsor_mode: str | None = None
    sponsor_marquee_seconds: int | None = None
    sponsor_bucket_url: str | None = None
    sponsor_tier_weights: str | None = None


@router.get("/display")
async def get_display(principal: Manager, db: DB) -> dict:
    values = await settings_service.get_all(db, principal.organization_id)
    return {
        k: values[k]
        for k in (
            "sponsor_mode",
            "sponsor_marquee_seconds",
            "sponsor_bucket_url",
            "sponsor_tier_weights",
        )
    }


@router.put("/display")
async def set_display(principal: Manager, db: DB, data: DisplaySettings) -> dict:
    org_id = principal.organization_id
    if data.sponsor_mode is not None:
        if data.sponsor_mode not in ("rotation", "marquee"):
            raise BadRequest("Modus muss rotation oder marquee sein.")
        await settings_service.set_value(db, org_id, "sponsor_mode", data.sponsor_mode)
    if data.sponsor_marquee_seconds is not None:
        if not 5 <= data.sponsor_marquee_seconds <= 300:
            raise BadRequest("Laufbanddauer muss zwischen 5 und 300 Sekunden liegen.")
        await settings_service.set_value(
            db, org_id, "sponsor_marquee_seconds", str(data.sponsor_marquee_seconds)
        )
    if data.sponsor_tier_weights is not None:
        parts = [p.strip() for p in data.sponsor_tier_weights.split(",")]
        if len(parts) != 5 or not all(p.isdigit() and int(p) > 0 for p in parts):
            raise BadRequest("Klassengewichte: fünf positive Zahlen, durch Komma getrennt.")
        await settings_service.set_value(db, org_id, "sponsor_tier_weights", ",".join(parts))
    validation: dict | None = None
    if data.sponsor_bucket_url is not None:
        url = data.sponsor_bucket_url.strip()
        if url:
            listing = await service.list_bucket(url, use_cache=False)
            if listing.error:
                raise BadRequest(f"Bucket konnte nicht gelesen werden: {listing.error}")
            validation = {"normalized_url": listing.base_url, "found": listing.counts()}
            url = listing.base_url
        await settings_service.set_value(db, org_id, "sponsor_bucket_url", url)
    await db.commit()
    values = await settings_service.get_all(db, org_id)
    return {
        **{
            k: values[k]
            for k in (
                "sponsor_mode",
                "sponsor_marquee_seconds",
                "sponsor_bucket_url",
                "sponsor_tier_weights",
            )
        },
        "bucket_validation": validation,
    }

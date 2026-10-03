"""Sponsor logos: uploaded images (normalised server-side) or an S3 bucket listing."""

from __future__ import annotations

import csv
import io
import logging
import re
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest
from app.core.scoping import tenant_select
from app.db.models import Sponsor

log = logging.getLogger("bibby.sponsors")

MAX_LOGO_EDGE = 600
TIER_FOLDERS = {"gold": 1, "silber": 2, "silver": 2, "bronze": 3}
_cache: dict[str, tuple[float, list[dict]]] = {}
CACHE_SECONDS = 60


def normalize_logo(data: bytes) -> tuple[bytes, str]:
    """Re-encodes an uploaded image (strips metadata, bounds size). Returns (bytes, mime)."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise BadRequest("Die Datei ist kein lesbares Bild.") from exc
    img.thumbnail((MAX_LOGO_EDGE, MAX_LOGO_EDGE))
    out = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P"):
        img.convert("RGBA").save(out, format="PNG", optimize=True)
        return out.getvalue(), "image/png"
    img.convert("RGB").save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue(), "image/jpeg"


def normalize_bucket_url(url: str) -> str:
    """Maps a Scaleway/S3 *website* endpoint to the S3 API endpoint (needed for ListObjectsV2).

    `https://bucket.s3-website.fr-par.scw.cloud/prefix` → `https://bucket.s3.fr-par.scw.cloud/prefix`
    """
    parts = urlsplit(url.strip())
    host = re.sub(r"\.s3-website[.-]", ".s3.", parts.netloc)
    host = re.sub(r"\.s3-website\.", ".s3.", host)
    return urlunsplit((parts.scheme or "https", host, parts.path.rstrip("/"), "", ""))


@dataclass
class BucketListing:
    base_url: str
    by_tier: dict[int, list[dict]] = field(default_factory=dict)
    error: str | None = None

    def counts(self) -> dict[str, int]:
        return {str(t): len(v) for t, v in sorted(self.by_tier.items())}


async def list_bucket(base_url: str, use_cache: bool = True) -> BucketListing:
    base = normalize_bucket_url(base_url)
    now = time.monotonic()
    if use_cache and base in _cache and _cache[base][0] > now - CACHE_SECONDS:
        return _listing_from_items(base, _cache[base][1])
    parts = urlsplit(base)
    prefix = parts.path.lstrip("/")
    prefix = f"{prefix}/" if prefix else ""
    list_url = urlunsplit((parts.scheme, parts.netloc, "/", f"list-type=2&prefix={prefix}", ""))
    items: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(list_url)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns = {"s3": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
            tag = "s3:Contents" if ns else "Contents"
            key_tag = "s3:Key" if ns else "Key"
            for node in root.findall(tag, ns):
                key_node = node.find(key_tag, ns)
                if key_node is not None and key_node.text:
                    items.append({"key": key_node.text})
            names = await _load_csv(client, base, prefix, items)
    except (httpx.HTTPError, ET.ParseError) as exc:
        log.warning("sponsor bucket listing failed for %s: %s", base, exc)
        return BucketListing(base_url=base, error="Bucket nicht erreichbar oder nicht lesbar.")
    enriched = []
    for it in items:
        rel = it["key"][len(prefix) :] if it["key"].startswith(prefix) else it["key"]
        folder, _, filename = rel.partition("/")
        tier = TIER_FOLDERS.get(folder.lower())
        if (
            not tier
            or not filename
            or not re.search(r"\.(png|jpe?g|gif|webp|svg)$", filename, re.I)
        ):
            continue
        meta = names.get(filename, {})
        enriched.append(
            {
                "tier": tier,
                "image_url": f"{base}/{folder}/{filename}",
                "name": meta.get("name") or filename.rsplit(".", 1)[0],
                "url": meta.get("url") or None,
            }
        )
    _cache[base] = (now, enriched)
    return _listing_from_items(base, enriched)


async def _load_csv(
    client: httpx.AsyncClient, base: str, prefix: str, items: list[dict]
) -> dict[str, dict]:
    if not any(it["key"] == f"{prefix}sponsors.csv" for it in items):
        return {}
    try:
        resp = await client.get(f"{base}/sponsors.csv")
        resp.raise_for_status()
    except httpx.HTTPError:
        return {}
    names: dict[str, dict] = {}
    for row in csv.reader(io.StringIO(resp.text)):
        if len(row) >= 2 and row[0].strip() and row[0].strip().lower() != "dateiname":
            names[row[0].strip()] = {
                "name": row[1].strip(),
                "url": row[2].strip() if len(row) > 2 else "",
            }
    return names


def _listing_from_items(base: str, items: list[dict]) -> BucketListing:
    listing = BucketListing(base_url=base)
    for it in items:
        listing.by_tier.setdefault(it["tier"], []).append(it)
    return listing


async def public_sponsors(
    db: AsyncSession, org_id: uuid.UUID, slug: str, bucket_url: str
) -> list[dict]:
    if bucket_url:
        listing = await list_bucket(bucket_url)
        return [it for tier in sorted(listing.by_tier) for it in listing.by_tier[tier]]
    rows = (
        await db.execute(tenant_select(Sponsor, org_id).order_by(Sponsor.tier, Sponsor.created_at))
    ).scalars()
    return [
        {
            "id": str(s.id),
            "tier": s.tier,
            "name": s.name,
            "url": s.url,
            "image_url": f"/api/public/{slug}/sponsors/{s.id}/image",
        }
        for s in rows
    ]

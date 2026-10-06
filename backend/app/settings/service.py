"""Per-organization key/value settings with defaults."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import decrypt_field, encrypt_field
from app.db.models import OrgSetting

DEFAULTS: dict[str, str] = {
    "mail_mode": "off",  # live | test | off
    "mail_sender_name": "",
    "mail_sender_local_part": "",  # local part of the sender; empty = noreply-<slug>
    "mail_reply_to": "",
    "mail_subject_de": "Ihre Anmeldung – Verwaltungslink",
    "mail_subject_en": "Your registration – management link",
    "mail_body_de": (
        "Vielen Dank für Ihre Anmeldung!\n\nÜber folgenden persönlichen Link können Sie Ihre "
        "Anmeldung einsehen und ändern sowie Startnummer und Urkunde herunterladen:\n{link}\n\n"
        "Bitte bewahren Sie diesen Link auf."
    ),
    "mail_body_en": (
        "Thank you for registering!\n\nUse this personal link to view and change your "
        "registration and to download your bib and certificate:\n{link}\n\nPlease keep this link."
    ),
    "sponsor_mode": "rotation",  # rotation | marquee
    "sponsor_marquee_seconds": "30",
    "sponsor_bucket_url": "",
    "sponsor_tier_weights": "5,3,2,1,1",
    "sepa_creditor_name": "",
    "sepa_creditor_id": "",
    "sepa_mandate_prefix": "BIBBY",
    "sumup_api_key": "",  # stored encrypted
    "sumup_merchant_code": "",
    "plausibility_threshold_seconds": "3",
}

SECRET_KEYS = {"sumup_api_key"}
PUBLIC_KEYS = {"sponsor_mode", "sponsor_marquee_seconds", "sponsor_tier_weights"}
ADMIN_ONLY_KEYS = {"mail_mode", "mail_sender_local_part", "sumup_api_key", "sumup_merchant_code"}

LOCAL_PART_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._+-]{0,62}[a-z0-9])?$")


def sender_domain() -> str:
    """The platform's fixed sending domain (domain part of BIBBY_MAIL_DEFAULT_SENDER)."""
    return get_settings().mail_default_sender.rsplit("@", 1)[-1]


def normalize_local_part(value: str) -> str:
    """Validates an organization's sender local part; raises ValueError with a German message."""
    local = value.strip().lower()
    if not local:
        return ""
    if "@" in local:
        raise ValueError(
            f"Bitte nur den Teil vor dem @ eingeben – die Domain ist fest @{sender_domain()}."
        )
    if not LOCAL_PART_RE.match(local):
        raise ValueError(
            "Absenderadresse: nur Kleinbuchstaben, Ziffern sowie . _ + - sind erlaubt "
            "(max. 64 Zeichen, nicht mit . oder - beginnen/enden)."
        )
    return local


def sender_address(values: dict[str, str], slug: str) -> str:
    """Organization-specific no-reply sender on the fixed platform domain."""
    local = values.get("mail_sender_local_part", "") or f"noreply-{slug}"
    return f"{local}@{sender_domain()}"


async def get_all(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, str]:
    rows = (
        await db.execute(select(OrgSetting).where(OrgSetting.organization_id == organization_id))
    ).scalars()
    values = dict(DEFAULTS)
    for row in rows:
        values[row.key] = row.value
    return values


async def get(db: AsyncSession, organization_id: uuid.UUID, key: str) -> str:
    row = (
        await db.execute(
            select(OrgSetting)
            .where(OrgSetting.organization_id == organization_id)
            .where(OrgSetting.key == key)
        )
    ).scalar_one_or_none()
    return row.value if row is not None else DEFAULTS.get(key, "")


async def get_secret(db: AsyncSession, organization_id: uuid.UUID, key: str) -> str:
    raw = await get(db, organization_id, key)
    if not raw:
        return ""
    return decrypt_field(raw) or ""


async def set_value(db: AsyncSession, organization_id: uuid.UUID, key: str, value: str) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    if key in SECRET_KEYS and value:
        value = encrypt_field(value)
    row = (
        await db.execute(
            select(OrgSetting)
            .where(OrgSetting.organization_id == organization_id)
            .where(OrgSetting.key == key)
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(OrgSetting(organization_id=organization_id, key=key, value=value))
    else:
        row.value = value


def masked_view(values: dict[str, str]) -> dict[str, str | bool]:
    """Settings as shown to admins: secrets are never returned, only whether they are set."""
    out: dict[str, str | bool] = {}
    for k, v in values.items():
        if k in SECRET_KEYS:
            out[f"{k}_set"] = bool(v)
        else:
            out[k] = v
    return out

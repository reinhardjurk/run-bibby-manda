"""Transactional e-mail (Scaleway TEM) with per-organization mode `live | test | off`.

Mail is sent as a background task **after** the registration transaction is committed, and a
failing mail never fails a registration.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.db.session import get_sessionmaker
from app.settings import service as settings_service

log = logging.getLogger("bibby.mail")


@dataclass
class OutgoingMail:
    to: str
    subject: str
    text: str
    sender_name: str = ""
    reply_to: str = ""


class MailSender:
    """Default sender: HTTP call to the transactional mail API. Replaced by a fake in tests."""

    async def send(self, mail: OutgoingMail) -> None:
        s = get_settings()
        if not s.mail_api_key or not s.mail_project_id:
            log.warning("mail not configured – skipping mail to %s", mail.to)
            return
        payload = {
            "from": {"email": s.mail_default_sender, "name": mail.sender_name or "Bibby"},
            "to": [{"email": mail.to}],
            "subject": mail.subject,
            "text": mail.text,
            "project_id": s.mail_project_id,
        }
        if mail.reply_to:
            payload["additional_headers"] = [{"key": "Reply-To", "value": mail.reply_to}]
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                s.mail_api_url, json=payload, headers={"X-Auth-Token": s.mail_api_key}
            )
            resp.raise_for_status()


sender: MailSender = MailSender()


def set_sender(new_sender: MailSender) -> None:
    global sender
    sender = new_sender


def render_confirmation(values: dict[str, str], language: str, link: str) -> tuple[str, str]:
    lang = "en" if language == "en" else "de"
    subject = values.get(f"mail_subject_{lang}", "")
    body = values.get(f"mail_body_{lang}", "").replace("{link}", link)
    return subject, body


async def send_confirmation_mail(
    organization_id: uuid.UUID, to: str, language: str, link: str
) -> None:
    """Background task entry point. Opens its own session; swallows and logs any failure."""
    try:
        async with get_sessionmaker()() as db:
            values = await settings_service.get_all(db, organization_id)
        mode = values.get("mail_mode", "off")
        if mode == "off":
            log.info("mail mode off – not sending confirmation to %s", to)
            return
        recipient = get_settings().mail_test_recipient if mode == "test" else to
        subject, body = render_confirmation(values, language, link)
        if mode == "test":
            subject = f"[TEST → {to}] {subject}"
        await sender.send(
            OutgoingMail(
                to=recipient,
                subject=subject,
                text=body,
                sender_name=values.get("mail_sender_name", ""),
                reply_to=values.get("mail_reply_to", ""),
            )
        )
    except (httpx.HTTPError, OSError) as exc:
        log.error("confirmation mail to %s failed: %s", to, exc)

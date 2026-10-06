"""Migrations are the single source of truth: no drift against the ORM models. Mail robustness."""

from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.db import Base
from app.db.session import get_engine
from app.mail import service as mail_service
from app.mail.service import MailSender

from tests.conftest import create_org, login, registration_payload, setup_event


async def test_migrations_match_models():
    def _compare(sync_conn):
        ctx = MigrationContext.configure(
            sync_conn, opts={"compare_type": True, "compare_server_default": False}
        )
        return compare_metadata(ctx, Base.metadata)

    async with get_engine().connect() as conn:
        diffs = await conn.run_sync(_compare)
    assert diffs == [], f"schema drift between alembic migrations and models: {diffs}"


async def test_health_and_version(client):
    assert (await client.get("/health")).json() == {"status": "ok"}
    v = (await client.get("/version")).json()
    assert v["backend"] == "dev" and v["db_schema"] == "0002_row_level_security"


class FailingSender(MailSender):
    def __init__(self):
        self.calls = 0

    async def send(self, mail):
        self.calls += 1
        import httpx

        raise httpx.ConnectError("mail down")


async def test_mail_failure_never_fails_registration(client):
    await create_org("mailfail")
    s = await login(client, "mailfail")
    await s.put(
        "/api/mailfail/team/settings",
        json={"values": {"mail_mode": "live"}, "confirm_live_mail": True},
    )
    failing = FailingSender()
    mail_service.set_sender(failing)
    ev, comps = await setup_event(s)
    r = await client.post(
        "/api/public/mailfail/registrations", json=registration_payload(ev["id"], comps[0]["id"])
    )
    assert r.status_code == 201
    assert failing.calls == 1
    assert (await s.get(f"/api/mailfail/team/registrations?event_id={ev['id']}")).json()[
        "total"
    ] == 1


async def test_mail_mode_switching_rules(client, mails):
    await create_org("mailmode")
    s = await login(client, "mailmode")
    ev, comps = await setup_event(s)
    # default off → nothing sent
    await client.post(
        "/api/public/mailmode/registrations", json=registration_payload(ev["id"], comps[0]["id"])
    )
    assert mails.sent == []
    # live requires confirmation
    assert (
        await s.put("/api/mailmode/team/settings", json={"values": {"mail_mode": "live"}})
    ).status_code == 400
    assert (
        await s.put(
            "/api/mailmode/team/settings",
            json={"values": {"mail_mode": "live"}, "confirm_live_mail": True},
        )
    ).status_code == 200
    await s.put(
        "/api/mailmode/team/settings",
        json={"values": {"mail_subject_en": "Your bib", "mail_body_en": "Link: {link}"}},
    )
    r = await client.post(
        "/api/public/mailmode/registrations",
        json=registration_payload(ev["id"], comps[0]["id"], language="en"),
    )
    assert len(mails.sent) == 1
    assert (
        mails.sent[0].subject == "Your bib"
        and mails.sent[0].text == f"Link: {r.json()['manage_url']}"
    )
    assert (
        mails.sent[0].to == r.json()["manage_url"]
        and False
        or mails.sent[0].to.endswith("@example.org")
    )


async def test_per_org_sender_address(client, mails):
    from tests.conftest import add_user

    org = await create_org("sender")
    s = await login(client, "sender")
    view = (await s.get("/api/sender/team/settings")).json()
    assert view["mail_sender_domain"] == "example.org"
    assert view["mail_sender_address"] == "noreply-sender@example.org"

    # invalid local parts are rejected with a readable message; full addresses too
    r = await s.put("/api/sender/team/settings", json={"values": {"mail_sender_local_part": "a b"}})
    assert r.status_code == 400
    r = await s.put(
        "/api/sender/team/settings", json={"values": {"mail_sender_local_part": "x@y.de"}}
    )
    assert r.status_code == 400 and "Domain ist fest" in r.json()["detail"]
    r = await s.put(
        "/api/sender/team/settings", json={"values": {"mail_sender_local_part": "Anmeldung-TSV"}}
    )
    assert r.status_code == 200 and r.json()["mail_sender_address"] == "anmeldung-tsv@example.org"

    # only org admins may change it
    await add_user(org, "office@example.org", ("race_office",))
    office = await login(client, "sender", "office@example.org")
    r = await office.put(
        "/api/sender/team/settings", json={"values": {"mail_sender_local_part": "hack"}}
    )
    assert r.status_code == 403

    # the confirmation mail is sent from the organization's address, without Reply-To
    await s.put(
        "/api/sender/team/settings",
        json={"values": {"mail_mode": "live"}, "confirm_live_mail": True},
    )
    ev, comps = await setup_event(s)
    r = await client.post(
        "/api/public/sender/registrations", json=registration_payload(ev["id"], comps[0]["id"])
    )
    assert r.status_code == 201
    assert len(mails.sent) == 1
    assert mails.sent[0].from_address == "anmeldung-tsv@example.org"
    assert mails.sent[0].reply_to == ""

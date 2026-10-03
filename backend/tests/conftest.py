"""Shared fixtures: migrated test database, ASGI client, fake mail + payment provider."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

os.environ.setdefault(
    "BIBBY_DATABASE_URL", "postgresql+asyncpg://bibby:bibby@localhost:5432/bibby_test"
)
os.environ["BIBBY_ENV"] = "test"
os.environ["BIBBY_PAYMENT_PROVIDER"] = "fake"
os.environ["BIBBY_COOKIE_SECURE"] = "false"
os.environ["BIBBY_APP_SECRET"] = "test-app-secret-not-for-production-use"
os.environ["BIBBY_PUBLIC_BASE_URL"] = "http://frontend.test"
os.environ["BIBBY_LOGIN_IP_LIMIT"] = "1000"
os.environ["BIBBY_LOGIN_ACCOUNT_LIMIT"] = "1000"
os.environ["BIBBY_REGISTRATION_LIMIT"] = "1000"
os.environ["BIBBY_WEBHOOK_LIMIT"] = "1000"

import httpx  # noqa: E402
import pytest  # noqa: E402
from app.core.ratelimit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import Base  # noqa: E402
from app.db.models import AppUser, Organization, PlatformAdmin, UserRole  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402
from app.mail import service as mail_service  # noqa: E402
from app.mail.service import MailSender, OutgoingMail  # noqa: E402
from app.main import app  # noqa: E402
from app.payments.sumup import FakeSumUpClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


class CapturingSender(MailSender):
    def __init__(self) -> None:
        self.sent: list[OutgoingMail] = []

    async def send(self, mail: OutgoingMail) -> None:
        self.sent.append(mail)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Runs the real Alembic migrations against the test database (schema source of truth)."""
    env = dict(os.environ)
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
    )


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with get_engine().begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    limiter.reset()
    FakeSumUpClient.checkouts.clear()
    FakeSumUpClient.fail_create = False
    yield


@pytest.fixture
def mails() -> CapturingSender:
    sender = CapturingSender()
    mail_service.set_sender(sender)
    return sender


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class Session:
    """A logged-in HTTP session for one organization user (cookie jar + CSRF header)."""

    def __init__(self, client: httpx.AsyncClient, slug: str, csrf: str) -> None:
        self.client = client
        self.slug = slug
        self.csrf = csrf

    def _h(self, headers: dict | None) -> dict:
        return {"X-CSRF-Token": self.csrf, **(headers or {})}

    async def get(self, path: str, **kw):
        return await self.client.get(path, **kw)

    async def post(self, path: str, headers: dict | None = None, **kw):
        return await self.client.post(path, headers=self._h(headers), **kw)

    async def put(self, path: str, headers: dict | None = None, **kw):
        return await self.client.put(path, headers=self._h(headers), **kw)

    async def patch(self, path: str, headers: dict | None = None, **kw):
        return await self.client.patch(path, headers=self._h(headers), **kw)

    async def delete(self, path: str, headers: dict | None = None, **kw):
        return await self.client.delete(path, headers=self._h(headers), **kw)


async def create_org(
    slug: str,
    name: str | None = None,
    roles: tuple[str, ...] = ("admin",),
    email: str = "admin@example.org",
    password: str = "correct-horse-battery",
) -> Organization:
    async with get_sessionmaker()() as db:
        org = Organization(slug=slug, name=name or slug.title())
        db.add(org)
        await db.flush()
        user = AppUser(
            organization_id=org.id,
            email=email,
            display_name="Admin",
            password_hash=hash_password(password),
        )
        user.roles = [UserRole(organization_id=org.id, role=r) for r in roles]
        db.add(user)
        await db.commit()
        await db.refresh(org)
        return org


async def add_user(
    org: Organization, email: str, roles: tuple[str, ...], password: str = "correct-horse-battery"
) -> AppUser:
    async with get_sessionmaker()() as db:
        user = AppUser(
            organization_id=org.id,
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(password),
        )
        user.roles = [UserRole(organization_id=org.id, role=r) for r in roles]
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def create_platform_admin(
    email: str = "root@example.org", password: str = "platform-root-secret"
) -> PlatformAdmin:
    async with get_sessionmaker()() as db:
        admin = PlatformAdmin(email=email, password_hash=hash_password(password))
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin


async def login(
    client: httpx.AsyncClient,
    slug: str,
    email: str = "admin@example.org",
    password: str = "correct-horse-battery",
) -> Session:
    # Each Session gets its own client cookie jar so several users can coexist in one test.
    fresh = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    resp = await fresh.post(f"/api/{slug}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return Session(fresh, slug, resp.json()["csrf_token"])


async def platform_login(
    email: str = "root@example.org", password: str = "platform-root-secret"
) -> Session:
    fresh = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    resp = await fresh.post("/api/platform/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return Session(fresh, "platform", resp.json()["csrf_token"])


def event_payload(**overrides) -> dict:
    base = {
        "name": "Stadtlauf",
        "year": 2026,
        "event_date": "2026-06-14",
        "registration_deadline": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        "default_start_time": "2026-06-14T10:00:00+02:00",
        "tshirt_options": "S\nM\nL",
        "youth_cutoff_date": "2008-01-01",
        "venue_postal_code": "82194",
        "bib_start_number": 1,
    }
    base.update(overrides)
    return base


def competition_payload(**overrides) -> dict:
    base = {
        "title_de": "10 km Lauf",
        "title_en": "10 km run",
        "start_time": "2026-06-14T10:00:00+02:00",
        "price_adult_cents": 1500,
        "price_youth_cents": 800,
        "age_class_scheme": "five",
        "gender_scoring": True,
        "relay_scoring": False,
    }
    base.update(overrides)
    return base


async def setup_event(
    session: Session, event: dict | None = None, competitions: list[dict] | None = None
) -> tuple[dict, list[dict]]:
    resp = await session.post(f"/api/{session.slug}/team/events", json=event or event_payload())
    assert resp.status_code == 201, resp.text
    ev = resp.json()
    comps = []
    for c in competitions or [competition_payload()]:
        r = await session.post(f"/api/{session.slug}/team/events/{ev['id']}/competitions", json=c)
        assert r.status_code == 201, r.text
        comps.append(r.json())
    return ev, comps


def registration_payload(event_id: str, competition_id: str, **overrides) -> dict:
    n = uuid.uuid4().hex[:6]
    base = {
        "event_id": event_id,
        "competition_id": competition_id,
        "first_name": "Anna",
        "last_name": f"Test{n}",
        "birth_date": "1990-05-04",
        "gender": "f",
        "email": f"anna.{n}@example.org",
        "language": "de",
        "team_name": None,
        "tshirt_size": "M",
        "postal_code": "80331",
        "heard_about": "friends",
        "consent_data": True,
        "consent_publish": True,
        "payment_method": "on_site",
    }
    base.update(overrides)
    return base


VALID_IBAN = "DE89 3704 0044 0532 0130 00"
TODAY = date.today()

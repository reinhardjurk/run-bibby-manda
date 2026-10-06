"""Configuration and HTTP helpers for the end-to-end suite.

Environment variables (all tests):
  BIBBY_E2E_BASE_URL   e.g. https://www.run-bibby.eu        (required)
  BIBBY_E2E_SLUG       organization slug used for the tests  (required)
  BIBBY_E2E_EMAIL      org admin e-mail                      (required)
  BIBBY_E2E_PASSWORD   org admin password                    (required)
Optional:
  BIBBY_E2E_PLATFORM_EMAIL / BIBBY_E2E_PLATFORM_PASSWORD   super admin (platform tests)
  BIBBY_E2E_SECOND_SLUG                                      another organization (isolation tests)
  BIBBY_E2E_RATELIMIT=1                                      run the login rate-limit test (locks the
                                                             test account for a few minutes)
Test data is marked: event names start with "E2E ", e-mails end with @e2e.example.org,
device labels / users / sponsors carry the prefix "E2E".
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

TEST_PREFIX = "E2E"
TEST_DOMAIN = "e2e.example.org"
VALID_IBAN = "DE89 3704 0044 0532 0130 00"


@dataclass(frozen=True)
class Config:
    base_url: str
    slug: str
    email: str
    password: str
    platform_email: str | None
    platform_password: str | None
    second_slug: str | None
    ratelimit_tests: bool

    @classmethod
    def from_env(cls) -> Config:
        missing = [
            k
            for k in (
                "BIBBY_E2E_BASE_URL",
                "BIBBY_E2E_SLUG",
                "BIBBY_E2E_EMAIL",
                "BIBBY_E2E_PASSWORD",
            )
            if not os.environ.get(k)
        ]
        if missing:
            print(f"missing environment variables: {', '.join(missing)}", file=sys.stderr)
            raise SystemExit(2)
        return cls(
            base_url=os.environ["BIBBY_E2E_BASE_URL"].rstrip("/"),
            slug=os.environ["BIBBY_E2E_SLUG"],
            email=os.environ["BIBBY_E2E_EMAIL"],
            password=os.environ["BIBBY_E2E_PASSWORD"],
            platform_email=os.environ.get("BIBBY_E2E_PLATFORM_EMAIL") or None,
            platform_password=os.environ.get("BIBBY_E2E_PLATFORM_PASSWORD") or None,
            second_slug=os.environ.get("BIBBY_E2E_SECOND_SLUG") or None,
            ratelimit_tests=os.environ.get("BIBBY_E2E_RATELIMIT") == "1",
        )


class Session:
    """HTTP session with cookie jar and CSRF header handling (team or platform)."""

    def __init__(self, base_url: str) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=60, follow_redirects=False)
        self.csrf = ""

    def _headers(self, headers: dict | None) -> dict:
        return {"X-CSRF-Token": self.csrf, **(headers or {})}

    def get(self, path: str, **kw) -> httpx.Response:
        return self.client.get(path, **kw)

    def post(self, path: str, headers: dict | None = None, **kw) -> httpx.Response:
        return self.client.post(path, headers=self._headers(headers), **kw)

    def put(self, path: str, headers: dict | None = None, **kw) -> httpx.Response:
        return self.client.put(path, headers=self._headers(headers), **kw)

    def patch(self, path: str, headers: dict | None = None, **kw) -> httpx.Response:
        return self.client.patch(path, headers=self._headers(headers), **kw)

    def delete(self, path: str, headers: dict | None = None, **kw) -> httpx.Response:
        return self.client.delete(path, headers=self._headers(headers), **kw)

    def close(self) -> None:
        self.client.close()


def team_login(base_url: str, slug: str, email: str, password: str) -> Session:
    s = Session(base_url)
    r = s.post(f"/api/{slug}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"login as {email} failed: {r.status_code} {r.text}")
    s.csrf = r.json()["csrf_token"]
    return s


def platform_login(base_url: str, email: str, password: str) -> Session:
    s = Session(base_url)
    r = s.post("/api/platform/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"platform login failed: {r.status_code} {r.text}")
    s.csrf = r.json()["csrf_token"]
    return s


def unique(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def event_payload(name_suffix: str = "") -> dict[str, Any]:
    start = (datetime.now(UTC) + timedelta(days=7)).replace(
        hour=8, minute=0, second=0, microsecond=0
    )
    return {
        "name": f"{TEST_PREFIX} Lauf {name_suffix or unique()}",
        "year": start.year,
        "event_date": start.date().isoformat(),
        "registration_deadline": iso(start - timedelta(days=1)),
        "default_start_time": iso(start),
        "tshirt_options": "S\nM\nL\nXL",
        "tshirt_included": False,
        "youth_cutoff_date": date(start.year - 18, 1, 1).isoformat(),
        "venue_postal_code": "82194",
        "bib_start_number": 1,
        "certificate_offset_lines": 0,
    }


def competition_payload(title: str, start: str, **overrides: Any) -> dict[str, Any]:
    base = {
        "title_de": title,
        "title_en": title,
        "start_time": start,
        "price_adult_cents": 1500,
        "price_youth_cents": 800,
        "age_class_scheme": "five",
        "gender_scoring": True,
        "relay_scoring": False,
        "bib_range_start": None,
        "bib_range_end": None,
        "sort_order": 0,
    }
    base.update(overrides)
    return base


def registration_payload(event_id: str, competition_id: str, **overrides: Any) -> dict[str, Any]:
    n = unique()
    base = {
        "event_id": event_id,
        "competition_id": competition_id,
        "first_name": "Test",
        "last_name": f"{TEST_PREFIX}-{n}",
        "birth_date": "1990-05-04",
        "gender": "f",
        "email": f"{n}@{TEST_DOMAIN}",
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


def register(client: httpx.Client, slug: str, payload: dict[str, Any]) -> httpx.Response:
    """Public registration with one automatic wait on 429 (public rate limit)."""
    r = client.post(f"/api/public/{slug}/registrations", json=payload)
    if r.status_code == 429:
        time.sleep(65)
        r = client.post(f"/api/public/{slug}/registrations", json=payload)
    return r


def token_of(created: dict[str, Any]) -> str:
    return created["manage_url"].split("token=")[1]

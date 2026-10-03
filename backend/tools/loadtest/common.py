"""Shared helpers for the load-test tools. Configuration via environment variables:

BIBBY_LOADTEST_BASE_URL  e.g. https://lauf.example.org   (required)
BIBBY_LOADTEST_SLUG      organization slug               (required)
BIBBY_LOADTEST_EMAIL     org admin e-mail                (required)
BIBBY_LOADTEST_PASSWORD  org admin password              (required)

Test data is marked: e-mails end with @loadtest.example.org, the load-test event uses bib
numbers from 90001, and events/devices are prefixed with LOADTEST.
"""

from __future__ import annotations

import os
import statistics
import sys
import time
from dataclasses import dataclass, field

import httpx

TEST_DOMAIN = "loadtest.example.org"
TEST_PREFIX = "LOADTEST"
TEST_BIB_START = 90001


@dataclass
class Config:
    base_url: str
    slug: str
    email: str
    password: str

    @classmethod
    def from_env(cls) -> Config:
        missing = [
            k
            for k in (
                "BIBBY_LOADTEST_BASE_URL",
                "BIBBY_LOADTEST_SLUG",
                "BIBBY_LOADTEST_EMAIL",
                "BIBBY_LOADTEST_PASSWORD",
            )
            if not os.environ.get(k)
        ]
        if missing:
            print(f"missing environment variables: {', '.join(missing)}", file=sys.stderr)
            sys.exit(2)
        return cls(
            base_url=os.environ["BIBBY_LOADTEST_BASE_URL"].rstrip("/"),
            slug=os.environ["BIBBY_LOADTEST_SLUG"],
            email=os.environ["BIBBY_LOADTEST_EMAIL"],
            password=os.environ["BIBBY_LOADTEST_PASSWORD"],
        )


class TeamClient:
    """Cookie session + CSRF header for team endpoints."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.client = httpx.AsyncClient(base_url=cfg.base_url, timeout=60)
        self.csrf = ""

    async def login(self) -> None:
        r = await self.client.post(
            f"/api/{self.cfg.slug}/auth/login",
            json={"email": self.cfg.email, "password": self.cfg.password},
        )
        r.raise_for_status()
        self.csrf = r.json()["csrf_token"]

    def _h(self) -> dict[str, str]:
        return {"X-CSRF-Token": self.csrf}

    async def get(self, path: str, **kw) -> httpx.Response:
        return await self.client.get(path, **kw)

    async def post(self, path: str, **kw) -> httpx.Response:
        return await self.client.post(path, headers=self._h(), **kw)

    async def put(self, path: str, **kw) -> httpx.Response:
        return await self.client.put(path, headers=self._h(), **kw)

    async def patch(self, path: str, **kw) -> httpx.Response:
        return await self.client.patch(path, headers=self._h(), **kw)

    async def delete(self, path: str, **kw) -> httpx.Response:
        return await self.client.delete(path, headers=self._h(), **kw)

    async def ensure_mail_off(self) -> None:
        """Load tests must never send e-mail: mail mode is forced to `off` (and verified)."""
        r = await self.put(
            f"/api/{self.cfg.slug}/team/settings", json={"values": {"mail_mode": "off"}}
        )
        r.raise_for_status()
        if r.json().get("mail_mode") != "off":
            print("could not switch mail mode off – aborting", file=sys.stderr)
            sys.exit(3)

    async def close(self) -> None:
        await self.client.aclose()


@dataclass
class Latencies:
    samples: list[float] = field(default_factory=list)

    def add(self, started: float) -> None:
        self.samples.append((time.perf_counter() - started) * 1000)

    def summary(self) -> str:
        if not self.samples:
            return "no samples"
        s = sorted(self.samples)
        p50 = statistics.median(s)
        p95 = s[min(len(s) - 1, int(round(0.95 * len(s))) - 1)] if len(s) > 1 else s[0]
        return f"n={len(s)} p50={p50:.0f}ms p95={p95:.0f}ms max={s[-1]:.0f}ms"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)

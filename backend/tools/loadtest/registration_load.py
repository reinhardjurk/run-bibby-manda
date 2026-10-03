"""Concurrent public registrations against a live environment.

Checks: all requests succeed, bib numbers are unique and ≥ 90001, latencies p50/p95.
Exit code ≠ 0 on any violation.

    BIBBY_LOADTEST_CONCURRENCY=20 BIBBY_LOADTEST_TOTAL=200 python -m tools.loadtest.registration_load
"""

from __future__ import annotations

import asyncio
import os
import random
import time
import uuid

import httpx

from tools.loadtest.common import TEST_BIB_START, TEST_DOMAIN, Config, Latencies, TeamClient, fail
from tools.loadtest.seed import ensure_event


def payload(event_id: str, competition_id: str, i: int) -> dict:
    uid = uuid.uuid4().hex[:8]
    return {
        "event_id": event_id,
        "competition_id": competition_id,
        "first_name": f"Last{i}",
        "last_name": f"Test-{uid}",
        "birth_date": f"{random.randint(1950, 2012)}-0{random.randint(1, 9)}-1{random.randint(0, 9)}",
        "gender": random.choice(["f", "m", "x"]),
        "email": f"lt-{uid}@{TEST_DOMAIN}",
        "language": "de",
        "team_name": random.choice([None, f"Team {i % 7}"]),
        "tshirt_size": random.choice(["S", "M", "L"]),
        "postal_code": random.choice(["80331", "10115", "20095", "82194"]),
        "heard_about": "other",
        "consent_data": True,
        "consent_publish": random.random() < 0.8,
        "payment_method": "on_site",
    }


async def main() -> None:
    cfg = Config.from_env()
    concurrency = int(os.environ.get("BIBBY_LOADTEST_CONCURRENCY", "20"))
    total = int(os.environ.get("BIBBY_LOADTEST_TOTAL", "200"))
    tc = TeamClient(cfg)
    await tc.login()
    await tc.ensure_mail_off()
    event = await ensure_event(tc)
    comps = [c["id"] for c in event["competitions"]]
    await tc.close()

    lat = Latencies()
    bibs: list[int] = []
    errors: list[str] = []
    sem = asyncio.Semaphore(concurrency)

    async def one(i: int, client: httpx.AsyncClient) -> None:
        async with sem:
            started = time.perf_counter()
            try:
                r = await client.post(
                    f"/api/public/{cfg.slug}/registrations",
                    json=payload(event["id"], random.choice(comps), i),
                )
            except httpx.HTTPError as exc:
                errors.append(f"{i}: {exc}")
                return
            lat.add(started)
            if r.status_code == 429:
                errors.append(
                    f"{i}: rate limited (429) – raise BIBBY_REGISTRATION_LIMIT for load tests"
                )
            elif r.status_code != 201:
                errors.append(f"{i}: {r.status_code} {r.text[:120]}")
            else:
                bibs.append(r.json()["bib_number"])

    async with httpx.AsyncClient(base_url=cfg.base_url, timeout=60) as client:
        t0 = time.perf_counter()
        await asyncio.gather(*(one(i, client) for i in range(total)))
        elapsed = time.perf_counter() - t0

    print(
        f"registrations: ok={len(bibs)} errors={len(errors)} in {elapsed:.1f}s ({len(bibs) / max(elapsed, 0.001):.1f}/s)"
    )
    print(f"latency: {lat.summary()}")
    for e in errors[:10]:
        print("  ", e)
    if errors:
        fail(f"{len(errors)} failed registrations")
    if len(set(bibs)) != len(bibs):
        fail("duplicate bib numbers under concurrency!")
    if bibs and min(bibs) < TEST_BIB_START:
        fail(f"bib numbers below {TEST_BIB_START} – wrong event?")
    print("OK: all bib numbers unique")


if __name__ == "__main__":
    asyncio.run(main())

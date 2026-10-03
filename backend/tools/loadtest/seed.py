"""Creates (or reuses) the marked load-test event with two competitions. Prints the event id.

python -m tools.loadtest.seed
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from tools.loadtest.common import TEST_BIB_START, TEST_PREFIX, Config, TeamClient


async def ensure_event(tc: TeamClient) -> dict:
    slug = tc.cfg.slug
    events = (await tc.get(f"/api/{slug}/team/events")).json()
    for e in events:
        if e["name"].startswith(TEST_PREFIX):
            return e
    start = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0)
    r = await tc.post(
        f"/api/{slug}/team/events",
        json={
            "name": f"{TEST_PREFIX} Lauf",
            "year": start.year,
            "event_date": start.date().isoformat(),
            "registration_deadline": (start + timedelta(days=1)).isoformat(),
            "default_start_time": start.isoformat(),
            "tshirt_options": "S\nM\nL",
            "youth_cutoff_date": f"{start.year - 18}-01-01",
            "venue_postal_code": "80331",
            "bib_start_number": TEST_BIB_START,
        },
    )
    r.raise_for_status()
    event = r.json()
    for title, relay in (("10 km", False), ("5 km Staffel", True)):
        r = await tc.post(
            f"/api/{slug}/team/events/{event['id']}/competitions",
            json={
                "title_de": title,
                "title_en": title,
                "start_time": start.isoformat(),
                "price_adult_cents": 1000,
                "price_youth_cents": 500,
                "age_class_scheme": "five",
                "gender_scoring": True,
                "relay_scoring": relay,
            },
        )
        r.raise_for_status()
    return (await tc.get(f"/api/{slug}/team/events/{event['id']}")).json()


async def main() -> None:
    cfg = Config.from_env()
    tc = TeamClient(cfg)
    await tc.login()
    await tc.ensure_mail_off()
    event = await ensure_event(tc)
    print(event["id"])
    await tc.close()


if __name__ == "__main__":
    asyncio.run(main())

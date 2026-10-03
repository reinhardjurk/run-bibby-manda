"""Removes all marked load-test data of the organization: registrations with the test mail domain,
LOADTEST events (cascade: bibs, payments, timing records) and LOADTEST device tokens.

    python -m tools.loadtest.cleanup
"""

from __future__ import annotations

import asyncio

from tools.loadtest.common import TEST_DOMAIN, TEST_PREFIX, Config, TeamClient


async def main() -> None:
    cfg = Config.from_env()
    tc = TeamClient(cfg)
    await tc.login()
    slug = cfg.slug
    removed_regs = 0
    events = (await tc.get(f"/api/{slug}/team/events")).json()
    for e in events:
        if e["name"].startswith(TEST_PREFIX):
            continue
        # stray test registrations in regular events (by e-mail domain)
        page = 1
        while True:
            data = (
                await tc.get(
                    f"/api/{slug}/team/registrations",
                    params={"event_id": e["id"], "page": page, "page_size": 500},
                )
            ).json()
            victims = [r for r in data["items"] if r["email"].endswith(f"@{TEST_DOMAIN}")]
            for r in victims:
                if (
                    await tc.delete(f"/api/{slug}/team/registrations/{r['id']}")
                ).status_code == 204:
                    removed_regs += 1
            if page * 500 >= data["total"]:
                break
            page += 1
    removed_events = 0
    for e in events:
        if e["name"].startswith(TEST_PREFIX):
            r = await tc.delete(f"/api/{slug}/team/events/{e['id']}")
            if r.status_code == 204:
                removed_events += 1
            else:
                print(f"could not delete event {e['name']}: {r.status_code} {r.text}")
    removed_devices = 0
    for d in (await tc.get(f"/api/{slug}/team/timing/devices")).json():
        if d["label"].startswith(TEST_PREFIX):
            if (await tc.delete(f"/api/{slug}/team/timing/devices/{d['id']}")).status_code == 204:
                removed_devices += 1
    await tc.close()
    print(
        f"cleanup: events={removed_events} registrations={removed_regs} devices={removed_devices}"
    )


if __name__ == "__main__":
    asyncio.run(main())

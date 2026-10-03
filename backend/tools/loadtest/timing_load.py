"""Timing ingest load test: several device senders, offline-queue style batches with deliberate
re-sends (idempotency), p50/p95 latencies. Exit code ≠ 0 on violations.

    BIBBY_LOADTEST_DEVICES=4 BIBBY_LOADTEST_BATCHES=50 python -m tools.loadtest.timing_load
"""

from __future__ import annotations

import asyncio
import os
import random
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx

from tools.loadtest.common import TEST_BIB_START, TEST_PREFIX, Config, Latencies, TeamClient, fail
from tools.loadtest.seed import ensure_event


async def main() -> None:
    cfg = Config.from_env()
    devices = int(os.environ.get("BIBBY_LOADTEST_DEVICES", "4"))
    batches = int(os.environ.get("BIBBY_LOADTEST_BATCHES", "50"))
    batch_size = int(os.environ.get("BIBBY_LOADTEST_BATCH_SIZE", "10"))
    tc = TeamClient(cfg)
    await tc.login()
    await tc.ensure_mail_off()
    event = await ensure_event(tc)
    tokens: list[str] = []
    for d in range(devices):
        label = f"{TEST_PREFIX} device {d} {uuid.uuid4().hex[:4]}"
        r = await tc.post(
            f"/api/{cfg.slug}/team/timing/devices", json={"label": label, "time_offset_seconds": d}
        )
        r.raise_for_status()
        tokens.append(r.json()["token"])

    lat = Latencies()
    expected_inserted = 0
    inserted = 0
    duplicates = 0
    errors: list[str] = []
    base = datetime.now(UTC)

    async def sender(token: str, idx: int) -> None:
        nonlocal inserted, duplicates, expected_inserted
        async with httpx.AsyncClient(
            base_url=cfg.base_url, timeout=60, headers={"X-Device-Token": token}
        ) as client:
            queue: list[dict] = []
            for b in range(batches):
                records = [
                    {
                        "bib_number": TEST_BIB_START + random.randint(0, 500),
                        "absolute_time": (base + timedelta(seconds=b * 3 + i * 0.3)).isoformat(),
                        "dedup_key": f"lt-{idx}-{uuid.uuid4().hex}",
                    }
                    for i in range(batch_size)
                ]
                queue.append({"event_id": event["id"], "records": records})
                expected_inserted += batch_size
                # offline queue: sometimes re-send the previous batch (must be counted as duplicates only)
                to_send = [queue[-1]] + (
                    [queue[-2]] if len(queue) > 1 and random.random() < 0.3 else []
                )
                for body in to_send:
                    started = time.perf_counter()
                    try:
                        r = await client.post(f"/api/{cfg.slug}/timing/records", json=body)
                    except httpx.HTTPError as exc:
                        errors.append(str(exc))
                        continue
                    lat.add(started)
                    if r.status_code != 200:
                        errors.append(f"{r.status_code} {r.text[:120]}")
                        continue
                    inserted += r.json()["inserted"]
                    duplicates += r.json()["duplicates"]

    t0 = time.perf_counter()
    await asyncio.gather(*(sender(t, i) for i, t in enumerate(tokens)))
    elapsed = time.perf_counter() - t0
    print(
        f"timing: inserted={inserted} expected={expected_inserted} duplicates={duplicates} errors={len(errors)} in {elapsed:.1f}s"
    )
    print(f"latency: {lat.summary()}")
    summary = (
        await tc.get(f"/api/{cfg.slug}/team/timing/summary", params={"event_id": event["id"]})
    ).json()
    print(f"server records: {summary}")
    await tc.close()
    if errors:
        fail(f"{len(errors)} failed uploads: {errors[:3]}")
    if inserted != expected_inserted:
        fail("inserted count differs from expected – idempotency broken")
    print("OK: idempotent ingest verified")


if __name__ == "__main__":
    asyncio.run(main())

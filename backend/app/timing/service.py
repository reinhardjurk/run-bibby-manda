"""Timing service: idempotent record ingest, finish-time computation, relay formation,
plausibility check."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DeviceContext
from app.core.scoping import tenant_select
from app.db.models import Competition, Event, Registration, TimingRecord
from app.results.relays import RelayMember, form_relays
from app.timing.compute import COUNTED_STATUSES, mean_finish_time, net_seconds, spread_seconds
from app.timing.schemas import RecordIn


async def ingest_records(
    db: AsyncSession, actor: DeviceContext, event: Event, records: list[RecordIn]
) -> tuple[int, int]:
    """Inserts records; repeated uploads (same dedup key) are silently ignored. Returns
    (inserted, duplicates)."""
    if not records:
        return 0, 0
    offset = timedelta(seconds=actor.offset_seconds)
    values = [
        {
            "id": uuid.uuid4(),
            "organization_id": actor.organization_id,
            "event_id": event.id,
            "bib_number": r.bib_number,
            "absolute_time": r.absolute_time + offset,
            "source_token_id": actor.token.id if actor.token else None,
            "source_label": actor.label,
            "dedup_key": r.dedup_key,
            "status": "valid",
        }
        for r in records
    ]
    stmt = (
        insert(TimingRecord)
        .values(values)
        .on_conflict_do_nothing(constraint="uq_timing_event_dedup")
    )
    result = await db.execute(stmt)
    await db.commit()
    inserted = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else 0
    return inserted, len(records) - inserted


async def records_for_bib(
    db: AsyncSession, org_id: uuid.UUID, event: Event, bib_number: int
) -> list[TimingRecord]:
    stmt = (
        tenant_select(TimingRecord, org_id)
        .where(TimingRecord.event_id == event.id, TimingRecord.bib_number == bib_number)
        .order_by(TimingRecord.absolute_time)
    )
    return list((await db.execute(stmt)).scalars())


async def compute_all(db: AsyncSession, org_id: uuid.UUID, event: Event) -> tuple[int, int, int]:
    """Recomputes every net time of the event from scratch, then (re)forms relays."""
    comps = {c.id: c for c in event.competitions}
    regs = list(
        (
            await db.execute(
                tenant_select(Registration, org_id).where(Registration.event_id == event.id)
            )
        )
        .scalars()
        .unique()
    )
    recs = (
        await db.execute(
            tenant_select(TimingRecord, org_id)
            .where(TimingRecord.event_id == event.id)
            .where(TimingRecord.status.in_(COUNTED_STATUSES))
        )
    ).scalars()
    by_bib: dict[int, list] = defaultdict(list)
    for rec in recs:
        by_bib[rec.bib_number].append(rec.absolute_time)

    computed = 0
    no_start = 0
    for reg in regs:
        comp = comps.get(reg.competition_id)
        times = by_bib.get(reg.bib_number, []) if reg.bib_number is not None else []
        finish = mean_finish_time(times)
        if finish is None or comp is None:
            reg.finish_seconds = None
            continue
        if comp.start_time is None:
            reg.finish_seconds = None
            no_start += 1
            continue
        reg.finish_seconds = net_seconds(finish, comp.start_time)
        computed += 1
    relays = _form_relays(regs, comps)
    await db.commit()
    return computed, no_start, relays


def _form_relays(regs: list[Registration], comps: dict[uuid.UUID, Competition]) -> int:
    """Relay formation is always rebuilt completely; disabling clears assignments."""
    formed = 0
    by_comp: dict[uuid.UUID, list[Registration]] = defaultdict(list)
    for reg in regs:
        by_comp[reg.competition_id].append(reg)
    for comp_id, members in by_comp.items():
        comp = comps.get(comp_id)
        if comp is None or not comp.relay_scoring:
            for r in members:
                r.relay_id = None
            continue
        confirmed = [r for r in members if r.status == "confirmed"]
        assignment = form_relays(
            [RelayMember(r.id, r.team_name, r.finish_seconds) for r in confirmed]
        )
        for r in members:
            r.relay_id = assignment.get(r.id)
        formed += len({v for v in assignment.values() if v is not None})
    return formed


async def plausibility(
    db: AsyncSession, org_id: uuid.UUID, event: Event, threshold: float
) -> list[tuple[int, float, list]]:
    recs = (
        await db.execute(
            tenant_select(TimingRecord, org_id)
            .where(TimingRecord.event_id == event.id)
            .where(TimingRecord.status.in_(COUNTED_STATUSES))
            .order_by(TimingRecord.bib_number, TimingRecord.absolute_time)
        )
    ).scalars()
    by_bib: dict[int, list] = defaultdict(list)
    for rec in recs:
        by_bib[rec.bib_number].append(rec.absolute_time)
    out = []
    for bib, times in sorted(by_bib.items()):
        spread = spread_seconds(times)
        if spread > threshold:
            out.append((bib, spread, times))
    return out


async def record_counts(db: AsyncSession, org_id: uuid.UUID, event: Event) -> dict:
    rows = await db.execute(
        select(TimingRecord.status, TimingRecord.bib_number).where(
            TimingRecord.organization_id == org_id, TimingRecord.event_id == event.id
        )
    )
    statuses: dict[str, int] = defaultdict(int)
    bibs: set[int] = set()
    for status, bib in rows:
        statuses[status] += 1
        bibs.add(bib)
    return {"records": dict(statuses), "distinct_bibs": len(bibs)}

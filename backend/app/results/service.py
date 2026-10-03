"""Result queries: per-competition placements and relay results for an event."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoping import tenant_select
from app.db.models import Competition, Event, Registration
from app.results.placements import ResultRow, compute_placements
from app.results.relays import RelayMember, RelayResult, score_relays


@dataclass
class CompetitionResults:
    competition: Competition
    rows: list[ResultRow]
    relays: list[RelayResult]


async def load_competition_rows(
    db: AsyncSession, org_id: uuid.UUID, competition: Competition
) -> list[Registration]:
    stmt = (
        tenant_select(Registration, org_id)
        .where(Registration.competition_id == competition.id)
        .where(Registration.status == "confirmed")
    )
    return list((await db.execute(stmt)).scalars().unique())


def to_rows(regs: list[Registration]) -> list[ResultRow]:
    return [
        ResultRow(
            registration_id=str(r.id),
            bib_number=r.bib_number,
            first_name=r.participant.first_name,
            last_name=r.participant.last_name,
            gender=r.participant.gender,
            birth_date=r.participant.birth_date,
            team_name=r.team_name,
            finish_seconds=r.finish_seconds,
            consent_publish=r.consent_publish,
            relay_id=str(r.relay_id) if r.relay_id else None,
        )
        for r in regs
    ]


def relay_results(regs: list[Registration]) -> list[RelayResult]:
    groups: dict[uuid.UUID, tuple[str, list[RelayMember]]] = {}
    for r in regs:
        if r.relay_id is None:
            continue
        name, members = groups.setdefault(r.relay_id, (r.team_name or "", []))
        members.append(RelayMember(r.id, r.team_name, r.finish_seconds))
    return score_relays(groups)


async def competition_results(
    db: AsyncSession, org_id: uuid.UUID, event: Event, competition: Competition
) -> CompetitionResults:
    regs = await load_competition_rows(db, org_id, competition)
    rows = compute_placements(
        to_rows(regs), event.year, competition.age_class_scheme, competition.gender_scoring
    )
    relays = relay_results(regs) if competition.relay_scoring else []
    for row in rows:
        if row.relay_id:
            for rel in relays:
                if str(rel.relay_id) == row.relay_id:
                    row.extra["relay_place"] = rel.place
                    row.extra["relay_total"] = rel.total_scored
                    row.extra["relay_seconds"] = rel.total_seconds
    return CompetitionResults(competition=competition, rows=rows, relays=relays)


async def event_results(
    db: AsyncSession, org_id: uuid.UUID, event: Event
) -> list[CompetitionResults]:
    comps = list(
        (
            await db.execute(
                select(Competition)
                .where(Competition.event_id == event.id)
                .where(Competition.organization_id == org_id)
                .order_by(Competition.sort_order, Competition.title_de)
            )
        ).scalars()
    )
    return [await competition_results(db, org_id, event, c) for c in comps]


def row_to_public(row: ResultRow) -> dict:
    from app.results.placements import format_time

    return {
        "place": row.place_overall,
        "bib_number": row.bib_number,
        "name": f"{row.first_name} {row.last_name}",
        "team_name": row.team_name,
        "age_class": row.age_class,
        "place_age_class": row.place_age_class,
        "place_gender": row.place_gender,
        "gender": row.gender,
        "time": format_time(row.finish_seconds),
        "finish_seconds": float(row.finish_seconds) if row.finish_seconds is not None else None,
        "relay_place": row.extra.get("relay_place"),
        "relay_total": row.extra.get("relay_total"),
        "relay_time": format_time(row.extra.get("relay_seconds")),
    }

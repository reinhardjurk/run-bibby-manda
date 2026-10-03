"""Statistics for the moderation tab."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoping import tenant_select
from app.db.models import Event, Registration
from app.results.placements import format_time
from app.results.service import event_results
from app.stats.travel import estimate_travel


def _age(birth: date, on: date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


async def event_statistics(db: AsyncSession, org_id: uuid.UUID, event: Event) -> dict:
    regs = list(
        (
            await db.execute(
                tenant_select(Registration, org_id)
                .where(Registration.event_id == event.id)
                .where(Registration.status != "cancelled")
            )
        )
        .scalars()
        .unique()
    )
    ref = event.event_date or date.today()
    ages = [(_age(r.participant.birth_date, ref), r) for r in regs]
    finished = [r for r in regs if r.finish_seconds is not None]
    teams = {r.team_name.strip() for r in regs if r.team_name and r.team_name.strip()}
    youngest = min(ages, key=lambda a: a[0], default=None)
    oldest = max(ages, key=lambda a: a[0], default=None)

    results = await event_results(db, org_id, event)
    per_comp = []
    all_relays = []
    for cr in results:
        comp_regs = [r for r in regs if r.competition_id == cr.competition.id]
        by_gender = Counter(r.participant.gender for r in comp_regs)
        comp_ages = [(_age(r.participant.birth_date, ref), r) for r in comp_regs]
        fastest = next((r for r in cr.rows if r.place_overall == 1), None)
        fastest_f = next((r for r in cr.rows if r.gender == "f" and r.place_gender == 1), None)
        fastest_m = next((r for r in cr.rows if r.gender == "m" and r.place_gender == 1), None)
        y = min(comp_ages, key=lambda a: a[0], default=None)
        o = max(comp_ages, key=lambda a: a[0], default=None)
        per_comp.append(
            {
                "competition": {"id": str(cr.competition.id), "title_de": cr.competition.title_de},
                "total": len(comp_regs),
                "finished": sum(1 for r in comp_regs if r.finish_seconds is not None),
                "by_gender": dict(by_gender),
                "youngest": _person(y),
                "oldest": _person(o),
                "fastest": _fast(fastest),
                "fastest_female": _fast(fastest_f),
                "fastest_male": _fast(fastest_m),
            }
        )
        for rel in cr.relays:
            all_relays.append(
                {
                    "competition": cr.competition.title_de,
                    "team_name": rel.team_name,
                    "place": rel.place,
                    "complete": rel.complete,
                    "time": format_time(rel.total_seconds),
                    "members": len(rel.members),
                }
            )

    # Returning participants: same participant registered in other events of this organization.
    other = await db.execute(
        select(Registration.participant_id)
        .where(Registration.organization_id == org_id, Registration.event_id != event.id)
        .distinct()
    )
    other_ids = {pid for (pid,) in other}
    regulars = [r for r in regs if r.participant_id in other_ids]

    travel = estimate_travel([r.postal_code for r in regs], event.venue_postal_code)
    return {
        "event": {
            "id": str(event.id),
            "name": event.name,
            "year": event.year,
            "venue_postal_code": event.venue_postal_code,
        },
        "overview": {
            "participants": len(regs),
            "finished": len(finished),
            "teams": len(teams),
            "relays": sum(1 for r in all_relays),
            "relays_complete": sum(1 for r in all_relays if r["complete"]),
            "average_age": round(sum(a for a, _ in ages) / len(ages), 1) if ages else None,
            "youngest": _person(youngest),
            "oldest": _person(oldest),
        },
        "competitions": per_comp,
        "relays": all_relays,
        "team_names": sorted(teams, key=str.lower),
        "travel": {
            "available": event.venue_postal_code is not None,
            "counted": travel.counted,
            "unknown": travel.unknown,
            "buckets": travel.buckets,
            "average_km": round(travel.average_km, 1) if travel.average_km is not None else None,
            "farthest_km": round(travel.farthest_km, 1) if travel.farthest_km is not None else None,
            "farthest_region": travel.farthest_region,
            "top_regions": [{"region": r, "name": n, "count": c} for r, n, c in travel.top_regions],
        },
        "regulars": {
            "count": len(regulars),
            "names": sorted(
                f"{r.participant.first_name} {r.participant.last_name}" for r in regulars
            )[:200],
        },
        "heard_about": dict(Counter(r.heard_about or "unknown" for r in regs)),
        "tshirt_sizes": dict(Counter(r.tshirt_size or "–" for r in regs)),
    }


def _person(entry) -> dict | None:
    if entry is None:
        return None
    age, r = entry
    return {
        "name": f"{r.participant.first_name} {r.participant.last_name}",
        "age": age,
        "bib_number": r.bib_number,
    }


def _fast(row) -> dict | None:
    if row is None:
        return None
    return {
        "name": f"{row.first_name} {row.last_name}",
        "time": format_time(row.finish_seconds),
        "bib_number": row.bib_number,
    }

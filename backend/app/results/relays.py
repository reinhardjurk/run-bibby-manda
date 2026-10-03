"""Relay (Staffel) formation and scoring.

Confirmed registrations of one competition are grouped by normalised team name. Exactly three
members form a relay; groups of two or four-plus do not. A relay is scored only when all three
members have a finish time: total = sum, ranked among all scored relays of the competition.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from app.registrations.identity import normalize_team_name


@dataclass
class RelayMember:
    registration_id: uuid.UUID
    team_name: str | None
    finish_seconds: Decimal | None


def form_relays(members: list[RelayMember]) -> dict[uuid.UUID, uuid.UUID | None]:
    """Returns registration_id → relay_id (None when not part of a relay)."""
    groups: dict[str, list[RelayMember]] = defaultdict(list)
    for m in members:
        key = normalize_team_name(m.team_name)
        if key:
            groups[key].append(m)
    assignment: dict[uuid.UUID, uuid.UUID | None] = {m.registration_id: None for m in members}
    for group in groups.values():
        if len(group) == 3:
            relay_id = uuid.uuid4()
            for m in group:
                assignment[m.registration_id] = relay_id
    return assignment


@dataclass
class RelayResult:
    relay_id: uuid.UUID
    team_name: str
    members: list[RelayMember]
    total_seconds: Decimal | None
    place: int | None
    total_scored: int

    @property
    def complete(self) -> bool:
        return self.total_seconds is not None


def score_relays(
    relays: dict[uuid.UUID, tuple[str, list[RelayMember]]],
) -> list[RelayResult]:
    results: list[RelayResult] = []
    for relay_id, (team_name, members) in relays.items():
        total: Decimal | None
        if len(members) == 3 and all(m.finish_seconds is not None for m in members):
            total = sum((m.finish_seconds for m in members if m.finish_seconds), Decimal(0))
        else:
            total = None
        results.append(RelayResult(relay_id, team_name, members, total, None, 0))
    scored = sorted(
        (r for r in results if r.total_seconds is not None),
        key=lambda r: r.total_seconds or Decimal(0),
    )
    for idx, r in enumerate(scored, start=1):
        r.place = idx
        r.total_scored = len(scored)
    results.sort(
        key=lambda r: (r.total_seconds is None, r.total_seconds or Decimal(0), r.team_name)
    )
    return results

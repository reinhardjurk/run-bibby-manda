"""Placement calculation over the complete field (publication consent only filters display)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.results.age_classes import age_class


@dataclass
class ResultRow:
    registration_id: str
    bib_number: int | None
    first_name: str
    last_name: str
    gender: str
    birth_date: date
    team_name: str | None
    finish_seconds: Decimal | None
    consent_publish: bool
    relay_id: str | None = None
    age_class: str = ""
    place_overall: int | None = None
    place_gender: int | None = None
    place_age_class: int | None = None
    total_in_class: int = 0
    total_in_gender: int = 0
    total_overall: int = 0
    extra: dict = field(default_factory=dict)


def compute_placements(
    rows: list[ResultRow], year: int, scheme: str, gender_scoring: bool
) -> list[ResultRow]:
    """Assigns places (overall / gender / age class) to all finished rows. Ties share a place."""
    finished = [r for r in rows if r.finish_seconds is not None]
    finished.sort(key=lambda r: (r.finish_seconds, r.bib_number or 0))
    for r in rows:
        r.age_class = age_class(r.birth_date, r.gender, year, scheme, gender_scoring)

    _assign(finished, lambda r: "all", "place_overall", "total_overall")
    if gender_scoring:
        _assign(finished, lambda r: r.gender, "place_gender", "total_gender")
    if scheme != "none":
        _assign(finished, lambda r: r.age_class, "place_age_class", "total_in_class")
    return rows


def _assign(finished: list[ResultRow], key, place_attr: str, total_attr: str) -> None:
    groups: dict[str, list[ResultRow]] = defaultdict(list)
    for r in finished:
        groups[key(r)].append(r)
    for members in groups.values():
        last_time: Decimal | None = None
        last_place = 0
        for idx, r in enumerate(members, start=1):
            place = last_place if r.finish_seconds == last_time else idx
            setattr(r, place_attr, place)
            setattr(r, total_attr, len(members))
            last_time, last_place = r.finish_seconds, place


def format_time(seconds: Decimal | float | None) -> str:
    if seconds is None:
        return ""
    total = int(round(float(seconds)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

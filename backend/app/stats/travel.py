"""Travel distance estimate based on German postal code 'Leitregionen' (first two digits).

Distance = haversine between region centres (±30 km accuracy; same region = 0 km).
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

BUCKETS = (25, 50, 100, 250, 500)


@lru_cache
def region_centres() -> dict[str, tuple[float, float, str]]:
    with resources.files("app.data").joinpath("plz_leitregionen.csv").open(encoding="utf-8") as f:
        return {
            row["region"]: (float(row["lat"]), float(row["lon"]), row["name"])
            for row in csv.DictReader(f)
        }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def region_of(postal_code: str | None) -> str | None:
    if not postal_code:
        return None
    digits = "".join(ch for ch in postal_code if ch.isdigit())
    if len(digits) != 5:
        return None
    return digits[:2]


def distance_km(from_plz: str | None, to_plz: str | None) -> float | None:
    a, b = region_of(from_plz), region_of(to_plz)
    if a is None or b is None:
        return None
    if a == b:
        return 0.0
    centres = region_centres()
    if a not in centres or b not in centres:
        return None
    la1, lo1, _ = centres[a]
    la2, lo2, _ = centres[b]
    return haversine_km(la1, lo1, la2, lo2)


@dataclass
class TravelStats:
    counted: int
    unknown: int
    buckets: dict[str, int]
    average_km: float | None
    farthest_km: float | None
    farthest_region: str | None
    top_regions: list[tuple[str, str, int]]


def estimate_travel(postal_codes: list[str | None], venue_plz: str | None) -> TravelStats:
    distances: list[tuple[float, str]] = []
    unknown = 0
    regions: Counter[str] = Counter()
    for plz in postal_codes:
        d = distance_km(plz, venue_plz)
        if d is None:
            unknown += 1
            continue
        reg = region_of(plz) or ""
        regions[reg] += 1
        distances.append((d, reg))
    buckets: dict[str, int] = {f"<{b}": 0 for b in BUCKETS}
    buckets[f">={BUCKETS[-1]}"] = 0
    for d, _ in distances:
        for b in BUCKETS:
            if d < b:
                buckets[f"<{b}"] += 1
                break
        else:
            buckets[f">={BUCKETS[-1]}"] += 1
    centres = region_centres()
    farthest = max(distances, default=None)
    return TravelStats(
        counted=len(distances),
        unknown=unknown,
        buckets=buckets,
        average_km=(sum(d for d, _ in distances) / len(distances)) if distances else None,
        farthest_km=farthest[0] if farthest else None,
        farthest_region=(
            f"{farthest[1]} {centres.get(farthest[1], (0, 0, ''))[2]}" if farthest else None
        ),
        top_regions=[
            (reg, centres.get(reg, (0, 0, ""))[2], n) for reg, n in regions.most_common(10)
        ],
    )

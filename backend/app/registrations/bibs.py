"""Bib number allocation rules (pure logic; the DB wrapper lives in service.py).

* Competition **with** range: sequential within the range (max+1, starting at range start).
  Ranges may be shared between competitions; shared ranges count up together. Full → error.
* Competition **without** range: sequential from the event's start number, skipping every
  number that lies inside any defined range of the event.
"""

from __future__ import annotations

from collections.abc import Iterable


class BibRangeFull(Exception):
    pass


def next_bib_in_range(assigned: Iterable[int], start: int, end: int) -> int:
    used = {n for n in assigned if start <= n <= end}
    candidate = max(used) + 1 if used else start
    if candidate > end:
        # Try to fill holes (e.g. after manual re-assignment) before giving up.
        for n in range(start, end + 1):
            if n not in used:
                return n
        raise BibRangeFull()
    return candidate


def next_bib_outside_ranges(
    assigned: Iterable[int], start_number: int, ranges: Iterable[tuple[int, int]]
) -> int:
    ranges_list = list(ranges)
    used = set(assigned)
    free_used = {n for n in used if not any(a <= n <= b for a, b in ranges_list)}
    candidate = max(max(free_used) + 1, start_number) if free_used else start_number
    while True:
        inside = next(((a, b) for a, b in ranges_list if a <= candidate <= b), None)
        if inside is None:
            if candidate not in used:
                return candidate
            candidate += 1
        else:
            candidate = inside[1] + 1

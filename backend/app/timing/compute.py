"""Finish time computation: mean of all non-ignored recordings minus competition start."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

COUNTED_STATUSES = ("valid", "manual")


def mean_finish_time(times: list[datetime]) -> datetime | None:
    if not times:
        return None
    base = times[0]
    offsets = [(t - base).total_seconds() for t in times]
    from datetime import timedelta

    return base + timedelta(seconds=sum(offsets) / len(offsets))


def net_seconds(finish: datetime, start: datetime) -> Decimal:
    delta = Decimal(str((finish - start).total_seconds()))
    return delta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def spread_seconds(times: list[datetime]) -> float:
    if len(times) < 2:
        return 0.0
    return (max(times) - min(times)).total_seconds()

"""Entry fee calculation."""

from __future__ import annotations

from datetime import date


def is_youth(birth_date: date, youth_cutoff: date | None) -> bool:
    """Youth = born on or after the event's youth cutoff date."""
    return youth_cutoff is not None and birth_date >= youth_cutoff


def price_cents(
    birth_date: date, youth_cutoff: date | None, price_adult: int, price_youth: int | None
) -> int:
    if price_youth is not None and is_youth(birth_date, youth_cutoff):
        return price_youth
    return price_adult

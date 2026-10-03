"""Age class computation.

* `five`: five-year classes based on the age reached in the event year (W/M/X 30, 35, ...;
  under 20 grouped by youth classes U20/U18/U16/U14/U12/U10).
* `one`: single-year classes (age reached in the event year).
* `none`: no age classes.
"""

from __future__ import annotations

from datetime import date

GENDER_PREFIX = {"f": "W", "m": "M", "x": "X"}


def age_in_year(birth_date: date, year: int) -> int:
    return year - birth_date.year


def age_class(birth_date: date, gender: str, year: int, scheme: str, gender_scoring: bool) -> str:
    if scheme == "none":
        return ""
    prefix = GENDER_PREFIX.get(gender, "X") if gender_scoring else ""
    age = age_in_year(birth_date, year)
    if scheme == "one":
        return f"{prefix}{age}"
    if age < 20:
        for limit in (10, 12, 14, 16, 18, 20):
            if age < limit:
                return f"{prefix}U{limit}"
    base = (age // 5) * 5
    return f"{prefix}{base}" if base >= 30 else f"{prefix}HK"  # Hauptklasse 20–29

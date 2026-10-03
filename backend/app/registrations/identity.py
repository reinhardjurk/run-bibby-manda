"""Participant identity normalisation (match key) and team name normalisation."""

from __future__ import annotations

import re
import unicodedata
from datetime import date


def normalize_text(value: str) -> str:
    """Lower-case, accent-stripped, whitespace-collapsed representation."""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    stripped = stripped.replace("ß", "ss")
    return re.sub(r"\s+", " ", stripped).strip().lower()


def match_key(first_name: str, last_name: str, birth_date: date) -> str:
    return f"{normalize_text(last_name)}|{normalize_text(first_name)}|{birth_date.isoformat()}"


def normalize_team_name(value: str | None) -> str | None:
    if value is None:
        return None
    norm = re.sub(r"\s+", "", normalize_text(value))
    return norm or None

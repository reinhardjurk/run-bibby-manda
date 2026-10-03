"""IBAN validation (ISO 13616 mod-97), masking and SEPA mandate references."""

from __future__ import annotations

import re
import secrets
import string

_IBAN_LENGTHS = {
    "AT": 20, "BE": 16, "CH": 21, "CZ": 24, "DE": 22, "DK": 18, "ES": 24, "FI": 18, "FR": 27,
    "GB": 22, "HU": 28, "IE": 22, "IT": 27, "LI": 21, "LU": 20, "NL": 18, "NO": 15, "PL": 28,
    "PT": 25, "SE": 24, "SI": 19, "SK": 24,
}  # fmt: skip


def normalize_iban(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def is_valid_iban(value: str) -> bool:
    iban = normalize_iban(value)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        return False
    expected = _IBAN_LENGTHS.get(iban[:2])
    if expected is not None and len(iban) != expected:
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(numeric) % 97 == 1


def mask_iban(value: str) -> str:
    iban = normalize_iban(value)
    if len(iban) < 8:
        return "*" * len(iban)
    return f"{iban[:4]} {'*' * (len(iban) - 8)} {iban[-4:]}".replace("*" * 4, "**** ").strip()


def new_mandate_reference(prefix: str, year: int) -> str:
    alphabet = string.ascii_uppercase + string.digits
    rnd = "".join(secrets.choice(alphabet) for _ in range(8))
    clean_prefix = re.sub(r"[^A-Z0-9]", "", prefix.upper())[:10] or "BIBBY"
    return f"{clean_prefix}-{year}-{rnd}"

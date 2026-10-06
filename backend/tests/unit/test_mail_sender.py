import pytest
from app.settings.service import normalize_local_part, sender_address, sender_domain


def test_sender_domain_is_fixed_platform_domain():
    assert sender_domain() == "example.org"  # from BIBBY_MAIL_DEFAULT_SENDER default in tests


def test_sender_address_defaults_to_noreply_slug():
    assert sender_address({}, "groebenzell") == "noreply-groebenzell@example.org"
    assert (
        sender_address({"mail_sender_local_part": "anmeldung-tsv"}, "x")
        == "anmeldung-tsv@example.org"
    )


def test_local_part_validation():
    assert normalize_local_part("  Anmeldung.TSV+2026 ") == "anmeldung.tsv+2026"
    assert normalize_local_part("") == ""
    with pytest.raises(ValueError, match="Domain ist fest"):
        normalize_local_part("anmeldung@verein.de")
    for bad in ("-start", "end.", "has space", "ümlaut", "a" * 70):
        with pytest.raises(ValueError):
            normalize_local_part(bad)

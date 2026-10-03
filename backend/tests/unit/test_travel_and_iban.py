from app.payments.iban import is_valid_iban, mask_iban, new_mandate_reference
from app.stats.travel import distance_km, estimate_travel, haversine_km, region_of


def test_haversine_known_distance():
    # Munich (48.14, 11.58) – Berlin (52.52, 13.40) ≈ 504 km
    assert abs(haversine_km(48.14, 11.58, 52.52, 13.40) - 504) < 10


def test_region_and_same_region_zero():
    assert region_of("82194") == "82"
    assert region_of("8219") is None
    assert region_of("D-82194") == "82"
    assert distance_km("82194", "82140") == 0.0


def test_estimate_buckets_and_regions():
    stats = estimate_travel(["82194", "80331", "10115", None, "1234", "20095"], "82194")
    assert stats.counted == 4 and stats.unknown == 2
    assert stats.buckets["<25"] == 1
    assert stats.buckets["<50"] + stats.buckets["<100"] == 1  # Munich centre from region 82
    assert stats.buckets[">=500"] + stats.buckets["<500"] == 2  # Berlin + Hamburg
    assert stats.farthest_region is not None and stats.average_km is not None
    assert stats.top_regions[0][2] == 1


def test_iban_validation_and_masking():
    assert is_valid_iban("DE89 3704 0044 0532 0130 00")
    assert not is_valid_iban("DE89 3704 0044 0532 0130 01")
    assert not is_valid_iban("DE89")
    assert not is_valid_iban("XX00 1234")
    masked = mask_iban("DE89370400440532013000")
    assert masked.startswith("DE89") and masked.endswith("3000") and "3704" not in masked


def test_mandate_reference_format():
    ref = new_mandate_reference("Verein e.V.", 2026)
    prefix, year, rnd = ref.split("-")
    assert prefix == "VEREINEV" and year == "2026" and len(rnd) == 8

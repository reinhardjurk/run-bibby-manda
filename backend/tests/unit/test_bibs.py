import pytest
from app.registrations.bibs import BibRangeFull, next_bib_in_range, next_bib_outside_ranges


def test_range_starts_at_lower_bound():
    assert next_bib_in_range([], 100, 199) == 100


def test_range_sequential_max_plus_one():
    assert next_bib_in_range([100, 101, 105], 100, 199) == 106


def test_range_ignores_numbers_outside():
    assert next_bib_in_range([1, 2, 3, 500], 100, 199) == 100


def test_shared_ranges_count_up_together():
    # two competitions sharing 100–199: assignments from both are considered
    assert next_bib_in_range([100, 101], 100, 199) == 102


def test_range_full_raises():
    with pytest.raises(BibRangeFull):
        next_bib_in_range(range(100, 200), 100, 199)


def test_range_fills_holes_before_failing():
    assigned = [n for n in range(100, 200) if n != 150]
    assert next_bib_in_range(assigned, 100, 199) == 150


def test_outside_ranges_starts_at_start_number():
    assert next_bib_outside_ranges([], 1, []) == 1
    assert next_bib_outside_ranges([], 500, []) == 500


def test_outside_ranges_skips_defined_ranges():
    assert next_bib_outside_ranges([], 1, [(1, 50)]) == 51
    assert next_bib_outside_ranges([51, 52], 1, [(1, 50), (53, 60)]) == 61


def test_outside_ranges_continues_after_max_free_number():
    assert next_bib_outside_ranges([100, 101, 300], 1, [(300, 399)]) == 102


def test_outside_ranges_never_returns_used_number():
    assert next_bib_outside_ranges([1, 2, 3], 1, []) == 4

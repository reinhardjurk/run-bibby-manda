import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.registrations.identity import match_key, normalize_team_name
from app.registrations.pricing import price_cents
from app.results.age_classes import age_class
from app.results.placements import ResultRow, compute_placements, format_time
from app.results.relays import RelayMember, form_relays, score_relays
from app.timing.compute import mean_finish_time, net_seconds, spread_seconds


def row(bib, gender, birth_year, seconds, team=None):
    return ResultRow(
        registration_id=str(uuid.uuid4()),
        bib_number=bib,
        first_name="A",
        last_name="B",
        gender=gender,
        birth_date=date(birth_year, 1, 1),
        team_name=team,
        finish_seconds=Decimal(seconds) if seconds is not None else None,
        consent_publish=True,
    )


def test_age_class_schemes():
    assert age_class(date(1990, 1, 1), "f", 2026, "five", True) == "W35"
    assert age_class(date(1990, 1, 1), "m", 2026, "one", True) == "M36"
    assert age_class(date(2000, 1, 1), "m", 2026, "five", True) == "MHK"
    assert age_class(date(2012, 1, 1), "f", 2026, "five", True) == "WU16"
    assert age_class(date(1990, 1, 1), "f", 2026, "none", True) == ""
    assert age_class(date(1990, 1, 1), "f", 2026, "five", False) == "35"


def test_placements_overall_gender_and_class_with_ties():
    rows = [
        row(1, "f", 1990, 3600),
        row(2, "m", 1990, 3500),
        row(3, "f", 1990, 3600),
        row(4, "f", 1960, 4000),
        row(5, "m", 1990, None),
    ]
    compute_placements(rows, 2026, "five", True)
    by_bib = {r.bib_number: r for r in rows}
    assert by_bib[2].place_overall == 1
    assert by_bib[1].place_overall == 2 and by_bib[3].place_overall == 2  # tie shares place
    assert by_bib[4].place_overall == 4
    assert by_bib[1].place_gender == 1 and by_bib[4].place_gender == 3
    assert by_bib[4].place_age_class == 1 and by_bib[4].age_class == "W65"
    assert by_bib[5].place_overall is None
    assert by_bib[2].total_overall == 4


def test_placements_cover_whole_field_regardless_of_consent():
    rows = [row(1, "f", 1990, 100), row(2, "f", 1990, 200)]
    rows[0].consent_publish = False
    compute_placements(rows, 2026, "none", False)
    assert rows[1].place_overall == 2  # non-published runner still occupies place 1


def test_relay_formation_exactly_three():
    def m(team):
        return RelayMember(uuid.uuid4(), team, None)

    members = [
        m("Team A"),
        m("team  a"),
        m("TEAM A"),
        m("Team B"),
        m("Team B"),
        m("C"),
        m("C"),
        m("C"),
        m("C"),
        m(None),
    ]
    result = form_relays(members)
    a_ids = {result[x.registration_id] for x in members[:3]}
    assert len(a_ids) == 1 and None not in a_ids
    assert all(result[x.registration_id] is None for x in members[3:])


def test_relay_scoring_requires_all_three_times():
    rid1, rid2 = uuid.uuid4(), uuid.uuid4()
    relays = {
        rid1: (
            "Fast",
            [
                RelayMember(uuid.uuid4(), "Fast", Decimal(100)),
                RelayMember(uuid.uuid4(), "Fast", Decimal(100)),
                RelayMember(uuid.uuid4(), "Fast", Decimal(100)),
            ],
        ),
        rid2: (
            "Slow",
            [
                RelayMember(uuid.uuid4(), "Slow", Decimal(100)),
                RelayMember(uuid.uuid4(), "Slow", None),
                RelayMember(uuid.uuid4(), "Slow", Decimal(100)),
            ],
        ),
    }
    res = {r.relay_id: r for r in score_relays(relays)}
    assert (
        res[rid1].total_seconds == Decimal(300)
        and res[rid1].place == 1
        and res[rid1].total_scored == 1
    )
    assert res[rid2].total_seconds is None and res[rid2].place is None and not res[rid2].complete


def test_mean_finish_time_and_net_seconds():
    base = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    times = [
        base + timedelta(seconds=3600),
        base + timedelta(seconds=3602),
        base + timedelta(seconds=3604),
    ]
    finish = mean_finish_time(times)
    assert finish == base + timedelta(seconds=3602)
    assert net_seconds(finish, base) == Decimal("3602.00")
    assert spread_seconds(times) == 4.0
    assert mean_finish_time([]) is None


def test_price_youth_by_cutoff():
    assert price_cents(date(2010, 1, 1), date(2008, 1, 1), 1500, 800) == 800
    assert price_cents(date(2008, 1, 1), date(2008, 1, 1), 1500, 800) == 800
    assert price_cents(date(2007, 12, 31), date(2008, 1, 1), 1500, 800) == 1500
    assert price_cents(date(2010, 1, 1), None, 1500, 800) == 1500
    assert price_cents(date(2010, 1, 1), date(2008, 1, 1), 1500, None) == 1500


def test_identity_normalisation():
    assert match_key("Jörg", "Müller", date(1980, 2, 3)) == match_key(
        " jorg ", "MULLER", date(1980, 2, 3)
    )
    assert normalize_team_name("Die  Läufer") == normalize_team_name("DIE LAUFER")
    assert normalize_team_name("   ") is None


def test_format_time():
    assert format_time(Decimal("3661")) == "1:01:01"
    assert format_time(Decimal("125.4")) == "2:05"
    assert format_time(None) == ""

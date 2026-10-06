"""Area: Ergebnisse & Urkunden (Platzierungen, Altersklassen, Einzel-/Sammel-PDF,
öffentliche Ergebnisliste mit Einwilligung, Staffeln)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tools.e2e.api import registration_payload

R = "/api/{slug}/team/results"
T = "/api/{slug}/team/timing"

# name, gender, birth year offset (age at event), finish minutes, consent_publish
FIELD = [
    ("Anna", "f", 30, 40.0, True),
    ("Bea", "f", 32, 41.0, True),
    ("Carla", "f", 55, 45.0, False),
    ("Dirk", "m", 30, 38.0, True),
    ("Emil", "m", 62, 50.0, True),
]


@pytest.fixture(scope="module")
def field(admin, cfg, event, comps) -> dict:
    comp = comps["10 km"]
    start = datetime.fromisoformat(comp["start_time"])
    out = {}
    for name, gender, age, minutes, consent in FIELD:
        r = admin.post(
            f"/api/{cfg.slug}/team/registrations",
            json=registration_payload(
                event["id"],
                comp["id"],
                first_name=name,
                last_name="E2E-Urkunde",
                gender=gender,
                birth_date=f"{event['year'] - age}-06-15",
                consent_publish=consent,
            ),
        )
        assert r.status_code == 201, r.text
        out[name] = r.json()
        r = admin.post(
            f"{T.format(slug=cfg.slug)}/records/manual",
            json={
                "event_id": event["id"],
                "bib_number": out[name]["bib_number"],
                "absolute_time": (start + timedelta(minutes=minutes)).isoformat(),
            },
        )
        assert r.status_code == 201, r.text
    # relay competition: one complete relay of three, one incomplete pair
    relay = comps["Staffel 3x2 km"]
    rstart = datetime.fromisoformat(relay["start_time"])
    for i, (team, minutes) in enumerate(
        [
            ("E2E Staffel Rot", 8),
            ("E2E Staffel Rot", 9),
            ("E2E Staffel Rot", 10),
            ("E2E Staffel Blau", 7),
            ("E2E Staffel Blau", 7),
        ]
    ):
        r = admin.post(
            f"/api/{cfg.slug}/team/registrations",
            json=registration_payload(
                event["id"],
                relay["id"],
                first_name=f"Staffel{i}",
                last_name="E2E-Relay",
                team_name=team,
                gender="m",
            ),
        )
        assert r.status_code == 201, r.text
        out[f"relay{i}"] = r.json()
        admin.post(
            f"{T.format(slug=cfg.slug)}/records/manual",
            json={
                "event_id": event["id"],
                "bib_number": r.json()["bib_number"],
                "absolute_time": (rstart + timedelta(minutes=minutes)).isoformat(),
            },
        )
    r = admin.post(f"{T.format(slug=cfg.slug)}/compute", params={"event_id": event["id"]})
    assert r.status_code == 200 and r.json()["computed"] >= 10 and r.json()["relays_formed"] == 1, (
        r.text
    )
    return out


def test_overview_counts(admin, cfg, event, comps, field):
    ov = admin.get(f"{R.format(slug=cfg.slug)}/overview", params={"event_id": event["id"]}).json()
    comp = next(c for c in ov["competitions"] if c["competition"]["id"] == comps["10 km"]["id"])
    assert comp["finished"] >= 5
    classes = {c["age_class"]: c for c in comp["age_classes"]}
    assert any("30" in k for k in classes), classes.keys()
    assert sum(c["total"] for c in comp["age_classes"]) == comp["finished"]


def test_placements_overall_gender_and_age_class(admin, cfg, event, comps, field):
    res = admin.get(
        f"{T.format(slug=cfg.slug)}/internal-results", params={"event_id": event["id"]}
    ).json()
    comp = next(c for c in res["competitions"] if c["competition"]["id"] == comps["10 km"]["id"])
    rows = {r["name"].split(" ")[0]: r for r in comp["rows"] if r["name"].endswith("E2E-Urkunde")}
    assert rows["Dirk"]["place"] == 1 and rows["Anna"]["place"] == 2
    assert (
        rows["Anna"]["place_gender"] == 1
        and rows["Bea"]["place_gender"] == 2
        and rows["Dirk"]["place_gender"] == 1
    )
    assert (
        rows["Anna"]["age_class"] == rows["Bea"]["age_class"]
        and rows["Anna"]["place_age_class"] == 1
        and rows["Bea"]["place_age_class"] == 2
    )
    assert (
        rows["Carla"]["age_class"] != rows["Anna"]["age_class"]
        and rows["Carla"]["place_age_class"] == 1
    )
    assert rows["Anna"]["time"] == "40:00,00" or rows["Anna"]["time"].startswith("40:00")


def test_single_certificate(admin, cfg, event, field):
    url = f"{R.format(slug=cfg.slug)}/certificate.pdf"
    r = admin.get(url, params={"event_id": event["id"], "bib_number": field["Anna"]["bib_number"]})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    r = admin.get(
        url,
        params={
            "event_id": event["id"],
            "bib_number": field["Anna"]["bib_number"],
            "print_background": "false",
        },
    )
    assert r.status_code == 200
    assert admin.get(url, params={"event_id": event["id"], "bib_number": 999998}).status_code == 404


def test_batch_certificates_with_filters(admin, cfg, event, comps, field):
    url = f"{R.format(slug=cfg.slug)}/certificates.pdf"
    cid = comps["10 km"]["id"]
    r = admin.get(url, params={"event_id": event["id"], "competition_id": cid})
    assert r.status_code == 200 and int(r.headers["X-Certificate-Count"]) >= 5
    r = admin.get(url, params={"event_id": event["id"], "competition_id": cid, "gender": "f"})
    assert int(r.headers["X-Certificate-Count"]) >= 3
    res = admin.get(
        f"{T.format(slug=cfg.slug)}/internal-results", params={"event_id": event["id"]}
    ).json()
    anna = next(
        row
        for c in res["competitions"]
        for row in c["rows"]
        if row["bib_number"] == field["Anna"]["bib_number"]
    )
    r = admin.get(
        url,
        params={
            "event_id": event["id"],
            "competition_id": cid,
            "age_class": anna["age_class"],
            "gender": "f",
        },
    )
    assert r.status_code == 200 and int(r.headers["X-Certificate-Count"]) >= 2
    assert (
        admin.get(
            url, params={"event_id": event["id"], "competition_id": cid, "age_class": "Nonexistent"}
        ).status_code
        == 404
    )
    assert (
        admin.get(
            url,
            params={"event_id": event["id"], "competition_id": comps["5 km"]["id"], "gender": "q"},
        ).status_code
        == 404
    )


def test_public_results_respect_consent(anon, cfg, event, comps, field):
    res = anon.get(f"/api/public/{cfg.slug}/results", params={"event_id": event["id"]}).json()
    assert res["event"]["id"] == event["id"] and any(e["id"] == event["id"] for e in res["events"])
    comp = next(c for c in res["competitions"] if c["competition"]["id"] == comps["10 km"]["id"])
    names = [r["name"] for r in comp["rows"]]
    assert (
        "Anna E2E-Urkunde" in names and "Carla E2E-Urkunde" not in names
    )  # no consent → not published
    assert all(r["time"] for r in comp["rows"])
    assert (
        anon.get(
            f"/api/public/{cfg.slug}/results",
            params={"event_id": "00000000-0000-0000-0000-000000000000"},
        ).status_code
        == 404
    )


def test_relays(admin, cfg, event, comps, field):
    res = admin.get(
        f"{T.format(slug=cfg.slug)}/internal-results", params={"event_id": event["id"]}
    ).json()
    comp = next(
        c for c in res["competitions"] if c["competition"]["id"] == comps["Staffel 3x2 km"]["id"]
    )
    assert comp["competition"]["relay_scoring"] is True
    assert len(comp["relays"]) == 1
    rot = comp["relays"][0]
    assert (
        rot["team_name"] == "E2E Staffel Rot"
        and rot["complete"] is True
        and rot["place"] == 1
        and abs(rot["total_seconds"] - 27 * 60) < 0.01
    )
    rot_rows = [r for r in comp["rows"] if r["team_name"] == "E2E Staffel Rot"]
    assert all(r["relay_place"] == 1 and r["relay_total"] == 1 for r in rot_rows)
    blau = [r for r in comp["rows"] if r["team_name"] == "E2E Staffel Blau"]
    assert blau and all(r["relay_place"] is None for r in blau)  # only two → no relay
    # relay time format
    assert rot_rows[0]["relay_time"].startswith("27:00")

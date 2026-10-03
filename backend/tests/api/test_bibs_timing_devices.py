"""Bib ranges & concurrency, relays, device tokens (hash only, shown once), templates, certs."""

from __future__ import annotations

import asyncio
import io
from datetime import datetime, timedelta

import httpx
from app.db.models import DeviceToken
from app.db.session import get_sessionmaker
from app.main import app
from PIL import Image
from sqlalchemy import select

from tests.conftest import (
    competition_payload,
    create_org,
    event_payload,
    login,
    registration_payload,
    setup_event,
)


async def test_bib_ranges_shared_and_outside(client):
    await create_org("bibs")
    s = await login(client, "bibs")
    ev, comps = await setup_event(
        s,
        event=event_payload(bib_start_number=1),
        competitions=[
            competition_payload(title_de="Kinder", bib_range_start=1, bib_range_end=3),
            competition_payload(
                title_de="Bambini", bib_range_start=1, bib_range_end=3
            ),  # shared range
            competition_payload(title_de="Haupt", bib_range_start=None, bib_range_end=None),
            competition_payload(title_de="Walking", bib_range_start=10, bib_range_end=12),
        ],
    )
    kinder, bambini, haupt, walking = comps

    async def reg(comp):
        r = await client.post(
            "/api/public/bibs/registrations", json=registration_payload(ev["id"], comp["id"])
        )
        return r

    assert (await reg(kinder)).json()["bib_number"] == 1
    assert (await reg(bambini)).json()["bib_number"] == 2  # shared range counts up together
    assert (await reg(haupt)).json()["bib_number"] == 4  # skips 1–3
    assert (await reg(kinder)).json()["bib_number"] == 3
    r = await reg(bambini)
    assert r.status_code == 409 and "voll" in r.json()["detail"]
    assert (await reg(haupt)).json()["bib_number"] == 5
    assert (await reg(walking)).json()["bib_number"] == 10
    for _ in range(5):
        last = (await reg(haupt)).json()["bib_number"]
    assert last == 13  # 6,7,8,9 then skip 10–12 → 13

    # changing the competition never changes the bib; manual re-assignment does; duplicates → 409
    regs = (await s.get(f"/api/bibs/team/registrations?event_id={ev['id']}")).json()["items"]
    item = next(x for x in regs if x["bib_number"] == 13)
    r = await s.patch(
        f"/api/bibs/team/registrations/{item['id']}", json={"competition_id": walking["id"]}
    )
    assert r.json()["bib_number"] == 13
    r = await s.patch(f"/api/bibs/team/registrations/{item['id']}", json={"bib_number": 10})
    assert r.status_code == 409
    r = await s.patch(f"/api/bibs/team/registrations/{item['id']}", json={"bib_number": 99})
    assert r.status_code == 200 and r.json()["bib_number"] == 99

    # invalid ranges rejected
    r = await s.post(
        f"/api/bibs/team/events/{ev['id']}/competitions",
        json=competition_payload(bib_range_start=5, bib_range_end=None),
    )
    assert r.status_code == 422
    r = await s.post(
        f"/api/bibs/team/events/{ev['id']}/competitions",
        json=competition_payload(bib_range_start=5, bib_range_end=4),
    )
    assert r.status_code == 422


async def test_concurrent_registrations_get_unique_bibs(client):
    await create_org("conc")
    s = await login(client, "conc")
    ev, comps = await setup_event(s)

    async def one(i: int):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post(
                "/api/public/conc/registrations",
                json=registration_payload(
                    ev["id"], comps[0]["id"], last_name=f"Parallel{i}", birth_date="1980-01-01"
                ),
            )
            assert r.status_code == 201, r.text
            return r.json()["bib_number"]

    bibs = await asyncio.gather(*(one(i) for i in range(25)))
    assert sorted(bibs) == list(range(1, 26))


async def test_relays_and_certificates(client):
    await create_org("relay")
    s = await login(client, "relay")
    ev, comps = await setup_event(s, competitions=[competition_payload(relay_scoring=True)])
    comp = comps[0]
    start = datetime.fromisoformat(comp["start_time"])
    people = [
        ("Team Rot", 1),
        ("team rot ", 2),
        ("TEAM ROT", 3),
        ("Blau", 4),
        ("Blau", 5),
        ("Grün", 6),
        ("Grün", 7),
        ("Grün", 8),
        ("Grün", 9),
    ]
    bibs = {}
    for i, (team, _) in enumerate(people):
        r = await client.post(
            "/api/public/relay/registrations",
            json=registration_payload(
                ev["id"],
                comp["id"],
                team_name=team,
                last_name=f"L{i}",
                birth_date=f"19{70 + i}-01-01",
                gender="m" if i % 2 else "f",
            ),
        )
        bibs[i] = r.json()["bib_number"]
    dev = (await s.post("/api/relay/team/timing/devices", json={"label": "A"})).json()
    records = [
        {
            "bib_number": bibs[i],
            "absolute_time": (start + timedelta(minutes=40 + i)).isoformat(),
            "dedup_key": f"relay-key-{i}",
        }
        for i in range(9)
        if i != 7
    ]
    r = await client.post(
        "/api/relay/timing/records",
        json={"event_id": ev["id"], "records": records},
        headers={"X-Device-Token": dev["token"]},
    )
    assert r.json()["inserted"] == 8
    r = await s.post(f"/api/relay/team/timing/compute?event_id={ev['id']}")
    assert r.json() == {
        "computed": 8,
        "without_start_time": 0,
        "relays_formed": 1,
    }  # only Team Rot (3 members)

    internal = (await s.get(f"/api/relay/team/timing/internal-results?event_id={ev['id']}")).json()
    comp_res = internal["competitions"][0]
    assert comp_res["unfinished"] == 1
    assert (
        len(comp_res["relays"]) == 1
        and comp_res["relays"][0]["complete"]
        and comp_res["relays"][0]["place"] == 1
    )
    rot_rows = [row for row in comp_res["rows"] if row["relay_place"] == 1]
    assert len(rot_rows) == 3 and rot_rows[0]["relay_time"] == "2:03:00"

    # disabling relay scoring clears assignments on the next recomputation
    await s.patch(
        f"/api/relay/team/events/{ev['id']}/competitions/{comp['id']}",
        json=competition_payload(relay_scoring=False),
    )
    r = await s.post(f"/api/relay/team/timing/compute?event_id={ev['id']}")
    assert r.json()["relays_formed"] == 0
    detail = (
        await s.get(f"/api/relay/team/registrations/by-bib/{bibs[0]}?event_id={ev['id']}")
    ).json()
    assert detail["relay_id"] is None

    # certificate printing
    overview = (await s.get(f"/api/relay/team/results/overview?event_id={ev['id']}")).json()
    assert overview["competitions"][0]["finished"] == 8
    r = await s.get(
        f"/api/relay/team/results/certificates.pdf?event_id={ev['id']}&competition_id={comp['id']}"
    )
    assert (
        r.status_code == 200
        and r.headers["x-certificate-count"] == "8"
        and r.content[:4] == b"%PDF"
    )
    r = await s.get(
        f"/api/relay/team/results/certificates.pdf?event_id={ev['id']}&competition_id={comp['id']}&gender=f&print_background=false"
    )
    assert r.status_code == 200 and r.headers["x-certificate-count"] == "5"
    r = await s.get(
        f"/api/relay/team/results/certificate.pdf?event_id={ev['id']}&bib_number={bibs[7]}"
    )
    assert r.status_code == 404  # no time
    r = await s.get(
        f"/api/relay/team/results/certificate.pdf?event_id={ev['id']}&bib_number={bibs[0]}"
    )
    assert r.status_code == 200

    # plausibility: add a second, far-apart recording for bib 1
    r = await s.post(
        "/api/relay/team/timing/records/manual",
        json={
            "event_id": ev["id"],
            "bib_number": bibs[0],
            "absolute_time": (start + timedelta(minutes=40, seconds=10)).isoformat(),
        },
    )
    assert r.status_code == 201 and r.json()["status"] == "manual"
    pl = (
        await s.get(f"/api/relay/team/timing/plausibility?event_id={ev['id']}&threshold_seconds=3")
    ).json()
    assert [e["bib_number"] for e in pl["entries"]] == [bibs[0]] and pl["entries"][0][
        "spread_seconds"
    ] == 10.0
    # ignoring the outlier removes it from the mean
    recs = (
        await s.get(f"/api/relay/team/timing/records?event_id={ev['id']}&bib_number={bibs[0]}")
    ).json()
    manual = next(x for x in recs if x["status"] == "manual")
    await s.patch(f"/api/relay/team/timing/records/{manual['id']}", json={"status": "ignored"})
    pl = (
        await s.get(f"/api/relay/team/timing/plausibility?event_id={ev['id']}&threshold_seconds=3")
    ).json()
    assert pl["entries"] == []


async def test_device_tokens_are_hashed_and_shown_once(client):
    await create_org("dev")
    s = await login(client, "dev")
    r = await s.post(
        "/api/dev/team/timing/devices", json={"label": "Ziel 1", "time_offset_seconds": 1}
    )
    assert r.status_code == 201
    issued = r.json()
    assert issued["token"] in issued["kiosk_url"]
    # the list never returns the plaintext token
    listed = (await s.get("/api/dev/team/timing/devices")).json()
    assert "token" not in listed[0] and "token_hash" not in listed[0]
    async with get_sessionmaker()() as db:
        row = (await db.execute(select(DeviceToken))).scalar_one()
        assert row.token_hash != issued["token"] and len(row.token_hash) == 64
    ctx = await client.get("/api/dev/timing/context", headers={"X-Device-Token": issued["token"]})
    assert (
        ctx.status_code == 200
        and ctx.json()["device"] is True
        and ctx.json()["offset_seconds"] == 1
    )
    # reissue invalidates the old token; label collision → 409
    r = await s.post(f"/api/dev/team/timing/devices/{issued['id']}/reissue")
    new_token = r.json()["token"]
    assert new_token != issued["token"]
    assert (
        await client.get("/api/dev/timing/context", headers={"X-Device-Token": issued["token"]})
    ).status_code == 401
    assert (
        await client.get("/api/dev/timing/context", headers={"X-Device-Token": new_token})
    ).status_code == 200
    assert (
        await s.post("/api/dev/team/timing/devices", json={"label": "Ziel 1"})
    ).status_code == 409
    # revoking blocks the device; last_used_at is recorded
    await s.patch(f"/api/dev/team/timing/devices/{issued['id']}", json={"is_active": False})
    assert (
        await client.get("/api/dev/timing/context", headers={"X-Device-Token": new_token})
    ).status_code == 401
    listed = (await s.get("/api/dev/team/timing/devices")).json()
    assert listed[0]["last_used_at"] is not None and listed[0]["is_active"] is False
    # kiosk without any credential → 401
    assert (await client.get("/api/dev/timing/context")).status_code == 401


async def test_event_template_export_import_and_backgrounds(client):
    await create_org("tpl")
    s = await login(client, "tpl")
    ev, comps = await setup_event(
        s,
        competitions=[
            competition_payload(bib_range_start=100, bib_range_end=199),
            competition_payload(title_de="5 km"),
        ],
    )
    tpl = (await s.get(f"/api/tpl/team/events/{ev['id']}/template")).json()
    assert "year" not in tpl and "event_date" not in tpl and len(tpl["competitions"]) == 2
    assert tpl["competitions"][0]["start_time"] is None
    r = await s.post(
        "/api/tpl/team/events/import",
        json={
            **tpl,
            "year": 2027,
            "event_date": "2027-06-13",
            "default_start_time": "2027-06-13T10:00:00+02:00",
        },
    )
    assert r.status_code == 201
    imported = r.json()
    assert imported["year"] == 2027 and len(imported["competitions"]) == 2
    assert imported["competitions"][0]["start_time"].startswith("2027-06-13")

    img = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(img, format="PNG")
    r = await s.post(
        f"/api/tpl/team/events/{ev['id']}/background/certificate",
        files={"file": ("bg.png", img.getvalue(), "image/png")},
    )
    assert r.status_code == 200
    assert (await s.get(f"/api/tpl/team/events/{ev['id']}")).json()[
        "has_certificate_background"
    ] is True
    r = await s.post(
        f"/api/tpl/team/events/{ev['id']}/background/bib",
        files={"file": ("bg.txt", b"not an image", "text/plain")},
    )
    assert r.status_code == 400
    r = await s.patch(
        f"/api/tpl/team/events/{ev['id']}",
        json={
            "clear_fields": ["certificate_background"],
            "photo_base_url": "https://photos.example.org/lauf",
            "photo_hmac_seed": "abc123",
        },
    )
    assert r.json()["has_certificate_background"] is False and r.json()["photo_seed_set"] is True
    # photo link appears on the manage page, seed is never exposed
    reg = (
        await client.post(
            "/api/public/tpl/registrations", json=registration_payload(ev["id"], comps[0]["id"])
        )
    ).json()
    view = (
        await client.get(f"/api/public/tpl/manage?token={reg['manage_url'].split('token=')[1]}")
    ).json()
    assert view["photo_url"].startswith("https://photos.example.org/lauf/") and view[
        "photo_url"
    ].endswith("/index.html")
    assert len(view["photo_url"].split("/")[-2]) == 40
    assert "abc123" not in str(view)
    info = (await client.get("/api/public/tpl/info")).json()
    assert "abc123" not in str(info)


async def test_sponsors_upload_and_display_settings(client):
    await create_org("spons")
    s = await login(client, "spons")
    img = io.BytesIO()
    Image.new("RGBA", (1200, 800), (255, 0, 0, 255)).save(img, format="PNG")
    r = await s.post(
        "/api/spons/team/sponsors",
        data={"tier": "1", "name": "Bäckerei", "url": "https://example.org"},
        files={"file": ("logo.png", img.getvalue(), "image/png")},
    )
    assert r.status_code == 201
    pub = (await client.get("/api/public/spons/sponsors")).json()
    assert pub[0]["name"] == "Bäckerei" and pub[0]["tier"] == 1
    image = await client.get(pub[0]["image_url"])
    assert image.status_code == 200
    w, h = Image.open(io.BytesIO(image.content)).size
    assert max(w, h) <= 600  # normalised server-side
    r = await s.put(
        "/api/spons/team/sponsors/display",
        json={"sponsor_mode": "marquee", "sponsor_marquee_seconds": 4},
    )
    assert r.status_code == 400
    r = await s.put(
        "/api/spons/team/sponsors/display",
        json={"sponsor_mode": "marquee", "sponsor_marquee_seconds": 20},
    )
    assert r.status_code == 200 and r.json()["sponsor_mode"] == "marquee"
    info = (await client.get("/api/public/spons/info")).json()
    assert (
        info["sponsor_display"]["mode"] == "marquee"
        and info["sponsor_display"]["marquee_seconds"] == 20
    )

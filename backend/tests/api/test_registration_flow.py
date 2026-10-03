"""Public registration flow: all payment methods, duplicate detection, deadline, manage page,
freeze after timing, PDFs, mail after commit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.payments.sumup import FakeSumUpClient

from tests.conftest import (
    VALID_IBAN,
    create_org,
    login,
    registration_payload,
    setup_event,
)


async def test_full_race_day(client, mails):
    org = await create_org("groebenzell")
    s = await login(client, "groebenzell")
    ev, comps = await setup_event(s)
    comp = comps[0]

    # 1. on-site registration
    r = await client.post(
        f"/api/public/{org.slug}/registrations", json=registration_payload(ev["id"], comp["id"])
    )
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["bib_number"] == 1
    assert first["payment"]["method"] == "on_site" and first["payment"]["amount_cents"] == 1500
    assert "/groebenzell/manage?token=" in first["manage_url"]
    token = first["manage_url"].split("token=")[1]

    # mail was sent after commit (mode test → redirected to test recipient)
    await s.put("/api/groebenzell/team/settings", json={"values": {"mail_mode": "test"}})
    r = await client.post(
        f"/api/public/{org.slug}/registrations",
        json=registration_payload(ev["id"], comp["id"], birth_date="2012-03-03"),
    )
    assert r.status_code == 201
    youth = r.json()
    assert youth["payment"]["amount_cents"] == 800  # youth price
    assert youth["bib_number"] == 2
    assert len(mails.sent) == 1 and mails.sent[0].to == "test@example.org"
    assert youth["manage_url"] in mails.sent[0].text and "[TEST" in mails.sent[0].subject

    # 2. SEPA registration
    r = await client.post(
        f"/api/public/{org.slug}/registrations",
        json=registration_payload(
            ev["id"],
            comp["id"],
            payment_method="sepa_debit",
            iban=VALID_IBAN,
            account_holder="Anna Test",
        ),
    )
    assert r.status_code == 201, r.text
    sepa = r.json()
    assert (
        sepa["payment"]["iban_masked"].startswith("DE89")
        and "0532" not in sepa["payment"]["iban_masked"]
    )
    assert sepa["payment"]["mandate_reference"].startswith("BIBBY-2026-")

    # invalid IBAN rejected
    r = await client.post(
        f"/api/public/{org.slug}/registrations",
        json=registration_payload(
            ev["id"], comp["id"], payment_method="sepa_debit", iban="DE00 1234"
        ),
    )
    assert r.status_code == 400 and "IBAN" in r.json()["detail"]

    # 3. duplicate registration of the same person (name+birth date) → IntegrityError → 409
    dup = registration_payload(
        ev["id"], comp["id"], first_name="Anna", last_name="Doppelt", birth_date="1991-01-01"
    )
    assert (await client.post(f"/api/public/{org.slug}/registrations", json=dup)).status_code == 201
    r = await client.post(
        f"/api/public/{org.slug}/registrations",
        json={**dup, "first_name": " anna ", "last_name": "DOPPELT", "email": "x@example.org"},
    )
    assert r.status_code == 409 and "bereits angemeldet" in r.json()["detail"]

    # 4. manage page
    r = await client.get(f"/api/public/{org.slug}/manage", params={"token": token})
    assert r.status_code == 200
    view = r.json()
    assert view["bib_number"] == 1 and view["frozen"] is False and view["photo_url"] is None
    r = await client.get(f"/api/public/{org.slug}/manage", params={"token": "wrong"})
    assert r.status_code == 404

    r = await client.patch(
        f"/api/public/{org.slug}/manage",
        params={"token": token},
        json={"team_name": "Die Flitzer", "tshirt_size": "L"},
    )
    assert r.status_code == 200 and r.json()["team_name"] == "Die Flitzer"
    r = await client.patch(
        f"/api/public/{org.slug}/manage", params={"token": token}, json={"tshirt_size": "XXL"}
    )
    assert r.status_code == 400

    # bib pdf available, certificate not before timing
    r = await client.get(f"/api/public/{org.slug}/manage/bib.pdf", params={"token": token})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    r = await client.get(f"/api/public/{org.slug}/manage/certificate.pdf", params={"token": token})
    assert r.status_code == 404

    # 5. timing: two devices record bib 1, compute → frozen
    r = await s.post("/api/groebenzell/team/timing/devices", json={"label": "Handy A"})
    assert r.status_code == 201
    dev_a = r.json()
    r = await s.post(
        "/api/groebenzell/team/timing/devices", json={"label": "Handy B", "time_offset_seconds": 2}
    )
    dev_b = r.json()
    base = datetime.fromisoformat(comp["start_time"])
    t1 = base + timedelta(minutes=45)
    body = {
        "event_id": ev["id"],
        "records": [{"bib_number": 1, "absolute_time": t1.isoformat(), "dedup_key": "devA-0001"}],
    }
    r = await client.post(
        f"/api/{org.slug}/timing/records", json=body, headers={"X-Device-Token": dev_a["token"]}
    )
    assert r.status_code == 200 and r.json() == {"inserted": 1, "duplicates": 0}
    # idempotent re-upload (offline queue retry)
    r = await client.post(
        f"/api/{org.slug}/timing/records", json=body, headers={"X-Device-Token": dev_a["token"]}
    )
    assert r.json() == {"inserted": 0, "duplicates": 1}
    body_b = {
        "event_id": ev["id"],
        "records": [{"bib_number": 1, "absolute_time": t1.isoformat(), "dedup_key": "devB-0001"}],
    }
    r = await client.post(
        f"/api/{org.slug}/timing/records", json=body_b, headers={"X-Device-Token": dev_b["token"]}
    )
    assert r.status_code == 200
    r = await s.post("/api/groebenzell/team/timing/compute", params={"event_id": ev["id"]})
    assert r.status_code == 200 and r.json()["computed"] == 1

    r = await client.get(f"/api/public/{org.slug}/manage", params={"token": token})
    view = r.json()
    # device B has +2 s offset → mean of 45:00 and 45:02 = 45:01
    assert view["frozen"] is True and float(view["finish_seconds"]) == 2701.0
    r = await client.patch(
        f"/api/public/{org.slug}/manage", params={"token": token}, json={"team_name": "Neu"}
    )
    assert r.status_code == 409
    r = await client.get(f"/api/public/{org.slug}/manage/certificate.pdf", params={"token": token})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"

    # 6. public results only list consenting finishers; office still may edit frozen rows
    r = await client.get(f"/api/public/{org.slug}/results")
    rows = r.json()["competitions"][0]["rows"]
    assert len(rows) == 1 and rows[0]["bib_number"] == 1 and rows[0]["time"] == "45:01"
    r = await s.patch(
        f"/api/groebenzell/team/registrations/{first['registration_id']}",
        json={"team_name": "Office"},
    )
    assert r.status_code == 200 and r.json()["team_name"] == "Office"

    # 7. stats and sepa export
    r = await s.get("/api/groebenzell/team/stats", params={"event_id": ev["id"]})
    assert r.status_code == 200
    stats = r.json()
    assert stats["overview"]["participants"] == 4 and stats["overview"]["finished"] == 1
    assert stats["travel"]["available"] and stats["travel"]["counted"] == 4
    r = await s.post("/api/groebenzell/team/sepa/export.csv", params={"event_id": ev["id"]})
    assert r.status_code == 200 and r.headers["x-row-count"] == "1"
    assert "DE89370400440532013000" in r.text and "Startgeld Stadtlauf 2026" in r.text
    r = await s.post("/api/groebenzell/team/sepa/export.csv", params={"event_id": ev["id"]})
    assert r.headers["x-row-count"] == "0"  # already exported
    r = await s.post(
        "/api/groebenzell/team/sepa/export.csv",
        params={"event_id": ev["id"], "include_exported": "true"},
    )
    assert r.headers["x-row-count"] == "1"


async def test_deadline_enforced_server_side(client):
    org = await create_org("deadline")
    s = await login(client, "deadline")
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    ev, comps = await setup_event(
        s,
        event={
            **__import__("tests.conftest", fromlist=["event_payload"]).event_payload(),
            "registration_deadline": past,
        },
    )
    r = await client.post(
        f"/api/public/{org.slug}/registrations", json=registration_payload(ev["id"], comps[0]["id"])
    )
    assert r.status_code == 400 and "Meldeschluss" in r.json()["detail"]
    # office may still register after the deadline
    r = await s.post(
        "/api/deadline/team/registrations", json=registration_payload(ev["id"], comps[0]["id"])
    )
    assert r.status_code == 201


async def test_online_payment_flow(client):
    org = await create_org("online")
    s = await login(client, "online")
    ev, comps = await setup_event(s)
    # not configured → sumup not offered / rejected
    info = (await client.get(f"/api/public/{org.slug}/info")).json()
    assert "sumup" not in info["payment_methods"]
    r = await client.post(
        f"/api/public/{org.slug}/registrations",
        json=registration_payload(ev["id"], comps[0]["id"], payment_method="sumup"),
    )
    assert r.status_code == 400

    r = await s.put(
        "/api/online/team/settings",
        json={"values": {"sumup_api_key": "sup_sk_test_CHANGE_ME", "sumup_merchant_code": "MC123"}},
    )
    assert (
        r.status_code == 200
        and r.json()["sumup_api_key_set"] is True
        and "sumup_api_key" not in r.json()
    )
    info = (await client.get(f"/api/public/{org.slug}/info")).json()
    assert "sumup" in info["payment_methods"]

    # provider down → nothing stored
    FakeSumUpClient.fail_create = True
    r = await client.post(
        f"/api/public/{org.slug}/registrations",
        json=registration_payload(ev["id"], comps[0]["id"], payment_method="sumup"),
    )
    assert r.status_code == 503
    assert (await s.get("/api/online/team/registrations", params={"event_id": ev["id"]})).json()[
        "total"
    ] == 0
    FakeSumUpClient.fail_create = False

    r = await client.post(
        f"/api/public/{org.slug}/registrations",
        json=registration_payload(ev["id"], comps[0]["id"], payment_method="sumup"),
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["checkout_url"].startswith("https://pay.example.org/")
    token = created["manage_url"].split("token=")[1]
    view = (await client.get(f"/api/public/{org.slug}/manage", params={"token": token})).json()
    assert view["payment"]["status"] == "pending"
    # fresh checkout for an open payment
    r = await client.post(f"/api/public/{org.slug}/manage/checkout", params={"token": token})
    assert r.status_code == 200 and r.json()["checkout_url"]
    checkout_id = r.json()["checkout_url"].rsplit("/", 1)[1]  # the latest checkout counts

    # a forged webhook payload does not mark anything paid – status is verified at the provider
    r = await client.post(
        f"/api/public/{org.slug}/payments/webhook", json={"id": checkout_id, "status": "PAID"}
    )
    assert r.json()["paid"] is False
    FakeSumUpClient.mark_paid(checkout_id, "TX-777")
    r = await client.post(f"/api/public/{org.slug}/payments/webhook", json={"id": checkout_id})
    assert r.json()["paid"] is True
    view = (await client.get(f"/api/public/{org.slug}/manage", params={"token": token})).json()
    assert (
        view["payment"]["status"] == "paid"
        and view["payment"]["provider_transaction_code"] == "TX-777"
    )
    r = await client.post(f"/api/public/{org.slug}/manage/checkout", params={"token": token})
    assert r.json()["status"] == "paid"

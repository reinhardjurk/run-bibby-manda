"""Area: Anmeldebüro / Verwaltung der Anmeldungen (Suche, Paging, Bezahlt, Vollbearbeitung,
Startnummern-Konflikte, Dubletten zusammenführen, Löschen)."""

from __future__ import annotations

import random

import pytest

from tools.e2e.api import VALID_IBAN, event_payload, registration_payload, unique

BASE = "/api/{slug}/team/registrations"


def _office(admin, cfg, event, comp, **kw) -> dict:
    r = admin.post(
        BASE.format(slug=cfg.slug), json=registration_payload(event["id"], comp["id"], **kw)
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="module")
def three(admin, cfg, event, comps) -> list[dict]:
    created = [
        _office(
            admin, cfg, event, comps["5 km"], first_name=f"Rezeption{i}", last_name=f"E2E-Suche{i}"
        )
        for i in range(3)
    ]
    return [
        admin.get(f"{BASE.format(slug=cfg.slug)}/{c['registration_id']}").json() for c in created
    ]


def test_office_registration_is_confirmed_and_unpaid(three):
    for reg in three:
        assert reg["status"] == "confirmed" and reg["payment"]["status"] == "pending"
        assert reg["bib_number"] and reg["participant_id"]


def test_search_by_name_bib_and_paging(admin, cfg, event, three):
    url = BASE.format(slug=cfg.slug)
    r = admin.get(url, params={"event_id": event["id"], "q": "e2e-suche1"}).json()
    assert r["total"] == 1 and r["items"][0]["last_name"] == "E2E-Suche1"
    r = admin.get(url, params={"event_id": event["id"], "q": "rezeption2 e2e"}).json()
    assert r["total"] == 1  # "first last" search
    r = admin.get(url, params={"event_id": event["id"], "q": str(three[0]["bib_number"])}).json()
    assert any(i["id"] == three[0]["id"] for i in r["items"])
    r = admin.get(url, params={"event_id": event["id"], "page_size": 1, "page": 2}).json()
    assert r["total"] >= 3 and len(r["items"]) == 1 and r["page"] == 2
    r = admin.get(url, params={"event_id": event["id"], "status": "cancelled"}).json()
    assert all(i["status"] == "cancelled" for i in r["items"])
    assert admin.get(url, params={"event_id": event["id"], "page_size": 9999}).status_code == 422


def test_by_bib(admin, cfg, event, three):
    r = admin.get(
        f"{BASE.format(slug=cfg.slug)}/by-bib/{three[1]['bib_number']}",
        params={"event_id": event["id"]},
    )
    assert r.status_code == 200 and r.json()["id"] == three[1]["id"]
    assert (
        admin.get(
            f"{BASE.format(slug=cfg.slug)}/by-bib/999999", params={"event_id": event["id"]}
        ).status_code
        == 400
    )


def test_mark_paid(admin, cfg, three):
    r = admin.post(f"{BASE.format(slug=cfg.slug)}/{three[0]['id']}/mark-paid")
    assert (
        r.status_code == 200
        and r.json()["payment"]["status"] == "paid"
        and r.json()["payment"]["paid_at"]
    )


def test_full_edit(admin, cfg, comps, three):
    url = f"{BASE.format(slug=cfg.slug)}/{three[1]['id']}"
    r = admin.patch(
        url,
        json={
            "first_name": f"Renate{unique()}",
            "birth_date": "1975-02-02",
            "gender": "x",
            "tshirt_size": "XL",
            "team_name": "E2E Büro",
            "finish_seconds": "1234.56",
            "language": "en",
        },
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["first_name"], b["birth_date"], b["gender"], b["tshirt_size"], b["language"]) == (
        b["first_name"],
        "1975-02-02",
        "x",
        "XL",
        "en",
    )
    assert float(b["finish_seconds"]) == 1234.56
    r = admin.patch(url, json={"clear_finish": True, "competition_id": comps["10 km"]["id"]})
    assert r.json()["finish_seconds"] is None and r.json()["competition_id"] == comps["10 km"]["id"]
    assert r.json()["bib_number"] == three[1]["bib_number"]  # never changes implicitly
    r = admin.patch(
        url,
        json={
            "payment_method": "sepa_debit",
            "iban": VALID_IBAN,
            "account_holder": "E2E Holder",
            "amount_cents": 1500,
        },
    )
    assert r.json()["payment"]["method"] == "sepa_debit" and r.json()["payment"][
        "iban_masked"
    ].startswith("DE89")
    assert admin.patch(url, json={"iban": "DE12 0000"}).status_code == 400
    r = admin.patch(url, json={"payment_status": "paid"})
    assert r.json()["payment"]["status"] == "paid"
    r = admin.patch(url, json={"status": "cancelled"})
    assert r.json()["status"] == "cancelled"
    assert admin.patch(url, json={"status": "confirmed"}).status_code == 200


def test_manual_bib_reassignment_and_conflict(admin, cfg, event, three):
    url = f"{BASE.format(slug=cfg.slug)}/{three[2]['id']}"
    r = admin.patch(url, json={"bib_number": three[0]["bib_number"]})
    assert r.status_code == 409 and "Startnummer" in r.json()["detail"]
    free = 7000 + random.randint(0, 999)
    r = admin.patch(url, json={"bib_number": free})
    assert r.status_code == 200 and r.json()["bib_number"] == free
    r = admin.get(f"{BASE.format(slug=cfg.slug)}/by-bib/{free}", params={"event_id": event["id"]})
    assert r.status_code == 200
    assert (
        admin.get(
            f"{BASE.format(slug=cfg.slug)}/by-bib/{three[2]['bib_number']}",
            params={"event_id": event["id"]},
        ).status_code
        == 400
    )


def test_identity_edit_into_existing_person_conflicts(admin, cfg, three):
    # renaming person 2 so that name + birth date equal person 0 → duplicate person
    p0 = three[0]
    r = admin.patch(
        f"{BASE.format(slug=cfg.slug)}/{three[2]['id']}",
        json={
            "first_name": p0["first_name"],
            "last_name": p0["last_name"],
            "birth_date": p0["birth_date"],
        },
    )
    assert r.status_code == 409 and "zusammenführen" in r.json()["detail"]


def test_merge_participants(admin, cfg, event, comps, three):
    url = BASE.format(slug=cfg.slug)
    # two persons registered in the same event cannot be merged
    r = admin.post(
        f"{url}/merge-participants",
        json={
            "source_participant_id": three[2]["participant_id"],
            "target_participant_id": three[0]["participant_id"],
        },
    )
    assert r.status_code == 409
    assert (
        admin.post(
            f"{url}/merge-participants",
            json={
                "source_participant_id": three[0]["participant_id"],
                "target_participant_id": three[0]["participant_id"],
            },
        ).status_code
        == 400
    )
    # the same person entered with a typo in another event is merged into the real person
    other = admin.post(f"/api/{cfg.slug}/team/events", json=event_payload("Merge")).json()
    comp = admin.post(
        f"/api/{cfg.slug}/team/events/{other['id']}/competitions",
        json={**comps["5 km"], "title_de": "Lauf", "title_en": "Run"},
    ).json()
    dup = _office(admin, cfg, other, comp, first_name="Rezeptoin0", last_name="E2E-Suche0")
    dup_detail = admin.get(f"{url}/{dup['registration_id']}").json()
    r = admin.post(
        f"{url}/merge-participants",
        json={
            "source_participant_id": dup_detail["participant_id"],
            "target_participant_id": three[0]["participant_id"],
        },
    )
    assert r.status_code == 200 and r.json()["moved"] == 1
    merged = admin.get(f"{url}/{dup['registration_id']}").json()
    assert (
        merged["participant_id"] == three[0]["participant_id"]
        and merged["first_name"] == three[0]["first_name"]
    )
    assert admin.delete(f"/api/{cfg.slug}/team/events/{other['id']}").status_code == 204


def test_office_bib_pdf_and_delete(admin, cfg, three):
    url = f"{BASE.format(slug=cfg.slug)}/{three[2]['id']}"
    r = admin.get(f"{url}/bib.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert admin.delete(url).status_code == 204
    assert admin.get(url).status_code == 404
    assert admin.delete(url).status_code == 404

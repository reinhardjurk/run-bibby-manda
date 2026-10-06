"""Area: Online-Anmeldung (Preise, Zahlarten, Dubletten, Meldeschluss, Startnummern)."""

from __future__ import annotations

import pytest

from tools.e2e.api import VALID_IBAN, register, registration_payload, token_of


@pytest.fixture(scope="module")
def state() -> dict:
    return {}


def test_register_on_site_adult(anon, cfg, event, comps, state):
    r = register(anon, cfg.slug, registration_payload(event["id"], comps["5 km"]["id"]))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["payment"] == {
        **body["payment"],
        "method": "on_site",
        "status": "pending",
        "amount_cents": 1000,
    }
    assert body["bib_number"] >= 1 and "token=" in body["manage_url"]
    state["first"] = body


def test_youth_price_and_bib_range(anon, cfg, event, comps, state):
    youth_birth = f"{event['year'] - 10}-03-03"
    r = register(
        anon,
        cfg.slug,
        registration_payload(event["id"], comps["10 km"]["id"], birth_date=youth_birth),
    )
    assert r.status_code == 201, r.text
    assert r.json()["payment"]["amount_cents"] == 800
    assert 100 <= r.json()["bib_number"] <= 199  # inside the configured range
    state["range_first"] = r.json()["bib_number"]
    r2 = register(anon, cfg.slug, registration_payload(event["id"], comps["10 km"]["id"]))
    assert r2.json()["bib_number"] == state["range_first"] + 1  # sequential inside the range


def test_numbers_outside_range_skip_ranges(anon, cfg, event, comps, state):
    r = register(anon, cfg.slug, registration_payload(event["id"], comps["5 km"]["id"]))
    assert r.status_code == 201
    n = r.json()["bib_number"]
    assert not 100 <= n <= 199


def test_sepa_registration(anon, cfg, event, comps, state):
    payload = registration_payload(
        event["id"],
        comps["5 km"]["id"],
        payment_method="sepa_debit",
        iban=VALID_IBAN,
        account_holder="E2E Kontoinhaber",
    )
    r = register(anon, cfg.slug, payload)
    assert r.status_code == 201, r.text
    p = r.json()["payment"]
    assert (
        p["method"] == "sepa_debit"
        and p["iban_masked"].startswith("DE89")
        and "0532" not in p["iban_masked"]
    )
    assert p["mandate_reference"] and p["mandate_reference"].count("-") >= 2
    state["sepa"] = r.json()


def test_invalid_iban_rejected(anon, cfg, event, comps):
    payload = registration_payload(
        event["id"], comps["5 km"]["id"], payment_method="sepa_debit", iban="DE00 1234 5678"
    )
    r = register(anon, cfg.slug, payload)
    assert r.status_code == 400 and "IBAN" in r.json()["detail"]


def test_consent_and_tshirt_validation(anon, cfg, event, comps):
    r = register(
        anon, cfg.slug, registration_payload(event["id"], comps["5 km"]["id"], consent_data=False)
    )
    assert r.status_code == 400
    r = register(
        anon, cfg.slug, registration_payload(event["id"], comps["5 km"]["id"], tshirt_size="XXXXL")
    )
    assert r.status_code == 400
    r = register(
        anon,
        cfg.slug,
        registration_payload(event["id"], comps["5 km"]["id"], heard_about="telepathy"),
    )
    assert r.status_code == 422


def test_duplicate_person_rejected(anon, cfg, event, comps):
    payload = registration_payload(
        event["id"], comps["5 km"]["id"], first_name="Dubletta", birth_date="1988-08-08"
    )
    assert register(anon, cfg.slug, payload).status_code == 201
    again = {**payload, "first_name": " DUBLETTA ", "email": "other@e2e.example.org"}
    r = register(anon, cfg.slug, again)
    assert r.status_code == 409 and "bereits angemeldet" in r.json()["detail"]


def test_team_name_autocomplete(anon, cfg, event, comps):
    team = "E2E Flitzer"
    assert (
        register(
            anon, cfg.slug, registration_payload(event["id"], comps["5 km"]["id"], team_name=team)
        ).status_code
        == 201
    )
    names = anon.get(f"/api/public/{cfg.slug}/team-names", params={"q": "e2e flit"}).json()
    assert team in names


def test_deadline_enforced_server_side(anon, admin, cfg, event, comps, past_deadline):
    r = register(anon, cfg.slug, registration_payload(event["id"], comps["5 km"]["id"]))
    assert r.status_code == 400 and "Meldeschluss" in r.json()["detail"]
    info = anon.get(f"/api/public/{cfg.slug}/info").json()
    ev = next(e for e in info["events"] if e["id"] == event["id"])
    assert ev["registration_open"] is False
    # the race office may still register after the deadline
    r = admin.post(
        f"/api/{cfg.slug}/team/registrations",
        json=registration_payload(event["id"], comps["5 km"]["id"]),
    )
    assert r.status_code == 201


def test_online_payment_if_configured(anon, admin, cfg, event, comps):
    info = anon.get(f"/api/public/{cfg.slug}/info").json()
    if "sumup" not in info["payment_methods"]:
        pytest.skip("SumUp not configured for this organization")
    r = register(
        anon,
        cfg.slug,
        registration_payload(event["id"], comps["5 km"]["id"], payment_method="sumup"),
    )
    assert r.status_code == 201, r.text
    assert r.json()["checkout_url"].startswith("http")
    token = token_of(r.json())
    view = anon.get(f"/api/public/{cfg.slug}/manage", params={"token": token}).json()
    assert view["payment"]["method"] == "sumup" and view["payment"]["status"] == "pending"
    r = anon.post(f"/api/public/{cfg.slug}/manage/checkout", params={"token": token})
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["checkout_url"]
    # a forged webhook never marks anything paid
    r = anon.post(
        f"/api/public/{cfg.slug}/payments/webhook", json={"id": "nonexistent", "status": "PAID"}
    )
    assert r.json()["handled"] is False

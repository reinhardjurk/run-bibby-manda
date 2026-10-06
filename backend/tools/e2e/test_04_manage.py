"""Area: Verwaltungsseite der Teilnehmenden (Ansicht, Änderungen, Downloads, Fotos)."""

from __future__ import annotations

import pytest

from tools.e2e.api import register, registration_payload, token_of


@pytest.fixture(scope="module")
def reg(anon, cfg, event, comps):
    r = register(anon, cfg.slug, registration_payload(event["id"], comps["5 km"]["id"]))
    assert r.status_code == 201, r.text
    return r.json()


def test_view_and_wrong_token(anon, cfg, reg):
    token = token_of(reg)
    view = anon.get(f"/api/public/{cfg.slug}/manage", params={"token": token}).json()
    assert view["bib_number"] == reg["bib_number"] and view["frozen"] is False
    assert view["competitions"] and view["tshirt_options"]
    assert (
        anon.get(f"/api/public/{cfg.slug}/manage", params={"token": token + "x"}).status_code == 404
    )
    if cfg.second_slug:
        assert (
            anon.get(f"/api/public/{cfg.second_slug}/manage", params={"token": token}).status_code
            == 404
        )


def test_update_fields_but_bib_never_changes(anon, cfg, reg, comps):
    token = token_of(reg)
    r = anon.patch(
        f"/api/public/{cfg.slug}/manage",
        params={"token": token},
        json={"team_name": "E2E Team", "tshirt_size": "L", "email": "changed@e2e.example.org"},
    )
    assert r.status_code == 200
    assert (
        r.json()["team_name"] == "E2E Team"
        and r.json()["tshirt_size"] == "L"
        and r.json()["email"] == "changed@e2e.example.org"
    )
    # change competition: price of the open payment follows, bib number stays
    r = anon.patch(
        f"/api/public/{cfg.slug}/manage",
        params={"token": token},
        json={"competition_id": comps["10 km"]["id"]},
    )
    assert r.status_code == 200
    assert (
        r.json()["competition_id"] == comps["10 km"]["id"]
        and r.json()["bib_number"] == reg["bib_number"]
    )
    assert r.json()["payment"]["amount_cents"] == 1500
    assert (
        anon.patch(
            f"/api/public/{cfg.slug}/manage", params={"token": token}, json={"tshirt_size": "nope"}
        ).status_code
        == 400
    )


def test_bib_pdf_and_certificate_before_timing(anon, cfg, reg):
    token = token_of(reg)
    r = anon.get(f"/api/public/{cfg.slug}/manage/bib.pdf", params={"token": token})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert (
        anon.get(
            f"/api/public/{cfg.slug}/manage/certificate.pdf", params={"token": token}
        ).status_code
        == 404
    )


def test_photo_link_uses_hmac_folder(anon, admin, cfg, event, reg):
    eid = event["id"]
    r = admin.patch(
        f"/api/{cfg.slug}/team/events/{eid}",
        json={
            "photo_base_url": "https://photos.example.org/e2e",
            "photo_hmac_seed": "e2e-seed-123",
        },
    )
    assert r.status_code == 200
    view = anon.get(f"/api/public/{cfg.slug}/manage", params={"token": token_of(reg)}).json()
    assert view["photo_url"].startswith("https://photos.example.org/e2e/") and view[
        "photo_url"
    ].endswith("/index.html")
    assert len(view["photo_url"].split("/")[-2]) == 40 and "e2e-seed-123" not in str(view)
    admin.patch(
        f"/api/{cfg.slug}/team/events/{eid}",
        json={"clear_fields": ["photo_base_url", "photo_hmac_seed"]},
    )

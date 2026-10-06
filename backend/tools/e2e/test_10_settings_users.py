"""Area: Organisations-Einstellungen (Mail, Absender, SumUp, Logo) und Benutzer/Rollen."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from tools.e2e.api import TEST_DOMAIN, Session, team_login, unique

SET = "/api/{slug}/team/settings"
USERS = "/api/{slug}/team/users"


def test_settings_view_hides_secrets(admin, cfg):
    v = admin.get(SET.format(slug=cfg.slug)).json()
    assert "sumup_api_key" not in v and isinstance(v["sumup_api_key_set"], bool)
    assert v["mail_mode"] == "off"  # forced by the suite
    assert v["mail_sender_domain"] and v["mail_sender_address"].endswith(
        "@" + v["mail_sender_domain"]
    )


def test_live_mail_requires_confirmation(admin, cfg):
    url = SET.format(slug=cfg.slug)
    assert admin.put(url, json={"values": {"mail_mode": "live"}}).status_code == 400
    assert admin.put(url, json={"values": {"mail_mode": "weird"}}).status_code == 400
    r = admin.put(url, json={"values": {"mail_mode": "live"}, "confirm_live_mail": True})
    assert r.status_code == 200 and r.json()["mail_mode"] == "live"
    assert admin.put(url, json={"values": {"mail_mode": "off"}}).json()["mail_mode"] == "off"
    assert admin.put(url, json={"values": {"no_such_key": "1"}}).status_code == 400


def test_sender_local_part(admin, cfg):
    url = SET.format(slug=cfg.slug)
    v = admin.put(url, json={"values": {"mail_sender_local_part": ""}}).json()
    assert v["mail_sender_address"] == f"noreply-{cfg.slug}@{v['mail_sender_domain']}"
    v = admin.put(url, json={"values": {"mail_sender_local_part": " Anmeldung-E2E "}}).json()
    assert (
        v["mail_sender_local_part"] == "anmeldung-e2e"
        and v["mail_sender_address"] == f"anmeldung-e2e@{v['mail_sender_domain']}"
    )
    for bad in ("a@b", "-start", "ende-", "ümlaut", "x" * 70):
        assert (
            admin.put(url, json={"values": {"mail_sender_local_part": bad}}).status_code == 400
        ), bad
    admin.put(url, json={"values": {"mail_sender_local_part": ""}})


def test_mail_templates_and_sepa_creditor_roundtrip(admin, cfg):
    url = SET.format(slug=cfg.slug)
    v = admin.put(
        url,
        json={
            "values": {
                "mail_subject_de": "E2E Betreff",
                "mail_body_de": "Hallo {link}",
                "sepa_creditor_name": "E2E Verein",
                "sepa_mandate_prefix": "E2E",
            }
        },
    ).json()
    assert (
        v["mail_subject_de"] == "E2E Betreff"
        and v["sepa_creditor_name"] == "E2E Verein"
        and v["sepa_mandate_prefix"] == "E2E"
    )
    # (restored by the suite's settings guard)


def test_sumup_key_is_write_only(admin, cfg):
    url = SET.format(slug=cfg.slug)
    if admin.get(url).json()["sumup_api_key_set"]:
        pytest.skip("organization has a real SumUp key configured – not touching it")
    v = admin.put(
        url,
        json={
            "values": {"sumup_api_key": "sup_sk_e2e_dummy_key_value", "sumup_merchant_code": "ME2E"}
        },
    ).json()
    assert v["sumup_api_key_set"] is True and "sup_sk_e2e" not in str(v)
    v = admin.put(url, json={"values": {"sumup_api_key": ""}}).json()
    assert v["sumup_api_key_set"] is True  # empty = keep
    v = admin.delete(f"{url}/secret/sumup_api_key").json()
    assert v["sumup_api_key_set"] is False
    assert admin.delete(f"{url}/secret/mail_mode").status_code == 403
    admin.put(url, json={"values": {"sumup_merchant_code": ""}})


def test_logo_upload(admin, anon, cfg):
    original = anon.get(f"/api/public/{cfg.slug}/assets/logo")
    buf = io.BytesIO()
    Image.new("RGB", (200, 80), "blue").save(buf, format="PNG")
    r = admin.post(
        f"{SET.format(slug=cfg.slug)}/logo",
        files={"file": ("logo.png", buf.getvalue(), "image/png")},
    )
    assert r.status_code == 200
    got = anon.get(f"/api/public/{cfg.slug}/assets/logo")
    assert got.status_code == 200 and got.headers["content-type"].startswith("image/")
    assert (
        admin.post(
            f"{SET.format(slug=cfg.slug)}/logo", files={"file": ("x.txt", b"nope", "text/plain")}
        ).status_code
        == 400
    )
    if original.status_code == 200:
        admin.post(
            f"{SET.format(slug=cfg.slug)}/logo",
            files={"file": ("logo", original.content, original.headers["content-type"])},
        )
    else:
        assert admin.delete(f"{SET.format(slug=cfg.slug)}/logo").status_code == 204
        assert anon.get(f"/api/public/{cfg.slug}/assets/logo").status_code == 404


@pytest.fixture(scope="module")
def timing_user(admin, cfg) -> dict:
    email = f"timer-{unique()}@{TEST_DOMAIN}"
    password = "e2e-timer-testpasswort-1"
    r = admin.post(
        USERS.format(slug=cfg.slug),
        json={
            "email": email,
            "display_name": "E2E Timer",
            "password": password,
            "roles": ["timing"],
        },
    )
    assert r.status_code == 201, r.text
    return {**r.json(), "password": password}


def test_user_validation(admin, cfg, timing_user):
    url = USERS.format(slug=cfg.slug)
    assert (
        admin.post(
            url,
            json={
                "email": timing_user["email"],
                "password": "e2e-timer-testpasswort-1",
                "roles": [],
            },
        ).status_code
        == 409
    )
    assert (
        admin.post(
            url, json={"email": f"x-{unique()}@{TEST_DOMAIN}", "password": "short", "roles": []}
        ).status_code
        == 422
    )
    assert (
        admin.post(
            url,
            json={
                "email": f"x-{unique()}@{TEST_DOMAIN}",
                "password": "long-enough-testpasswort",
                "roles": ["god"],
            },
        ).status_code
        == 400
    )
    assert any(
        u["id"] == timing_user["id"] and u["roles"] == ["timing"] for u in admin.get(url).json()
    )


def test_roles_are_enforced(cfg, timing_user):
    s = team_login(cfg.base_url, cfg.slug, timing_user["email"], timing_user["password"])
    try:
        assert s.get(f"/api/{cfg.slug}/team/timing/devices").status_code == 200
        assert (
            s.get(f"/api/{cfg.slug}/team/events").status_code == 200
        )  # events are readable for the team
        assert (
            s.post(
                f"/api/{cfg.slug}/team/events", json={"name": "E2E nope", "year": 2030}
            ).status_code
            == 403
        )
        assert s.get(f"/api/{cfg.slug}/team/users").status_code == 403
        assert s.get(f"/api/{cfg.slug}/team/settings").status_code == 403
        assert (
            s.get(
                f"/api/{cfg.slug}/team/sepa/summary",
                params={"event_id": "00000000-0000-0000-0000-000000000000"},
            ).status_code
            == 403
        )
    finally:
        s.close()


def test_update_deactivate_and_delete_user(admin, cfg, timing_user):
    url = f"{USERS.format(slug=cfg.slug)}/{timing_user['id']}"
    r = admin.patch(
        url,
        json={
            "roles": ["timing", "race_office"],
            "display_name": "E2E Timer 2",
            "password": "e2e-timer-testpasswort-2",
        },
    )
    assert r.status_code == 200 and r.json()["roles"] == ["race_office", "timing"]
    s = team_login(cfg.base_url, cfg.slug, timing_user["email"], "e2e-timer-testpasswort-2")
    s.close()
    assert admin.patch(url, json={"is_active": False}).json()["is_active"] is False
    with pytest.raises(RuntimeError):
        team_login(cfg.base_url, cfg.slug, timing_user["email"], "e2e-timer-testpasswort-2")
    assert admin.delete(url).status_code == 204
    assert admin.get(url).status_code in (404, 405)


def test_admin_cannot_lock_itself_out(admin, cfg):
    me = admin.get(f"/api/{cfg.slug}/auth/me").json()
    mine = next(
        u
        for u in admin.get(USERS.format(slug=cfg.slug)).json()
        if u["email"].lower() == me["email"].lower()
    )
    url = f"{USERS.format(slug=cfg.slug)}/{mine['id']}"
    assert admin.patch(url, json={"is_active": False}).status_code == 400
    assert admin.patch(url, json={"roles": ["timing"]}).status_code == 400
    assert admin.delete(url).status_code == 400
    assert admin.get(f"/api/{cfg.slug}/auth/me").status_code == 200


def test_session_object_is_isolated(cfg):
    s = Session(cfg.base_url)
    assert s.get(f"/api/{cfg.slug}/team/users").status_code == 401
    s.close()

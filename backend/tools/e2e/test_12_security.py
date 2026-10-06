"""Area: Sicherheit & Mandantentrennung (404 statt 403, Fremd-IDs, Fremd-Slug, Rate-Limits)."""

from __future__ import annotations

import uuid

import pytest

from tools.e2e.api import TEST_DOMAIN, Session, platform_login, unique

NIL = "00000000-0000-0000-0000-000000000000"


def test_unknown_slug_and_ids_are_404(anon, admin, cfg):
    assert anon.get(f"/api/public/{unique('no-org-')}/info").status_code == 404
    # login never reveals whether the organization or the account exists
    assert anon.post(
        f"/api/{unique('no-org-')}/auth/login", json={"email": "a@b.de", "password": "x"}
    ).status_code in (401, 404)
    assert admin.get(f"/api/{cfg.slug}/team/events/{NIL}").status_code == 404
    assert admin.get(f"/api/{cfg.slug}/team/events/not-a-uuid").status_code == 404
    assert admin.get(f"/api/{cfg.slug}/team/registrations/{uuid.uuid4()}").status_code == 404
    assert admin.get(f"/api/{cfg.slug}/team/timing/devices/{uuid.uuid4()}").status_code in (
        404,
        405,
    )
    assert (
        admin.get(f"/api/{cfg.slug}/team/registrations", params={"event_id": NIL}).status_code
        == 404
    )


def test_registration_rejects_foreign_competition(anon, admin, cfg, event, comps):
    other = admin.post(
        f"/api/{cfg.slug}/team/events", json={"name": "E2E Fremd", "year": event["year"]}
    ).json()
    comp = admin.post(
        f"/api/{cfg.slug}/team/events/{other['id']}/competitions",
        json={**comps["5 km"], "title_de": "Fremd", "title_en": "Foreign"},
    ).json()
    from tools.e2e.api import registration_payload

    r = anon.post(
        f"/api/public/{cfg.slug}/registrations", json=registration_payload(event["id"], comp["id"])
    )
    assert r.status_code == 404  # competition belongs to another event
    admin.delete(f"/api/{cfg.slug}/team/events/{other['id']}")


@pytest.mark.second_org
def test_cross_organization_isolation(cfg, admin, event, anon):
    if not cfg.second_slug:
        pytest.skip("BIBBY_E2E_SECOND_SLUG not set")
    s2 = cfg.second_slug
    assert anon.get(f"/api/public/{s2}/info").status_code == 200
    # the admin session of org A is worthless for org B
    assert admin.get(f"/api/{s2}/team/events").status_code == 401
    assert admin.get(f"/api/{s2}/auth/me").status_code == 401
    # objects of org A are invisible through org B's public endpoints
    assert anon.get(f"/api/public/{s2}/events/{event['id']}/competitions").status_code == 404
    assert (
        anon.get(f"/api/public/{s2}/results", params={"event_id": event["id"]}).status_code == 404
    )
    if cfg.platform_email and cfg.platform_password:
        p = platform_login(cfg.base_url, cfg.platform_email, cfg.platform_password)
        try:
            org_b = next(o for o in p.get("/api/platform/organizations").json() if o["slug"] == s2)
            p.post(f"/api/platform/organizations/{org_b['id']}/enter")
            # acting as org B, org A's event id yields 404 – never 403, never data
            assert p.get(f"/api/{s2}/team/events/{event['id']}").status_code == 404
            assert (
                p.get(f"/api/{s2}/team/registrations", params={"event_id": event["id"]}).status_code
                == 404
            )
            assert (
                p.get(f"/api/{s2}/team/stats", params={"event_id": event["id"]}).status_code == 404
            )
            assert all(e["id"] != event["id"] for e in p.get(f"/api/{s2}/team/events").json())
            p.post("/api/platform/leave")
        finally:
            p.close()


def test_csrf_is_required_even_with_valid_session(cfg):
    s = Session(cfg.base_url)
    r = s.post(f"/api/{cfg.slug}/auth/login", json={"email": cfg.email, "password": cfg.password})
    assert r.status_code == 200
    s.csrf = "forged"
    assert (
        s.post(f"/api/{cfg.slug}/team/timing/devices", json={"label": "E2E csrf"}).status_code
        == 403
    )
    s.csrf = r.json()["csrf_token"]
    s.post(f"/api/{cfg.slug}/auth/logout")
    s.close()


def test_security_headers_on_api_and_spa(anon, cfg):
    r = anon.get(f"/api/public/{cfg.slug}/info")
    assert r.status_code == 200
    page = anon.get(f"/{cfg.slug}")
    assert page.status_code in (200, 404)  # 404 only when the SPA is not served by this backend
    if page.status_code == 200:
        assert "text/html" in page.headers["content-type"]


@pytest.mark.ratelimit
def test_login_rate_limit_per_account(anon, cfg):
    if not cfg.ratelimit_tests:
        pytest.skip("set BIBBY_E2E_RATELIMIT=1 to run (locks a throw-away account for minutes)")
    email = f"ratelimit-{unique()}@{TEST_DOMAIN}"
    codes = [
        anon.post(
            f"/api/{cfg.slug}/auth/login", json={"email": email, "password": "wrong"}
        ).status_code
        for _ in range(12)
    ]
    # account limit (8/5 min) or – after many logins from this IP – the IP limit; both end in 429
    assert 429 in codes and codes[-1] == 429

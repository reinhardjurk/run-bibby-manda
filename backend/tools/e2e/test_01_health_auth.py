"""Area: Basis & Anmeldung am Team-Bereich (health/version, login, CSRF, logout)."""

from __future__ import annotations

from tools.e2e.api import Session


def test_health_and_version(anon):
    assert anon.get("/health").json() == {"status": "ok"}
    v = anon.get("/version").json()
    assert v["backend"] and v["db_schema"], v


def test_public_info_shape(anon, cfg):
    info = anon.get(f"/api/public/{cfg.slug}/info").json()
    assert info["organization"]["slug"] == cfg.slug
    assert "on_site" in info["payment_methods"] and "sepa_debit" in info["payment_methods"]
    assert "heard_about_options" in info and "sponsor_display" in info


def test_login_errors_are_generic(anon, cfg):
    r1 = anon.post(
        f"/api/{cfg.slug}/auth/login", json={"email": "nobody@e2e.example.org", "password": "x"}
    )
    r2 = anon.post(
        f"/api/{cfg.slug}/auth/login", json={"email": cfg.email, "password": "definitely-wrong"}
    )
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]


def test_me_logout_and_csrf(cfg):
    s = Session(cfg.base_url)
    r = s.post(f"/api/{cfg.slug}/auth/login", json={"email": cfg.email, "password": cfg.password})
    assert r.status_code == 200
    cookies = " ".join(r.headers.get_list("set-cookie"))
    assert "bibby_session=" in cookies and "HttpOnly" in cookies
    s.csrf = r.json()["csrf_token"]
    me = s.get(f"/api/{cfg.slug}/auth/me").json()
    assert me["email"].lower() == cfg.email.lower() and me["organization"]["slug"] == cfg.slug
    # mutating call without CSRF header is rejected, with header accepted
    assert (
        s.client.post(f"/api/{cfg.slug}/team/events", json={"name": "x", "year": 2026}).status_code
        == 403
    )
    assert s.post(f"/api/{cfg.slug}/auth/logout").status_code == 200
    assert s.get(f"/api/{cfg.slug}/auth/me").status_code == 401
    s.close()


def test_session_is_bound_to_organization(admin, cfg):
    assert admin.get(f"/api/{cfg.slug}/team/events").status_code == 200
    assert admin.get("/api/definitely-not-an-org/team/events").status_code == 404
    if cfg.second_slug:
        assert admin.get(f"/api/{cfg.second_slug}/team/events").status_code == 401

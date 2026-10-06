"""Role checks, CSRF, generic login errors, rate limits, suspended organizations."""

from __future__ import annotations

import httpx
from app.config import get_settings
from app.main import app

from tests.conftest import add_user, create_org, login, setup_event


async def test_role_matrix(client):
    org = await create_org("roles")
    admin = await login(client, "roles")
    ev, comps = await setup_event(admin)
    for email, roles in (
        ("office@example.org", ("race_office",)),
        ("timer@example.org", ("timing",)),
        ("sponsor@example.org", ("sponsor_management",)),
        ("sepa@example.org", ("sepa",)),
        ("viewer@example.org", ("viewer",)),
    ):
        await add_user(org, email, roles)
    office = await login(client, "roles", "office@example.org")
    timer = await login(client, "roles", "timer@example.org")
    sponsor = await login(client, "roles", "sponsor@example.org")
    sepa = await login(client, "roles", "sepa@example.org")
    viewer = await login(client, "roles", "viewer@example.org")
    eid = ev["id"]

    async def code(sess, method, path, **kw):
        return (await getattr(sess, method)(path, **kw)).status_code

    # viewer: stats only
    assert await code(viewer, "get", f"/api/roles/team/stats?event_id={eid}") == 200
    assert await code(viewer, "get", f"/api/roles/team/registrations?event_id={eid}") == 403
    assert await code(viewer, "get", "/api/roles/team/timing/devices") == 403
    assert await code(viewer, "get", "/api/roles/team/sponsors") == 403
    assert await code(viewer, "get", f"/api/roles/team/sepa/summary?event_id={eid}") == 403
    assert await code(viewer, "get", "/api/roles/team/users") == 403
    assert (
        await code(viewer, "post", "/api/roles/team/events", json={"name": "x", "year": 2026})
        == 403
    )
    # sepa: only sepa
    assert await code(sepa, "get", f"/api/roles/team/sepa/summary?event_id={eid}") == 200
    assert await code(sepa, "get", f"/api/roles/team/stats?event_id={eid}") == 403
    # sponsor management: only sponsors
    assert await code(sponsor, "get", "/api/roles/team/sponsors") == 200
    assert await code(sponsor, "get", f"/api/roles/team/registrations?event_id={eid}") == 403
    # timing: devices + records, but no compute / no registrations edit
    assert await code(timer, "get", "/api/roles/team/timing/devices") == 200
    assert await code(timer, "post", f"/api/roles/team/timing/compute?event_id={eid}") == 403
    assert await code(timer, "get", f"/api/roles/team/registrations?event_id={eid}") == 403
    # race office: everything operational, but no user management, no event delete
    assert await code(office, "get", f"/api/roles/team/registrations?event_id={eid}") == 200
    assert await code(office, "post", f"/api/roles/team/timing/compute?event_id={eid}") == 200
    assert await code(office, "get", "/api/roles/team/users") == 403
    assert await code(office, "delete", f"/api/roles/team/events/{eid}") == 403
    assert (
        await code(office, "put", "/api/roles/team/settings", json={"values": {"mail_mode": "off"}})
        == 403
    )
    # admin: all
    assert await code(admin, "get", "/api/roles/team/users") == 200
    assert await code(admin, "delete", f"/api/roles/team/events/{eid}") == 204


async def test_admin_self_lockout_protection(client):
    await create_org("lock")
    admin = await login(client, "lock")
    me = (await admin.get("/api/lock/auth/me")).json()
    users = (await admin.get("/api/lock/team/users")).json()
    me_id = next(u["id"] for u in users if u["email"] == me["email"])
    assert (
        await admin.patch(f"/api/lock/team/users/{me_id}", json={"is_active": False})
    ).status_code == 400
    assert (
        await admin.patch(f"/api/lock/team/users/{me_id}", json={"roles": ["viewer"]})
    ).status_code == 400
    assert (await admin.delete(f"/api/lock/team/users/{me_id}")).status_code == 400
    r = await admin.post(
        "/api/lock/team/users",
        json={"email": "new@example.org", "password": "longenoughpw1", "roles": ["timing"]},
    )
    assert r.status_code == 201
    r = await admin.post(
        "/api/lock/team/users",
        json={"email": "new@example.org", "password": "longenoughpw1", "roles": ["timing"]},
    )
    assert r.status_code == 409


async def test_csrf_required_for_cookie_sessions(client):
    await create_org("csrf")
    s = await login(client, "csrf")
    # same cookie jar, but without the CSRF header → 403
    r = await s.client.post("/api/csrf/team/events", json={"name": "x", "year": 2026})
    assert r.status_code == 403
    r = await s.client.post(
        "/api/csrf/team/events", json={"name": "x", "year": 2026}, headers={"X-CSRF-Token": "wrong"}
    )
    assert r.status_code == 403
    r = await s.post("/api/csrf/team/events", json={"name": "x", "year": 2026})
    assert r.status_code == 201
    # the session cookie is httpOnly
    login_resp = await client.post(
        "/api/csrf/auth/login",
        json={"email": "admin@example.org", "password": "correct-horse-battery"},
    )
    set_cookie = " ".join(login_resp.headers.get_list("set-cookie"))
    assert (
        "bibby_session=" in set_cookie
        and "HttpOnly" in set_cookie
        and "SameSite=lax" in set_cookie.lower().replace("samesite=lax", "SameSite=lax")
    )


async def test_login_errors_are_generic_and_logout_invalidates(client):
    await create_org("gen")
    r1 = await client.post(
        "/api/gen/auth/login", json={"email": "nobody@example.org", "password": "x"}
    )
    r2 = await client.post(
        "/api/gen/auth/login", json={"email": "admin@example.org", "password": "wrong"}
    )
    assert r1.status_code == r2.status_code == 401 and r1.json()["detail"] == r2.json()["detail"]
    s = await login(client, "gen")
    assert (await s.get("/api/gen/auth/me")).status_code == 200
    assert (await s.post("/api/gen/auth/logout")).status_code == 200
    assert (await s.get("/api/gen/auth/me")).status_code == 401


async def test_login_rate_limit_and_backoff(client, monkeypatch):
    await create_org("rl")
    settings = get_settings()
    monkeypatch.setattr(settings, "login_account_limit", 3)
    for _ in range(3):
        assert (
            await client.post(
                "/api/rl/auth/login", json={"email": "admin@example.org", "password": "wrong"}
            )
        ).status_code == 401
    r = await client.post(
        "/api/rl/auth/login",
        json={"email": "admin@example.org", "password": "correct-horse-battery"},
    )
    assert r.status_code == 429 and "Zu viele" in r.json()["detail"]


async def test_registration_rate_limit(client, monkeypatch):
    await create_org("rl2")
    s = await login(client, "rl2")
    ev, comps = await setup_event(s)
    from tests.conftest import registration_payload

    monkeypatch.setattr(get_settings(), "registration_limit", 2)
    for _ in range(2):
        assert (
            await client.post(
                "/api/public/rl2/registrations", json=registration_payload(ev["id"], comps[0]["id"])
            )
        ).status_code == 201
    r = await client.post(
        "/api/public/rl2/registrations", json=registration_payload(ev["id"], comps[0]["id"])
    )
    assert r.status_code == 429


async def test_suspended_org(client):
    from tests.conftest import create_platform_admin, platform_login

    org = await create_org("susp")
    s = await login(client, "susp")
    await create_platform_admin()
    p = await platform_login()
    r = await p.patch(f"/api/platform/organizations/{org.id}", json={"status": "suspended"})
    assert r.status_code == 200 and r.json()["status"] == "suspended"
    assert (await client.get("/api/public/susp/info")).status_code == 423
    assert (
        await client.post(
            "/api/susp/auth/login",
            json={"email": "admin@example.org", "password": "correct-horse-battery"},
        )
    ).status_code == 401
    assert (await s.get("/api/susp/team/events")).status_code == 401  # existing sessions revoked
    r = await p.patch(f"/api/platform/organizations/{org.id}", json={"status": "active"})
    assert (await client.get("/api/public/susp/info")).status_code == 200  # data preserved


async def test_error_middleware_adds_cors_headers_on_500(monkeypatch):
    from app.registrations import router_public

    async def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(router_public.service, "team_names", boom)
    await create_org("cors")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as c:
        r = await c.get(
            "/api/public/cors/team-names?q=a", headers={"Origin": "http://localhost:5173"}
        )
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert r.json() == {"detail": "Interner Fehler."}


async def test_role_update_keeps_existing_role(client):
    """Replacing a user's roles with a set that still contains an existing role must not trip
    over the (user_id, role) unique constraint."""
    org = await create_org("rollen")
    user = await add_user(org, "timer@rollen.de", ("timing",))
    s = await login(client, "rollen")
    r = await s.patch(
        f"/api/rollen/team/users/{user.id}", json={"roles": ["timing", "race_office"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["roles"] == ["race_office", "timing"]
    r = await s.patch(f"/api/rollen/team/users/{user.id}", json={"roles": ["viewer"]})
    assert r.status_code == 200 and r.json()["roles"] == ["viewer"]
    r = await s.patch(f"/api/rollen/team/users/{user.id}", json={"roles": []})
    assert r.status_code == 200 and r.json()["roles"] == []

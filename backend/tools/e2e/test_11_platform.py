"""Area: Super-Admin / Plattform (Übersicht, Organisationen anlegen/sperren/löschen,
Org betreten, Audit)."""

from __future__ import annotations

import pytest

from tools.e2e.api import TEST_DOMAIN, team_login, unique

pytestmark = pytest.mark.platform
P = "/api/platform"


@pytest.fixture(scope="module")
def temp_org(platform) -> dict:
    slug = f"e2e-{unique()}"
    r = platform.post(
        f"{P}/organizations",
        json={
            "slug": slug,
            "name": f"E2E Org {slug}",
            "contact_email": f"org@{TEST_DOMAIN}",
            "admin_email": f"admin@{TEST_DOMAIN}",
            "admin_password": "e2e-orgadmin-testpasswort",
        },
    )
    assert r.status_code == 201, r.text
    org = r.json()
    yield org
    platform.delete(f"{P}/organizations/{org['id']}", params={"confirm_slug": slug})


def test_platform_me_overview_settings(platform, cfg):
    me = platform.get(f"{P}/auth/me").json()
    assert me["email"].lower() == cfg.platform_email.lower()
    ov = platform.get(f"{P}/overview").json()
    assert ov["organizations"] >= 1 and ov["db_size_bytes"] > 0 and "storage_bytes" in ov
    st = platform.get(f"{P}/settings").json()
    assert st["public_base_url"] and st["payment_provider"] and "mail_configured" in st
    orgs = platform.get(f"{P}/organizations").json()
    assert any(o["slug"] == cfg.slug for o in orgs)
    assert any(a["is_self"] for a in platform.get(f"{P}/admins").json())


def test_create_org_validation(platform, temp_org):
    assert temp_org["status"] == "active"
    r = platform.post(f"{P}/organizations", json={"slug": temp_org["slug"], "name": "dup"})
    assert r.status_code == 409
    for bad in ("api", "platform", "Bad Slug", "-x"):
        assert (
            platform.post(f"{P}/organizations", json={"slug": bad, "name": "x"}).status_code == 422
        ), bad


def test_org_admin_can_login_and_platform_manages_users(platform, cfg, temp_org, anon):
    s = team_login(
        cfg.base_url, temp_org["slug"], f"admin@{TEST_DOMAIN}", "e2e-orgadmin-testpasswort"
    )
    assert s.get(f"/api/{temp_org['slug']}/auth/me").json()["roles"] == ["admin"]
    s.close()
    users = platform.get(f"{P}/organizations/{temp_org['id']}/users").json()
    assert len(users) == 1 and users[0]["roles"] == ["admin"]
    r = platform.post(
        f"{P}/organizations/{temp_org['id']}/admins",
        json={"email": f"second@{TEST_DOMAIN}", "password": "e2e-second-testpasswort"},
    )
    assert r.status_code == 201
    assert (
        platform.post(
            f"{P}/organizations/{temp_org['id']}/admins",
            json={"email": f"second@{TEST_DOMAIN}", "password": "e2e-second-testpasswort"},
        ).status_code
        == 409
    )
    r = platform.post(
        f"{P}/organizations/{temp_org['id']}/reset-password",
        json={"user_id": users[0]["id"], "password": "e2e-reset-testpasswort"},
    )
    assert r.status_code == 200
    with pytest.raises(RuntimeError):
        team_login(
            cfg.base_url, temp_org["slug"], f"admin@{TEST_DOMAIN}", "e2e-orgadmin-testpasswort"
        )
    s = team_login(cfg.base_url, temp_org["slug"], f"admin@{TEST_DOMAIN}", "e2e-reset-testpasswort")
    s.close()
    assert anon.get(f"/api/public/{temp_org['slug']}/info").status_code == 200


def test_enter_and_leave_org(platform, temp_org):
    slug = temp_org["slug"]
    assert platform.get(f"/api/{slug}/team/events").status_code == 401
    r = platform.post(f"{P}/organizations/{temp_org['id']}/enter")
    assert r.status_code == 200 and r.json()["acting_organization"]["slug"] == slug
    assert platform.get(f"{P}/auth/me").json()["acting_organization"]["slug"] == slug
    assert platform.get(f"/api/{slug}/team/events").status_code == 200
    me = platform.get(f"/api/{slug}/auth/me").json()
    assert me["is_platform_admin"] is True and "admin" in me["roles"]
    # acting as one org never opens another one
    assert platform.get(f"/api/{temp_org['slug']}x/team/events").status_code == 404
    assert platform.post(f"{P}/leave").json()["acting_organization"] is None
    assert platform.get(f"/api/{slug}/team/events").status_code == 401
    audit = platform.get(f"{P}/audit", params={"organization_id": temp_org["id"]}).json()
    actions = {a["action"] for a in audit}
    assert {"organization.create", "organization.enter", "organization.leave"} <= actions
    assert all(a["admin"] for a in audit)


def test_suspend_and_delete(platform, cfg, temp_org, anon):
    slug = temp_org["slug"]
    r = platform.patch(
        f"{P}/organizations/{temp_org['id']}", json={"status": "suspended", "name": "E2E gesperrt"}
    )
    assert (
        r.status_code == 200
        and r.json()["status"] == "suspended"
        and r.json()["name"] == "E2E gesperrt"
    )
    assert anon.get(f"/api/public/{slug}/info").status_code == 423
    with pytest.raises(RuntimeError):
        team_login(cfg.base_url, slug, f"admin@{TEST_DOMAIN}", "e2e-reset-testpasswort")
    assert (
        platform.patch(f"{P}/organizations/{temp_org['id']}", json={"status": "active"}).json()[
            "status"
        ]
        == "active"
    )
    assert (
        platform.delete(f"{P}/organizations/{temp_org['id']}").status_code == 400
    )  # slug confirmation
    assert (
        platform.delete(
            f"{P}/organizations/{temp_org['id']}", params={"confirm_slug": "wrong"}
        ).status_code
        == 400
    )
    assert (
        platform.delete(
            f"{P}/organizations/{temp_org['id']}", params={"confirm_slug": slug}
        ).status_code
        == 204
    )
    assert anon.get(f"/api/public/{slug}/info").status_code == 404
    assert platform.get(f"{P}/organizations/{temp_org['id']}/users").status_code == 404


def test_platform_login_is_separate_from_team_login(cfg, anon):
    assert anon.get(f"{P}/overview").status_code == 401
    r = anon.post(f"{P}/auth/login", json={"email": cfg.email, "password": cfg.password})
    assert r.status_code == 401  # org admin credentials are not platform credentials

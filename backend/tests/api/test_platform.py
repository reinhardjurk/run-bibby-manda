"""Super admin: organizations, first admin, acting as organization with audit, self-protection."""

from __future__ import annotations

from app.db.models import AuditLog
from app.db.session import get_sessionmaker
from sqlalchemy import select

from tests.conftest import create_platform_admin, login, platform_login, setup_event


async def test_platform_lifecycle_and_audit(client):
    await create_platform_admin()
    p = await platform_login()
    # unauthenticated → 401
    assert (await client.get("/api/platform/organizations")).status_code == 401

    r = await p.post(
        "/api/platform/organizations",
        json={
            "slug": "neu",
            "name": "Neuer Verein",
            "contact_email": "info@example.org",
            "admin_email": "chef@example.org",
            "admin_password": "sehr-geheim-123",
        },
    )
    assert r.status_code == 201, r.text
    org = r.json()
    assert (
        await p.post("/api/platform/organizations", json={"slug": "neu", "name": "Dup"})
    ).status_code == 409
    assert (
        await p.post("/api/platform/organizations", json={"slug": "api", "name": "Reserved"})
    ).status_code == 422

    # first org admin can log in and has the admin role
    s = await login(client, "neu", "chef@example.org", "sehr-geheim-123")
    assert "admin" in (await s.get("/api/neu/auth/me")).json()["roles"]

    # overview counts
    await setup_event(s)
    orgs = (await p.get("/api/platform/organizations")).json()
    mine = next(o for o in orgs if o["slug"] == "neu")
    assert mine["events"] == 1 and mine["users"] == 1
    overview = (await p.get("/api/platform/overview")).json()
    assert overview["organizations"] >= 1 and overview["events"] >= 1

    # second admin + password reset
    r = await p.post(
        f"/api/platform/organizations/{org['id']}/admins",
        json={"email": "zweiter@example.org", "password": "zweites-testpasswort-456"},
    )
    assert r.status_code == 201
    users = (await p.get(f"/api/platform/organizations/{org['id']}/users")).json()
    uid = next(u["id"] for u in users if u["email"] == "chef@example.org")
    assert (
        await p.post(
            f"/api/platform/organizations/{org['id']}/reset-password",
            json={"user_id": uid, "password": "neues-testpasswort-789"},
        )
    ).status_code == 200
    assert (await s.get("/api/neu/auth/me")).status_code == 401  # old sessions revoked
    await login(client, "neu", "chef@example.org", "neues-testpasswort-789")

    # acting as organization: platform cookie works on team endpoints only after "enter"
    assert (await p.get("/api/neu/team/events")).status_code == 401
    r = await p.post(f"/api/platform/organizations/{org['id']}/enter")
    assert r.status_code == 200 and r.json()["acting_organization"]["slug"] == "neu"
    me = (await p.get("/api/neu/auth/me")).json()
    assert me["is_platform_admin"] is True and "admin" in me["roles"]
    r = await p.post("/api/neu/team/events", json={"name": "Vom Super-Admin", "year": 2027})
    assert r.status_code == 201
    # ... but not in another organization
    r2 = await p.post("/api/platform/organizations", json={"slug": "andere", "name": "Andere"})
    assert (await p.get("/api/andere/team/events")).status_code == 401
    assert (await p.post("/api/platform/leave")).status_code == 200
    assert (await p.get("/api/neu/team/events")).status_code == 401

    async with get_sessionmaker()() as db:
        actions = [
            (a.action, a.method)
            for a in (await db.execute(select(AuditLog).order_by(AuditLog.created_at))).scalars()
        ]
    assert ("organization.create", "POST") in actions
    assert ("organization.enter", "POST") in actions
    assert ("org.write", "POST") in actions  # the event creation while acting as org
    assert ("organization.leave", "POST") in actions
    audit = (await p.get("/api/platform/audit")).json()
    assert any(a["action"] == "org.write" and a["path"] == "/api/neu/team/events" for a in audit)

    # delete requires slug confirmation
    assert (await p.delete(f"/api/platform/organizations/{r2.json()['id']}")).status_code == 400
    assert (
        await p.delete(f"/api/platform/organizations/{r2.json()['id']}?confirm_slug=andere")
    ).status_code == 204


async def test_super_admin_cannot_remove_itself(client):
    admin = await create_platform_admin()
    p = await platform_login()
    assert (await p.delete(f"/api/platform/admins/{admin.id}")).status_code == 400
    r = await p.post(
        "/api/platform/admins",
        json={"email": "second@example.org", "password": "another-long-secret"},
    )
    assert r.status_code == 201
    other = r.json()["id"]
    assert (await p.delete(f"/api/platform/admins/{other}")).status_code == 204
    # the last one can never be deleted
    r = await p.post(
        "/api/platform/admins",
        json={"email": "third@example.org", "password": "another-long-secret"},
    )
    p3 = await platform_login("third@example.org", "another-long-secret")
    assert (await p3.delete(f"/api/platform/admins/{admin.id}")).status_code == 204
    assert (await p3.delete(f"/api/platform/admins/{r.json()['id']}")).status_code == 400

"""Cross-tenant isolation (acceptance criterion): two organizations with identical names,
users and events coexist; every cross-tenant access yields 404 (never 403) or is scoped away."""

from __future__ import annotations

from datetime import datetime, timedelta

from tests.conftest import (
    VALID_IBAN,
    create_org,
    login,
    registration_payload,
    setup_event,
)


async def _org_with_data(client, slug):
    org = await create_org(slug, name="Lauftreff", email="admin@example.org")
    s = await login(client, slug)
    ev, comps = await setup_event(s)
    reg = (
        await client.post(
            f"/api/public/{slug}/registrations",
            json=registration_payload(
                ev["id"],
                comps[0]["id"],
                first_name="Max",
                last_name="Mustermann",
                birth_date="1985-01-01",
                payment_method="sepa_debit",
                iban=VALID_IBAN,
            ),
        )
    ).json()
    dev = (await s.post(f"/api/{slug}/team/timing/devices", json={"label": "Gerät 1"})).json()
    return org, s, ev, comps[0], reg, dev


async def test_identical_data_coexists_and_is_isolated(client):
    org_a, sa, ev_a, comp_a, reg_a, dev_a = await _org_with_data(client, "verein-a")
    org_b, sb, ev_b, comp_b, reg_b, dev_b = await _org_with_data(client, "verein-b")

    # identical persons / emails / event names / device labels / bib numbers exist in both
    assert reg_a["bib_number"] == reg_b["bib_number"] == 1
    assert ev_a["name"] == ev_b["name"]

    # ----- team endpoints: ids of the other organization → 404 -----
    for path in (
        f"/api/verein-a/team/events/{ev_b['id']}",
        f"/api/verein-a/team/registrations/{reg_b['registration_id']}",
        f"/api/verein-a/team/registrations?event_id={ev_b['id']}",
        f"/api/verein-a/team/stats?event_id={ev_b['id']}",
        f"/api/verein-a/team/sepa/summary?event_id={ev_b['id']}",
        f"/api/verein-a/team/timing/records?event_id={ev_b['id']}",
        f"/api/verein-a/team/timing/plausibility?event_id={ev_b['id']}",
        f"/api/verein-a/team/timing/internal-results?event_id={ev_b['id']}",
        f"/api/verein-a/team/results/overview?event_id={ev_b['id']}",
        f"/api/verein-a/team/results/certificate.pdf?event_id={ev_b['id']}&bib_number=1",
        f"/api/verein-a/team/results/certificates.pdf?event_id={ev_b['id']}&competition_id={comp_b['id']}",
        f"/api/verein-a/team/events/{ev_b['id']}/template",
        f"/api/verein-a/team/registrations/{reg_b['registration_id']}/bib.pdf",
    ):
        r = await sa.get(path)
        assert r.status_code == 404, (path, r.status_code, r.text)

    # write attempts across tenants
    assert (
        await sa.patch(f"/api/verein-a/team/events/{ev_b['id']}", json={"name": "Hacked"})
    ).status_code == 404
    assert (
        await sa.patch(
            f"/api/verein-a/team/registrations/{reg_b['registration_id']}",
            json={"team_name": "Hacked"},
        )
    ).status_code == 404
    assert (
        await sa.post(f"/api/verein-a/team/registrations/{reg_b['registration_id']}/mark-paid")
    ).status_code == 404
    assert (await sa.delete(f"/api/verein-a/team/events/{ev_b['id']}")).status_code == 404
    assert (
        await sa.post(f"/api/verein-a/team/timing/compute?event_id={ev_b['id']}")
    ).status_code == 404
    assert (
        await sa.post(
            f"/api/verein-a/team/events/{ev_b['id']}/competitions", json={"title_de": "X"}
        )
    ).status_code == 404
    assert (
        await sa.patch(
            f"/api/verein-a/team/timing/devices/{dev_b['id']}", json={"is_active": False}
        )
    ).status_code == 404
    assert (
        await sa.post(f"/api/verein-a/team/timing/devices/{dev_b['id']}/reissue")
    ).status_code == 404
    assert (
        await sa.post(f"/api/verein-a/team/sepa/export.csv?event_id={ev_b['id']}")
    ).status_code == 404
    # competition of B inside event of A → 404
    r = await sa.post(
        "/api/verein-a/team/registrations", json=registration_payload(ev_a["id"], comp_b["id"])
    )
    assert r.status_code == 404
    # cross-tenant update pointing to a foreign competition
    r = await sa.patch(
        f"/api/verein-a/team/registrations/{reg_a['registration_id']}",
        json={"competition_id": comp_b["id"]},
    )
    assert r.status_code == 404

    # session of A is worthless under slug B
    assert (await sa.get("/api/verein-b/team/events")).status_code == 401
    assert (await sa.get("/api/verein-b/auth/me")).status_code == 401
    # the listing of A never contains B's data
    listing = (await sa.get("/api/verein-a/team/events")).json()
    assert {e["id"] for e in listing} == {ev_a["id"]}
    regs = (await sa.get(f"/api/verein-a/team/registrations?event_id={ev_a['id']}")).json()
    assert {x["id"] for x in regs["items"]} == {reg_a["registration_id"]}
    devices = (await sa.get("/api/verein-a/team/timing/devices")).json()
    assert {d["id"] for d in devices} == {dev_a["id"]}

    # ----- public endpoints -----
    token_a = reg_a["manage_url"].split("token=")[1]
    assert (await client.get(f"/api/public/verein-b/manage?token={token_a}")).status_code == 404
    assert (await client.get(f"/api/public/verein-a/manage?token={token_a}")).status_code == 200
    assert (
        await client.get(f"/api/public/verein-b/manage/bib.pdf?token={token_a}")
    ).status_code == 404
    r = await client.post(
        "/api/public/verein-b/registrations", json=registration_payload(ev_a["id"], comp_a["id"])
    )
    assert r.status_code == 404
    r = await client.get(f"/api/public/verein-b/results?event_id={ev_a['id']}")
    assert r.status_code == 404
    r = await client.get(f"/api/public/verein-b/events/{ev_a['id']}/competitions")
    assert r.status_code == 404
    # team names are per organization
    await client.patch(
        f"/api/public/verein-a/manage?token={token_a}", json={"team_name": "GeheimTeamA"}
    )
    assert "GeheimTeamA" in (await client.get("/api/public/verein-a/team-names?q=geheim")).json()
    assert (await client.get("/api/public/verein-b/team-names?q=geheim")).json() == []

    # ----- device tokens are bound to the organization -----
    now = datetime.fromisoformat(comp_b["start_time"]) + timedelta(minutes=30)
    body = {
        "event_id": ev_b["id"],
        "records": [{"bib_number": 1, "absolute_time": now.isoformat(), "dedup_key": "cross-0001"}],
    }
    r = await client.post(
        "/api/verein-b/timing/records", json=body, headers={"X-Device-Token": dev_a["token"]}
    )
    assert r.status_code == 401
    # device of B used with event of A under slug B → 404 (event not in B)
    body_a = {**body, "event_id": ev_a["id"]}
    r = await client.post(
        "/api/verein-b/timing/records", json=body_a, headers={"X-Device-Token": dev_b["token"]}
    )
    assert r.status_code == 404
    r = await client.post(
        "/api/verein-b/timing/records", json=body, headers={"X-Device-Token": dev_b["token"]}
    )
    assert r.status_code == 200 and r.json()["inserted"] == 1
    # A's timing listing does not see B's record
    assert (await sa.get(f"/api/verein-a/team/timing/records?event_id={ev_a['id']}")).json() == []

    # ----- webhooks: a payment of A cannot be touched via B -----
    r = await client.post(
        "/api/public/verein-b/payments/webhook", json={"checkout_reference": "anything"}
    )
    assert r.json()["handled"] is False

    # ----- statistics / sepa of A only count A -----
    stats = (await sa.get(f"/api/verein-a/team/stats?event_id={ev_a['id']}")).json()
    assert stats["overview"]["participants"] == 1
    r = await sa.post(f"/api/verein-a/team/sepa/export.csv?event_id={ev_a['id']}")
    assert r.headers["x-row-count"] == "1"
    # mandate references are unique per org but may collide in shape across orgs – both exist
    assert reg_a["payment"]["mandate_reference"] != reg_b["payment"]["mandate_reference"]


async def test_users_are_unique_per_org_not_globally(client):
    await create_org("c1", email="same@example.org")
    await create_org("c2", email="same@example.org")
    s1 = await login(client, "c1", email="same@example.org")
    s2 = await login(client, "c2", email="same@example.org")
    assert (await s1.get("/api/c1/auth/me")).json()["organization"]["slug"] == "c1"
    assert (await s2.get("/api/c2/auth/me")).json()["organization"]["slug"] == "c2"
    # user of c1 cannot manage users of c2
    users_c2 = (await s2.get("/api/c2/team/users")).json()
    r = await s1.patch(f"/api/c1/team/users/{users_c2[0]['id']}", json={"roles": ["viewer"]})
    assert r.status_code == 404


async def test_unknown_slug_and_guessed_uuids(client):
    await create_org("real")
    s = await login(client, "real")
    assert (await client.get("/api/public/nope/info")).status_code == 404
    assert (
        await client.post("/api/nope/auth/login", json={"email": "a@example.org", "password": "x"})
    ).status_code == 401
    assert (
        await s.get("/api/real/team/events/00000000-0000-0000-0000-000000000000")
    ).status_code == 404
    assert (await s.get("/api/real/team/events/not-a-uuid")).status_code == 404
    assert (await s.get("/api/real/team/registrations/not-a-uuid")).status_code == 404

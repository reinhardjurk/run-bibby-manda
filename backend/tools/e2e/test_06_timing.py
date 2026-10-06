"""Area: Zeiterfassung (Geräte-Tokens, idempotenter Upload, Offsets, manuelle Erfassung,
Berechnung, Plausibilität, Einfrieren der Anmeldung)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import httpx
import pytest

from tools.e2e.api import registration_payload, token_of

T = "/api/{slug}/team/timing"


def _dev(cfg, token: str) -> httpx.Client:
    return httpx.Client(base_url=cfg.base_url, timeout=60, headers={"X-Device-Token": token})


def _start(comps) -> datetime:
    return datetime.fromisoformat(comps["5 km"]["start_time"])


@pytest.fixture(scope="module")
def runners(admin, cfg, event, comps, anon) -> dict:
    """Four office registrations in 5 km plus one public registration (manage token known)."""
    out = {}
    for name in ("Alpha", "Beta", "Gamma", "Delta"):
        r = admin.post(
            f"/api/{cfg.slug}/team/registrations",
            json=registration_payload(
                event["id"],
                comps["5 km"]["id"],
                first_name=name,
                last_name="E2E-Zeit",
                consent_publish=name != "Delta",
            ),
        )
        assert r.status_code == 201, r.text
        out[name] = r.json()
    r = anon.post(
        f"/api/public/{cfg.slug}/registrations",
        json=registration_payload(
            event["id"], comps["5 km"]["id"], first_name="Public", last_name="E2E-Zeit"
        ),
    )
    assert r.status_code == 201, r.text
    out["Public"] = r.json()
    return out


@pytest.fixture(scope="module")
def device(admin, cfg) -> dict:
    r = admin.post(
        f"{T.format(slug=cfg.slug)}/devices", json={"label": "E2E Ziel 1", "time_offset_seconds": 0}
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_device_token_shown_once(admin, cfg, device):
    assert (
        device["token"]
        and device["token"] in device["kiosk_url"]
        and f"/{cfg.slug}/timing" in device["kiosk_url"]
    )
    listed = admin.get(f"{T.format(slug=cfg.slug)}/devices").json()
    mine = next(d for d in listed if d["id"] == device["id"])
    assert "token" not in mine and mine["is_active"] is True
    assert (
        admin.post(f"{T.format(slug=cfg.slug)}/devices", json={"label": "E2E Ziel 1"}).status_code
        == 409
    )


def test_context_requires_device_or_timing_user(cfg, device, event, anon):
    assert anon.get(f"/api/{cfg.slug}/timing/context").status_code == 401
    with _dev(cfg, "wrong-token") as bad:
        assert bad.get(f"/api/{cfg.slug}/timing/context").status_code == 401
    with _dev(cfg, device["token"]) as dev:
        ctx = dev.get(f"/api/{cfg.slug}/timing/context").json()
    assert (
        ctx["device"] is True
        and ctx["actor"] == "E2E Ziel 1"
        and ctx["organization"]["slug"] == cfg.slug
    )
    assert any(e["id"] == event["id"] and len(e["competitions"]) == 3 for e in ctx["events"])
    if cfg.second_slug:
        with _dev(cfg, device["token"]) as dev:
            assert dev.get(f"/api/{cfg.second_slug}/timing/context").status_code == 401


def test_upload_is_idempotent(cfg, device, event, comps, runners):
    start = _start(comps)
    key = uuid.uuid4().hex
    batch = {
        "event_id": event["id"],
        "records": [
            {
                "bib_number": runners["Alpha"]["bib_number"],
                "absolute_time": (start + timedelta(minutes=20)).isoformat(),
                "dedup_key": f"{key}-a1",
            },
            {
                "bib_number": runners["Alpha"]["bib_number"],
                "absolute_time": (start + timedelta(minutes=20, seconds=2)).isoformat(),
                "dedup_key": f"{key}-a2",
            },
            {
                "bib_number": runners["Beta"]["bib_number"],
                "absolute_time": (start + timedelta(minutes=21)).isoformat(),
                "dedup_key": f"{key}-b1",
            },
        ],
    }
    with _dev(cfg, device["token"]) as dev:
        first = dev.post(f"/api/{cfg.slug}/timing/records", json=batch).json()
        again = dev.post(f"/api/{cfg.slug}/timing/records", json=batch).json()
        assert first == {"inserted": 3, "duplicates": 0} and again == {
            "inserted": 0,
            "duplicates": 3,
        }
        # partial overlap – only the new record is inserted
        batch["records"].append(
            {
                "bib_number": runners["Beta"]["bib_number"],
                "absolute_time": (start + timedelta(minutes=21, seconds=1)).isoformat(),
                "dedup_key": f"{key}-b2",
            }
        )
        assert dev.post(f"/api/{cfg.slug}/timing/records", json=batch).json() == {
            "inserted": 1,
            "duplicates": 3,
        }
        assert (
            dev.post(
                f"/api/{cfg.slug}/timing/records",
                json={
                    "event_id": event["id"],
                    "records": [
                        {"bib_number": 1, "absolute_time": start.isoformat(), "dedup_key": "short"}
                    ],
                },
            ).status_code
            == 422
        )
        assert (
            dev.post(
                f"/api/{cfg.slug}/timing/records",
                json={"event_id": str(uuid.uuid4()), "records": []},
            ).status_code
            == 404
        )


def test_device_offset_is_applied(admin, cfg, event, comps, runners):
    start = _start(comps)
    r = admin.post(
        f"{T.format(slug=cfg.slug)}/devices",
        json={"label": "E2E Ziel 2 (+10s)", "time_offset_seconds": 10},
    )
    assert r.status_code == 201
    dev2 = r.json()
    at = start + timedelta(minutes=22)
    with _dev(cfg, dev2["token"]) as dev:
        res = dev.post(
            f"/api/{cfg.slug}/timing/records",
            json={
                "event_id": event["id"],
                "records": [
                    {
                        "bib_number": runners["Gamma"]["bib_number"],
                        "absolute_time": at.isoformat(),
                        "dedup_key": uuid.uuid4().hex,
                    }
                ],
            },
        ).json()
    assert res["inserted"] == 1
    recs = admin.get(
        f"{T.format(slug=cfg.slug)}/records",
        params={"event_id": event["id"], "bib_number": runners["Gamma"]["bib_number"]},
    ).json()
    assert len(recs) == 1 and recs[0]["source_label"] == "E2E Ziel 2 (+10s)"
    assert datetime.fromisoformat(recs[0]["absolute_time"]) == at + timedelta(seconds=10)
    # offset can be changed afterwards (affects future uploads only)
    assert (
        admin.patch(
            f"{T.format(slug=cfg.slug)}/devices/{dev2['id']}", json={"time_offset_seconds": -5}
        ).json()["time_offset_seconds"]
        == -5
    )


def test_manual_record_summary_and_edit(admin, cfg, event, comps, runners):
    start = _start(comps)
    r = admin.post(
        f"{T.format(slug=cfg.slug)}/records/manual",
        json={
            "event_id": event["id"],
            "bib_number": runners["Delta"]["bib_number"],
            "absolute_time": (start + timedelta(minutes=30)).isoformat(),
        },
    )
    assert r.status_code == 201 and r.json()["status"] == "manual"
    rec = r.json()
    s = admin.get(f"{T.format(slug=cfg.slug)}/summary", params={"event_id": event["id"]}).json()
    assert s["records"]["manual"] >= 1 and s["records"]["valid"] >= 5 and s["distinct_bibs"] >= 4
    r = admin.patch(
        f"{T.format(slug=cfg.slug)}/records/{rec['id']}",
        json={"absolute_time": (start + timedelta(minutes=31)).isoformat(), "status": "ignored"},
    )
    assert r.status_code == 200 and r.json()["status"] == "ignored"
    assert (
        admin.patch(
            f"{T.format(slug=cfg.slug)}/records/{rec['id']}", json={"status": "bogus"}
        ).status_code
        == 422
    )
    assert (
        admin.patch(
            f"{T.format(slug=cfg.slug)}/records/{rec['id']}", json={"status": "manual"}
        ).status_code
        == 200
    )
    all_recs = admin.get(
        f"{T.format(slug=cfg.slug)}/records", params={"event_id": event["id"]}
    ).json()
    assert any(x["id"] == rec["id"] for x in all_recs)


def test_compute_freezes_registration_and_enables_certificate(
    admin, cfg, event, comps, runners, anon
):
    r = admin.post(f"{T.format(slug=cfg.slug)}/compute", params={"event_id": event["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["computed"] >= 4
    alpha = admin.get(
        f"/api/{cfg.slug}/team/registrations/{runners['Alpha']['registration_id']}"
    ).json()
    assert abs(float(alpha["finish_seconds"]) - 1201.0) < 0.01  # mean of 20:00 and 20:02
    gamma = admin.get(
        f"/api/{cfg.slug}/team/registrations/{runners['Gamma']['registration_id']}"
    ).json()
    assert abs(float(gamma["finish_seconds"]) - 1330.0) < 0.01  # 22:00 + 10 s offset
    delta = admin.get(
        f"/api/{cfg.slug}/team/registrations/{runners['Delta']['registration_id']}"
    ).json()
    assert abs(float(delta["finish_seconds"]) - 1860.0) < 0.01  # manual, edited to 31:00
    public = admin.get(
        f"/api/{cfg.slug}/team/registrations/{runners['Public']['registration_id']}"
    ).json()
    assert public["finish_seconds"] is None  # no recording yet
    # the public registration gets a time → manage page is frozen
    rec = admin.post(
        f"{T.format(slug=cfg.slug)}/records/manual",
        json={
            "event_id": event["id"],
            "bib_number": runners["Public"]["bib_number"],
            "absolute_time": (_start(comps) + timedelta(minutes=25)).isoformat(),
        },
    )
    assert rec.status_code == 201
    admin.post(f"{T.format(slug=cfg.slug)}/compute", params={"event_id": event["id"]})
    token = token_of(runners["Public"])
    view = anon.get(f"/api/public/{cfg.slug}/manage", params={"token": token}).json()
    assert view["frozen"] is True and view["finish_seconds"] is not None
    r = anon.patch(
        f"/api/public/{cfg.slug}/manage", params={"token": token}, json={"team_name": "zu spät"}
    )
    assert r.status_code == 409
    r = anon.get(f"/api/public/{cfg.slug}/manage/certificate.pdf", params={"token": token})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    # removing the record and recomputing unfreezes again
    assert admin.delete(f"{T.format(slug=cfg.slug)}/records/{rec.json()['id']}").status_code == 204
    admin.post(f"{T.format(slug=cfg.slug)}/compute", params={"event_id": event["id"]})
    assert (
        anon.get(f"/api/public/{cfg.slug}/manage", params={"token": token}).json()["frozen"]
        is False
    )


def test_plausibility(admin, cfg, device, event, comps, runners):
    start = _start(comps)
    bib = runners["Beta"]["bib_number"]
    with _dev(cfg, device["token"]) as dev:
        dev.post(
            f"/api/{cfg.slug}/timing/records",
            json={
                "event_id": event["id"],
                "records": [
                    {
                        "bib_number": bib,
                        "absolute_time": (start + timedelta(minutes=21, seconds=9)).isoformat(),
                        "dedup_key": uuid.uuid4().hex,
                    }
                ],
            },
        )
    r = admin.get(
        f"{T.format(slug=cfg.slug)}/plausibility",
        params={"event_id": event["id"], "threshold_seconds": 3},
    ).json()
    hit = next((e for e in r["entries"] if e["bib_number"] == bib), None)
    assert hit and abs(hit["spread_seconds"] - 9.0) < 0.01 and len(hit["timestamps"]) == 3
    r = admin.get(
        f"{T.format(slug=cfg.slug)}/plausibility",
        params={"event_id": event["id"], "threshold_seconds": 20},
    ).json()
    assert not any(e["bib_number"] == bib for e in r["entries"])
    assert (
        admin.get(
            f"{T.format(slug=cfg.slug)}/plausibility",
            params={"event_id": event["id"], "threshold_seconds": -1},
        ).status_code
        == 400
    )
    default = admin.get(
        f"{T.format(slug=cfg.slug)}/plausibility", params={"event_id": event["id"]}
    ).json()
    assert default["threshold_seconds"] > 0


def test_internal_results_include_non_consenting(admin, cfg, event, comps, runners):
    r = admin.get(
        f"{T.format(slug=cfg.slug)}/internal-results", params={"event_id": event["id"]}
    ).json()
    comp = next(c for c in r["competitions"] if c["competition"]["id"] == comps["5 km"]["id"])
    delta = next(row for row in comp["rows"] if row["bib_number"] == runners["Delta"]["bib_number"])
    assert delta["consent_publish"] is False and delta["place"] >= 1
    assert comp["unfinished"] >= 1


def test_reissue_and_revoke(admin, cfg, device, event):
    old = device["token"]
    r = admin.post(f"{T.format(slug=cfg.slug)}/devices/{device['id']}/reissue")
    assert r.status_code == 200 and r.json()["token"] != old
    new = r.json()["token"]
    with _dev(cfg, old) as dev:
        assert dev.get(f"/api/{cfg.slug}/timing/context").status_code == 401
    with _dev(cfg, new) as dev:
        assert dev.get(f"/api/{cfg.slug}/timing/context").status_code == 200
    assert (
        admin.patch(
            f"{T.format(slug=cfg.slug)}/devices/{device['id']}", json={"is_active": False}
        ).json()["is_active"]
        is False
    )
    with _dev(cfg, new) as dev:
        assert dev.get(f"/api/{cfg.slug}/timing/context").status_code == 401
    assert admin.delete(f"{T.format(slug=cfg.slug)}/devices/{device['id']}").status_code == 204
    assert admin.delete(f"{T.format(slug=cfg.slug)}/devices/{device['id']}").status_code == 404

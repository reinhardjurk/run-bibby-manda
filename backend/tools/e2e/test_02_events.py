"""Area: Events & Strecken (CRUD, Nummernkreise, Vorlagen, Hintergründe)."""

from __future__ import annotations

import io

from PIL import Image

from tools.e2e.api import competition_payload, event_payload


def test_event_and_competitions_created(event, comps):
    assert event["name"].startswith("E2E ")
    assert set(comps) == {"10 km", "5 km", "Staffel 3x2 km"}
    assert comps["10 km"]["bib_range_start"] == 100 and comps["10 km"]["bib_range_end"] == 199
    assert comps["Staffel 3x2 km"]["relay_scoring"] is True


def test_event_is_fully_editable(admin, cfg, event):
    eid = event["id"]
    r = admin.patch(
        f"/api/{cfg.slug}/team/events/{eid}",
        json={
            "tshirt_options": "S\nM\nL\nXL\nXXL",
            "certificate_offset_lines": 2,
            "tshirt_included": True,
        },
    )
    assert (
        r.status_code == 200
        and r.json()["certificate_offset_lines"] == 2
        and r.json()["tshirt_included"] is True
    )
    r = admin.patch(
        f"/api/{cfg.slug}/team/events/{eid}",
        json={
            "tshirt_options": event["tshirt_options"],
            "certificate_offset_lines": 0,
            "tshirt_included": False,
        },
    )
    assert r.status_code == 200
    # photo seed is write-only
    r = admin.patch(
        f"/api/{cfg.slug}/team/events/{eid}",
        json={
            "photo_base_url": "https://photos.example.org/e2e",
            "photo_hmac_seed": "e2e-secret-seed",
        },
    )
    assert r.json()["photo_seed_set"] is True and "e2e-secret-seed" not in r.text


def test_bib_range_validation(admin, cfg, event):
    eid = event["id"]
    bad = competition_payload(
        "kaputt", event["default_start_time"], bib_range_start=10, bib_range_end=5
    )
    assert (
        admin.post(f"/api/{cfg.slug}/team/events/{eid}/competitions", json=bad).status_code == 422
    )
    half = competition_payload(
        "kaputt", event["default_start_time"], bib_range_start=10, bib_range_end=None
    )
    assert (
        admin.post(f"/api/{cfg.slug}/team/events/{eid}/competitions", json=half).status_code == 422
    )


def test_competition_add_update_delete(admin, cfg, event):
    eid = event["id"]
    r = admin.post(
        f"/api/{cfg.slug}/team/events/{eid}/competitions",
        json=competition_payload(
            "Bambini", event["default_start_time"], bib_range_start=900, bib_range_end=950
        ),
    )
    assert r.status_code == 201
    cid = r.json()["id"]
    upd = competition_payload(
        "Bambini 400 m", event["default_start_time"], price_adult_cents=300, price_youth_cents=None
    )
    r = admin.patch(f"/api/{cfg.slug}/team/events/{eid}/competitions/{cid}", json=upd)
    assert r.status_code == 200 and r.json()["title_de"] == "Bambini 400 m"
    assert admin.delete(f"/api/{cfg.slug}/team/events/{eid}/competitions/{cid}").status_code == 204


def test_template_export_import(admin, cfg, event):
    tpl = admin.get(f"/api/{cfg.slug}/team/events/{event['id']}/template").json()
    assert "year" not in tpl and "event_date" not in tpl and len(tpl["competitions"]) >= 3
    body = {**tpl, **event_payload("Import"), "competitions": tpl["competitions"]}
    r = admin.post(f"/api/{cfg.slug}/team/events/import", json=body)
    assert r.status_code == 201
    imported = r.json()
    assert len(imported["competitions"]) == len(tpl["competitions"])
    assert admin.delete(f"/api/{cfg.slug}/team/events/{imported['id']}").status_code == 204


def test_background_upload_and_clear(admin, cfg, event):
    eid = event["id"]
    buf = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(buf, format="PNG")
    r = admin.post(
        f"/api/{cfg.slug}/team/events/{eid}/background/certificate",
        files={"file": ("bg.png", buf.getvalue(), "image/png")},
    )
    assert r.status_code == 200
    assert (
        admin.get(f"/api/{cfg.slug}/team/events/{eid}").json()["has_certificate_background"] is True
    )
    assert admin.get(f"/api/{cfg.slug}/team/events/{eid}/background/certificate").status_code == 200
    r = admin.post(
        f"/api/{cfg.slug}/team/events/{eid}/background/bib",
        files={"file": ("x.txt", b"not an image", "text/plain")},
    )
    assert r.status_code == 400
    r = admin.patch(
        f"/api/{cfg.slug}/team/events/{eid}", json={"clear_fields": ["certificate_background"]}
    )
    assert r.json()["has_certificate_background"] is False


def test_delete_event_requires_admin_and_cascades(admin, cfg):
    r = admin.post(f"/api/{cfg.slug}/team/events", json=event_payload("Delete"))
    eid = r.json()["id"]
    assert admin.delete(f"/api/{cfg.slug}/team/events/{eid}").status_code == 204
    assert admin.get(f"/api/{cfg.slug}/team/events/{eid}").status_code == 404

"""Area: Sponsoren (Upload, Klassen, Anzeige-Einstellungen, öffentliche Ausgabe)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

S = "/api/{slug}/team/sponsors"


def _png(color="red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 120), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def sponsor(admin, cfg) -> dict:
    r = admin.post(
        S.format(slug=cfg.slug),
        files={"file": ("logo.png", _png(), "image/png")},
        data={"tier": "1", "name": "E2E Sponsor", "url": "https://sponsor.e2e.example.org"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_upload_list_and_public_image(admin, anon, cfg, sponsor):
    assert sponsor["tier"] == 1 and sponsor["name"] == "E2E Sponsor"
    listed = admin.get(S.format(slug=cfg.slug)).json()
    assert any(s["id"] == sponsor["id"] for s in listed)
    r = anon.get(sponsor["image_url"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    pub = anon.get(f"/api/public/{cfg.slug}/sponsors").json()
    assert any(s.get("url") == "https://sponsor.e2e.example.org" for s in pub)


def test_validation(admin, cfg):
    r = admin.post(
        S.format(slug=cfg.slug),
        files={"file": ("x.txt", b"nope", "text/plain")},
        data={"tier": "2"},
    )
    assert r.status_code == 400
    r = admin.post(
        S.format(slug=cfg.slug),
        files={"file": ("logo.png", _png(), "image/png")},
        data={"tier": "9", "name": "E2E bad"},
    )
    assert r.status_code == 400


def test_update_and_delete(admin, cfg, sponsor):
    r = admin.patch(
        f"{S.format(slug=cfg.slug)}/{sponsor['id']}",
        json={"tier": 3, "name": "E2E Sponsor neu", "url": ""},
    )
    assert r.status_code == 200 and r.json()["tier"] == 3 and r.json()["url"] is None
    assert (
        admin.patch(f"{S.format(slug=cfg.slug)}/{sponsor['id']}", json={"tier": 0}).status_code
        == 400
    )
    assert admin.delete(f"{S.format(slug=cfg.slug)}/{sponsor['id']}").status_code == 204
    assert admin.delete(f"{S.format(slug=cfg.slug)}/{sponsor['id']}").status_code == 404


def test_display_settings(admin, anon, cfg):
    url = f"{S.format(slug=cfg.slug)}/display"
    assert set(admin.get(url).json()) == {
        "sponsor_mode",
        "sponsor_marquee_seconds",
        "sponsor_bucket_url",
        "sponsor_tier_weights",
    }
    r = admin.put(
        url,
        json={
            "sponsor_mode": "marquee",
            "sponsor_marquee_seconds": 45,
            "sponsor_tier_weights": "9, 4,3,2,1",
        },
    )
    assert r.status_code == 200, r.text
    assert (
        r.json()["sponsor_mode"] == "marquee"
        and r.json()["sponsor_marquee_seconds"] == "45"
        and r.json()["sponsor_tier_weights"] == "9,4,3,2,1"
    )
    info = anon.get(f"/api/public/{cfg.slug}/info").json()
    assert info["sponsor_display"]["mode"] == "marquee"
    assert admin.put(url, json={"sponsor_mode": "blink"}).status_code == 400
    assert admin.put(url, json={"sponsor_marquee_seconds": 4}).status_code == 400
    assert admin.put(url, json={"sponsor_tier_weights": "1,2,3"}).status_code == 400
    assert admin.put(url, json={"sponsor_mode": "rotation"}).status_code == 200


def test_bucket_url_is_validated(admin, cfg):
    r = admin.put(
        f"{S.format(slug=cfg.slug)}/display",
        json={"sponsor_bucket_url": "https://no-such-bucket.e2e.example.org/sponsors"},
    )
    assert r.status_code == 400 and "Bucket" in r.json()["detail"]
    r = admin.put(f"{S.format(slug=cfg.slug)}/display", json={"sponsor_bucket_url": ""})
    assert r.status_code == 200 and r.json()["sponsor_bucket_url"] == ""

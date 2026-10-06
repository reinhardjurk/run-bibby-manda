"""Fixtures: configuration, sessions, the shared E2E event, settings snapshot and cleanup."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from tools.e2e.api import (
    TEST_PREFIX,
    Config,
    Session,
    competition_payload,
    event_payload,
    iso,
    platform_login,
    team_login,
)

RESTORABLE_SETTINGS = {
    "mail_mode", "mail_sender_name", "mail_sender_local_part", "mail_reply_to", "mail_subject_de",
    "mail_subject_en", "mail_body_de", "mail_body_en", "sponsor_mode", "sponsor_marquee_seconds",
    "sponsor_bucket_url", "sponsor_tier_weights", "sepa_creditor_name", "sepa_creditor_id",
    "sepa_mandate_prefix", "sumup_merchant_code", "plausibility_threshold_seconds",
}  # fmt: skip


def pytest_configure(config: pytest.Config) -> None:
    for name in ("platform", "second_org", "ratelimit", "slow"):
        config.addinivalue_line("markers", f"{name}: see tools/e2e/api.py")


@pytest.fixture(scope="session")
def cfg() -> Config:
    return Config.from_env()


@pytest.fixture(scope="session")
def anon(cfg: Config) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=cfg.base_url, timeout=60, follow_redirects=False) as c:
        yield c


@pytest.fixture(scope="session")
def admin(cfg: Config) -> Iterator[Session]:
    s = team_login(cfg.base_url, cfg.slug, cfg.email, cfg.password)
    me = s.get(f"/api/{cfg.slug}/auth/me").json()
    if "admin" not in me["roles"]:
        pytest.exit("BIBBY_E2E_EMAIL must be an org admin of the test organization", returncode=2)
    yield s
    s.close()


@pytest.fixture(scope="session")
def platform(cfg: Config) -> Iterator[Session]:
    if not (cfg.platform_email and cfg.platform_password):
        pytest.skip("BIBBY_E2E_PLATFORM_EMAIL/PASSWORD not set")
    s = platform_login(cfg.base_url, cfg.platform_email, cfg.platform_password)
    yield s
    s.close()


@pytest.fixture(scope="session", autouse=True)
def settings_guard(cfg: Config, admin: Session) -> Iterator[dict]:
    """Forces mail mode off for the whole run and restores all settings afterwards."""
    before = admin.get(f"/api/{cfg.slug}/team/settings").json()
    r = admin.put(f"/api/{cfg.slug}/team/settings", json={"values": {"mail_mode": "off"}})
    assert r.status_code == 200 and r.json()["mail_mode"] == "off", r.text
    yield before
    restore = {k: v for k, v in before.items() if k in RESTORABLE_SETTINGS and isinstance(v, str)}
    admin.put(
        f"/api/{cfg.slug}/team/settings",
        json={"values": restore, "confirm_live_mail": restore.get("mail_mode") == "live"},
    )


@pytest.fixture(scope="session")
def event(cfg: Config, admin: Session) -> Iterator[dict]:
    """One shared event with three competitions; deleted (cascade) at the end of the run."""
    r = admin.post(f"/api/{cfg.slug}/team/events", json=event_payload())
    assert r.status_code == 201, r.text
    ev = r.json()
    start = ev["default_start_time"]
    comps = [
        competition_payload("10 km", start, bib_range_start=100, bib_range_end=199, sort_order=1),
        competition_payload(
            "5 km", start, price_adult_cents=1000, price_youth_cents=500, sort_order=2
        ),
        competition_payload(
            "Staffel 3x2 km",
            start,
            relay_scoring=True,
            age_class_scheme="none",
            gender_scoring=False,
            price_adult_cents=900,
            price_youth_cents=None,
            sort_order=3,
        ),
    ]
    for c in comps:
        r = admin.post(f"/api/{cfg.slug}/team/events/{ev['id']}/competitions", json=c)
        assert r.status_code == 201, r.text
    ev = admin.get(f"/api/{cfg.slug}/team/events/{ev['id']}").json()
    yield ev
    admin.delete(f"/api/{cfg.slug}/team/events/{ev['id']}")


@pytest.fixture(scope="session")
def comps(event: dict) -> dict[str, dict]:
    return {c["title_de"]: c for c in event["competitions"]}


@pytest.fixture(scope="session", autouse=True)
def cleanup_marked_data(cfg: Config, admin: Session) -> Iterator[None]:
    """Removes leftovers from earlier aborted runs first, and everything marked E2E at the end."""
    _cleanup(cfg, admin)
    yield
    _cleanup(cfg, admin)


def _cleanup(cfg: Config, admin: Session) -> None:
    slug = cfg.slug
    for ev in admin.get(f"/api/{slug}/team/events").json():
        if ev["name"].startswith(f"{TEST_PREFIX} "):
            admin.delete(f"/api/{slug}/team/events/{ev['id']}")
    for d in admin.get(f"/api/{slug}/team/timing/devices").json():
        if d["label"].startswith(TEST_PREFIX):
            admin.delete(f"/api/{slug}/team/timing/devices/{d['id']}")
    for u in admin.get(f"/api/{slug}/team/users").json():
        if u["email"].endswith("@e2e.example.org"):
            admin.delete(f"/api/{slug}/team/users/{u['id']}")
    for sp in admin.get(f"/api/{slug}/team/sponsors").json():
        if (sp["name"] or "").startswith(TEST_PREFIX):
            admin.delete(f"/api/{slug}/team/sponsors/{sp['id']}")


@pytest.fixture
def past_deadline(cfg: Config, admin: Session, event: dict) -> Iterator[None]:
    """Temporarily closes registration for the shared event."""
    eid = event["id"]
    past = iso(datetime.now(UTC) - timedelta(hours=1))
    assert (
        admin.patch(
            f"/api/{cfg.slug}/team/events/{eid}", json={"registration_deadline": past}
        ).status_code
        == 200
    )
    yield
    admin.patch(
        f"/api/{cfg.slug}/team/events/{eid}",
        json={"registration_deadline": event["registration_deadline"]},
    )

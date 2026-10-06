"""Creates (or repairs) the E2E test organization through the platform API – idempotent.

Needs the regular suite variables plus the super admin:
  BIBBY_E2E_BASE_URL, BIBBY_E2E_SLUG, BIBBY_E2E_EMAIL, BIBBY_E2E_PASSWORD,
  BIBBY_E2E_PLATFORM_EMAIL, BIBBY_E2E_PLATFORM_PASSWORD
Optional:
  BIBBY_E2E_SECOND_SLUG   a second organization for the isolation tests (created empty)
  BIBBY_E2E_ORG_NAME      display name of the test organization

Behaviour for the organization BIBBY_E2E_SLUG only:
  * missing            → created, with BIBBY_E2E_EMAIL as its first org admin
  * suspended          → re-activated
  * admin user missing → created; existing → password set to BIBBY_E2E_PASSWORD
Nothing else is touched. Secrets are never printed.
"""

from __future__ import annotations

import os
import sys

from tools.e2e.api import Config, platform_login, team_login

API = "/api/platform"


def _env(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        print(f"missing environment variable {name}", file=sys.stderr)
        raise SystemExit(2)
    return v


def _find(platform, slug: str) -> dict | None:
    return next((o for o in platform.get(f"{API}/organizations").json() if o["slug"] == slug), None)


def ensure_org(
    platform, slug: str, name: str, admin_email: str | None, admin_password: str | None
) -> dict:
    org = _find(platform, slug)
    if org is None:
        payload: dict = {"slug": slug, "name": name}
        if admin_email and admin_password:
            payload |= {
                "contact_email": admin_email,
                "admin_email": admin_email,
                "admin_password": admin_password,
            }
        r = platform.post(f"{API}/organizations", json=payload)
        if r.status_code != 201:
            raise SystemExit(f"could not create organization {slug}: {r.status_code} {r.text}")
        print(f"created organization {slug}")
        return r.json()
    print(f"organization {slug} exists (status {org['status']})")
    if org["status"] != "active":
        r = platform.patch(f"{API}/organizations/{org['id']}", json={"status": "active"})
        if r.status_code != 200:
            raise SystemExit(f"could not re-activate {slug}: {r.status_code} {r.text}")
        print(f"re-activated organization {slug}")
    if admin_email and admin_password:
        users = platform.get(f"{API}/organizations/{org['id']}/users").json()
        user = next((u for u in users if u["email"].lower() == admin_email.lower()), None)
        if user is None:
            r = platform.post(
                f"{API}/organizations/{org['id']}/admins",
                json={
                    "email": admin_email,
                    "password": admin_password,
                    "display_name": "E2E Admin",
                },
            )
            if r.status_code != 201:
                raise SystemExit(f"could not create admin in {slug}: {r.status_code} {r.text}")
            print(f"created org admin {admin_email} in {slug}")
        else:
            if "admin" not in user["roles"] or not user["is_active"]:
                raise SystemExit(
                    f"{admin_email} exists in {slug} but is not an active admin – fix manually"
                )
            r = platform.post(
                f"{API}/organizations/{org['id']}/reset-password",
                json={"user_id": user["id"], "password": admin_password},
            )
            if r.status_code != 200:
                raise SystemExit(f"could not reset password in {slug}: {r.status_code} {r.text}")
            print(f"password of {admin_email} in {slug} set from BIBBY_E2E_PASSWORD")
    return org


def main() -> int:
    cfg = Config.from_env()
    platform_email, platform_password = (
        _env("BIBBY_E2E_PLATFORM_EMAIL"),
        _env("BIBBY_E2E_PLATFORM_PASSWORD"),
    )
    name = os.environ.get("BIBBY_E2E_ORG_NAME") or "Test-Organisation (E2E)"
    platform = platform_login(cfg.base_url, platform_email, platform_password)
    try:
        ensure_org(platform, cfg.slug, name, cfg.email, cfg.password)
        if cfg.second_slug:
            ensure_org(platform, cfg.second_slug, f"{name} 2", None, None)
    finally:
        platform.post(f"{API}/auth/logout")
        platform.close()
    s = team_login(cfg.base_url, cfg.slug, cfg.email, cfg.password)
    me = s.get(f"/api/{cfg.slug}/auth/me").json()
    s.post(f"/api/{cfg.slug}/auth/logout")
    s.close()
    if "admin" not in me["roles"]:
        print(f"{cfg.email} is not an admin of {cfg.slug}", file=sys.stderr)
        return 1
    print(f"ready: {cfg.base_url}/{cfg.slug} with admin {cfg.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Runtime configuration (environment variables with prefix BIBBY_)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")


def normalize_database_url(url: str) -> str:
    """Accepts the URL forms cloud consoles print and maps them to the asyncpg dialect.

    * surrounding whitespace, newlines and quotes (pasted secrets) are removed
    * `postgres://` and `postgresql://` → `postgresql+asyncpg://`
    * libpq `sslmode=<mode>` → asyncpg `ssl=<mode>`; the mode is cleaned and validated so a
      broken value fails fast with a readable message instead of deep inside asyncpg
    """
    url = url.strip().strip("\"'").strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix) :]
            break
    if "?" not in url:
        return url
    base, _, query = url.partition("?")
    params: list[str] = []
    for part in query.split("&"):
        key, sep, value = part.partition("=")
        key, value = key.strip().strip("\"'"), value.strip().strip("\"'")
        if key.lower() in ("sslmode", "ssl"):
            mode = "".join(ch for ch in value.lower() if ch.isalnum() or ch == "-")
            if mode not in SSL_MODES:
                raise ValueError(
                    f"BIBBY_DATABASE_URL: ungültiger SSL-Modus {value!r} – erlaubt sind "
                    f"{', '.join(SSL_MODES)} (z. B. ?ssl=require)"
                )
            key, value = "ssl", mode
        if key:
            params.append(f"{key}={value}" if sep else key)
    return f"{base}?{'&'.join(params)}" if params else base


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIBBY_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+asyncpg://bibby:bibby@localhost:5432/bibby"
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # Cryptography – all secrets are injected via environment / IaC, never in the repo.
    app_secret: str = Field(default="dev-only-app-secret-CHANGE_ME", min_length=16)
    field_encryption_key: str = ""  # Fernet key (urlsafe base64, 32 bytes). Empty = derived (dev).

    # Sessions / cookies
    session_ttl_hours: int = 72
    cookie_secure: bool = True
    cookie_domain: str | None = None
    cors_origins: list[str] = ["http://localhost:5173"]
    public_base_url: str = "http://localhost:5173"

    # Rate limits (requests per window) – overridable per environment.
    ratelimit_enabled: bool = True
    login_ip_limit: int = 20
    login_ip_window_seconds: int = 300
    login_account_limit: int = 8
    login_account_window_seconds: int = 300
    registration_limit: int = 30
    registration_window_seconds: int = 60
    webhook_limit: int = 120
    webhook_window_seconds: int = 60

    # Mail (Scaleway Transactional Email). Test address receives everything in mode "test".
    mail_api_url: str = (
        "https://api.scaleway.com/transactional-email/v1alpha1/regions/fr-par/emails"
    )
    mail_project_id: str = ""
    mail_api_key: str = ""
    mail_default_sender: str = "noreply@example.org"
    mail_test_recipient: str = "test@example.org"

    # Payments
    sumup_api_base: str = "https://api.sumup.com"
    payment_provider: str = "sumup"  # "sumup" | "fake" (tests only)

    # PDF rendering pool
    pdf_workers: int = 2

    # Build info
    git_sha: str = "dev"

    # Platform bootstrap: creates the first super admin on startup if no platform admin exists.
    bootstrap_platform_admin_email: str = ""
    bootstrap_platform_admin_password: str = ""

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        return normalize_database_url(v)


@lru_cache
def get_settings() -> Settings:
    return Settings()

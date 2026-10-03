"""Password hashing, HMAC token hashing, field encryption."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


# A constant-time dummy check keeps login timing identical for unknown accounts.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt())


def dummy_password_check() -> None:
    bcrypt.checkpw(b"never-matches", _DUMMY_HASH)


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str, purpose: str = "token") -> str:
    """HMAC-SHA256 of a token under the app secret. Only hashes are persisted."""
    key = get_settings().app_secret.encode("utf-8")
    msg = f"{purpose}:{token}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def hmac_hex(seed: str, message: str, length: int = 40) -> str:
    return hmac.new(seed.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()[
        :length
    ]


def _fernet(key: str | None = None) -> Fernet:
    s = get_settings()
    raw = key if key is not None else s.field_encryption_key
    if not raw:
        # Development fallback: derive a key from the app secret. Production sets an explicit key.
        digest = hashlib.sha256(f"field:{s.app_secret}".encode()).digest()
        raw = base64.urlsafe_b64encode(digest).decode("ascii")
    return Fernet(raw.encode("ascii"))


def encrypt_field(value: str, key: str | None = None) -> str:
    return _fernet(key).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_field(value: str, key: str | None = None) -> str | None:
    """Returns None if the value cannot be decrypted (e.g. after key rotation)."""
    try:
        return _fernet(key).decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None

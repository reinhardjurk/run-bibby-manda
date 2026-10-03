"""Operational commands (run inside the backend container / CI):

python -m app.cli create-platform-admin EMAIL PASSWORD
python -m app.cli reencrypt-ibans OLD_FERNET_KEY        # after rotating BIBBY_FIELD_ENCRYPTION_KEY
python -m app.cli generate-fernet-key
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.security import decrypt_field, encrypt_field, hash_password
from app.db.models import OrgSetting, Payment, PlatformAdmin
from app.db.session import get_sessionmaker
from app.settings.service import SECRET_KEYS


async def create_platform_admin(email: str, password: str) -> None:
    async with get_sessionmaker()() as db:
        existing = (
            await db.execute(select(PlatformAdmin).where(PlatformAdmin.email == email.lower()))
        ).scalar_one_or_none()
        if existing:
            existing.password_hash = hash_password(password)
            existing.is_active = True
            print(f"updated password of {email}")
        else:
            db.add(PlatformAdmin(email=email.lower(), password_hash=hash_password(password)))
            print(f"created platform admin {email}")
        await db.commit()


async def reencrypt(old_key: str) -> int:
    """Re-encrypts every Fernet-protected field from OLD key to the currently configured key.

    Values already readable with the new key are left untouched; undecryptable values are reported
    and skipped (exports show a placeholder for them). Returns the number of failures.
    """
    failures = 0
    async with get_sessionmaker()() as db:
        payments = (
            await db.execute(select(Payment).where(Payment.iban_encrypted.is_not(None)))
        ).scalars()
        for p in payments:
            assert p.iban_encrypted is not None
            if decrypt_field(p.iban_encrypted) is not None:
                continue
            plain = decrypt_field(p.iban_encrypted, old_key)
            if plain is None:
                failures += 1
                print(f"payment {p.id}: cannot decrypt with old key", file=sys.stderr)
                continue
            p.iban_encrypted = encrypt_field(plain)
        settings = (
            await db.execute(select(OrgSetting).where(OrgSetting.key.in_(SECRET_KEYS)))
        ).scalars()
        for row in settings:
            if not row.value or decrypt_field(row.value) is not None:
                continue
            plain = decrypt_field(row.value, old_key)
            if plain is None:
                failures += 1
                print(f"org_setting {row.id}: cannot decrypt with old key", file=sys.stderr)
                continue
            row.value = encrypt_field(plain)
        await db.commit()
    print(f"re-encryption finished, failures={failures}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bibby")
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("create-platform-admin")
    a.add_argument("email")
    a.add_argument("password")
    r = sub.add_parser("reencrypt-ibans")
    r.add_argument("old_key")
    sub.add_parser("generate-fernet-key")
    args = parser.parse_args(argv)
    if args.cmd == "create-platform-admin":
        asyncio.run(create_platform_admin(args.email, args.password))
        return 0
    if args.cmd == "reencrypt-ibans":
        return 1 if asyncio.run(reencrypt(args.old_key)) else 0
    if args.cmd == "generate-fernet-key":
        print(Fernet.generate_key().decode())
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())

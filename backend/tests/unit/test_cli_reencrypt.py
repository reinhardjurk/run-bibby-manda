from app.core.security import decrypt_field, encrypt_field
from cryptography.fernet import Fernet


def test_field_encryption_roundtrip_and_key_rotation():
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    token = encrypt_field("DE89370400440532013000", old)
    assert decrypt_field(token, new) is None  # wrong key never raises
    assert decrypt_field(token, old) == "DE89370400440532013000"
    rotated = encrypt_field(decrypt_field(token, old) or "", new)
    assert decrypt_field(rotated, new) == "DE89370400440532013000"

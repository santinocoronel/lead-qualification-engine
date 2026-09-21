from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


def encrypt_value(value: str, fernet_key: str) -> str:
    f = Fernet(fernet_key.encode())
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str, fernet_key: str) -> str:
    try:
        f = Fernet(fernet_key.encode())
        return f.decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt value — invalid key or corrupted data") from exc

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import FERNET_KEY


def _fernet() -> Fernet:
    if not FERNET_KEY:
        # Dev fallback — deterministic insecure key so local stub works.
        # Never use in production without FERNET_KEY set.
        key = Fernet.generate_key()
        # Prefer a stable key derived from SESSION_SECRET for restarts in stub mode.
        from base64 import urlsafe_b64encode
        from hashlib import sha256

        from app.config import SESSION_SECRET

        dig = sha256(SESSION_SECRET.encode("utf-8")).digest()
        key = urlsafe_b64encode(dig)
        return Fernet(key)
    return Fernet(FERNET_KEY.encode("utf-8") if isinstance(FERNET_KEY, str) else FERNET_KEY)


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_token(token_enc: str) -> str:
    try:
        return _fernet().decrypt(token_enc.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Cannot decrypt token — check FERNET_KEY") from exc

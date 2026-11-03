from __future__ import annotations

from fastapi import HTTPException, Request

from app.crypto_util import decrypt_token
from app.db import get_db, row_to_dict
from app.session import get_user_id


def require_user(request: Request) -> dict:
    uid = get_user_id(request)
    if uid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    user = row_to_dict(row)
    if not user:
        raise HTTPException(status_code=401, detail="User gone")
    return user


def user_token(user: dict) -> str:
    enc = user.get("token_enc")
    if not enc:
        raise HTTPException(status_code=401, detail="No Disk token")
    try:
        return decrypt_token(enc)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

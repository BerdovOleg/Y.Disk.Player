from __future__ import annotations

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.requests import Request
from starlette.responses import Response

from app.config import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    SESSION_SECRET,
)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(SESSION_SECRET, salt="omt-session-v1")


def set_session(response: Response, user_id: int) -> None:
    token = _serializer().dumps({"uid": int(user_id)})
    samesite = COOKIE_SAMESITE if COOKIE_SAMESITE in {"lax", "strict", "none"} else "lax"
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=COOKIE_SECURE or samesite == "none",
        samesite=samesite,
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE if COOKIE_SAMESITE in {"lax", "strict", "none"} else "lax",
    )


def get_user_id(request: Request) -> int | None:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        data = _serializer().loads(raw, max_age=COOKIE_MAX_AGE)
        uid = data.get("uid")
        return int(uid) if uid is not None else None
    except (BadSignature, TypeError, ValueError):
        return None

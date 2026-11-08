from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import (
    ALLOW_DEV_AUTH,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    OAUTH_REDIRECT_URI,
    YANDEX_AUTH_URL,
    YANDEX_CLIENT_ID,
    YANDEX_CLIENT_SECRET,
    YANDEX_DISK_API,
    YANDEX_LOGIN_URL,
    YANDEX_OAUTH_SCOPES,
    YANDEX_TOKEN_URL,
    oauth_configured,
)
from app.crypto_util import decrypt_token, encrypt_token
from app.db import get_db, row_to_dict
from app.session import clear_session, get_user_id, set_session

router = APIRouter(prefix="/auth", tags=["auth"])


def _oauth_state_cookie(response, state: str) -> None:
    samesite = COOKIE_SAMESITE if COOKIE_SAMESITE in {"lax", "strict", "none"} else "lax"
    response.set_cookie(
        "omt_oauth_state",
        state,
        max_age=600,
        httponly=True,
        secure=COOKIE_SECURE or samesite == "none",
        samesite=samesite,
        path="/",
    )


@router.get("/status")
async def auth_status(request: Request):
    uid = get_user_id(request)
    oauth = oauth_configured()
    user = None
    disk_ok: bool | None = None
    disk_error: str | None = None
    if uid is not None:
        with get_db() as db:
            row = db.execute(
                "SELECT id, yandex_id, display_name, token_enc FROM users WHERE id = ?",
                (uid,),
            ).fetchone()
            full = row_to_dict(row)
            if full:
                user = {
                    "id": full["id"],
                    "yandex_id": full["yandex_id"],
                    "display_name": full["display_name"],
                }
                enc = full.get("token_enc")
                if enc:
                    try:
                        token = decrypt_token(enc)
                        if token.startswith("dev-stub"):
                            disk_ok = False
                            disk_error = "dev stub token"
                        else:
                            async with httpx.AsyncClient(timeout=15.0) as client:
                                r = await client.get(
                                    YANDEX_DISK_API,
                                    headers={"Authorization": f"OAuth {token}"},
                                )
                            disk_ok = r.status_code < 400
                            if not disk_ok:
                                try:
                                    msg = r.json().get("message") or r.json().get("error")
                                except Exception:
                                    msg = r.text[:120]
                                disk_error = f"{r.status_code}: {msg}"
                    except Exception as exc:  # noqa: BLE001
                        disk_ok = False
                        disk_error = str(exc)
    return {
        "authenticated": user is not None,
        "user": user,
        "oauth_configured": oauth,
        "dev_auth_available": ALLOW_DEV_AUTH and not oauth,
        "disk_ok": disk_ok,
        "disk_error": disk_error,
        "relogin_hint": (
            "Disk API forbidden — re-login via Yandex so the token gets disk scopes"
            if disk_ok is False and disk_error and "403" in str(disk_error)
            else None
        ),
    }


@router.get("/login")
async def login():
    if not oauth_configured():
        if ALLOW_DEV_AUTH:
            return RedirectResponse("/auth/dev-login", status_code=302)
        raise HTTPException(503, "Yandex OAuth not configured (set YANDEX_CLIENT_ID/SECRET)")
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": YANDEX_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "force_confirm": "yes",
        "state": state,
    }
    # Only pass scope when explicitly configured. Requesting scopes that are
    # not enabled on the OAuth app causes Yandex error=invalid_scope.
    if YANDEX_OAUTH_SCOPES:
        params["scope"] = YANDEX_OAUTH_SCOPES
    url = f"{YANDEX_AUTH_URL}?{urlencode(params)}"
    resp = RedirectResponse(url, status_code=302)
    _oauth_state_cookie(resp, state)
    return resp


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    if not oauth_configured():
        raise HTTPException(503, "OAuth not configured")
    if error:
        detail = error_description or error
        if error == "invalid_scope":
            detail = (
                f"{detail}. Enable Disk scopes (cloud_api:disk.read / disk.write / "
                "disk.info) as default permissions on https://oauth.yandex.ru/ for "
                "this app, clear YANDEX_OAUTH_SCOPES (or set only scopes the app has), "
                "then try /auth/login again."
            )
        raise HTTPException(400, detail)
    if not code:
        raise HTTPException(400, "Missing code")
    expected = request.cookies.get("omt_oauth_state")
    if expected and state and expected != state:
        raise HTTPException(400, "Invalid OAuth state")

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            YANDEX_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": YANDEX_CLIENT_ID,
                "client_secret": YANDEX_CLIENT_SECRET,
            },
        )
        if token_resp.status_code >= 400:
            # Never echo OAuth token material — status only
            raise HTTPException(400, f"Token exchange failed ({token_resp.status_code})")
        token_data = token_resp.json()
        access = token_data.get("access_token")
        if not access:
            raise HTTPException(400, "No access_token")

        info = await client.get(
            YANDEX_LOGIN_URL,
            params={"format": "json"},
            headers={"Authorization": f"OAuth {access}"},
        )
        if info.status_code >= 400:
            raise HTTPException(400, f"Login info failed ({info.status_code})")
        profile = info.json()

    yandex_id = str(profile.get("id") or profile.get("psuid") or "")
    display = profile.get("display_name") or profile.get("real_name") or profile.get("login") or "Yandex user"
    if not yandex_id:
        raise HTTPException(400, "No Yandex user id")

    enc = encrypt_token(access)
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE yandex_id = ?", (yandex_id,)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE users SET display_name=?, token_enc=?, updated_at=datetime('now') WHERE id=?",
                (display, enc, existing["id"]),
            )
            uid = existing["id"]
        else:
            cur = db.execute(
                "INSERT INTO users (yandex_id, display_name, token_enc) VALUES (?,?,?)",
                (yandex_id, display, enc),
            )
            uid = cur.lastrowid
        # Ensure per-user prefs row (isolated library view, etc.)
        pref = db.execute(
            "SELECT user_id FROM user_preferences WHERE user_id=?", (uid,)
        ).fetchone()
        if not pref:
            db.execute(
                "INSERT INTO user_preferences (user_id, library_view) VALUES (?, ?)",
                (uid, "genre"),
            )

    resp = RedirectResponse("/", status_code=302)
    set_session(resp, int(uid))
    resp.delete_cookie("omt_oauth_state")
    return resp


@router.post("/dev-login")
@router.get("/dev-login")
async def dev_login():
    if oauth_configured() and not ALLOW_DEV_AUTH:
        raise HTTPException(403, "Dev login disabled when OAuth is configured")
    if not ALLOW_DEV_AUTH:
        raise HTTPException(403, "Dev auth disabled")

    with get_db() as db:
        row = db.execute(
            "SELECT id FROM users WHERE yandex_id = ?", ("dev-local",)
        ).fetchone()
        if row:
            uid = row["id"]
            # Keep a stub encrypted token so Disk calls fail clearly if used
            db.execute(
                "UPDATE users SET display_name=?, updated_at=datetime('now') WHERE id=?",
                ("Dev User", uid),
            )
        else:
            enc = encrypt_token("dev-stub-token-not-valid-for-disk")
            cur = db.execute(
                "INSERT INTO users (yandex_id, display_name, token_enc) VALUES (?,?,?)",
                ("dev-local", "Dev User", enc),
            )
            uid = cur.lastrowid

    resp = RedirectResponse("/", status_code=302)
    set_session(resp, int(uid))
    return resp


@router.post("/logout")
@router.get("/logout")
async def logout():
    resp = RedirectResponse("/", status_code=302)
    clear_session(resp)
    return resp


@router.get("/switch")
@router.post("/switch")
async def switch_account():
    """Clear current session and force a fresh Yandex login (family account switch)."""
    resp = RedirectResponse("/auth/login", status_code=302)
    clear_session(resp)
    return resp

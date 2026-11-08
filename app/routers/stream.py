from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.deps import require_user, user_token
from app.disk.client import DiskError, get_download_href
from app.db import get_db, row_to_dict

router = APIRouter(prefix="/api", tags=["stream"])

_MIME_FIX = {
    "audio/mp3": "audio/mpeg",
    "audio/x-mp3": "audio/mpeg",
    "audio/flac": "audio/flac",
    "audio/x-flac": "audio/flac",
}


def _normalize_mime(mime: str | None) -> str:
    if not mime:
        return "audio/mpeg"
    return _MIME_FIX.get(mime.lower(), mime)


@router.get("/stream/{track_id}")
async def stream_track(track_id: int, request: Request):
    user = require_user(request)
    token = user_token(user)

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM tracks WHERE id=? AND user_id=?",
            (track_id, user["id"]),
        ).fetchone()
    track = row_to_dict(row)
    if not track:
        raise HTTPException(404, "Track not found")
    if track.get("available") == 0:
        raise HTTPException(410, "Track file missing on Disk — run library scan")

    # Dev stub token cannot hit real Disk
    if token.startswith("dev-stub"):
        raise HTTPException(
            503,
            "Dev stub has no Disk access — configure Yandex OAuth and re-login",
        )

    try:
        href = await get_download_href(token, track["disk_path"])
    except DiskError as exc:
        detail = str(exc)
        if exc.status == 403:
            detail = (
                "Disk access forbidden — open /auth/login to re-authorize "
                "with cloud_api:disk.read / disk.write scopes"
            )
        raise HTTPException(exc.status or 502, detail) from exc

    range_header = request.headers.get("range")
    upstream_headers: dict[str, str] = {
        "Accept": "*/*",
    }
    if range_header:
        upstream_headers["Range"] = range_header

    client = httpx.AsyncClient(timeout=None, follow_redirects=True)
    try:
        upstream = await client.send(
            client.build_request("GET", href, headers=upstream_headers),
            stream=True,
        )
    except Exception as exc:
        await client.aclose()
        raise HTTPException(502, f"Upstream stream failed: {exc}") from exc

    if upstream.status_code >= 400:
        body = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(
            upstream.status_code,
            body.decode("utf-8", errors="replace")[:300],
        )

    media_type = _normalize_mime(
        track.get("mime") or upstream.headers.get("content-type")
    )
    out_headers: dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=0, no-transform",
        "Content-Type": media_type,
    }
    for key in ("Content-Length", "Content-Range"):
        if key in upstream.headers:
            out_headers[key] = upstream.headers[key]
    # Prefer upstream media type when it looks like audio/*
    up_ct = upstream.headers.get("content-type")
    if up_ct and up_ct.lower().startswith("audio/"):
        out_headers["Content-Type"] = _normalize_mime(up_ct.split(";")[0].strip())
        media_type = out_headers["Content-Type"]

    async def body_iter():
        try:
            async for chunk in upstream.aiter_bytes(64 * 1024):
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        body_iter(),
        status_code=upstream.status_code,
        media_type=media_type,
        headers=out_headers,
    )

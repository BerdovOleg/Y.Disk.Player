from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from app.deps import require_user, user_token
from app.disk.client import DiskError, get_download_href
from app.db import get_db, row_to_dict

router = APIRouter(prefix="/api", tags=["stream"])


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

    # Dev stub token cannot hit real Disk
    if token.startswith("dev-stub"):
        raise HTTPException(
            503,
            "Dev stub has no Disk access — configure Yandex OAuth and re-login",
        )

    try:
        href = await get_download_href(token, track["disk_path"])
    except DiskError as exc:
        raise HTTPException(exc.status or 502, str(exc)) from exc

    range_header = request.headers.get("range")
    upstream_headers: dict[str, str] = {}
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
        raise HTTPException(upstream.status_code, body.decode("utf-8", errors="replace"))

    media_type = track.get("mime") or upstream.headers.get("content-type") or "audio/mpeg"
    out_headers: dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=0",
    }
    for key in ("Content-Length", "Content-Range", "Content-Type"):
        if key in upstream.headers:
            out_headers[key] = upstream.headers[key]
    if "Content-Type" not in out_headers:
        out_headers["Content-Type"] = media_type

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

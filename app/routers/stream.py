from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.deps import require_user, user_token
from app.disk.client import DiskError, download_to_path, get_download_href
from app.db import get_db, row_to_dict
from app.hot_cache import cache_stats, get_cached, put_from_path

router = APIRouter(prefix="/api", tags=["stream"])
log = logging.getLogger("omt.stream")

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


def _ext_for_track(track: dict) -> str:
    path = track.get("disk_path") or ""
    suffix = Path(path).suffix.lower()
    if suffix:
        return suffix
    mime = (track.get("mime") or "").lower()
    if "flac" in mime:
        return ".flac"
    if "mpeg" in mime or "mp3" in mime:
        return ".mp3"
    if "mp4" in mime or "m4a" in mime:
        return ".m4a"
    return ".bin"


async def _populate_cache(user_id: int, track: dict, token: str) -> None:
    try:
        ext = _ext_for_track(track)
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp_path = Path(tmp.name)
        try:
            await download_to_path(token, track["disk_path"], tmp_path)
            await put_from_path(
                user_id,
                int(track["id"]),
                tmp_path,
                mime=track.get("mime"),
            )
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception:
        log.exception("cache populate failed track=%s", track.get("id"))


@router.get("/cache/status")
def stream_cache_status(request: Request):
    require_user(request)
    return cache_stats()


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

    # Dev stub token cannot hit real Disk (cache may still serve)
    cached = get_cached(user["id"], track_id)
    if cached is not None:
        media_type = _normalize_mime(track.get("mime"))
        return FileResponse(
            path=str(cached),
            media_type=media_type,
            filename=Path(track["disk_path"]).name,
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "private, max-age=0, no-transform",
                "X-OMT-Cache": "HIT",
            },
        )

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

    # Populate hot cache in background for next hit
    asyncio.create_task(_populate_cache(user["id"], track, token))

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
        "X-OMT-Cache": "MISS",
    }
    for key in ("Content-Length", "Content-Range"):
        if key in upstream.headers:
            out_headers[key] = upstream.headers[key]
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

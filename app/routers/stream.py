from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.config import STREAM_EARLY_BYTES
from app.deps import require_user, user_token
from app.disk.client import DiskError, get_download_href
from app.db import get_db, row_to_dict
from app.hot_cache import cache_stats, get_cached, put_from_path
from app.http_util import async_client, is_network_io_failure

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


@router.get("/cache/status")
def stream_cache_status(request: Request):
    require_user(request)
    return {**cache_stats(), "early_bytes": STREAM_EARLY_BYTES}


@router.get("/stream/{track_id}")
async def stream_track(track_id: int, request: Request):
    """
    Fast start / progressive stream:
    - Cache HIT → FileResponse (browser Range seek works).
    - Cache MISS → Range-proxy Disk immediately (no wait for full download).
      Full file tees into hot cache in the background for the next play.
    """
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

    range_header = request.headers.get("range")
    # Full-body requests: tee to cache while streaming (early play + fill).
    # Range seeks: passthrough only — do not corrupt partial cache writes.
    want_tee = not range_header

    upstream_headers: dict[str, str] = {"Accept": "*/*"}
    if range_header:
        upstream_headers["Range"] = range_header

    client = async_client(timeout=None, follow_redirects=True)
    try:
        try:
            upstream = await client.send(
                client.build_request("GET", href, headers=upstream_headers),
                stream=True,
            )
        except (httpx.HTTPError, OSError) as exc:
            if not is_network_io_failure(exc):
                await client.aclose()
                raise HTTPException(502, f"Upstream stream failed: {exc}") from exc
            # One retry with a fresh IPv4 client + refreshed href
            await client.aclose()
            try:
                href = await get_download_href(token, track["disk_path"])
            except DiskError as disk_exc:
                raise HTTPException(
                    disk_exc.status or 502, str(disk_exc)
                ) from disk_exc
            client = async_client(timeout=None, follow_redirects=True)
            try:
                upstream = await client.send(
                    client.build_request("GET", href, headers=upstream_headers),
                    stream=True,
                )
            except Exception as retry_exc:
                await client.aclose()
                raise HTTPException(
                    502, f"Upstream stream failed: {retry_exc}"
                ) from retry_exc
    except HTTPException:
        raise
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
        "X-OMT-Early-Bytes": str(STREAM_EARLY_BYTES),
        "X-OMT-Progressive": "1" if want_tee else "0",
    }
    for key in ("Content-Length", "Content-Range"):
        if key in upstream.headers:
            out_headers[key] = upstream.headers[key]
    up_ct = upstream.headers.get("content-type")
    if up_ct and up_ct.lower().startswith("audio/"):
        out_headers["Content-Type"] = _normalize_mime(up_ct.split(";")[0].strip())
        media_type = out_headers["Content-Type"]

    tee_path: Path | None = None
    tee_fp = None
    if want_tee:
        ext = _ext_for_track(track)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tee_path = Path(tmp.name)
        tee_fp = tmp

    written = 0
    early_logged = False
    complete = False
    expected_len: int | None = None
    cl = upstream.headers.get("content-length")
    if cl and cl.isdigit():
        expected_len = int(cl)
    user_id = user["id"]
    track_id_local = int(track["id"])
    mime_local = track.get("mime")

    async def body_iter():
        nonlocal written, early_logged, tee_fp, complete
        try:
            async for chunk in upstream.aiter_bytes(64 * 1024):
                if tee_fp is not None:
                    tee_fp.write(chunk)
                    written += len(chunk)
                    if not early_logged and written >= STREAM_EARLY_BYTES:
                        early_logged = True
                        log.debug(
                            "progressive early bytes ready track=%s n=%s",
                            track_id_local,
                            written,
                        )
                yield chunk
            complete = True
        finally:
            await upstream.aclose()
            await client.aclose()
            if tee_fp is not None and tee_path is not None:
                try:
                    tee_fp.flush()
                    tee_fp.close()
                    tee_fp = None
                    size_ok = tee_path.exists() and tee_path.stat().st_size > 0
                    full = complete and (
                        expected_len is None or written >= expected_len
                    )
                    if size_ok and full:
                        asyncio.create_task(
                            _finalize_cache(user_id, track_id_local, tee_path, mime_local)
                        )
                    else:
                        tee_path.unlink(missing_ok=True)
                except Exception:
                    log.exception("tee finalize failed track=%s", track_id_local)
                    if tee_path is not None:
                        tee_path.unlink(missing_ok=True)

    return StreamingResponse(
        body_iter(),
        status_code=upstream.status_code,
        media_type=media_type,
        headers=out_headers,
    )


async def _finalize_cache(
    user_id: int, track_id: int, path: Path, mime: str | None
) -> None:
    try:
        await put_from_path(user_id, track_id, path, mime=mime)
    except Exception:
        log.exception("cache put failed track=%s", track_id)
    finally:
        path.unlink(missing_ok=True)

from __future__ import annotations

import mimetypes
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.config import DISK_ROOT, YANDEX_DISK_API


class DiskError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"OAuth {token}"}


def _norm_path(path: str) -> str:
    path = path.strip()
    if path.startswith("disk:"):
        path = path[5:]
    return "/" + path.strip("/")


def music_path(*parts: str) -> str:
    clean = [DISK_ROOT.strip("/")]
    for p in parts:
        p = str(p).strip("/").replace("\\", "/")
        if p:
            clean.append(p)
    return "/" + "/".join(clean)


async def ensure_folder(token: str, path: str) -> None:
    """Create folder and parents on Disk (idempotent)."""
    path = _norm_path(path)
    segments = path.strip("/").split("/")
    current = ""
    async with httpx.AsyncClient(timeout=60.0) as client:
        for seg in segments:
            current = f"{current}/{seg}"
            r = await client.put(
                f"{YANDEX_DISK_API}/resources",
                params={"path": current},
                headers=_headers(token),
            )
            if r.status_code in (201, 409):
                continue
            if r.status_code == 401:
                raise DiskError("Unauthorized", 401)
            if r.status_code == 403:
                raise DiskError(
                    "Forbidden — re-login via Yandex so the token includes Disk scopes",
                    403,
                )
            if r.status_code >= 400 and r.status_code != 409:
                raise DiskError(f"mkdir failed {current}: {r.text}", r.status_code)


async def upload_file(
    token: str, local_path: Path, remote_path: str, overwrite: bool = True
) -> dict[str, Any]:
    remote_path = _norm_path(remote_path)
    parent = "/".join(remote_path.split("/")[:-1]) or "/"
    await ensure_folder(token, parent)

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.get(
            f"{YANDEX_DISK_API}/resources/upload",
            params={"path": remote_path, "overwrite": str(overwrite).lower()},
            headers=_headers(token),
        )
        if r.status_code >= 400:
            raise DiskError(f"upload href failed: {r.text}", r.status_code)
        href = r.json().get("href")
        if not href:
            raise DiskError("No upload href from Disk API")

        data = local_path.read_bytes()
        mime = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
        put = await client.put(href, content=data, headers={"Content-Type": mime})
        if put.status_code not in (201, 202):
            raise DiskError(f"upload put failed: {put.status_code} {put.text}", put.status_code)
        return {"path": remote_path, "size": len(data)}


async def get_download_href(token: str, remote_path: str) -> str:
    remote_path = _norm_path(remote_path)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f"{YANDEX_DISK_API}/resources/download",
            params={"path": remote_path},
            headers=_headers(token),
        )
        if r.status_code == 403:
            raise DiskError(
                "Forbidden — re-login via Yandex so the token includes Disk scopes",
                403,
            )
        if r.status_code >= 400:
            raise DiskError(f"download href failed: {r.text}", r.status_code)
        href = r.json().get("href")
        if not href:
            raise DiskError("No download href")
        return href


async def get_meta(token: str, remote_path: str) -> dict[str, Any]:
    remote_path = _norm_path(remote_path)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f"{YANDEX_DISK_API}/resources",
            params={"path": remote_path},
            headers=_headers(token),
        )
        if r.status_code == 403:
            raise DiskError(
                "Forbidden — re-login via Yandex so the token includes Disk scopes",
                403,
            )
        if r.status_code >= 400:
            raise DiskError(f"meta failed: {r.text}", r.status_code)
        return r.json()


async def iter_files(
    token: str, root: str, *, page_size: int = 200
) -> AsyncIterator[dict[str, Any]]:
    """Yield file/dir resource dicts under root (recursive for directories)."""
    root = _norm_path(root)
    stack = [root]
    async with httpx.AsyncClient(timeout=60.0) as client:
        while stack:
            current = stack.pop()
            offset = 0
            while True:
                r = await client.get(
                    f"{YANDEX_DISK_API}/resources",
                    params={
                        "path": current,
                        "limit": page_size,
                        "offset": offset,
                    },
                    headers=_headers(token),
                )
                if r.status_code == 404:
                    break
                if r.status_code == 403:
                    raise DiskError(
                        "Forbidden — re-login via Yandex so the token includes Disk scopes",
                        403,
                    )
                if r.status_code >= 400:
                    raise DiskError(f"list failed {current}: {r.text}", r.status_code)
                data = r.json()
                # Root itself might be a file
                if data.get("type") == "file" and offset == 0 and current == root:
                    yield data
                    break
                emb = data.get("_embedded") or {}
                items = emb.get("items") or []
                for item in items:
                    yield item
                    if item.get("type") == "dir":
                        p = item.get("path") or ""
                        if p.startswith("disk:"):
                            p = p[5:]
                        if not p.startswith("/"):
                            p = "/" + p
                        stack.append(p)
                total = emb.get("total")
                offset += len(items)
                if not items or (total is not None and offset >= total):
                    break


async def download_to_path(token: str, remote_path: str, dest: Path) -> Path:
    href = await get_download_href(token, remote_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
        async with client.stream("GET", href) as r:
            if r.status_code >= 400:
                body = await r.aread()
                raise DiskError(
                    f"download failed: {body.decode('utf-8', errors='replace')[:200]}",
                    r.status_code,
                )
            with dest.open("wb") as out:
                async for chunk in r.aiter_bytes(256 * 1024):
                    out.write(chunk)
    return dest


def encode_disk_path(path: str) -> str:
    return quote(path, safe="/")

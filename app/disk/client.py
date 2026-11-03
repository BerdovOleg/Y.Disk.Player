from __future__ import annotations

import mimetypes
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


def music_path(*parts: str) -> str:
    clean = [DISK_ROOT.strip("/")]
    for p in parts:
        p = str(p).strip("/").replace("\\", "/")
        if p:
            clean.append(p)
    return "/" + "/".join(clean)


async def ensure_folder(token: str, path: str) -> None:
    """Create folder and parents on Disk (idempotent)."""
    path = "/" + path.strip("/")
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
            # 409 = already exists
            if r.status_code >= 400 and r.status_code != 409:
                raise DiskError(f"mkdir failed {current}: {r.text}", r.status_code)


async def upload_file(
    token: str, local_path: Path, remote_path: str, overwrite: bool = True
) -> dict[str, Any]:
    remote_path = "/" + remote_path.strip("/")
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
    remote_path = "/" + remote_path.strip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f"{YANDEX_DISK_API}/resources/download",
            params={"path": remote_path},
            headers=_headers(token),
        )
        if r.status_code >= 400:
            raise DiskError(f"download href failed: {r.text}", r.status_code)
        href = r.json().get("href")
        if not href:
            raise DiskError("No download href")
        return href


async def get_meta(token: str, remote_path: str) -> dict[str, Any]:
    remote_path = "/" + remote_path.strip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f"{YANDEX_DISK_API}/resources",
            params={"path": remote_path},
            headers=_headers(token),
        )
        if r.status_code >= 400:
            raise DiskError(f"meta failed: {r.text}", r.status_code)
        return r.json()


def encode_disk_path(path: str) -> str:
    return quote(path, safe="/")

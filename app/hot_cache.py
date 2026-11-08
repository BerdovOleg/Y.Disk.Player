from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from app.config import TRACK_CACHE_DIR, TRACK_CACHE_MAX_BYTES, TRACK_CACHE_TTL_HOURS

log = logging.getLogger("omt.cache")
_lock = threading.Lock()


def _meta_path(entry: Path) -> Path:
    return entry.with_suffix(entry.suffix + ".meta.json")


def cache_file_for(user_id: int, track_id: int, ext: str = ".bin") -> Path:
    TRACK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    if len(safe_ext) > 8:
        safe_ext = ".bin"
    return TRACK_CACHE_DIR / f"u{user_id}_t{track_id}{safe_ext}"


def _read_meta(path: Path) -> dict[str, Any] | None:
    meta = _meta_path(path)
    if not meta.exists():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_meta(path: Path, data: dict[str, Any]) -> None:
    _meta_path(path).write_text(json.dumps(data), encoding="utf-8")


def _ttl_seconds() -> float:
    return max(TRACK_CACHE_TTL_HOURS, 0) * 3600


def get_cached(user_id: int, track_id: int) -> Path | None:
    """Return fresh cache path or None. Touches last_access on hit."""
    with _lock:
        matches = list(TRACK_CACHE_DIR.glob(f"u{user_id}_t{track_id}.*"))
        matches = [p for p in matches if not p.name.endswith(".meta.json")]
        if not matches:
            return None
        path = matches[0]
        meta = _read_meta(path) or {}
        cached_at = float(meta.get("cached_at") or path.stat().st_mtime)
        if _ttl_seconds() and (time.time() - cached_at) > _ttl_seconds():
            _delete_entry(path)
            return None
        if not path.exists() or path.stat().st_size <= 0:
            _delete_entry(path)
            return None
        meta["last_access"] = time.time()
        meta["cached_at"] = cached_at
        _write_meta(path, meta)
        return path


def put_bytes(
    user_id: int,
    track_id: int,
    data: bytes,
    *,
    mime: str | None = None,
    ext: str = ".bin",
) -> Path:
    path = cache_file_for(user_id, track_id, ext)
    with _lock:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        now = time.time()
        _write_meta(
            path,
            {
                "user_id": user_id,
                "track_id": track_id,
                "mime": mime,
                "size": len(data),
                "cached_at": now,
                "last_access": now,
            },
        )
        _evict_if_needed()
        return path


async def put_from_path(
    user_id: int,
    track_id: int,
    src: Path,
    *,
    mime: str | None = None,
) -> Path:
    ext = src.suffix or ".bin"
    path = cache_file_for(user_id, track_id, ext)
    with _lock:
        tmp = path.with_suffix(path.suffix + ".tmp")
        shutil.copyfile(src, tmp)
        tmp.replace(path)
        now = time.time()
        size = path.stat().st_size
        _write_meta(
            path,
            {
                "user_id": user_id,
                "track_id": track_id,
                "mime": mime,
                "size": size,
                "cached_at": now,
                "last_access": now,
            },
        )
        _evict_if_needed()
        return path


def _delete_entry(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        _meta_path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _evict_if_needed() -> None:
    TRACK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[float, int, Path]] = []
    total = 0
    for path in TRACK_CACHE_DIR.iterdir():
        if path.name.endswith(".meta.json") or path.name.endswith(".tmp"):
            continue
        if not path.is_file():
            continue
        meta = _read_meta(path) or {}
        size = int(meta.get("size") or path.stat().st_size)
        last = float(meta.get("last_access") or path.stat().st_mtime)
        # drop expired
        cached_at = float(meta.get("cached_at") or path.stat().st_mtime)
        if _ttl_seconds() and (time.time() - cached_at) > _ttl_seconds():
            _delete_entry(path)
            continue
        total += size
        entries.append((last, size, path))

    if total <= TRACK_CACHE_MAX_BYTES:
        return
    entries.sort(key=lambda x: x[0])  # oldest access first
    for last, size, path in entries:
        if total <= TRACK_CACHE_MAX_BYTES:
            break
        log.info("cache evict %s (%s bytes)", path.name, size)
        _delete_entry(path)
        total -= size


def cache_stats() -> dict[str, Any]:
    TRACK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    count = 0
    for path in TRACK_CACHE_DIR.iterdir():
        if path.name.endswith(".meta.json") or not path.is_file():
            continue
        meta = _read_meta(path) or {}
        total += int(meta.get("size") or path.stat().st_size)
        count += 1
    return {
        "dir": str(TRACK_CACHE_DIR),
        "files": count,
        "bytes": total,
        "max_bytes": TRACK_CACHE_MAX_BYTES,
        "ttl_hours": TRACK_CACHE_TTL_HOURS,
    }

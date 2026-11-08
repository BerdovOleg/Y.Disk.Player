from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from app.audio_meta import read_tags
from app.catalog import upsert_track_from_tags
from app.config import DISK_ROOT
from app.db import get_db
from app.disk.client import DiskError, download_to_path, iter_files

log = logging.getLogger("omt.scan")

AUDIO_EXT = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma", ".aiff"}


def _disk_path_from_item(item: dict[str, Any]) -> str:
    """Normalize Disk API path (disk:/Music/...) to /Music/..."""
    path = item.get("path") or ""
    if path.startswith("disk:"):
        path = path[5:]
    if not path.startswith("/"):
        path = "/" + path
    return path


async def scan_disk_library(user_id: int, token: str, root: str | None = None) -> dict[str, Any]:
    """
    Recursively list DISK_ROOT, upsert audio into SQLite, mark missing as unavailable.
    Downloads files only when new or size changed (for mutagen tags).
    """
    root = root or DISK_ROOT
    seen_paths: set[str] = set()
    added = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    with get_db() as db:
        existing_rows = db.execute(
            "SELECT id, disk_path, size_bytes FROM tracks WHERE user_id=?",
            (user_id,),
        ).fetchall()
    by_path = {r["disk_path"]: dict(r) for r in existing_rows}

    async for item in iter_files(token, root):
        if item.get("type") != "file":
            continue
        name = item.get("name") or ""
        ext = Path(name).suffix.lower()
        if ext not in AUDIO_EXT:
            continue
        remote = _disk_path_from_item(item)
        seen_paths.add(remote)
        size = item.get("size")
        prev = by_path.get(remote)

        if prev and prev.get("size_bytes") == size:
            # Still present; ensure available=1 without re-download
            with get_db() as db:
                db.execute(
                    "UPDATE tracks SET available=1 WHERE id=?",
                    (prev["id"],),
                )
            skipped += 1
            continue

        suffix = ext or ".bin"
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)
            await download_to_path(token, remote, tmp_path)
            tags = read_tags(tmp_path)
            if size is not None:
                tags["size_bytes"] = size
            mime = item.get("mime_type") or tags.get("mime")
            if mime:
                tags["mime"] = mime
            track = upsert_track_from_tags(user_id, tags, remote)
            if prev:
                updated += 1
            else:
                added += 1
            by_path[remote] = track
        except DiskError as exc:
            log.warning("scan download failed %s: %s", remote, exc)
            errors.append(f"{remote}: {exc}")
        except Exception as exc:  # noqa: BLE001
            log.exception("scan failed %s", remote)
            errors.append(f"{remote}: {exc}")
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    missing = 0
    with get_db() as db:
        for path, row in by_path.items():
            if path not in seen_paths:
                db.execute(
                    "UPDATE tracks SET available=0 WHERE id=?",
                    (row["id"],),
                )
                missing += 1

    return {
        "ok": True,
        "root": root,
        "seen": len(seen_paths),
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "unavailable": missing,
        "errors": errors[:20],
        "error_count": len(errors),
    }

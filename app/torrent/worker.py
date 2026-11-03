from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Any

from app.audio_meta import read_tags, safe_segment
from app.config import TORRENT_DOWNLOAD_DIR
from app.crypto_util import decrypt_token
from app.db import get_db, row_to_dict
from app.disk.client import music_path, upload_file

log = logging.getLogger("omt.torrent")

AUDIO_EXT = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma", ".aiff"}

_lt = None
_lt_error: str | None = None


def _import_libtorrent():
    global _lt, _lt_error
    if _lt is not None or _lt_error:
        return _lt
    try:
        import libtorrent as lt  # type: ignore

        _lt = lt
        return lt
    except Exception as exc:  # noqa: BLE001
        _lt_error = str(exc)
        log.warning("libtorrent unavailable: %s", exc)
        return None


class TorrentWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: dict[int, asyncio.Task] = {}

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def libtorrent_status(self) -> dict[str, Any]:
        lt = _import_libtorrent()
        return {
            "available": lt is not None,
            "error": _lt_error,
        }

    async def start_list(self, job_id: int) -> None:
        loop = self._loop or asyncio.get_running_loop()
        task = loop.create_task(self._list_files(job_id))
        with self._lock:
            self._tasks[job_id] = task

    async def start_download(self, job_id: int) -> None:
        loop = self._loop or asyncio.get_running_loop()
        task = loop.create_task(self._download_and_upload(job_id))
        with self._lock:
            self._tasks[job_id] = task

    def _update_job(self, job_id: int, **fields: Any) -> None:
        cols = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [job_id]
        with get_db() as db:
            db.execute(
                f"UPDATE import_jobs SET {cols}, updated_at=datetime('now') WHERE id=?",
                vals,
            )

    def _job(self, job_id: int) -> dict | None:
        with get_db() as db:
            return row_to_dict(
                db.execute("SELECT * FROM import_jobs WHERE id=?", (job_id,)).fetchone()
            )

    def _user_token(self, user_id: int) -> str:
        with get_db() as db:
            row = db.execute(
                "SELECT token_enc FROM users WHERE id=?", (user_id,)
            ).fetchone()
        if not row or not row["token_enc"]:
            raise RuntimeError("No token")
        return decrypt_token(row["token_enc"])

    async def _list_files(self, job_id: int) -> None:
        self._update_job(job_id, status="listing", error=None)
        lt = _import_libtorrent()
        if lt is None:
            # Stub listing when libtorrent missing — allows UI/flow testing
            job = self._job(job_id)
            stub = [
                {
                    "index": 0,
                    "path": "Example Artist/Example Album/01 - Track.mp3",
                    "size": 3_500_000,
                    "audio": True,
                },
                {
                    "index": 1,
                    "path": "readme.txt",
                    "size": 1200,
                    "audio": False,
                },
            ]
            self._update_job(
                job_id,
                status="awaiting_confirm",
                file_list_json=json.dumps(stub),
                info_hash="stub-no-libtorrent",
                error=f"libtorrent unavailable ({_lt_error}); showing stub file list",
            )
            return

        job = self._job(job_id)
        if not job:
            return
        try:
            files = await asyncio.to_thread(self._sync_list_files, lt, job)
            self._update_job(
                job_id,
                status="awaiting_confirm",
                file_list_json=json.dumps(files["files"]),
                info_hash=files.get("info_hash"),
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("list failed job=%s", job_id)
            self._update_job(job_id, status="error", error=str(exc))

    def _sync_list_files(self, lt: Any, job: dict) -> dict[str, Any]:
        ses = lt.session({"listen_interfaces": "0.0.0.0:0"})
        params: dict[str, Any] = {
            "save_path": str(TORRENT_DOWNLOAD_DIR / f"job-{job['id']}"),
            "flags": lt.torrent_flags.default_flags
            | lt.torrent_flags.upload_mode
            | getattr(lt.torrent_flags, "paused", 0),
        }
        TORRENT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (TORRENT_DOWNLOAD_DIR / f"job-{job['id']}").mkdir(parents=True, exist_ok=True)

        if job["source_type"] == "magnet":
            handle = lt.add_magnet_uri(ses, job["source_ref"], params)
        else:
            path = Path(job["source_ref"])
            params["ti"] = lt.torrent_info(str(path))
            handle = ses.add_torrent(params)

        # Wait for metadata
        for _ in range(120):  # ~60s
            if handle.status().has_metadata:
                break
            import time

            time.sleep(0.5)
        if not handle.status().has_metadata:
            ses.remove_torrent(handle)
            raise TimeoutError("Timed out waiting for torrent metadata")

        ti = handle.torrent_file()
        out = []
        for i, f in enumerate(ti.files()):
            p = f.path
            ext = Path(p).suffix.lower()
            out.append(
                {
                    "index": i,
                    "path": p,
                    "size": f.size,
                    "audio": ext in AUDIO_EXT,
                }
            )
        info_hash = str(ti.info_hash())
        ses.remove_torrent(handle)
        return {"files": out, "info_hash": info_hash}

    async def _download_and_upload(self, job_id: int) -> None:
        job = self._job(job_id)
        if not job:
            return
        if not job.get("legal_confirmed"):
            self._update_job(job_id, status="error", error="Legal confirmation required")
            return

        lt = _import_libtorrent()
        if lt is None:
            self._update_job(
                job_id,
                status="error",
                error=f"Cannot download: libtorrent unavailable ({_lt_error})",
            )
            return

        self._update_job(job_id, status="downloading", progress=0, error=None)
        try:
            save_dir = await asyncio.to_thread(self._sync_download, lt, job)
            self._update_job(job_id, status="uploading", progress=0.5)
            token = self._user_token(job["user_id"])
            selected = json.loads(job["selected_json"] or "[]")
            file_list = {f["index"]: f for f in json.loads(job["file_list_json"] or "[]")}

            uploaded = 0
            total = max(len(selected), 1)
            for idx in selected:
                meta = file_list.get(idx) or file_list.get(str(idx))
                if not meta:
                    # selected may be int list
                    meta = next(
                        (f for f in file_list.values() if f["index"] == idx), None
                    )
                if not meta:
                    continue
                rel = meta["path"]
                local = Path(save_dir) / rel
                if not local.exists():
                    # libtorrent may flatten differently
                    candidates = list(Path(save_dir).rglob(Path(rel).name))
                    if candidates:
                        local = candidates[0]
                    else:
                        continue
                if local.suffix.lower() not in AUDIO_EXT:
                    continue
                tags = read_tags(local)
                artist = safe_segment(tags["artist"])
                album = safe_segment(tags["album"])
                year = tags["year"]
                year_part = f"{year} - " if year else ""
                remote = music_path(
                    artist, f"{year_part}{album}", safe_segment(local.name)
                )
                await upload_file(token, local, remote)
                self._catalog_track(job["user_id"], tags, remote, local)
                uploaded += 1
                self._update_job(job_id, progress=0.5 + 0.5 * (uploaded / total))

            self._update_job(job_id, status="done", progress=1.0, error=None)
        except Exception as exc:  # noqa: BLE001
            log.exception("download failed job=%s", job_id)
            self._update_job(job_id, status="error", error=str(exc))

    def _sync_download(self, lt: Any, job: dict) -> str:
        save_path = TORRENT_DOWNLOAD_DIR / f"job-{job['id']}"
        save_path.mkdir(parents=True, exist_ok=True)
        params: dict[str, Any] = {"save_path": str(save_path)}
        ses = lt.session({"listen_interfaces": "0.0.0.0:0"})

        if job["source_type"] == "magnet":
            handle = lt.add_magnet_uri(ses, job["source_ref"], params)
        else:
            params["ti"] = lt.torrent_info(job["source_ref"])
            handle = ses.add_torrent(params)

        selected = set(json.loads(job["selected_json"] or "[]"))
        # Wait metadata
        import time

        for _ in range(120):
            if handle.status().has_metadata:
                break
            time.sleep(0.5)
        if not handle.status().has_metadata:
            raise TimeoutError("metadata timeout")

        ti = handle.torrent_file()
        priorities = []
        for i in range(ti.num_files()):
            priorities.append(4 if i in selected else 0)
        handle.prioritize_files(priorities)

        # Download until done or timeout (~30 min)
        for _ in range(3600):
            st = handle.status()
            if st.is_seeding or (
                st.state in (lt.torrent_status.seeding, lt.torrent_status.finished)
            ):
                break
            # progress among selected
            prog = st.progress
            # best-effort update without opening another connection heavily
            time.sleep(0.5)
        else:
            raise TimeoutError("download timeout")

        return str(save_path)

    def _catalog_track(
        self, user_id: int, tags: dict, remote: str, local: Path
    ) -> None:
        year = tags.get("year")
        artist = tags["artist"]
        album = tags["album"]
        year_part = f"{year} - " if year else ""
        with get_db() as db:
            alb = db.execute(
                """
                SELECT id FROM albums
                WHERE user_id=? AND artist=? AND title=? AND (
                    (year IS NULL AND ? IS NULL) OR year=?
                )
                """,
                (user_id, artist, album, year, year),
            ).fetchone()
            if alb:
                album_id = alb["id"]
            else:
                cur = db.execute(
                    """
                    INSERT INTO albums (user_id, artist, title, year, disk_path)
                    VALUES (?,?,?,?,?)
                    """,
                    (
                        user_id,
                        artist,
                        album,
                        year,
                        music_path(
                            safe_segment(artist),
                            f"{year_part}{safe_segment(album)}",
                        ),
                    ),
                )
                album_id = cur.lastrowid

            existing = db.execute(
                "SELECT id FROM tracks WHERE user_id=? AND disk_path=?",
                (user_id, remote),
            ).fetchone()
            if existing:
                db.execute(
                    """
                    UPDATE tracks SET album_id=?, title=?, artist=?, duration_sec=?,
                        track_num=?, mime=?, size_bytes=? WHERE id=?
                    """,
                    (
                        album_id,
                        tags["title"],
                        artist,
                        tags.get("duration_sec"),
                        tags.get("track_num"),
                        tags.get("mime"),
                        tags.get("size_bytes"),
                        existing["id"],
                    ),
                )
            else:
                db.execute(
                    """
                    INSERT INTO tracks
                      (user_id, album_id, title, artist, duration_sec, track_num, mime, size_bytes, disk_path)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        user_id,
                        album_id,
                        tags["title"],
                        artist,
                        tags.get("duration_sec"),
                        tags.get("track_num"),
                        tags.get("mime"),
                        tags.get("size_bytes"),
                        remote,
                    ),
                )


_worker: TorrentWorker | None = None


def get_worker() -> TorrentWorker:
    global _worker
    if _worker is None:
        _worker = TorrentWorker()
    return _worker

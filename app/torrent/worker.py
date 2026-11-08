from __future__ import annotations

import asyncio
import json
import logging
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

from app.audio_meta import read_tags
from app.catalog import upsert_track_from_tags
from app.config import TORRENT_DOWNLOAD_DIR
from app.crypto_util import decrypt_token
from app.db import get_db, row_to_dict
from app.disk.client import disk_path_preserve_rel, upload_file

log = logging.getLogger("omt.torrent")

AUDIO_EXT = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma", ".aiff"}

_lt = None
_lt_error: str | None = None
_lt_version: str | None = None

_BREW_SITE = "/opt/homebrew/lib/python3.15/site-packages"


def _import_libtorrent():
    global _lt, _lt_error, _lt_version
    if _lt is not None:
        return _lt
    if _lt_error and _lt is None and "unavailable" in (_lt_error or ""):
        # allow retry after brew install in same process? reset once
        pass
    try:
        import libtorrent as lt  # type: ignore

        _lt = lt
        _lt_version = getattr(lt, "__version__", None) or str(
            getattr(lt, "version", "?")
        )
        _lt_error = None
        return lt
    except Exception:
        # Brew-installed bindings (Homebrew python@3.15)
        if _BREW_SITE not in sys.path:
            sys.path.insert(0, _BREW_SITE)
        try:
            import libtorrent as lt  # type: ignore

            _lt = lt
            _lt_version = getattr(lt, "__version__", None) or str(
                getattr(lt, "version", "?")
            )
            _lt_error = None
            return lt
        except Exception as exc:  # noqa: BLE001
            _lt_error = str(exc)
            log.warning("libtorrent unavailable: %s", exc)
            return None


def _make_session(lt: Any) -> Any:
    ses = lt.session()
    settings = {
        "listen_interfaces": "0.0.0.0:0",
        "enable_dht": True,
        "enable_lsd": True,
        "enable_upnp": True,
        "enable_natpmp": True,
        "announce_to_all_tiers": True,
        "announce_to_all_trackers": True,
    }
    try:
        ses.apply_settings(settings)
    except Exception:
        # Older API fallback
        try:
            ses.listen_on(6881, 6891)
        except Exception:
            pass
    for host, port in (
        ("router.bittorrent.com", 6881),
        ("router.utorrent.com", 6881),
        ("dht.transmissionbt.com", 6881),
    ):
        try:
            ses.add_dht_router(host, port)
        except Exception:
            pass
    try:
        ses.start_dht()
    except Exception:
        pass
    return ses


def _iter_torrent_files(ti: Any) -> list[dict[str, Any]]:
    """List files from torrent_info (libtorrent 2.x file_storage is not iterable)."""
    fs = ti.files()
    out: list[dict[str, Any]] = []
    n = fs.num_files()
    for i in range(n):
        try:
            p = fs.file_path(i)
        except Exception:
            p = fs.file_name(i)
        try:
            size = int(fs.file_size(i))
        except Exception:
            size = 0
        ext = Path(str(p)).suffix.lower()
        out.append(
            {
                "index": i,
                "path": str(p),
                "size": size,
                "audio": ext in AUDIO_EXT,
            }
        )
    return out


def _file_size(ti: Any, index: int) -> int:
    fs = ti.files()
    try:
        return int(fs.file_size(index))
    except Exception:
        return 0


class TorrentWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: dict[int, asyncio.Task] = {}

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def libtorrent_status(self) -> dict[str, Any]:
        # Reset cached miss so brew install mid-run can be picked up
        global _lt, _lt_error
        if _lt is None:
            _lt_error = None
        lt = _import_libtorrent()
        return {
            "available": lt is not None,
            "version": _lt_version,
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
            self._update_job(
                job_id,
                status="error",
                error=(
                    f"libtorrent unavailable ({_lt_error}). "
                    "Install: brew install libtorrent-rasterbar and use "
                    "Homebrew Python 3.15 venv (--system-site-packages)."
                ),
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
        ses = _make_session(lt)
        save = TORRENT_DOWNLOAD_DIR / f"job-{job['id']}"
        save.mkdir(parents=True, exist_ok=True)
        params: dict[str, Any] = {
            "save_path": str(save),
        }
        try:
            params["flags"] = (
                lt.torrent_flags.upload_mode
                | lt.torrent_flags.paused
                | lt.torrent_flags.auto_managed
            )
        except Exception:
            pass

        if job["source_type"] == "magnet":
            handle = lt.add_magnet_uri(ses, job["source_ref"], params)
        else:
            path = Path(job["source_ref"])
            params["ti"] = lt.torrent_info(str(path))
            handle = ses.add_torrent(params)

        try:
            handle.resume()
        except Exception:
            pass

        for _ in range(180):  # ~90s for metadata
            if handle.status().has_metadata:
                break
            time.sleep(0.5)
        if not handle.status().has_metadata:
            try:
                ses.remove_torrent(handle)
            except Exception:
                pass
            raise TimeoutError("Timed out waiting for torrent metadata")

        ti = handle.torrent_file()
        out = _iter_torrent_files(ti)
        info_hash = str(ti.info_hash())
        try:
            ses.remove_torrent(handle, lt.session.delete_files)
        except Exception:
            try:
                ses.remove_torrent(handle)
            except Exception:
                pass
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

        save_dir = TORRENT_DOWNLOAD_DIR / f"job-{job_id}"
        self._update_job(job_id, status="downloading", progress=0, error=None)
        try:
            save_dir = Path(
                await asyncio.to_thread(self._sync_download, lt, job, job_id)
            )
            self._update_job(job_id, status="uploading", progress=0.5)
            token = self._user_token(job["user_id"])
            selected = json.loads(job["selected_json"] or "[]")
            file_list = {f["index"]: f for f in json.loads(job["file_list_json"] or "[]")}

            uploaded = 0
            total = max(len(selected), 1)
            for idx in selected:
                meta = file_list.get(idx)
                if not meta:
                    meta = next(
                        (f for f in file_list.values() if f["index"] == idx), None
                    )
                if not meta:
                    continue
                rel = meta["path"]
                local = Path(save_dir) / rel
                if not local.exists():
                    candidates = list(Path(save_dir).rglob(Path(rel).name))
                    if candidates:
                        local = candidates[0]
                    else:
                        continue
                if local.suffix.lower() not in AUDIO_EXT:
                    continue
                tags = read_tags(local)
                # Keep torrent relative folder layout under DISK_ROOT (no flatten)
                remote = disk_path_preserve_rel(rel)
                await upload_file(token, local, remote)
                upsert_track_from_tags(job["user_id"], tags, remote)
                uploaded += 1
                self._update_job(job_id, progress=0.5 + 0.5 * (uploaded / total))

            self._update_job(job_id, status="done", progress=1.0, error=None)
        except Exception as exc:  # noqa: BLE001
            log.exception("download failed job=%s", job_id)
            self._update_job(job_id, status="error", error=str(exc))
        finally:
            # Wipe temp download tree after catalog (or on failure)
            try:
                if save_dir.exists():
                    shutil.rmtree(save_dir, ignore_errors=True)
            except Exception:
                pass

    def _sync_download(self, lt: Any, job: dict, job_id: int) -> str:
        save_path = TORRENT_DOWNLOAD_DIR / f"job-{job_id}"
        save_path.mkdir(parents=True, exist_ok=True)
        ses = _make_session(lt)
        params: dict[str, Any] = {"save_path": str(save_path)}

        if job["source_type"] == "magnet":
            handle = lt.add_magnet_uri(ses, job["source_ref"], params)
        else:
            params["ti"] = lt.torrent_info(job["source_ref"])
            handle = ses.add_torrent(params)

        selected = {int(x) for x in json.loads(job["selected_json"] or "[]")}

        for _ in range(180):
            if handle.status().has_metadata:
                break
            time.sleep(0.5)
        if not handle.status().has_metadata:
            raise TimeoutError("metadata timeout")

        ti = handle.torrent_file()
        n_files = ti.files().num_files()
        priorities = [4 if i in selected else 0 for i in range(n_files)]
        try:
            handle.prioritize_files(priorities)
        except Exception:
            for i, prio in enumerate(priorities):
                try:
                    handle.file_priority(i, prio)
                except Exception:
                    pass

        try:
            handle.resume()
        except Exception:
            pass
        try:
            handle.set_upload_mode(False)
        except Exception:
            pass

        # Download until selected files complete or ~45 min
        for tick in range(5400):
            st = handle.status()
            prog = float(st.progress)
            if tick % 4 == 0:
                self._update_job(job_id, progress=min(prog * 0.5, 0.49))

            finished = False
            try:
                if st.state in (
                    getattr(lt.torrent_status, "seeding", 5),
                    getattr(lt.torrent_status, "finished", 4),
                ):
                    finished = True
            except Exception:
                pass
            if getattr(st, "is_finished", False) or getattr(st, "is_seeding", False):
                finished = True

            # Selected-file progress (ignore deselected)
            try:
                fp = handle.file_progress()
                if fp and selected:
                    done = all(
                        (fp[i] >= _file_size(ti, i))
                        for i in selected
                        if i < len(fp) and _file_size(ti, i) > 0
                    )
                    if done:
                        finished = True
            except Exception:
                pass

            if finished:
                break
            time.sleep(0.5)
        else:
            raise TimeoutError("download timeout")

        try:
            ses.remove_torrent(handle)
        except Exception:
            pass
        return str(save_path)


_worker: TorrentWorker | None = None


def get_worker() -> TorrentWorker:
    global _worker
    if _worker is None:
        _worker = TorrentWorker()
    return _worker

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.config import DISK_SCAN_INTERVAL_HOURS
from app.crypto_util import decrypt_token
from app.db import get_db, row_to_dict
from app.disk.client import DiskError
from app.disk.scanner import scan_disk_library

log = logging.getLogger("omt.scan_sched")

_task: asyncio.Task | None = None
_lock = asyncio.Lock()


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_scan_status(user_id: int | None = None) -> dict[str, Any]:
    with get_db() as db:
        if user_id is not None:
            row = row_to_dict(
                db.execute(
                    "SELECT * FROM scan_state WHERE user_id=?", (user_id,)
                ).fetchone()
            )
            return {
                "interval_hours": DISK_SCAN_INTERVAL_HOURS,
                "enabled": DISK_SCAN_INTERVAL_HOURS > 0,
                "user": row,
            }
        rows = db.execute(
            """
            SELECT * FROM scan_state
            ORDER BY CASE WHEN last_finished_at IS NULL THEN 1 ELSE 0 END,
                     last_finished_at DESC
            """
        ).fetchall()
        return {
            "interval_hours": DISK_SCAN_INTERVAL_HOURS,
            "enabled": DISK_SCAN_INTERVAL_HOURS > 0,
            "users": [dict(r) for r in rows],
        }


def _set_state(user_id: int, **fields: Any) -> None:
    with get_db() as db:
        existing = db.execute(
            "SELECT user_id FROM scan_state WHERE user_id=?", (user_id,)
        ).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO scan_state (user_id) VALUES (?)",
                (user_id,),
            )
        cols = ", ".join(f"{k}=?" for k in fields)
        db.execute(
            f"UPDATE scan_state SET {cols} WHERE user_id=?",
            (*fields.values(), user_id),
        )


async def run_scan_for_user(user_id: int, token: str) -> dict[str, Any]:
    _set_state(
        user_id,
        last_started_at=_utcnow(),
        last_status="running",
        last_error=None,
    )
    try:
        result = await scan_disk_library(user_id, token)
        _set_state(
            user_id,
            last_finished_at=_utcnow(),
            last_status="ok",
            last_result_json=json.dumps(result),
            last_error=None,
        )
        return result
    except Exception as exc:  # noqa: BLE001
        _set_state(
            user_id,
            last_finished_at=_utcnow(),
            last_status="error",
            last_error=str(exc)[:500],
        )
        raise


async def _scan_all_users() -> None:
    async with _lock:
        with get_db() as db:
            users = [
                dict(r)
                for r in db.execute(
                    "SELECT id, token_enc FROM users WHERE token_enc IS NOT NULL"
                ).fetchall()
            ]
        for u in users:
            try:
                token = decrypt_token(u["token_enc"])
            except Exception:
                continue
            if token.startswith("dev-stub"):
                continue
            try:
                await run_scan_for_user(int(u["id"]), token)
                log.info("scheduled scan ok user=%s", u["id"])
            except DiskError as exc:
                log.warning("scheduled scan disk error user=%s: %s", u["id"], exc)
            except Exception:
                log.exception("scheduled scan failed user=%s", u["id"])


async def _loop() -> None:
    # small delay after startup
    await asyncio.sleep(15)
    while True:
        hours = DISK_SCAN_INTERVAL_HOURS
        if hours <= 0:
            await asyncio.sleep(3600)
            continue
        try:
            await _scan_all_users()
        except Exception:
            log.exception("scheduled scan loop error")
        await asyncio.sleep(max(hours, 0.1) * 3600)


def start_scheduler(loop: asyncio.AbstractEventLoop | None = None) -> None:
    global _task
    if DISK_SCAN_INTERVAL_HOURS <= 0:
        log.info("disk scan scheduler disabled (DISK_SCAN_INTERVAL_HOURS<=0)")
        return
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_loop(), name="omt-disk-scan")
    log.info(
        "disk scan scheduler started interval_hours=%s", DISK_SCAN_INTERVAL_HOURS
    )


def stop_scheduler() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
    _task = None

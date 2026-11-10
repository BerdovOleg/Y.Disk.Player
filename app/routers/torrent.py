from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.config import TORRENT_DOWNLOAD_DIR
from app.deps import require_user
from app.db import get_db, row_to_dict
from app.torrent.worker import get_worker

router = APIRouter(prefix="/api/import", tags=["torrent"])


class ConfirmBody(BaseModel):
    selected: list[int] = Field(default_factory=list)
    legal_confirmed: bool = False


@router.get("/status")
def import_capability():
    return get_worker().libtorrent_status()


@router.get("/jobs")
def list_jobs(request: Request):
    user = require_user(request)
    with get_db() as db:
        rows = db.execute(
            """
            SELECT id, source_type, status, progress, error, info_hash,
                   legal_confirmed, created_at, updated_at
            FROM import_jobs WHERE user_id=?
            ORDER BY created_at DESC LIMIT 50
            """,
            (user["id"],),
        ).fetchall()
    return {"jobs": [dict(r) for r in rows]}


@router.get("/jobs/{job_id}")
def get_job(job_id: int, request: Request):
    user = require_user(request)
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM import_jobs WHERE id=? AND user_id=?",
            (job_id, user["id"]),
        ).fetchone()
    job = row_to_dict(row)
    if not job:
        raise HTTPException(404, "Job not found")
    # Parse JSON fields for client
    for key in ("file_list_json", "selected_json"):
        raw = job.get(key)
        if raw:
            try:
                job[key.replace("_json", "")] = json.loads(raw)
            except json.JSONDecodeError:
                job[key.replace("_json", "")] = None
    return job


@router.post("/magnet")
async def import_magnet(request: Request, magnet: str = Form(...)):
    user = require_user(request)
    magnet = magnet.strip()
    if not magnet.startswith("magnet:"):
        raise HTTPException(400, "Expected magnet: URI")
    with get_db() as db:
        cur = db.execute(
            """
            INSERT INTO import_jobs (user_id, source_type, source_ref, status)
            VALUES (?,?,?,?)
            """,
            (user["id"], "magnet", magnet, "pending"),
        )
        job_id = int(cur.lastrowid)
    await get_worker().start_list(job_id)
    return {"ok": True, "job_id": job_id}


@router.post("/torrent")
async def import_torrent_file(request: Request, file: UploadFile = File(...)):
    user = require_user(request)
    name = file.filename or "upload.torrent"
    if not name.lower().endswith(".torrent"):
        raise HTTPException(400, "Expected .torrent file")

    TORRENT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest_dir = TORRENT_DOWNLOAD_DIR / "uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)

    with get_db() as db:
        cur = db.execute(
            """
            INSERT INTO import_jobs (user_id, source_type, source_ref, status)
            VALUES (?,?,?,?)
            """,
            (user["id"], "torrent_file", "", "pending"),
        )
        job_id = int(cur.lastrowid)

    path = dest_dir / f"job-{job_id}.torrent"
    with path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    with get_db() as db:
        db.execute(
            "UPDATE import_jobs SET source_ref=? WHERE id=?",
            (str(path), job_id),
        )

    await get_worker().start_list(job_id)
    return {"ok": True, "job_id": job_id}


@router.post("/jobs/{job_id}/confirm")
async def confirm_job(job_id: int, body: ConfirmBody, request: Request):
    user = require_user(request)
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM import_jobs WHERE id=? AND user_id=?",
            (job_id, user["id"]),
        ).fetchone()
        job = row_to_dict(row)
        if not job:
            raise HTTPException(404, "Job not found")
        if job["status"] not in ("awaiting_confirm", "error"):
            # Allow re-confirm from awaiting_confirm primarily
            if job["status"] != "awaiting_confirm":
                raise HTTPException(400, f"Job status is {job['status']}")
        if not body.legal_confirmed:
            raise HTTPException(
                400,
                "You must confirm you have the legal right to download these files",
            )
        if not body.selected:
            raise HTTPException(400, "Select at least one file")

        db.execute(
            """
            UPDATE import_jobs
            SET selected_json=?, legal_confirmed=1, status='downloading',
                error=NULL, updated_at=datetime('now')
            WHERE id=?
            """,
            (json.dumps(body.selected), job_id),
        )

    await get_worker().start_download(job_id)
    return {"ok": True, "job_id": job_id, "status": "downloading"}

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.audio_meta import read_tags, safe_segment
from app.deps import require_user, user_token
from app.disk.client import DiskError, music_path, upload_file
from app.db import get_db, row_to_dict

router = APIRouter(prefix="/api", tags=["library"])

AUDIO_EXT = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma", ".aiff"}


@router.get("/library")
def list_library(request: Request):
    user = require_user(request)
    with get_db() as db:
        albums = db.execute(
            """
            SELECT a.*,
                   (SELECT COUNT(*) FROM tracks t WHERE t.album_id = a.id) AS track_count
            FROM albums a
            WHERE a.user_id = ?
            ORDER BY a.artist COLLATE NOCASE, a.year, a.title COLLATE NOCASE
            """,
            (user["id"],),
        ).fetchall()
        tracks = db.execute(
            """
            SELECT t.*,
                   EXISTS(SELECT 1 FROM favorites f WHERE f.user_id=? AND f.track_id=t.id) AS is_favorite
            FROM tracks t
            WHERE t.user_id = ?
            ORDER BY t.artist COLLATE NOCASE, t.album_id, t.track_num, t.title COLLATE NOCASE
            """,
            (user["id"], user["id"]),
        ).fetchall()
    return {
        "albums": [dict(a) for a in albums],
        "tracks": [dict(t) for t in tracks],
    }


@router.get("/tracks/{track_id}")
def get_track(track_id: int, request: Request):
    user = require_user(request)
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM tracks WHERE id=? AND user_id=?",
            (track_id, user["id"]),
        ).fetchone()
    track = row_to_dict(row)
    if not track:
        raise HTTPException(404, "Track not found")
    return track


@router.post("/upload")
async def upload_audio(request: Request, file: UploadFile = File(...)):
    user = require_user(request)
    token = user_token(user)

    filename = file.filename or "audio.bin"
    ext = Path(filename).suffix.lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(400, f"Unsupported audio type: {ext or '(none)'}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp_path = Path(tmp.name)
        while chunk := await file.read(1024 * 1024):
            tmp.write(chunk)

    try:
        meta = read_tags(tmp_path)
        artist = safe_segment(meta["artist"], "Unknown Artist")
        album = safe_segment(meta["album"], "Unknown Album")
        year = meta["year"]
        year_part = f"{year} - " if year else ""
        remote_name = safe_segment(Path(filename).name, "track" + ext)
        remote = music_path(artist, f"{year_part}{album}", remote_name)

        try:
            await upload_file(token, tmp_path, remote)
        except DiskError as exc:
            raise HTTPException(exc.status or 502, str(exc)) from exc

        with get_db() as db:
            alb = db.execute(
                """
                SELECT id FROM albums
                WHERE user_id=? AND artist=? AND title=? AND (
                    (year IS NULL AND ? IS NULL) OR year=?
                )
                """,
                (user["id"], meta["artist"], meta["album"], year, year),
            ).fetchone()
            if alb:
                album_id = alb["id"]
                db.execute(
                    "UPDATE albums SET disk_path=? WHERE id=?",
                    (music_path(artist, f"{year_part}{album}"), album_id),
                )
            else:
                cur = db.execute(
                    """
                    INSERT INTO albums (user_id, artist, title, year, disk_path)
                    VALUES (?,?,?,?,?)
                    """,
                    (
                        user["id"],
                        meta["artist"],
                        meta["album"],
                        year,
                        music_path(artist, f"{year_part}{album}"),
                    ),
                )
                album_id = cur.lastrowid

            existing = db.execute(
                "SELECT id FROM tracks WHERE user_id=? AND disk_path=?",
                (user["id"], remote),
            ).fetchone()
            if existing:
                db.execute(
                    """
                    UPDATE tracks SET album_id=?, title=?, artist=?, duration_sec=?,
                        track_num=?, mime=?, size_bytes=?
                    WHERE id=?
                    """,
                    (
                        album_id,
                        meta["title"],
                        meta["artist"],
                        meta["duration_sec"],
                        meta["track_num"],
                        meta["mime"],
                        meta["size_bytes"],
                        existing["id"],
                    ),
                )
                track_id = existing["id"]
            else:
                cur = db.execute(
                    """
                    INSERT INTO tracks
                      (user_id, album_id, title, artist, duration_sec, track_num, mime, size_bytes, disk_path)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        user["id"],
                        album_id,
                        meta["title"],
                        meta["artist"],
                        meta["duration_sec"],
                        meta["track_num"],
                        meta["mime"],
                        meta["size_bytes"],
                        remote,
                    ),
                )
                track_id = cur.lastrowid

            track = row_to_dict(
                db.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
            )
        return {"ok": True, "track": track, "disk_path": remote}
    finally:
        tmp_path.unlink(missing_ok=True)

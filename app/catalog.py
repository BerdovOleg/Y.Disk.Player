from __future__ import annotations

from pathlib import Path
from typing import Any

from app.audio_meta import safe_segment
from app.db import get_db, row_to_dict
from app.disk.client import music_path


def upsert_track_from_tags(
    user_id: int, tags: dict[str, Any], remote: str
) -> dict[str, Any]:
    """Insert or update album+track for a Disk path. Returns track row."""
    year = tags.get("year")
    artist = tags.get("artist") or "Unknown Artist"
    album = tags.get("album") or "Unknown Album"
    year_part = f"{year} - " if year else ""
    album_disk = music_path(
        safe_segment(artist),
        f"{year_part}{safe_segment(album)}",
    )

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
            db.execute(
                "UPDATE albums SET disk_path=? WHERE id=?",
                (album_disk, album_id),
            )
        else:
            cur = db.execute(
                """
                INSERT INTO albums (user_id, artist, title, year, disk_path)
                VALUES (?,?,?,?,?)
                """,
                (user_id, artist, album, year, album_disk),
            )
            album_id = cur.lastrowid

        existing = db.execute(
            "SELECT id FROM tracks WHERE user_id=? AND disk_path=?",
            (user_id, remote),
        ).fetchone()
        fields = (
            album_id,
            tags.get("title") or Path(remote).stem,
            artist,
            tags.get("duration_sec"),
            tags.get("track_num"),
            tags.get("mime"),
            tags.get("size_bytes"),
        )
        if existing:
            db.execute(
                """
                UPDATE tracks SET album_id=?, title=?, artist=?, duration_sec=?,
                    track_num=?, mime=?, size_bytes=?, available=1
                WHERE id=?
                """,
                (*fields, existing["id"]),
            )
            track_id = existing["id"]
        else:
            cur = db.execute(
                """
                INSERT INTO tracks
                  (user_id, album_id, title, artist, duration_sec, track_num,
                   mime, size_bytes, disk_path, available)
                VALUES (?,?,?,?,?,?,?,?,?,1)
                """,
                (user_id, *fields, remote),
            )
            track_id = cur.lastrowid

        return row_to_dict(
            db.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
        )  # type: ignore[return-value]

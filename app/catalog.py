from __future__ import annotations

from pathlib import Path
from typing import Any

from app.audio_meta import UNKNOWN_ALBUM, UNKNOWN_ARTIST, UNKNOWN_GENRE, safe_segment
from app.db import get_db, row_to_dict
from app.disk.client import music_path


def album_disk_from_remote(remote: str, artist: str, album: str, year: int | None) -> str:
    """Prefer parent folder of the track on Disk; fall back to Artist/Year - Album."""
    parts = [p for p in remote.strip("/").split("/") if p]
    if len(parts) >= 2:
        return "/" + "/".join(parts[:-1])
    year_part = f"{year} - " if year else ""
    return music_path(
        safe_segment(artist),
        f"{year_part}{safe_segment(album)}",
    )


def upsert_track_from_tags(
    user_id: int, tags: dict[str, Any], remote: str
) -> dict[str, Any]:
    """Insert or update album+track for a Disk path. Returns track row."""
    year = tags.get("year")
    artist = tags.get("artist") or UNKNOWN_ARTIST
    album = tags.get("album") or UNKNOWN_ALBUM
    genre = (tags.get("genre") or UNKNOWN_GENRE).strip() or UNKNOWN_GENRE
    album_disk = album_disk_from_remote(remote, artist, album, year)

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
            genre,
            tags.get("duration_sec"),
            tags.get("track_num"),
            tags.get("mime"),
            tags.get("size_bytes"),
        )
        if existing:
            db.execute(
                """
                UPDATE tracks SET album_id=?, title=?, artist=?, genre=?, duration_sec=?,
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
                  (user_id, album_id, title, artist, genre, duration_sec, track_num,
                   mime, size_bytes, disk_path, available)
                VALUES (?,?,?,?,?,?,?,?,?,?,1)
                """,
                (user_id, *fields, remote),
            )
            track_id = cur.lastrowid

        return row_to_dict(
            db.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
        )  # type: ignore[return-value]


def build_library_tree(tracks: list[dict[str, Any]], albums_by_id: dict[int, dict]) -> list[dict]:
    """Genre → Artist → Album → Track nested tree. Tracks keep list order within album."""
    # genre -> artist -> album_id -> tracks
    genres: dict[str, dict[str, dict[int, list[dict]]]] = {}
    for t in tracks:
        genre = (t.get("genre") or UNKNOWN_GENRE).strip() or UNKNOWN_GENRE
        artist = t.get("artist") or UNKNOWN_ARTIST
        album_id = t.get("album_id") or 0
        genres.setdefault(genre, {}).setdefault(artist, {}).setdefault(album_id, []).append(t)

    tree: list[dict] = []
    for genre in sorted(genres.keys(), key=lambda g: (g == UNKNOWN_GENRE, g.lower())):
        artists_out = []
        for artist in sorted(genres[genre].keys(), key=str.lower):
            albums_out = []
            album_map = genres[genre][artist]
            # sort albums by year/title via album row when present
            def album_sort_key(aid: int) -> tuple:
                alb = albums_by_id.get(aid) or {}
                return (
                    alb.get("year") is None,
                    alb.get("year") or 0,
                    (alb.get("title") or "").lower(),
                )

            for album_id in sorted(album_map.keys(), key=album_sort_key):
                alb = albums_by_id.get(album_id) or {}
                tracks_in = album_map[album_id]
                tracks_sorted = sorted(
                    tracks_in,
                    key=lambda x: (
                        x.get("track_num") is None,
                        x.get("track_num") or 0,
                        (x.get("title") or "").lower(),
                    ),
                )
                albums_out.append(
                    {
                        "album_id": album_id or None,
                        "title": alb.get("title")
                        or (tracks_sorted[0].get("album") if tracks_sorted else UNKNOWN_ALBUM)
                        or UNKNOWN_ALBUM,
                        "year": alb.get("year"),
                        "artist": artist,
                        "genre": genre,
                        "tracks": tracks_sorted,
                    }
                )
            artists_out.append({"artist": artist, "genre": genre, "albums": albums_out})
        tree.append({"genre": genre, "artists": artists_out})
    return tree

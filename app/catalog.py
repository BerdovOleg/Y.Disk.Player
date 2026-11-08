from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from app.audio_meta import UNKNOWN_ALBUM, UNKNOWN_ARTIST, UNKNOWN_GENRE, safe_segment
from app.db import get_db, row_to_dict, sync_track_fts
from app.disk.client import music_path

LibraryView = Literal["genre", "artist", "album"]
LIBRARY_VIEWS: tuple[str, ...] = ("genre", "artist", "album")


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

        title = tags.get("title") or Path(remote).stem
        sync_track_fts(
            db,
            int(track_id),
            title=title,
            artist=artist,
            album=album,
            genre=genre,
            user_id=user_id,
        )

        return row_to_dict(
            db.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
        )  # type: ignore[return-value]


def _sort_tracks(tracks: list[dict]) -> list[dict]:
    return sorted(
        tracks,
        key=lambda x: (
            x.get("track_num") is None,
            x.get("track_num") or 0,
            (x.get("title") or "").lower(),
        ),
    )


def _album_sort_key(albums_by_id: dict[int, dict], aid: int) -> tuple:
    alb = albums_by_id.get(aid) or {}
    return (
        alb.get("year") is None,
        alb.get("year") or 0,
        (alb.get("title") or "").lower(),
    )


def _album_node(
    album_id: int,
    tracks: list[dict],
    albums_by_id: dict[int, dict],
    *,
    artist: str,
    genre: str | None = None,
) -> dict:
    alb = albums_by_id.get(album_id) or {}
    tracks_sorted = _sort_tracks(tracks)
    return {
        "album_id": album_id or None,
        "title": alb.get("title")
        or (tracks_sorted[0].get("album") if tracks_sorted else UNKNOWN_ALBUM)
        or (tracks_sorted[0].get("album_title") if tracks_sorted else None)
        or UNKNOWN_ALBUM,
        "year": alb.get("year"),
        "artist": artist,
        "genre": genre,
        "tracks": tracks_sorted,
    }


def build_library_tree(
    tracks: list[dict[str, Any]],
    albums_by_id: dict[int, dict],
    mode: str = "genre",
) -> list[dict]:
    """
    Nested library tree.
    mode=genre  → Genre → Artist → Album → Track
    mode=artist → Artist → Album → Track
    mode=album  → Album → Track
    """
    view = mode if mode in LIBRARY_VIEWS else "genre"

    if view == "album":
        albums: dict[int, list[dict]] = {}
        for t in tracks:
            albums.setdefault(t.get("album_id") or 0, []).append(t)
        out = []
        for album_id in sorted(albums.keys(), key=lambda a: _album_sort_key(albums_by_id, a)):
            sample = albums[album_id][0]
            artist = sample.get("artist") or UNKNOWN_ARTIST
            genre = (sample.get("genre") or UNKNOWN_GENRE).strip() or UNKNOWN_GENRE
            out.append(
                _album_node(
                    album_id,
                    albums[album_id],
                    albums_by_id,
                    artist=artist,
                    genre=genre,
                )
            )
        return out

    if view == "artist":
        artists: dict[str, dict[int, list[dict]]] = {}
        for t in tracks:
            artist = t.get("artist") or UNKNOWN_ARTIST
            album_id = t.get("album_id") or 0
            artists.setdefault(artist, {}).setdefault(album_id, []).append(t)
        out = []
        for artist in sorted(artists.keys(), key=str.lower):
            albums_out = []
            album_map = artists[artist]
            for album_id in sorted(
                album_map.keys(), key=lambda a: _album_sort_key(albums_by_id, a)
            ):
                sample = album_map[album_id][0]
                genre = (sample.get("genre") or UNKNOWN_GENRE).strip() or UNKNOWN_GENRE
                albums_out.append(
                    _album_node(
                        album_id,
                        album_map[album_id],
                        albums_by_id,
                        artist=artist,
                        genre=genre,
                    )
                )
            out.append({"artist": artist, "albums": albums_out})
        return out

    # genre (default)
    genres: dict[str, dict[str, dict[int, list[dict]]]] = {}
    for t in tracks:
        genre = (t.get("genre") or UNKNOWN_GENRE).strip() or UNKNOWN_GENRE
        artist = t.get("artist") or UNKNOWN_ARTIST
        album_id = t.get("album_id") or 0
        genres.setdefault(genre, {}).setdefault(artist, {}).setdefault(album_id, []).append(
            t
        )

    tree: list[dict] = []
    for genre in sorted(genres.keys(), key=lambda g: (g == UNKNOWN_GENRE, g.lower())):
        artists_out = []
        for artist in sorted(genres[genre].keys(), key=str.lower):
            albums_out = []
            album_map = genres[genre][artist]
            for album_id in sorted(
                album_map.keys(), key=lambda a: _album_sort_key(albums_by_id, a)
            ):
                albums_out.append(
                    _album_node(
                        album_id,
                        album_map[album_id],
                        albums_by_id,
                        artist=artist,
                        genre=genre,
                    )
                )
            artists_out.append({"artist": artist, "genre": genre, "albums": albums_out})
        tree.append({"genre": genre, "artists": artists_out})
    return tree

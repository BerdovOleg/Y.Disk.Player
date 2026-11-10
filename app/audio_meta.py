from __future__ import annotations

from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile

UNKNOWN_ARTIST = "Unknown Artist"
UNKNOWN_ALBUM = "Unknown Album"
UNKNOWN_GENRE = "Без жанра"


def parse_filename_artist_title(stem: str) -> tuple[str | None, str | None]:
    """
    If stem contains ' - ', before first separator = artist, after = title.
    Returns (None, None) when pattern does not apply.
    """
    stem = (stem or "").strip()
    if " - " not in stem:
        return None, None
    left, right = stem.split(" - ", 1)
    left, right = left.strip(), right.strip()
    if left and right:
        return left, right
    return None, None


def read_tags(path: Path) -> dict[str, Any]:
    """Extract common tags via mutagen. Filename fallback for artist/title; genre default."""
    path = Path(path)
    stem = path.stem
    fn_artist, fn_title = parse_filename_artist_title(stem)

    artist: str | None = None
    album: str | None = None
    title: str | None = None
    genre: str | None = None
    year: int | None = None
    track_num: int | None = None
    duration: float | None = None

    try:
        audio = MutagenFile(str(path), easy=True)
    except Exception:
        audio = None

    if audio is not None:

        def first(key: str) -> str | None:
            vals = audio.get(key) if hasattr(audio, "get") else None
            if not vals:
                return None
            return str(vals[0]).strip() or None

        artist = first("artist")
        album = first("album")
        title = first("title")
        genre = first("genre")
        date = first("date") or first("year")
        if date:
            digits = "".join(c for c in date[:4] if c.isdigit())
            if len(digits) == 4:
                year = int(digits)
        track = first("tracknumber")
        if track:
            num = track.split("/")[0].strip()
            if num.isdigit():
                track_num = int(num)
        try:
            duration = float(audio.info.length) if audio.info else None
        except Exception:
            duration = None

    if not artist:
        artist = fn_artist or UNKNOWN_ARTIST
    if not title:
        title = fn_title or stem
    if not album:
        album = UNKNOWN_ALBUM
    if not genre:
        genre = UNKNOWN_GENRE

    mime = None
    try:
        raw = MutagenFile(str(path))
        if raw is not None and getattr(raw, "mime", None):
            mime = raw.mime[0]
    except Exception:
        pass

    return {
        "artist": artist,
        "album": album,
        "title": title,
        "genre": genre,
        "year": year,
        "track_num": track_num,
        "duration_sec": duration,
        "mime": mime,
        "size_bytes": path.stat().st_size if path.exists() else None,
    }


def safe_segment(name: str, fallback: str = "Unknown") -> str:
    name = (name or fallback).strip() or fallback
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    name = name.strip(". ")
    return name[:120] or fallback

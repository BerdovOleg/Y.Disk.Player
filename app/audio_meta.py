from __future__ import annotations

from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile


def read_tags(path: Path) -> dict[str, Any]:
    """Extract common tags via mutagen. Safe defaults on missing tags."""
    artist = "Unknown Artist"
    album = "Unknown Album"
    title = path.stem
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

        artist = first("artist") or artist
        album = first("album") or album
        title = first("title") or title
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

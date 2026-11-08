from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.deps import require_user
from app.db import get_db, row_to_dict

router = APIRouter(prefix="/api/playlists", tags=["playlists"])


class PlaylistCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class PlaylistRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class AddTracksBody(BaseModel):
    track_ids: list[int] = Field(default_factory=list)
    track_id: int | None = None


class ReorderBody(BaseModel):
    track_ids: list[int] = Field(default_factory=list)


def _owned_playlist(db, playlist_id: int, user_id: int) -> dict:
    row = db.execute(
        "SELECT * FROM playlists WHERE id=? AND user_id=?",
        (playlist_id, user_id),
    ).fetchone()
    pl = row_to_dict(row)
    if not pl:
        raise HTTPException(404, "Playlist not found")
    return pl


def _playlist_with_tracks(db, playlist_id: int, user_id: int) -> dict:
    pl = _owned_playlist(db, playlist_id, user_id)
    tracks = db.execute(
        """
        SELECT t.*, pt.position,
               EXISTS(SELECT 1 FROM favorites f WHERE f.user_id=? AND f.track_id=t.id) AS is_favorite
        FROM playlist_tracks pt
        JOIN tracks t ON t.id = pt.track_id
        WHERE pt.playlist_id=? AND t.user_id=?
        ORDER BY pt.position ASC, t.title COLLATE NOCASE
        """,
        (user_id, playlist_id, user_id),
    ).fetchall()
    pl["tracks"] = [dict(t) for t in tracks]
    pl["track_count"] = len(pl["tracks"])
    return pl


@router.get("")
def list_playlists(request: Request):
    user = require_user(request)
    with get_db() as db:
        rows = db.execute(
            """
            SELECT p.*,
                   (SELECT COUNT(*) FROM playlist_tracks pt WHERE pt.playlist_id=p.id) AS track_count
            FROM playlists p
            WHERE p.user_id=?
            ORDER BY p.updated_at DESC, p.id DESC
            """,
            (user["id"],),
        ).fetchall()
    return {"playlists": [dict(r) for r in rows]}


@router.post("")
def create_playlist(body: PlaylistCreate, request: Request):
    user = require_user(request)
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "Title required")
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO playlists (user_id, title) VALUES (?,?)",
            (user["id"], title),
        )
        pid = int(cur.lastrowid)
        return _playlist_with_tracks(db, pid, user["id"])


@router.get("/{playlist_id}")
def get_playlist(playlist_id: int, request: Request):
    user = require_user(request)
    with get_db() as db:
        return _playlist_with_tracks(db, playlist_id, user["id"])


@router.patch("/{playlist_id}")
def rename_playlist(playlist_id: int, body: PlaylistRename, request: Request):
    user = require_user(request)
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "Title required")
    with get_db() as db:
        _owned_playlist(db, playlist_id, user["id"])
        db.execute(
            "UPDATE playlists SET title=?, updated_at=datetime('now') WHERE id=?",
            (title, playlist_id),
        )
        return _playlist_with_tracks(db, playlist_id, user["id"])


@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: int, request: Request):
    user = require_user(request)
    with get_db() as db:
        _owned_playlist(db, playlist_id, user["id"])
        db.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
    return {"ok": True, "id": playlist_id}


@router.post("/{playlist_id}/tracks")
def add_tracks(playlist_id: int, body: AddTracksBody, request: Request):
    user = require_user(request)
    ids = list(body.track_ids)
    if body.track_id is not None:
        ids.append(body.track_id)
    # dedupe preserve order
    seen: set[int] = set()
    uniq: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    if not uniq:
        raise HTTPException(400, "No tracks")

    with get_db() as db:
        _owned_playlist(db, playlist_id, user["id"])
        max_pos = db.execute(
            "SELECT COALESCE(MAX(position), -1) FROM playlist_tracks WHERE playlist_id=?",
            (playlist_id,),
        ).fetchone()[0]
        pos = int(max_pos) + 1
        for tid in uniq:
            track = db.execute(
                "SELECT id FROM tracks WHERE id=? AND user_id=?",
                (tid, user["id"]),
            ).fetchone()
            if not track:
                continue
            existing = db.execute(
                "SELECT 1 FROM playlist_tracks WHERE playlist_id=? AND track_id=?",
                (playlist_id, tid),
            ).fetchone()
            if existing:
                continue
            db.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?,?,?)",
                (playlist_id, tid, pos),
            )
            pos += 1
        db.execute(
            "UPDATE playlists SET updated_at=datetime('now') WHERE id=?",
            (playlist_id,),
        )
        return _playlist_with_tracks(db, playlist_id, user["id"])


@router.delete("/{playlist_id}/tracks/{track_id}")
def remove_track(playlist_id: int, track_id: int, request: Request):
    user = require_user(request)
    with get_db() as db:
        _owned_playlist(db, playlist_id, user["id"])
        db.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id=? AND track_id=?",
            (playlist_id, track_id),
        )
        # compact positions
        rows = db.execute(
            """
            SELECT track_id FROM playlist_tracks
            WHERE playlist_id=? ORDER BY position, track_id
            """,
            (playlist_id,),
        ).fetchall()
        for i, r in enumerate(rows):
            db.execute(
                "UPDATE playlist_tracks SET position=? WHERE playlist_id=? AND track_id=?",
                (i, playlist_id, r["track_id"]),
            )
        db.execute(
            "UPDATE playlists SET updated_at=datetime('now') WHERE id=?",
            (playlist_id,),
        )
        return _playlist_with_tracks(db, playlist_id, user["id"])


@router.put("/{playlist_id}/tracks")
def reorder_tracks(playlist_id: int, body: ReorderBody, request: Request):
    user = require_user(request)
    if not body.track_ids:
        raise HTTPException(400, "track_ids required")
    with get_db() as db:
        _owned_playlist(db, playlist_id, user["id"])
        existing = {
            r["track_id"]
            for r in db.execute(
                "SELECT track_id FROM playlist_tracks WHERE playlist_id=?",
                (playlist_id,),
            ).fetchall()
        }
        if set(body.track_ids) != existing:
            raise HTTPException(400, "track_ids must match playlist membership exactly")
        for i, tid in enumerate(body.track_ids):
            db.execute(
                "UPDATE playlist_tracks SET position=? WHERE playlist_id=? AND track_id=?",
                (i, playlist_id, tid),
            )
        db.execute(
            "UPDATE playlists SET updated_at=datetime('now') WHERE id=?",
            (playlist_id,),
        )
        return _playlist_with_tracks(db, playlist_id, user["id"])

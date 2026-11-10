from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.deps import require_user
from app.db import get_db, row_to_dict

router = APIRouter(prefix="/api", tags=["favorites"])


@router.get("/favorites")
def list_favorites(request: Request):
    user = require_user(request)
    with get_db() as db:
        rows = db.execute(
            """
            SELECT t.*, f.created_at AS favorited_at
            FROM favorites f
            JOIN tracks t ON t.id = f.track_id
            WHERE f.user_id = ?
            ORDER BY f.created_at DESC
            """,
            (user["id"],),
        ).fetchall()
    return {"tracks": [dict(r) for r in rows]}


@router.post("/favorites/{track_id}")
def add_favorite(track_id: int, request: Request):
    user = require_user(request)
    with get_db() as db:
        track = db.execute(
            "SELECT id FROM tracks WHERE id=? AND user_id=?",
            (track_id, user["id"]),
        ).fetchone()
        if not track:
            raise HTTPException(404, "Track not found")
        db.execute(
            "INSERT OR IGNORE INTO favorites (user_id, track_id) VALUES (?,?)",
            (user["id"], track_id),
        )
    return {"ok": True, "track_id": track_id, "favorited": True}


@router.delete("/favorites/{track_id}")
def remove_favorite(track_id: int, request: Request):
    user = require_user(request)
    with get_db() as db:
        db.execute(
            "DELETE FROM favorites WHERE user_id=? AND track_id=?",
            (user["id"], track_id),
        )
    return {"ok": True, "track_id": track_id, "favorited": False}

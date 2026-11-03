from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.deps import require_user
from app.db import get_db

router = APIRouter(prefix="/api", tags=["history"])


class HistoryBody(BaseModel):
    track_id: int
    position_sec: float = Field(default=0, ge=0)


@router.get("/history")
def list_history(request: Request, limit: int = 50):
    user = require_user(request)
    limit = max(1, min(limit, 200))
    with get_db() as db:
        rows = db.execute(
            """
            SELECT h.id AS history_id, h.played_at, h.position_sec, t.*
            FROM history h
            JOIN tracks t ON t.id = h.track_id
            WHERE h.user_id = ?
            ORDER BY h.played_at DESC
            LIMIT ?
            """,
            (user["id"], limit),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.post("/history")
def record_history(body: HistoryBody, request: Request):
    user = require_user(request)
    with get_db() as db:
        track = db.execute(
            "SELECT id FROM tracks WHERE id=? AND user_id=?",
            (body.track_id, user["id"]),
        ).fetchone()
        if not track:
            return {"ok": False, "error": "track not found"}
        db.execute(
            "INSERT INTO history (user_id, track_id, position_sec) VALUES (?,?,?)",
            (user["id"], body.track_id, body.position_sec),
        )
    return {"ok": True}

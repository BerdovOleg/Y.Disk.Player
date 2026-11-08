from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.deps import require_user
from app.db import get_db

router = APIRouter(prefix="/api", tags=["search"])


def _fts_query(q: str) -> str:
    """Build a safe FTS5 MATCH query: quote tokens, join with AND."""
    tokens = []
    for raw in q.replace('"', " ").split():
        t = raw.strip()
        if not t:
            continue
        # strip FTS operators that could break the query
        t = "".join(c for c in t if c.isalnum() or c in "-_./@")
        if t:
            tokens.append(f'"{t}"*')
    return " AND ".join(tokens)


@router.get("/search")
def search_library(request: Request, q: str = Query("", min_length=0)):
    user = require_user(request)
    q = (q or "").strip()
    if not q:
        return {"q": q, "tracks": [], "track_ids": []}
    match = _fts_query(q)
    if not match:
        return {"q": q, "tracks": [], "track_ids": []}

    with get_db() as db:
        try:
            rows = db.execute(
                """
                SELECT t.*,
                       a.title AS album_title,
                       EXISTS(SELECT 1 FROM favorites f WHERE f.user_id=? AND f.track_id=t.id) AS is_favorite
                FROM tracks_fts f
                JOIN tracks t ON t.id = f.rowid
                LEFT JOIN albums a ON a.id = t.album_id
                WHERE f.user_id=? AND tracks_fts MATCH ?
                ORDER BY bm25(tracks_fts), t.artist COLLATE NOCASE, t.title COLLATE NOCASE
                LIMIT 100
                """,
                (user["id"], user["id"], match),
            ).fetchall()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"Search failed: {exc}") from exc

    tracks = [dict(r) for r in rows]
    return {
        "q": q,
        "tracks": tracks,
        "track_ids": [t["id"] for t in tracks],
    }

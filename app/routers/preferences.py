from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.catalog import LIBRARY_VIEWS
from app.db import get_db, row_to_dict
from app.deps import require_user

router = APIRouter(prefix="/api", tags=["preferences"])


class PreferencesPatch(BaseModel):
    library_view: str | None = Field(default=None)


def _get_or_create(user_id: int) -> dict:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM user_preferences WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if not row:
            db.execute(
                "INSERT INTO user_preferences (user_id, library_view) VALUES (?, ?)",
                (user_id, "genre"),
            )
            row = db.execute(
                "SELECT * FROM user_preferences WHERE user_id=?",
                (user_id,),
            ).fetchone()
    return row_to_dict(row) or {"user_id": user_id, "library_view": "genre"}


@router.get("/preferences")
def get_preferences(request: Request):
    user = require_user(request)
    prefs = _get_or_create(user["id"])
    return {
        "library_view": prefs.get("library_view") or "genre",
        "views": list(LIBRARY_VIEWS),
        "updated_at": prefs.get("updated_at"),
    }


@router.patch("/preferences")
def patch_preferences(body: PreferencesPatch, request: Request):
    user = require_user(request)
    if body.library_view is None:
        return get_preferences(request)
    view = body.library_view.strip().lower()
    if view not in LIBRARY_VIEWS:
        raise HTTPException(400, f"library_view must be one of: {', '.join(LIBRARY_VIEWS)}")
    with get_db() as db:
        existing = db.execute(
            "SELECT user_id FROM user_preferences WHERE user_id=?",
            (user["id"],),
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE user_preferences
                SET library_view=?, updated_at=datetime('now')
                WHERE user_id=?
                """,
                (view, user["id"]),
            )
        else:
            db.execute(
                "INSERT INTO user_preferences (user_id, library_view) VALUES (?, ?)",
                (user["id"], view),
            )
    return get_preferences(request)

# 032 — Library view modes

**Date:** 2026-11-09

## Context
Need Genre→Artist→Album→Track | Artist→Album→Track | Album→Track toggles, persisted per user.

## Decision
Server builds tree by `mode`; preference in `user_preferences.library_view` (+ localStorage mirror). `GET /api/library?view=` override; `GET/PATCH /api/preferences`.

## Changes
- `app/catalog.py` — `build_library_tree(..., mode=)`
- `app/db.py` — `user_preferences`
- `app/routers/preferences.py`, `library.py`
- UI view-mode bar + render paths for artist/album modes

## Worked
Toggle persists across reload for the signed-in user.

## Failed / blocked
—

## Next
—

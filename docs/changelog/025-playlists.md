# 025 — Playlists CRUD + UI

**Date:** 2026-11-08

## Context
Post-MVP: users need named queues beyond shuffle of the whole library.

## Decision
Tables `playlists` + `playlist_tracks` (ordered). REST under `/api/playlists`. UI tab: create/rename/delete, add/remove/reorder, play as queue.

## Changes
- `app/db.py`, `app/routers/playlists.py`, `app/main.py`
- `static/index.html`, `static/js/app.js`, `static/css/app.css`

## Worked
CRUD + play-playlist smoke via API.

## Failed / blocked
—

## Next
FTS5 search (026).

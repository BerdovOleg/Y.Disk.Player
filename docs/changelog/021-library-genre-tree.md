# 021 — Library tree: Genre → Artist → Album → Track

**Date:** 2026-11-08

## Context
Flat track list made browsing large libraries hard; no genre dimension.

## Decision
Store `tracks.genre` (default «Без жанра» from mutagen or fallback). `/api/library` returns nested `tree` plus flat tracks. UI: expandable tree; ▶ on genre/artist/album queues all descendants in order.

## Changes
- `app/db.py`, `app/audio_meta.py`, `app/catalog.py`, `app/routers/library.py`
- `static/js/app.js`, `static/css/app.css`, `static/index.html`

## Worked
Tree API + expandable UI with play-to-queue.

## Failed / blocked
Existing rows keep «Без жанра» until re-scan/re-import refreshes tags.

## Next
Torrent path layout (022).

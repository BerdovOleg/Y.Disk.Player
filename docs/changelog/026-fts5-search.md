# 026 — FTS5 library search

**Date:** 2026-11-08

## Context
Need fast title/artist/album/genre search.

## Decision
SQLite FTS5 virtual table `tracks_fts`; sync on catalog upsert; `GET /api/search?q=`; library search box filters results.

## Changes
- `app/db.py` — FTS schema + rebuild/sync helpers
- `app/catalog.py` — sync on upsert
- `app/routers/search.py`
- UI search input

## Worked
Prefix token search returns matching tracks.

## Failed / blocked
—

## Next
Scheduled Disk scan (027).

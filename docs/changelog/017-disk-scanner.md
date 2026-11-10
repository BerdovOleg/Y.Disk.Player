# 017 — Disk scanner → SQLite catalog

**Date:** 2026-11-08

## Context
Files already on Disk under `DISK_ROOT` (`/Music`) were never indexed; MVP B originally deferred the scanner.

## Decision
Recursive list via Disk API; download only new/changed audio for mutagen tags; upsert albums/tracks; mark unseen paths `available=0`. Expose `POST /api/library/scan` + library UI button.

## Changes
- `app/disk/client.py` — `iter_files`, `download_to_path`
- `app/disk/scanner.py`, `app/catalog.py`
- `app/db.py` — `tracks.available` + migration
- `app/routers/library.py` — scan endpoint; upload uses shared upsert
- UI: «Сканировать Диск», unavailable styling

## Worked
Scanner + API + UI implemented; shared catalog helper.

## Failed / blocked
Live scan blocked until Disk token has scopes (same as 016 re-login).

## Next
Real libtorrent downloads (018).

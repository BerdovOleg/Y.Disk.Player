# 007 — Upload to Disk + mutagen

## Context
Users add one audio file at a time into `/Music/{Artist}/{Year} - {Album}/` and catalog it in SQLite.

## Decision
`POST /api/upload` writes temp file, reads tags with mutagen, uploads via Disk API href, upserts album/track rows. Path segments sanitized.

## Changes
- `app/audio_meta.py`, `app/disk/client.py`, `app/routers/library.py`
- UI upload control on library view

## Worked
Upload path and catalog wiring in place; Disk client uses httpx async.

## Failed / blocked
End-to-end Disk upload needs a valid OAuth token (not available in stub mode).

## Next
Range stream proxy + vanilla player (008).

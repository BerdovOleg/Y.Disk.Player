# 010 — Torrent import worker

## Context
Magnet/.torrent → file list → legal confirm → download selected → upload audio to Disk. No tracker search.

## Decision
`import_jobs` table + background worker. If libtorrent missing, return stub file list so UI/confirm flow is testable; download requires real libtorrent.

## Changes
- `app/torrent/worker.py`, `app/routers/torrent.py`
- Import UI with magnet, .torrent, file pickers, legal checkbox, job polling

## Worked
Job create/list/confirm API; stub listing when libtorrent absent.

## Failed / blocked
`libtorrent` / `python-libtorrent` not installed on this Mac — real downloads blocked until installed (e.g. brew + bindings).

## Next
Legal sources page + README polish (011).

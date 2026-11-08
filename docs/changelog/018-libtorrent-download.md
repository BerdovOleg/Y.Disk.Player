# 018 — Bind libtorrent; real download → Disk → wipe tmp

**Date:** 2026-11-08

## Context
Torrent path was a stub without libtorrent; downloads always failed after legal confirm.

## Decision
Install Homebrew `libtorrent-rasterbar` (Python 3.15 bindings). Recreate app `.venv` with Homebrew `python@3.15 --system-site-packages`. Worker: DHT session, real list/download after legal confirm, upload audio one-by-one, catalog, `shutil.rmtree` temp job dir. Remove stub file list (hard error if libtorrent missing).

## Changes
- System: `brew install libtorrent-rasterbar`
- `.venv` on Python 3.15 with system site-packages
- `app/torrent/worker.py` rewrite; README / `requirements.txt` notes
- Legal confirm flow unchanged (still required)

## Worked
`import libtorrent` → 2.1.2.0 in app venv; `/api/health` can report available.

## Failed / blocked
Full magnet download not smoke-tested with a real torrent (needs network peers + Disk write scopes). Listing/download path ready once OAuth Disk write works.

## Next
User: enable Disk scopes on OAuth app → `/auth/login` → scan → play; optional magnet with legal confirm.

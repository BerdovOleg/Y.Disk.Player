# 022 — Torrent upload keeps folder layout

**Date:** 2026-11-08

## Context
Torrent import flattened files to `Artist / Year - Album / filename`, discarding torrent relative paths.

## Decision
Upload each selected file to `DISK_ROOT / <torrent-relative-path>` (sanitized segments). Catalog album `disk_path` follows the track’s parent folder.

## Changes
- `app/disk/client.py` — `disk_path_preserve_rel`
- `app/torrent/worker.py` — use preserve helper
- `app/catalog.py` — album path from remote parent

## Worked
Relative album trees under `/Music/...` preserved.

## Failed / blocked
—

## Next
Filename artist/title fallback (023).

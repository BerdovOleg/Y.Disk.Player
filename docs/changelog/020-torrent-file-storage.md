# 020 — Torrent list crash: file_storage not iterable

**Date:** 2026-11-08

## Context
Import listing failed with `'file_storage' object is not iterable` under libtorrent 2.x — code did `for i, f in enumerate(ti.files())`.

## Decision
Use index API: `fs = ti.files()` then `for i in range(fs.num_files())` with `fs.file_path(i)` / `fs.file_size(i)`. Same for download completion size checks.

## Changes
- `app/torrent/worker.py` — `_iter_torrent_files`, `_file_size`; list + download paths
- `docs/changelog/020-torrent-file-storage.md`

## Worked
In-process list of a local smoke `.torrent` returns file entries without TypeError.

## Failed / blocked
Live magnet metadata still depends on network/DHT peers.

## Next
User: re-try magnet/.torrent → file list → legal confirm.

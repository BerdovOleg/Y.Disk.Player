# 023 — Filename fallback for missing artist/title

**Date:** 2026-11-08

## Context
Untagged files became «Unknown Artist» / stem-only titles.

## Decision
If mutagen has no artist/title, parse filename stem: before first ` - ` → artist, after → title (trim). Shared in `read_tags` so upload, Disk scan, and torrent import all get it. Genre still defaults to «Без жанра».

## Changes
- `app/audio_meta.py` — `parse_filename_artist_title`, genre + fallbacks

## Worked
Unit checks: `Artist - Title.mp3` → artist/title; no separator → Unknown Artist + stem.

## Failed / blocked
—

## Next
User: scan Disk to refresh genre/filename metadata on existing files.

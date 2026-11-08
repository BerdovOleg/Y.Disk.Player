# 024 — Magnet add: no add_magnet_uri on libtorrent 2.x

**Date:** 2026-11-08

## Context
Magnet import crashed: `AttributeError: module 'libtorrent' has no attribute 'add_magnet_uri'`.

## Decision
Use `lt.parse_magnet_uri(magnet)` → set `save_path`/`flags` → `ses.add_torrent(atp)`. `.torrent` files still use `ses.add_torrent({ti, save_path})`. (This build has neither `add_magnet_uri` nor `add_torrent_params.url`.)

## Changes
- `app/torrent/worker.py` — `_add_job_torrent` for list + download

## Worked
`parse_magnet_uri` + `add_torrent` succeeds; `.torrent` list path unchanged.

## Failed / blocked
—

## Next
User: retry magnet → file list.

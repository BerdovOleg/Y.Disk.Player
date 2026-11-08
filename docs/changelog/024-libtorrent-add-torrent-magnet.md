# 024 — Magnet add: no add_magnet_uri on libtorrent 2.x

**Date:** 2026-11-08

## Context
Magnet import crashed: `AttributeError: module 'libtorrent' has no attribute 'add_magnet_uri'`.

## Decision
Use `ses.add_torrent({..., 'url': magnet})` (and `ti` for `.torrent` files) via `_add_job_torrent`.

## Changes
- `app/torrent/worker.py` — list + download paths

## Worked
Import path no longer references removed `add_magnet_uri`.

## Failed / blocked
—

## Next
User: retry magnet → file list.

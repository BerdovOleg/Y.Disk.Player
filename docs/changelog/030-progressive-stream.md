# 030 — Progressive / early-play Range streaming

**Date:** 2026-11-09

## Context
Playback waited on cold cache path behavior that felt slow; need first-byte ASAP while still filling hot cache.

## Decision
On cache MISS: Range-proxy Disk immediately (no wait for full fill). Full-body responses tee into hot cache while streaming; Range seeks passthrough only. Cache HIT still `FileResponse` with Accept-Ranges. `STREAM_EARLY_BYTES` (default 512 KiB) marks progressive early-play readiness.

## Changes
- `app/routers/stream.py` — progressive tee + Range passthrough; `X-OMT-Progressive` / `X-OMT-Early-Bytes`
- `app/config.py` — `STREAM_EARLY_BYTES`

## Worked
Seek/Range preserved; next play can HIT after background promote.

## Failed / blocked
—

## Next
Tune `STREAM_EARLY_BYTES` on slow links if needed.

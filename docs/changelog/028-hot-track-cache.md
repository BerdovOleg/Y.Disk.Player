# 028 — Hot track stream cache

**Date:** 2026-11-08

## Context
Repeated Disk streaming is slow / rate-limited.

## Decision
Local cache dir (`TRACK_CACHE_DIR`) with TTL 24h and LRU size cap (`TRACK_CACHE_MAX_BYTES`). `/api/stream/{id}` serves cache on HIT (`X-OMT-Cache: HIT`); on MISS proxies Disk and populates cache in background. `GET /api/cache/status`.

## Changes
- `app/hot_cache.py`, `app/routers/stream.py`, `app/config.py`, `.env.example`, `.gitignore`

## Worked
Cache miss header + status stats in `/api/health`.

## Failed / blocked
—

## Next
—

# 027 — Scheduled Disk scan

**Date:** 2026-11-08

## Context
Library drifts from Disk without periodic rescan.

## Decision
Asyncio loop (default every 6h via `DISK_SCAN_INTERVAL_HOURS`; `0` disables). Persists `scan_state` per user. Manual scan updates the same status. UI shows last-scan banner. `GET /api/library/scan/status`.

## Changes
- `app/scan_scheduler.py`, `app/config.py`, `app/routers/library.py`, `app/main.py`
- `.env.example`, library UI banner

## Worked
Status endpoint + scheduler start on lifespan.

## Failed / blocked
Live scheduled scan still needs Disk-scoped OAuth token.

## Next
Hot track cache (028).

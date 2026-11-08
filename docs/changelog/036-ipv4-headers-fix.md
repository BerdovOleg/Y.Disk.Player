# 036 — MutableHeaders.pop + Disk IPv4 downloads

**Date:** 2026-11-09

## Context
1. `SecurityMiddleware` called `response.headers.pop(...)` — Starlette `MutableHeaders` has no `pop`, breaking responses.
2. Disk scan downloads failed with `file IO failure: LRC groups are unavailable in the local route table` (typical broken IPv6 path on macOS).

## Decision
- Delete `X-Powered-By` via `del` + `KeyError`.
- Prefer IPv4 for httpx via `AsyncHTTPTransport(local_address="0.0.0.0")` (`app/http_util.async_client`); retry Disk download/stream once on network IO failure.

## Changes
- `app/security.py`
- `app/http_util.py` (new)
- `app/disk/client.py`, `app/routers/stream.py`, `app/routers/auth.py`

## Worked
—

## Failed / blocked
—

## Next
Re-run Disk scan after uvicorn restart.

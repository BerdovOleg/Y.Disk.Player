# 031 — Multi-user family isolation

**Date:** 2026-11-09

## Context
One shared host for family; each Yandex login must keep its own Disk token, library, playlists, favorites, history, and cache.

## Decision
Session cookie binds `user_id`; all catalog/API queries already scoped by `user_id`. Cache paths `u{user_id}_t{track_id}`. Add `/auth/switch` (logout → fresh Yandex login) and UI «Сменить». Secure session cookies; no OAuth token in client JS or `/auth/status`.

## Changes
- `app/session.py` — Secure / HttpOnly / SameSite from config
- `app/routers/auth.py` — `/auth/switch`; safer OAuth state cookie; no token bodies in errors
- `static/index.html` / `app.js` — switch account control

## Worked
Separate Yandex accounts → separate rows + cache namespace; logout clears cookie.

## Failed / blocked
—

## Next
Each family member: Войти / Сменить with their own Yandex ID.

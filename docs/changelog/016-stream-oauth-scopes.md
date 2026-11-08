# 016 — Stream broken: Disk OAuth scopes + proxy harden

**Date:** 2026-11-08

## Context
Playback failed against a real Yandex user: Disk API returned **403 Forbidden** (“недостаточно прав”). Token existed but lacked Disk scopes; `/auth/login` did not request them.

## Decision
Request `login:info cloud_api:disk.read cloud_api:disk.write cloud_api:disk.info` on authorize (`YANDEX_OAUTH_SCOPES`). Surface `disk_ok` / re-login hint on `/auth/status`. Harden `/api/stream/{id}` (403 messaging, mime normalize `audio/mp3`→`audio/mpeg`, unavailable tracks → 410).

## Changes
- `app/config.py`, `app/routers/auth.py`, `app/routers/stream.py`, `app/disk/client.py`
- UI banner + player stream error hint (`static/js/app.js`, `player.js`, `index.html`)
- `.env.example`, README note: enable scopes on oauth.yandex.ru app, then re-login

## Worked
Diagnosed live Disk 403 without printing secrets; scopes wired; stream path clearer.

## Failed / blocked
End-to-end playback still needs **user re-login** after scopes are enabled on the OAuth app. Cannot complete browser OAuth from this agent alone.

## Next
Disk recursive scanner (017).

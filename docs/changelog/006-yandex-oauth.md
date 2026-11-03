# 006 — Yandex OAuth + Fernet + session

## Context
Disk access requires a Yandex token kept server-side; browser only gets an app session cookie.

## Decision
OAuth code flow via `/auth/login` → Yandex → `/auth/callback`. Encrypt access token with Fernet. Sign session cookie with itsdangerous. If `YANDEX_*` unset and `ALLOW_DEV_AUTH=1`, offer `/auth/dev-login` stub user.

## Changes
- `app/routers/auth.py`, `app/session.py`, `app/crypto_util.py`, `app/deps.py`
- Auth status endpoint for the UI

## Worked
Dev login creates local user with stub encrypted token; real OAuth path ready when env set.

## Failed / blocked
No real `YANDEX_CLIENT_ID/SECRET` on machine — production OAuth untested against Yandex.

## Next
Manual audio upload to Disk + mutagen catalog (007).

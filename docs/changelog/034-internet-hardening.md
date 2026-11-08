# 034 — Internet hardening (minimum)

**Date:** 2026-11-09

## Context
Public host needs cookie hardening, CSRF/Origin checks, auth rate limits, no client tokens, prod disables dev auth, optional IP allowlist, security headers, never log OAuth tokens.

## Decision
`SecurityMiddleware`: IP allowlist, auth rate limit, Origin check on mutating `/api`/`/auth`, security headers (+ HSTS in prod). `ENVIRONMENT=production` forces `ALLOW_DEV_AUTH=False`, `COOKIE_SECURE` default on. Session + OAuth state cookies HttpOnly/Secure/SameSite. Token exchange errors omit bodies.

## Changes
- `app/security.py`, wired in `app/main.py`
- `app/config.py` — prod / cookie / TRUSTED_ORIGINS / IP_ALLOWLIST / AUTH_RATE_LIMIT
- `app/session.py`, `app/routers/auth.py`

## Worked
Mutating cross-origin blocked; status never returns Disk token.

## Failed / blocked
—

## Next
Set `TRUSTED_ORIGINS`, `COOKIE_SECURE=1`, strong `SESSION_SECRET`/`FERNET_KEY` on VPS.

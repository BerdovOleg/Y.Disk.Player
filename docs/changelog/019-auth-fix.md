# 019 — Auth broken: invalid_scope after Disk scopes

**Date:** 2026-11-08

## Context
After 016 added `scope=login:info cloud_api:disk.*` to `/auth/login`, Yandex redirected to `/auth/callback?error=invalid_scope` (“Запрашиваемые доступы отсутствуют у данного приложения”). Login never issued a code.

## Decision
Omit `scope` from authorize unless `YANDEX_OAUTH_SCOPES` is non-empty. Default scopes empty — rely on permissions configured on the OAuth app. Surface Yandex `error` / `error_description` on callback instead of a bare “Missing code”. Cleared scopes in local `.env`.

## Changes
- `app/config.py`, `app/routers/auth.py`, `.env.example`, README
- `docs/changelog/019-auth-fix.md`

## Worked
Login 302 no longer sends `scope`; callback returns clear message on `invalid_scope`; fake-code exchange still 400 (not 500).

## Failed / blocked
Full browser login still needs Disk permissions enabled as **defaults** on oauth.yandex.ru for Disk API to work after login.

## Next
User: enable Disk defaults on OAuth app → Войти → scan / play.

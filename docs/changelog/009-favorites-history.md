# 009 — Favorites + history

## Context
MVP B requires per-user favorites and play history.

## Decision
SQLite `favorites` PK (user, track); `history` append-only with position. API + UI tabs; player records history on play start.

## Changes
- `app/routers/favorites.py`, `app/routers/history.py`
- Favorites/history views in `static/js/app.js`

## Worked
CRUD favorites and history insert/list against local SQLite.

## Failed / blocked
None for local/dev auth path.

## Next
Torrent worker + legal confirm (010).

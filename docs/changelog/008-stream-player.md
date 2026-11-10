# 008 — Range stream + player

## Context
Playback must stream from Disk through the app with HTTP Range / 206 support.

## Decision
`GET /api/stream/{track_id}` resolves Disk download href and proxies bytes (Range forwarded). Client player: play/pause, seek, rate, repeat, shuffle, queue.

## Changes
- `app/routers/stream.py`
- `static/js/player.js`, wired from `static/js/app.js`

## Worked
Proxy and player controls implemented; stub mode returns clear 503 without Disk.

## Failed / blocked
Live Range streaming unverified without real Disk files.

## Next
Favorites + history (009).

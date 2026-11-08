# 029 — UI redesign: Nordic daylight listening desk

**Date:** 2026-11-08

## Context
Post-feature shell still used dark neon-green look (glow, dark default). Brief: brand hero, expressive type, atmosphere, avoid AI cliché palettes / glow / pills; keep all features; mobile+desktop; 2–3 motions.

## Decision
**Visual direction:** Nordic daylight listening desk — linen field, slate ink, teal signal; light color-scheme; Syne + Figtree; diagonal grain + soft washes (no glow). Oversized `OneMoreTime` brand block; underline nav; sticky player rise.

## Changes
- `static/css/app.css` — full token + layout rewrite
- `static/index.html`, `static/legal.html` — shell, fonts, atmosphere
- Motions: brand rise, view enter, player slide-up (+ subtle track hover)

## Worked
Feature IDs/JS hooks preserved; responsive shell grid collapses cleanly.

## Failed / blocked
—

## Next
User: hard-refresh `http://127.0.0.1:8000`.

# 011 — Legal sources + README polish

## Context
MVP B ships a Legal sources page with disclaimer and a usable README.

## Decision
Static `/legal` page listing purchase/CC sources and torrent-use disclaimer. README documents quick start, env, scope, and blockers.

## Changes
- `static/legal.html`, route `/legal`
- Polished `README.md`

## Worked
Page served; disclaimer and no-tracker-search stance clear.

## Failed / blocked
Push/PR depends on git credentials; `gh` CLI absent on PATH.

## Next
Commit `feat/mvp-b`, push, open PR manually if needed.

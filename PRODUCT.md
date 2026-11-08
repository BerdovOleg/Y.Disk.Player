# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing codebase: FastAPI backend + vanilla static frontend (`static/` HTML/CSS/JS). SQLite catalog; Yandex Disk for audio storage. No redesign of this stack under this product record.

## Users

Several family members, each with their own Yandex account. Each person uses their own Disk and library. They open the same web app (phone or desktop) to listen, browse, and manage their music without sharing another member’s catalog.

## Product Purpose

OneMoreTime is a personal / family music library on Yandex Disk: authenticate with Yandex, keep a local catalog of the user’s Disk music, and play it in the browser. Success means music plays reliably and the UI does not annoy — listening stays out of the way.

## Positioning

Music stays on each user’s Yandex Disk; the app is the player and catalog for that Disk, not a shared streaming service or a communal family library. Multi-user isolation is by Yandex login (session-bound `user_id`), not by shared tracklists.

## Operating Context

- Sign in / switch / sign out with Yandex OAuth (or local dev stub when explicitly enabled).
- Browse library in nested views (genre → artist → album → track, or shorter trees).
- Search (FTS), playlists, favorites, history.
- Upload audio to Disk; optional torrent import with legal confirmation.
- Progressive Range streaming with hot cache; scheduled Disk scan.
- Phone access is equal to desktop: same responsive web app, not a separate native client.
- Public hosting / domain: undecided (no production host chosen yet). Deploy and security docs exist for when a VPS is chosen.

## Capabilities and Constraints

Confirmed capabilities:

- Yandex OAuth + Disk token (encrypted at rest); Disk API for upload, scan, download hrefs
- Library tree view modes with per-user preference persistence
- Playlists, favorites, history
- FTS5 search (title / artist / album / genre)
- Progressive stream (`/api/stream/{id}`) with Range seek and per-user hot cache
- Multi-user isolation: library, playlists, favorites, history, cache, Disk token scoped by `user_id`
- Torrent import (magnet / `.torrent`) with legal confirm before download → Disk
- Deploy samples (Docker / compose / nginx / systemd) and internet hardening (secure cookies, Origin checks, auth rate limit, optional IP allowlist; `ALLOW_DEV_AUTH` off in production)

Constraints / open facts:

- Hosting domain and server: undecided — do not invent a public URL or cloud vendor.
- Disk OAuth scopes must be enabled on the Yandex OAuth app; invalid scopes break login.
- Dev stub login has no real Disk access.
- No tracker search; torrent path is import-only with legal acknowledgment.
- Visual design system is not part of this product record (no DESIGN.md invented here).

## Brand Commitments

Product name: **OneMoreTime**. No other binding brand assets, voice guide, or identity system were confirmed for this record.

## Evidence on Hand

- Runnable app under `app/` and `static/`
- Legal page: `static/legal.html`
- Step changelogs: `docs/changelog/` (through family / deploy / security epics)
- Deploy notes: `README.md`, `Dockerfile`, `docker-compose.yml`, `deploy/`
- Do not fabricate testimonials, customer quotes, benchmarks, pricing, or a live public URL.

## Product Principles

1. Play first — starting and continuing playback beats chrome and ceremony.
2. Stay out of the way — the UI must not annoy; prefer calm, clear controls over novelty.
3. One login, one library — family members never see or mutate each other’s music.
4. Disk is source of truth — catalog and cache serve the user’s Disk; re-scan keeps them honest.
5. Phone equals desktop — responsive web is the product surface; no second-class mobile path.

## Accessibility & Inclusion

Phone and desktop are first-class on the same responsive web UI. No additional accessibility standard (e.g. a specific WCAG level) was confirmed beyond usable responsive access.

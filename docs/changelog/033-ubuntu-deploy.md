# 033 — Ubuntu deploy (Docker / nginx)

**Date:** 2026-11-09

## Context
Run on a public VPS for phone + desktop; TLS at the edge.

## Decision
Ship `Dockerfile` + `docker-compose.yml` (data volume), sample `deploy/nginx.conf` (HTTPS + Range streaming), optional `deploy/onemoretime.service`, README deploy section.

## Changes
- `Dockerfile`, `docker-compose.yml`
- `deploy/nginx.conf`, `deploy/onemoretime.service`
- `README.md` — Deploy on Ubuntu
- `.env.example` — production vars

## Worked
Compose exposes app to host nginx; certbot notes in nginx sample.

## Failed / blocked
—

## Next
Point DNS + OAuth redirect at the public HTTPS origin.

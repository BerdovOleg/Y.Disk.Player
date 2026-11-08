# OneMoreTime

Personal / family music library on **Yandex Disk**: upload audio, optional torrent import (with legal confirm), SQLite catalog, progressive Range streaming, Disk scan, favorites, history, playlists, FTS5, hot cache.

Each Yandex login is an isolated user (own Disk token, library, playlists, favorites, history, cache).

## Stack

- Python 3.12+ (macOS: Homebrew Python 3.15 + `libtorrent` for torrents)
- FastAPI, SQLite WAL, mutagen, cryptography (Fernet), httpx
- Vanilla JS player served as static files
- Optional Docker + nginx for Ubuntu VPS

## Quick start

```bash
cd /Users/olegberdov/OneMoreTime
# macOS + torrents:
brew install libtorrent-rasterbar
"$(brew --prefix python@3.15)/bin/python3.15" -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set FERNET_KEY, SESSION_SECRET, YANDEX_CLIENT_ID/SECRET
# Generate Fernet: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. On the [Yandex OAuth](https://oauth.yandex.ru/) app, enable **default** Disk permissions (`cloud_api:disk.read`, `cloud_api:disk.write`, `cloud_api:disk.info`), keep `YANDEX_OAUTH_SCOPES` empty, then **Войти**. Do not put scopes in the authorize URL unless those exact scopes are enabled on the app — otherwise Yandex returns `invalid_scope`.

## Family accounts

1. Each person uses **Войти** with their own Yandex ID (or **Сменить** to switch).
2. Session cookie (`omt_session`) binds `user_id` — libraries are never shared.
3. Disk token is stored encrypted server-side (`FERNET_KEY`); never exposed to browser JS.
4. Hot cache files are namespaced `u{user_id}_t{track_id}`.
5. Library view mode (genre / artist / album) is stored per user (`user_preferences`).

## Environment

See `.env.example`. Important keys:

| Variable | Purpose |
|----------|---------|
| `ENVIRONMENT` | `development` / `production` (prod forces `ALLOW_DEV_AUTH=0`) |
| `YANDEX_CLIENT_ID` / `YANDEX_CLIENT_SECRET` | Yandex OAuth app |
| `OAUTH_REDIRECT_URI` | Must match the public HTTPS callback in prod |
| `FERNET_KEY` | Encrypt Disk tokens at rest |
| `SESSION_SECRET` | Sign session cookie |
| `COOKIE_SECURE` / `COOKIE_SAMESITE` | HTTPS-only cookies in prod |
| `TRUSTED_ORIGINS` | Allowed Origins for mutating requests |
| `IP_ALLOWLIST` | Optional comma-separated IPs/CIDRs |
| `AUTH_RATE_LIMIT_PER_MIN` | Auth endpoint throttle (default 20) |
| `DISK_ROOT` | Library root on Disk (`/Music`) |
| `STREAM_EARLY_BYTES` | Progressive early-play marker (default 512 KiB) |
| `ALLOW_DEV_AUTH` | Local stub only; disabled in production |

## Features

1. Yandex ID login / logout / switch account
2. Upload audio → `/Music/{Artist}/{Year} - {Album}/` + mutagen tags
3. **Scan Disk** + scheduled rescan
4. Progressive stream `/api/stream/{id}` (Range / early play / hot cache)
5. Player: play/pause, seek, rate, repeat, shuffle, queue
6. Favorites, history, playlists, FTS5 search
7. Library view modes: Genre→Artist→Album | Artist→Album | Album→Track
8. Torrent import with legal confirm
9. [Legal sources](/legal) + disclaimer

## Deploy on Ubuntu (VPS)

Phone and desktop both hit the same HTTPS origin.

### 1. DNS + OAuth

- Point `music.example.com` A/AAAA to the VPS.
- In [Yandex OAuth](https://oauth.yandex.ru/), set callback to  
  `https://music.example.com/auth/callback`.
- Generate secrets on the server:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
openssl rand -hex 32
```

### 2. Docker Compose (recommended)

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx
git clone <your-fork> /opt/onemoretime && cd /opt/onemoretime
cp .env.example .env
# edit .env — see production checklist below
sudo docker compose up -d --build
# publish app to localhost only, e.g. add to compose temporarily:
# ports: ["127.0.0.1:8000:8000"]
```

Production `.env` checklist:

```env
ENVIRONMENT=production
ALLOW_DEV_AUTH=0
COOKIE_SECURE=1
COOKIE_SAMESITE=lax
OAUTH_REDIRECT_URI=https://music.example.com/auth/callback
TRUSTED_ORIGINS=https://music.example.com
FERNET_KEY=...
SESSION_SECRET=...
# Optional family lock-down:
# IP_ALLOWLIST=203.0.113.10,198.51.100.0/24
```

### 3. nginx + TLS

Copy [`deploy/nginx.conf`](deploy/nginx.conf), replace `music.example.com`, enable the site, then:

```bash
sudo certbot --nginx -d music.example.com
sudo nginx -t && sudo systemctl reload nginx
```

`proxy_buffering off` keeps Range streaming snappy for mobile players.

### 4. systemd alternative (no Docker)

See [`deploy/onemoretime.service`](deploy/onemoretime.service): venv under `/opt/onemoretime`, bind `127.0.0.1:8000`, nginx in front.

### 5. Hardening (shipped)

- Session + OAuth state: `HttpOnly`, `Secure` (prod), `SameSite=Lax`
- Origin check on mutating `/api` and `/auth`
- Auth rate limit; optional `IP_ALLOWLIST`
- Security headers + HSTS in production
- OAuth tokens never logged or returned to the client

## libtorrent

On macOS: `brew install libtorrent-rasterbar` and a Homebrew Python venv with `--system-site-packages`. `/api/health` reports `libtorrent.available`. Without bindings, import jobs fail clearly (no stub download).

## Changelog

Step logs: [`docs/changelog/`](docs/changelog/).

# OneMoreTime

Personal music library on **Yandex Disk**: upload audio, optional torrent import (with legal confirm), SQLite catalog, Range streaming, Disk scan, favorites, history.

MVP slice **B** — no tracker search, playlists, FTS5, or hot cache.

## Stack

- Python 3.15 recommended on macOS (Homebrew) so brew `libtorrent` bindings import
- FastAPI, SQLite WAL, mutagen, cryptography (Fernet), httpx
- Vanilla JS player served as static files

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

Open http://127.0.0.1:8000. Enable Disk scopes on the [Yandex OAuth](https://oauth.yandex.ru/) app (`cloud_api:disk.read`, `cloud_api:disk.write`, `cloud_api:disk.info`), then **Войти** (re-login after scope changes).

## Environment

See `.env.example`:

| Variable | Purpose |
|----------|---------|
| `YANDEX_CLIENT_ID` / `YANDEX_CLIENT_SECRET` | Yandex OAuth app |
| `YANDEX_OAUTH_SCOPES` | Default includes Disk read/write + login:info |
| `OAUTH_REDIRECT_URI` | Default `http://127.0.0.1:8000/auth/callback` |
| `FERNET_KEY` | Encrypt Disk tokens at rest |
| `SESSION_SECRET` | Sign session cookie |
| `DISK_ROOT` | Library root on Disk (`/Music`) |
| `ALLOW_DEV_AUTH` | Local stub login when OAuth unset |

## Features (MVP B)

1. Yandex ID login (or dev stub)
2. Upload one audio file → `/Music/{Artist}/{Year} - {Album}/` + mutagen tags
3. **Scan Disk** (`POST /api/library/scan`) — recurse `DISK_ROOT`, upsert tags, mark missing unavailable
4. Stream via `/api/stream/{id}` (Range / 206 proxy)
5. Player: play/pause, seek, rate, repeat, shuffle, queue
6. Favorites + history
7. Torrent: magnet/.torrent → file list → legal confirm → libtorrent → Disk → wipe tmp
8. [Legal sources](/legal) + disclaimer

## libtorrent

On macOS: `brew install libtorrent-rasterbar` and a Homebrew Python 3.15 venv with `--system-site-packages`. `/api/health` reports `libtorrent.available`. Without bindings, import jobs fail clearly (no stub download).

## Changelog

Step logs: [`docs/changelog/`](docs/changelog/).

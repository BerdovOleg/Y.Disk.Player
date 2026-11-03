# OneMoreTime

Personal music library on **Yandex Disk**: upload audio, optional torrent import (with legal confirm), SQLite catalog, Range streaming, favorites, history.

MVP slice **B** — no tracker search, playlists, FTS5, disk scanner, or hot cache.

## Stack

- Python 3.11+ (developed on 3.14), FastAPI, SQLite WAL
- mutagen, cryptography (Fernet), httpx, optional libtorrent
- Vanilla JS player served as static files

## Quick start

```bash
cd /Users/olegberdov/OneMoreTime
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set FERNET_KEY, SESSION_SECRET; optionally YANDEX_CLIENT_ID/SECRET
# Generate Fernet: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 — with empty Yandex OAuth and `ALLOW_DEV_AUTH=1`, use **Dev-вход**.

## Environment

See `.env.example`:

| Variable | Purpose |
|----------|---------|
| `YANDEX_CLIENT_ID` / `YANDEX_CLIENT_SECRET` | Yandex OAuth app |
| `OAUTH_REDIRECT_URI` | Default `http://127.0.0.1:8000/auth/callback` |
| `FERNET_KEY` | Encrypt Disk tokens at rest |
| `SESSION_SECRET` | Sign session cookie |
| `DISK_ROOT` | Library root on Disk (`/Music`) |
| `ALLOW_DEV_AUTH` | Local stub login when OAuth unset |

Register the redirect URI in [Yandex OAuth](https://oauth.yandex.ru/).

## Features (MVP B)

1. Yandex ID login (or dev stub)
2. Upload one audio file → `/Music/{Artist}/{Year} - {Album}/` + mutagen tags
3. Stream via `/api/stream/{id}` (Range / 206 proxy)
4. Player: play/pause, seek, rate, repeat, shuffle, queue
5. Favorites + history
6. Torrent: magnet/.torrent → file list → legal confirm → libtorrent → Disk
7. [Legal sources](/legal) + disclaimer

## libtorrent

Real torrent downloads need libtorrent Python bindings. Without them the import UI still lists a **stub** file list so the confirm flow can be exercised; download returns an error until libtorrent is installed.

## Changelog

Step logs: [`docs/changelog/`](docs/changelog/).

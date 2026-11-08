from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower() or "development"
IS_PROD = ENVIRONMENT in {"production", "prod"}

YANDEX_CLIENT_ID = os.getenv("YANDEX_CLIENT_ID", "").strip()
YANDEX_CLIENT_SECRET = os.getenv("YANDEX_CLIENT_SECRET", "").strip()
OAUTH_REDIRECT_URI = os.getenv(
    "OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback"
).strip()
FERNET_KEY = os.getenv("FERNET_KEY", "").strip()
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-insecure-session-secret").strip()
DISK_ROOT = os.getenv("DISK_ROOT", "/Music").rstrip("/") or "/Music"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "onemoretime.db")))

# Dev login: forced off in production
_allow_dev_raw = os.getenv("ALLOW_DEV_AUTH")
if IS_PROD:
    ALLOW_DEV_AUTH = False
elif _allow_dev_raw is None:
    ALLOW_DEV_AUTH = not bool(YANDEX_CLIENT_ID)
else:
    ALLOW_DEV_AUTH = _bool("ALLOW_DEV_AUTH", default=False)

TORRENT_DOWNLOAD_DIR = Path(
    os.getenv("TORRENT_DOWNLOAD_DIR", str(ROOT / "data" / "torrents"))
)
DISK_SCAN_INTERVAL_HOURS = float(os.getenv("DISK_SCAN_INTERVAL_HOURS", "6") or "6")
TRACK_CACHE_DIR = Path(
    os.getenv("TRACK_CACHE_DIR", str(ROOT / "data" / "cache" / "tracks"))
)
TRACK_CACHE_TTL_HOURS = float(os.getenv("TRACK_CACHE_TTL_HOURS", "24") or "24")
TRACK_CACHE_MAX_BYTES = _int("TRACK_CACHE_MAX_BYTES", 2 * 1024 * 1024 * 1024)
# Start playing while background cache continues (bytes)
STREAM_EARLY_BYTES = _int("STREAM_EARLY_BYTES", 512 * 1024)

STATIC_DIR = ROOT / "static"
COOKIE_NAME = "omt_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
COOKIE_SECURE = _bool("COOKIE_SECURE", default=IS_PROD)
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower() or "lax"
TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "TRUSTED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if o.strip()
]
# Comma-separated IPs/CIDRs; empty = allow all
IP_ALLOWLIST = [
    x.strip() for x in os.getenv("IP_ALLOWLIST", "").split(",") if x.strip()
]
AUTH_RATE_LIMIT_PER_MIN = _int("AUTH_RATE_LIMIT_PER_MIN", 20)

YANDEX_AUTH_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_LOGIN_URL = "https://login.yandex.ru/info"
YANDEX_DISK_API = "https://cloud-api.yandex.net/v1/disk"

YANDEX_OAUTH_SCOPES = os.getenv("YANDEX_OAUTH_SCOPES", "").strip()


def oauth_configured() -> bool:
    return bool(YANDEX_CLIENT_ID and YANDEX_CLIENT_SECRET)

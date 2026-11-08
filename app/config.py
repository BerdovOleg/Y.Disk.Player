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


YANDEX_CLIENT_ID = os.getenv("YANDEX_CLIENT_ID", "").strip()
YANDEX_CLIENT_SECRET = os.getenv("YANDEX_CLIENT_SECRET", "").strip()
OAUTH_REDIRECT_URI = os.getenv(
    "OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback"
).strip()
FERNET_KEY = os.getenv("FERNET_KEY", "").strip()
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-insecure-session-secret").strip()
DISK_ROOT = os.getenv("DISK_ROOT", "/Music").rstrip("/") or "/Music"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "onemoretime.db")))
ALLOW_DEV_AUTH = _bool("ALLOW_DEV_AUTH", default=not bool(YANDEX_CLIENT_ID))
TORRENT_DOWNLOAD_DIR = Path(
    os.getenv("TORRENT_DOWNLOAD_DIR", str(ROOT / "data" / "torrents"))
)
STATIC_DIR = ROOT / "static"
COOKIE_NAME = "omt_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

YANDEX_AUTH_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_LOGIN_URL = "https://login.yandex.ru/info"
YANDEX_DISK_API = "https://cloud-api.yandex.net/v1/disk"

# Disk scopes must also be enabled on the OAuth app at https://oauth.yandex.ru/
YANDEX_OAUTH_SCOPES = os.getenv(
    "YANDEX_OAUTH_SCOPES",
    "login:info cloud_api:disk.read cloud_api:disk.write cloud_api:disk.info",
).strip()


def oauth_configured() -> bool:
    return bool(YANDEX_CLIENT_ID and YANDEX_CLIENT_SECRET)

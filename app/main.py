from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import (
    DISK_SCAN_INTERVAL_HOURS,
    STATIC_DIR,
    TORRENT_DOWNLOAD_DIR,
    TRACK_CACHE_DIR,
)
from app.db import init_db
from app.hot_cache import cache_stats
from app.routers import (
    auth,
    favorites,
    history,
    library,
    playlists,
    search,
    stream,
    torrent,
)
from app.scan_scheduler import start_scheduler, stop_scheduler
from app.torrent.worker import get_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    TORRENT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TRACK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    worker = get_worker()
    worker.attach_loop(asyncio.get_running_loop())
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="OneMoreTime", version=__version__, lifespan=lifespan)

app.include_router(auth.router)
app.include_router(library.router)
app.include_router(search.router)
app.include_router(playlists.router)
app.include_router(stream.router)
app.include_router(favorites.router)
app.include_router(history.router)
app.include_router(torrent.router)


@app.get("/api/health")
def health():
    lt = get_worker().libtorrent_status()
    return {
        "ok": True,
        "version": __version__,
        "libtorrent": lt,
        "disk_scan_interval_hours": DISK_SCAN_INTERVAL_HOURS,
        "cache": cache_stats(),
    }


@app.get("/legal")
def legal_page():
    path = STATIC_DIR / "legal.html"
    return FileResponse(path)


if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

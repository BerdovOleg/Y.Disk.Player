from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import STATIC_DIR, TORRENT_DOWNLOAD_DIR
from app.db import init_db
from app.routers import auth, favorites, history, library, stream, torrent
from app.torrent.worker import get_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    TORRENT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    worker = get_worker()
    worker.attach_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="OneMoreTime", version=__version__, lifespan=lifespan)

app.include_router(auth.router)
app.include_router(library.router)
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
    }


@app.get("/legal")
def legal_page():
    path = STATIC_DIR / "legal.html"
    return FileResponse(path)


if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

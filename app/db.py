from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.config import DATABASE_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    yandex_id TEXT UNIQUE NOT NULL,
    display_name TEXT,
    token_enc TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    artist TEXT NOT NULL DEFAULT 'Unknown Artist',
    title TEXT NOT NULL DEFAULT 'Unknown Album',
    year INTEGER,
    disk_path TEXT,
    cover_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, artist, title, year)
);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    album_id INTEGER REFERENCES albums(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    artist TEXT NOT NULL DEFAULT 'Unknown Artist',
    genre TEXT NOT NULL DEFAULT 'Без жанра',
    duration_sec REAL,
    track_num INTEGER,
    mime TEXT,
    size_bytes INTEGER,
    disk_path TEXT NOT NULL,
    available INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, disk_path)
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, track_id)
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    played_at TEXT NOT NULL DEFAULT (datetime('now')),
    position_sec REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_history_user_played
    ON history(user_id, played_at DESC);

CREATE TABLE IF NOT EXISTS import_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL, -- magnet | torrent_file
    source_ref TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    -- pending | listing | awaiting_confirm | downloading | uploading | done | error | cancelled
    info_hash TEXT,
    file_list_json TEXT,
    selected_json TEXT,
    legal_confirmed INTEGER NOT NULL DEFAULT 0,
    progress REAL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_import_jobs_user
    ON import_jobs(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_playlists_user
    ON playlists(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (playlist_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_playlist_tracks_order
    ON playlist_tracks(playlist_id, position);

CREATE TABLE IF NOT EXISTS scan_state (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    last_started_at TEXT,
    last_finished_at TEXT,
    last_status TEXT,
    last_result_json TEXT,
    last_error TEXT
);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    title,
    artist,
    album,
    genre,
    user_id UNINDEXED,
    tokenize = 'unicode61'
);
"""


def _connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or DATABASE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tracks)").fetchall()}
    if "available" not in cols:
        conn.execute(
            "ALTER TABLE tracks ADD COLUMN available INTEGER NOT NULL DEFAULT 1"
        )
    if "genre" not in cols:
        conn.execute(
            "ALTER TABLE tracks ADD COLUMN genre TEXT NOT NULL DEFAULT 'Без жанра'"
        )


def _ensure_fts(conn: sqlite3.Connection) -> None:
    conn.executescript(FTS_SCHEMA)
    # Rebuild if empty but tracks exist
    fts_count = conn.execute("SELECT COUNT(*) FROM tracks_fts").fetchone()[0]
    track_count = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    if track_count and not fts_count:
        _rebuild_fts(conn)


def _rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM tracks_fts")
    rows = conn.execute(
        """
        SELECT t.id, t.title, t.artist, t.genre, t.user_id,
               COALESCE(a.title, '') AS album
        FROM tracks t
        LEFT JOIN albums a ON a.id = t.album_id
        """
    ).fetchall()
    conn.executemany(
        """
        INSERT INTO tracks_fts(rowid, title, artist, album, genre, user_id)
        VALUES (?,?,?,?,?,?)
        """,
        [
            (r["id"], r["title"], r["artist"], r["album"], r["genre"], r["user_id"])
            for r in rows
        ],
    )


def sync_track_fts(
    conn: sqlite3.Connection,
    track_id: int,
    *,
    title: str,
    artist: str,
    album: str,
    genre: str,
    user_id: int,
) -> None:
    conn.execute("DELETE FROM tracks_fts WHERE rowid=?", (track_id,))
    conn.execute(
        """
        INSERT INTO tracks_fts(rowid, title, artist, album, genre, user_id)
        VALUES (?,?,?,?,?,?)
        """,
        (track_id, title, artist, album or "", genre, user_id),
    )


def delete_track_fts(conn: sqlite3.Connection, track_id: int) -> None:
    conn.execute("DELETE FROM tracks_fts WHERE rowid=?", (track_id,))


def init_db(path: Path | None = None) -> None:
    conn = _connect(path)
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        _ensure_fts(conn)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)

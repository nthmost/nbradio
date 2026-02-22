"""
SQLite database for the KNOB Radio genre index.

Handles schema creation, migrations, and all CRUD operations.
"""

import sqlite3
import os
from contextlib import contextmanager

DEFAULT_DB_PATH = "/media/radio/genre_index.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tracks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    path          TEXT NOT NULL UNIQUE,
    filename      TEXT NOT NULL,
    directory     TEXT NOT NULL,
    filesize      INTEGER NOT NULL,
    mtime         REAL NOT NULL,
    duration      REAL,
    content_type  TEXT NOT NULL DEFAULT 'song',
    genre_parent  TEXT,
    genre_sub     TEXT,
    genre_source  TEXT,
    genre_confidence REAL,
    genre_raw     TEXT,
    artist        TEXT,
    title         TEXT,
    album         TEXT,
    acoustid      TEXT,
    musicbrainz_id TEXT,
    pass1_done    INTEGER NOT NULL DEFAULT 0,
    pass2_done    INTEGER NOT NULL DEFAULT 0,
    pass3_done    INTEGER NOT NULL DEFAULT 0,
    indexed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS classification_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id    INTEGER NOT NULL REFERENCES tracks(id),
    pass_num    INTEGER NOT NULL,
    genre_parent TEXT,
    genre_sub   TEXT,
    confidence  REAL,
    raw_label   TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_tracks_path ON tracks(path);
CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre_parent, genre_sub);
CREATE INDEX IF NOT EXISTS idx_tracks_content_type ON tracks(content_type);
CREATE INDEX IF NOT EXISTS idx_tracks_passes ON tracks(pass1_done, pass2_done, pass3_done);
CREATE INDEX IF NOT EXISTS idx_classification_log_track ON classification_log(track_id);
"""

SCHEMA_VERSION = "1"


class GenreDB:
    """SQLite wrapper for the genre index database."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._conn = None

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield self._conn
        except Exception:
            self._conn.rollback()
            raise

    def init_schema(self):
        """Create tables if they don't exist."""
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)
            # Set schema version
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("schema_version", SCHEMA_VERSION),
            )
            conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Track CRUD ──────────────────────────────────────────────────────

    def upsert_track(self, track_data):
        """Insert or update a track. track_data is a dict with column names as keys.
        Returns the track id."""
        with self.connection() as conn:
            # Check if track exists
            row = conn.execute(
                "SELECT id FROM tracks WHERE path = ?",
                (track_data["path"],),
            ).fetchone()

            if row:
                track_id = row["id"]
                # Update only scan-level fields, preserve classification
                conn.execute(
                    """UPDATE tracks SET
                        filename = ?, directory = ?, filesize = ?, mtime = ?,
                        updated_at = datetime('now')
                    WHERE id = ?""",
                    (
                        track_data["filename"],
                        track_data["directory"],
                        track_data["filesize"],
                        track_data["mtime"],
                        track_id,
                    ),
                )
            else:
                cursor = conn.execute(
                    """INSERT INTO tracks
                        (path, filename, directory, filesize, mtime, content_type)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        track_data["path"],
                        track_data["filename"],
                        track_data["directory"],
                        track_data["filesize"],
                        track_data["mtime"],
                        track_data.get("content_type", "song"),
                    ),
                )
                track_id = cursor.lastrowid
            conn.commit()
            return track_id

    def get_track_by_path(self, path):
        """Get a track by its relative path."""
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM tracks WHERE path = ?", (path,)
            ).fetchone()

    def get_track_by_id(self, track_id):
        """Get a track by its ID."""
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM tracks WHERE id = ?", (track_id,)
            ).fetchone()

    def get_tracks_needing_pass(self, pass_num, content_type="song", limit=None):
        """Get tracks that haven't completed a given pass.
        Only returns tracks of the given content_type (default: songs only)."""
        col = f"pass{pass_num}_done"
        query = f"SELECT * FROM tracks WHERE {col} = 0 AND content_type = ?"
        params = [content_type]
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with self.connection() as conn:
            return conn.execute(query, params).fetchall()

    def update_classification(self, track_id, genre_parent, genre_sub,
                              source, confidence, raw_label, pass_num,
                              extra_fields=None):
        """Update a track's genre classification and log the result."""
        col = f"pass{pass_num}_done"
        with self.connection() as conn:
            updates = {
                "genre_parent": genre_parent,
                "genre_sub": genre_sub,
                "genre_source": source,
                "genre_confidence": confidence,
                "genre_raw": raw_label,
                col: 1,
            }
            if extra_fields:
                updates.update(extra_fields)

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(track_id)

            conn.execute(
                f"UPDATE tracks SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )

            # Log the classification
            conn.execute(
                """INSERT INTO classification_log
                    (track_id, pass_num, genre_parent, genre_sub, confidence, raw_label)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (track_id, pass_num, genre_parent, genre_sub, confidence, raw_label),
            )
            conn.commit()

    def mark_pass_done(self, track_id, pass_num):
        """Mark a pass as complete without changing classification."""
        col = f"pass{pass_num}_done"
        with self.connection() as conn:
            conn.execute(
                f"UPDATE tracks SET {col} = 1, updated_at = datetime('now') WHERE id = ?",
                (track_id,),
            )
            conn.commit()

    def update_track_fields(self, track_id, fields):
        """Update arbitrary fields on a track."""
        if not fields:
            return
        with self.connection() as conn:
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            values = list(fields.values())
            values.append(track_id)
            conn.execute(
                f"UPDATE tracks SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()

    # ── Queries ─────────────────────────────────────────────────────────

    def count_tracks(self, where=None, params=None):
        """Count tracks with optional WHERE clause."""
        query = "SELECT COUNT(*) as cnt FROM tracks"
        if where:
            query += f" WHERE {where}"
        with self.connection() as conn:
            return conn.execute(query, params or []).fetchone()["cnt"]

    def genre_stats(self, group_by="genre_parent"):
        """Get genre distribution stats."""
        with self.connection() as conn:
            return conn.execute(
                f"""SELECT {group_by}, COUNT(*) as cnt
                    FROM tracks
                    WHERE content_type = 'song'
                    GROUP BY {group_by}
                    ORDER BY cnt DESC""",
            ).fetchall()

    def get_tracks_by_genre(self, parent=None, sub=None):
        """Get all tracks matching a genre."""
        conditions = ["content_type = 'song'"]
        params = []
        if parent:
            conditions.append("genre_parent = ?")
            params.append(parent)
        if sub:
            conditions.append("genre_sub = ?")
            params.append(sub)
        where = " AND ".join(conditions)
        with self.connection() as conn:
            return conn.execute(
                f"SELECT * FROM tracks WHERE {where} ORDER BY artist, title",
                params,
            ).fetchall()

    def get_unclassified(self):
        """Get tracks with no genre assignment."""
        with self.connection() as conn:
            return conn.execute(
                """SELECT * FROM tracks
                   WHERE content_type = 'song'
                     AND genre_parent IS NULL
                   ORDER BY directory, filename""",
            ).fetchall()

    def get_all_paths(self):
        """Get set of all tracked paths for change detection."""
        with self.connection() as conn:
            rows = conn.execute("SELECT path FROM tracks").fetchall()
            return {row["path"] for row in rows}

    def remove_track(self, path):
        """Remove a track (file was deleted)."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id FROM tracks WHERE path = ?", (path,)
            ).fetchone()
            if row:
                conn.execute(
                    "DELETE FROM classification_log WHERE track_id = ?",
                    (row["id"],),
                )
                conn.execute("DELETE FROM tracks WHERE id = ?", (row["id"],))
                conn.commit()

    def needs_rescan(self, path, mtime, filesize):
        """Check if a file needs rescanning (changed since last index)."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT mtime, filesize FROM tracks WHERE path = ?", (path,)
            ).fetchone()
            if row is None:
                return True  # new file
            return row["mtime"] != mtime or row["filesize"] != filesize

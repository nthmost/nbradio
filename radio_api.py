#!/usr/bin/env python3
"""KNOB Radio Control API

Zero-dependency HTTP server for genre switching, track queueing, and playback
control. Talks to Liquidsoap via telnet and queries the genre index SQLite DB.

Port 8081 by default.
"""

import argparse
import json
import os
import random
import socket
import sqlite3
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TELNET_HOST = "localhost"
TELNET_PORT = 1234
DB_PATH = "/media/radio/genre_index.db"
MEDIA_ROOT = "/media/radio"

# How many tracks to keep in the Liquidsoap queue when genre feeding
QUEUE_MIN = 2
QUEUE_PUSH = 3  # push this many when topping up
FEEDER_POLL_INTERVAL = 15  # seconds

# ---------------------------------------------------------------------------
# Telnet communication (same pattern as nowplaying.py)
# ---------------------------------------------------------------------------

def telnet_command(cmd, timeout=3):
    """Send a command to Liquidsoap telnet and return the response."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((TELNET_HOST, TELNET_PORT))
        sock.sendall((cmd + "\nquit\n").encode())
        response = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break
        sock.close()
        text = response.decode(errors="replace").strip()
        lines = text.splitlines()
        while lines and lines[-1].strip() in ("END", "Bye!"):
            lines.pop()
        return "\n".join(lines).strip()
    except Exception as e:
        return None


def queue_push(filepath):
    """Push a file to the Liquidsoap request queue. Returns True on success."""
    resp = telnet_command(f"queue.push {filepath}")
    return resp is not None and "error" not in (resp or "").lower()


def queue_list():
    """Get list of pending request IDs in the queue."""
    resp = telnet_command("queue.queue")
    if not resp:
        return []
    # Response is space-separated request IDs
    rids = resp.strip().split()
    return [r for r in rids if r]


def queue_ignore(rid):
    """Remove a pending request from the queue."""
    return telnet_command(f"queue.ignore {rid}")


def skip_track():
    """Skip the currently playing track."""
    return telnet_command("/stream_ogg.skip")


# ---------------------------------------------------------------------------
# Database access (lightweight, no import of genre package needed at runtime)
# ---------------------------------------------------------------------------

def get_db():
    """Get a read-only SQLite connection to the genre index."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def db_genre_stats():
    """Return genre/subgenre tree with track counts."""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT genre_parent, genre_sub, COUNT(*) as cnt
               FROM tracks
               WHERE content_type = 'song' AND genre_parent IS NOT NULL
               GROUP BY genre_parent, genre_sub
               ORDER BY genre_parent, cnt DESC"""
        ).fetchall()
    finally:
        conn.close()

    genres = {}
    for row in rows:
        parent = row["genre_parent"]
        sub = row["genre_sub"]
        cnt = row["cnt"]
        if parent not in genres:
            genres[parent] = {"count": 0, "subgenres": {}}
        genres[parent]["count"] += cnt
        if sub:
            genres[parent]["subgenres"][sub] = cnt
    return genres


def db_get_tracks(parent=None, sub=None):
    """Get tracks matching a genre. Returns list of dicts."""
    conn = get_db()
    try:
        conditions = ["content_type = 'song'"]
        params = []
        if parent:
            conditions.append("genre_parent = ?")
            params.append(parent)
        if sub:
            conditions.append("genre_sub = ?")
            params.append(sub)
        where = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT id, path, artist, title, genre_parent, genre_sub, duration FROM tracks WHERE {where}",
            params,
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def db_get_track_by_id(track_id):
    """Get a single track by ID."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, path, artist, title, genre_parent, genre_sub, duration FROM tracks WHERE id = ?",
            (track_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def db_search_tracks(query, genre=None, limit=20):
    """Search tracks by text (artist, title, filename). Optionally filter by genre."""
    conn = get_db()
    try:
        conditions = ["content_type = 'song'"]
        params = []

        # Text search across artist, title, filename
        search_terms = query.strip().split()
        for term in search_terms:
            conditions.append(
                "(artist LIKE ? OR title LIKE ? OR filename LIKE ?)"
            )
            like = f"%{term}%"
            params.extend([like, like, like])

        if genre:
            conditions.append("genre_parent = ?")
            params.append(genre)

        where = " AND ".join(conditions)
        params.append(limit)
        rows = conn.execute(
            f"""SELECT id, path, artist, title, genre_parent, genre_sub, duration
                FROM tracks WHERE {where}
                ORDER BY artist, title
                LIMIT ?""",
            params,
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def track_filepath(track):
    """Build full filesystem path for a track."""
    return os.path.join(MEDIA_ROOT, track["path"])


# ---------------------------------------------------------------------------
# Genre feeder thread
# ---------------------------------------------------------------------------

class GenreFeeder:
    """Background thread that keeps the Liquidsoap queue fed with genre tracks."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self._genre = None       # current parent genre
        self._subgenre = None    # current subgenre (optional)
        self._tracks = []        # shuffled track list
        self._index = 0          # current position in track list
        self._pushed = []        # tracks we've pushed (for status)

    @property
    def active(self):
        return self._genre is not None

    def status(self):
        with self._lock:
            if not self._genre:
                return None
            return {
                "genre": self._genre,
                "subgenre": self._subgenre,
                "tracks_available": len(self._tracks),
                "tracks_pushed": len(self._pushed),
                "position": self._index,
            }

    def start(self, genre, subgenre=None):
        """Start (or restart) the genre feeder.

        Pushes new genre tracks before clearing old queue entries so
        Liquidsoap always has something queued — avoids interrupting
        the currently playing track.
        """
        # Snapshot old queue entries before we push new ones
        old_queue = queue_list()

        # Stop the feed loop (but don't clear the queue yet)
        self.stop(clear_queue=False)

        tracks = db_get_tracks(parent=genre, sub=subgenre)
        if not tracks:
            return False

        random.shuffle(tracks)

        with self._lock:
            self._genre = genre
            self._subgenre = subgenre
            self._tracks = tracks
            self._index = 0
            self._pushed = []
            self._stop_event.clear()

        # Push new genre tracks first (so queue is never empty)
        self._push_batch(QUEUE_PUSH)

        # Now clear old queue entries that were there before
        for rid in old_queue:
            queue_ignore(rid)

        self._thread = threading.Thread(target=self._feed_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self, clear_queue=True):
        """Stop the feeder and optionally clear queued tracks."""
        if self._thread is not None:
            self._stop_event.set()
            self._thread.join(timeout=5)
            self._thread = None

        with self._lock:
            self._genre = None
            self._subgenre = None
            self._tracks = []
            self._index = 0
            self._pushed = []

        if clear_queue:
            # Clear any remaining queued tracks
            for rid in queue_list():
                queue_ignore(rid)

    def _next_track(self):
        """Get the next track, wrapping and reshuffling when exhausted."""
        with self._lock:
            if not self._tracks:
                return None
            if self._index >= len(self._tracks):
                random.shuffle(self._tracks)
                self._index = 0
            track = self._tracks[self._index]
            self._index += 1
            return track

    def _push_batch(self, count):
        """Push N tracks to the queue."""
        for _ in range(count):
            track = self._next_track()
            if track is None:
                break
            filepath = track_filepath(track)
            if os.path.exists(filepath):
                if queue_push(filepath):
                    with self._lock:
                        self._pushed.append(track)

    def _feed_loop(self):
        """Poll loop: keep the queue topped up."""
        while not self._stop_event.wait(FEEDER_POLL_INTERVAL):
            pending = queue_list()
            if len(pending) < QUEUE_MIN:
                self._push_batch(QUEUE_PUSH)


# Global feeder instance
feeder = GenreFeeder()

# ---------------------------------------------------------------------------
# OpenAPI Spec
# ---------------------------------------------------------------------------

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "KNOB Radio Control API",
        "description": (
            "Control API for KNOB (Noisebridge Radio). Lets you switch genres, "
            "queue specific tracks, skip tracks, and query what's playing. "
            "The station streams 24/7 at https://nthmost.com/nbradio/stream.ogg. "
            "When a genre override is active, the station plays shuffled tracks "
            "from that genre instead of the normal schedule. When the queue is "
            "empty and no genre is set, the normal time-based schedule resumes."
        ),
        "version": "1.1.0",
    },
    "servers": [
        {"url": "http://localhost:8081", "description": "Local"},
        {"url": "http://beyla.local:8081", "description": "LAN"},
    ],
    "paths": {
        "/api/genres": {
            "get": {
                "operationId": "listGenres",
                "summary": "List all genres with track counts",
                "description": (
                    "Returns the full genre tree: parent genres, their subgenres, "
                    "and how many classified tracks are in each. Use the parent "
                    "genre name (and optionally a subgenre) with POST /api/genre."
                ),
                "responses": {
                    "200": {
                        "description": "Genre tree",
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {
                                "genres": {
                                    "type": "object",
                                    "description": "Map of parent genre name to {count, subgenres: {name: count}}",
                                    "additionalProperties": {
                                        "type": "object",
                                        "properties": {
                                            "count": {"type": "integer"},
                                            "subgenres": {"type": "object", "additionalProperties": {"type": "integer"}},
                                        },
                                    },
                                },
                            },
                        }}},
                    },
                },
            },
        },
        "/api/genre": {
            "get": {
                "operationId": "getGenreOverride",
                "summary": "Get current genre override status",
                "description": "Returns whether a genre override is active and its details.",
                "responses": {
                    "200": {
                        "description": "Genre override status",
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {
                                "active": {"type": "boolean"},
                                "genre": {"type": "string", "nullable": True},
                                "subgenre": {"type": "string", "nullable": True},
                                "tracks_available": {"type": "integer"},
                                "tracks_pushed": {"type": "integer"},
                            },
                        }}},
                    },
                },
            },
            "post": {
                "operationId": "setGenreOverride",
                "summary": "Set genre override",
                "description": (
                    "Switch the station to play tracks from the specified genre. "
                    "Tracks are shuffled and fed to the queue automatically. "
                    "The switch takes effect after the current track finishes. "
                    "Use GET /api/genres to see available genre names."
                ),
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "required": ["genre"],
                        "properties": {
                            "genre": {"type": "string", "description": "Parent genre name, e.g. 'Bass', 'Chill', 'Electronic'"},
                            "subgenre": {"type": "string", "description": "Optional subgenre, e.g. 'Dubstep', 'Lofi'. Narrows the track pool."},
                        },
                    }}},
                },
                "responses": {
                    "200": {"description": "Genre set successfully"},
                    "400": {"description": "Missing genre parameter"},
                    "404": {"description": "No tracks found for that genre"},
                },
            },
            "delete": {
                "operationId": "clearGenreOverride",
                "summary": "Clear genre override",
                "description": "Stop the genre feed and return to the normal time-based schedule after the current track finishes.",
                "responses": {
                    "200": {"description": "Genre override cleared"},
                },
            },
        },
        "/api/queue": {
            "get": {
                "operationId": "getQueue",
                "summary": "Show queued tracks",
                "description": "Returns the number of pending tracks in the Liquidsoap request queue.",
                "responses": {
                    "200": {
                        "description": "Queue status",
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {
                                "count": {"type": "integer"},
                                "request_ids": {"type": "array", "items": {"type": "string"}},
                                "genre_feed": {"type": "object", "nullable": True},
                            },
                        }}},
                    },
                },
            },
            "post": {
                "operationId": "queueTrack",
                "summary": "Queue a specific track",
                "description": (
                    "Add a track to the playback queue. Provide either a track_id "
                    "(from search results or the genre DB) or a search string to "
                    "auto-select the best match. Queued tracks play after the "
                    "current track finishes, ahead of the normal schedule."
                ),
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "track_id": {"type": "integer", "description": "Database track ID"},
                            "search": {"type": "string", "description": "Search text (artist, title). Best match is queued."},
                        },
                    }}},
                },
                "responses": {
                    "200": {"description": "Track queued successfully"},
                    "400": {"description": "Missing track_id or search"},
                    "404": {"description": "Track not found"},
                },
            },
            "delete": {
                "operationId": "clearQueue",
                "summary": "Clear all queued tracks",
                "description": "Remove all pending tracks from the queue. Does not affect the currently playing track.",
                "responses": {
                    "200": {"description": "Queue cleared"},
                },
            },
        },
        "/api/skip": {
            "post": {
                "operationId": "skipTrack",
                "summary": "Skip the current track",
                "description": "Immediately end the current track. The next queued track (or schedule) takes over.",
                "responses": {
                    "200": {"description": "Track skipped"},
                },
            },
        },
        "/api/search": {
            "get": {
                "operationId": "searchTracks",
                "summary": "Search the music library",
                "description": "Search tracks by artist name, song title, or filename. Optionally filter by genre.",
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}, "description": "Search text"},
                    {"name": "genre", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Filter by parent genre"},
                    {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "default": 20, "maximum": 100}, "description": "Max results"},
                ],
                "responses": {
                    "200": {
                        "description": "Search results",
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {
                                "count": {"type": "integer"},
                                "results": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "path": {"type": "string"},
                                            "artist": {"type": "string"},
                                            "title": {"type": "string"},
                                            "genre_parent": {"type": "string"},
                                            "genre_sub": {"type": "string"},
                                            "duration": {"type": "number", "description": "Duration in seconds"},
                                        },
                                    },
                                },
                            },
                        }}},
                    },
                },
            },
        },
        "/api/now-playing": {
            "get": {
                "operationId": "getNowPlaying",
                "summary": "Get current playback state",
                "description": (
                    "Returns what's currently playing (artist, title, source), "
                    "time remaining, listener count, schedule info, plus genre "
                    "override and queue depth."
                ),
                "responses": {
                    "200": {
                        "description": "Current playback state",
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {
                                "artist": {"type": "string", "description": "Current track artist"},
                                "title": {"type": "string", "description": "Current track title"},
                                "filename": {"type": "string", "description": "Basename of the audio file"},
                                "remaining": {"type": "number", "nullable": True, "description": "Seconds remaining in current track"},
                                "remaining_fmt": {"type": "string", "description": "Remaining time in M:SS format"},
                                "source": {"type": "string", "description": "Active source: AUTODJ, Pandora's Box, Noisefloor, or LIVE DJ"},
                                "scheduled_source": {"type": "string", "description": "What the time-based schedule says should be playing"},
                                "next_source": {"type": "string", "description": "Next scheduled source name"},
                                "next_hour_fmt": {"type": "string", "description": "Hour when next source change occurs (e.g. '5pm')"},
                                "listeners": {"type": "integer", "description": "Current Icecast listener count"},
                                "listener_peak": {"type": "integer", "description": "Peak listener count since stream start"},
                                "time": {"type": "string", "description": "Current server time (HH:MM:SS AM/PM)"},
                                "icecast_connected": {"type": "boolean", "description": "Whether Icecast is reachable"},
                                "dj_connected": {"type": "boolean", "description": "Whether a live DJ is connected to the harbor input"},
                                "dj_client_ip": {"type": "string", "nullable": True, "description": "IP address of connected DJ client"},
                                "shazam_artist": {"type": "string", "description": "Shazam-recognized artist (for DJ sets)"},
                                "shazam_title": {"type": "string", "description": "Shazam-recognized title (for DJ sets)"},
                                "shazam_url": {"type": "string", "description": "Shazam match URL"},
                                "genre_override": {
                                    "type": "object", "nullable": True,
                                    "description": "Active genre override, or null if normal schedule",
                                    "properties": {
                                        "genre": {"type": "string", "description": "Parent genre name"},
                                        "subgenre": {"type": "string", "nullable": True, "description": "Subgenre name"},
                                        "tracks_available": {"type": "integer"},
                                        "tracks_pushed": {"type": "integer"},
                                        "position": {"type": "integer"},
                                    },
                                },
                                "queue_depth": {"type": "integer", "description": "Number of tracks in the Liquidsoap queue"},
                            },
                        }}},
                    },
                },
            },
        },
        "/api/spec": {
            "get": {
                "operationId": "getSpec",
                "summary": "OpenAPI spec for this API",
                "responses": {"200": {"description": "This document"}},
            },
        },
    },
}

# ---------------------------------------------------------------------------
# HTTP API Handler
# ---------------------------------------------------------------------------

def json_response(handler, data, status=200):
    payload = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(payload)


def read_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw)


class RadioAPIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if path == "/api/genres":
            self._handle_genres_list()
        elif path == "/api/genre":
            self._handle_genre_get()
        elif path == "/api/queue":
            self._handle_queue_get()
        elif path == "/api/search":
            self._handle_search(params)
        elif path == "/api/now-playing":
            self._handle_now_playing()
        elif path == "/api/spec":
            self._handle_spec()
        elif path == "" or path == "/":
            self._handle_index()
        else:
            json_response(self, {"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/genre":
            self._handle_genre_set()
        elif path == "/api/queue":
            self._handle_queue_add()
        elif path == "/api/skip":
            self._handle_skip()
        else:
            json_response(self, {"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/genre":
            self._handle_genre_clear()
        elif path == "/api/queue":
            self._handle_queue_clear()
        else:
            json_response(self, {"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # --- Genres ---

    def _handle_genres_list(self):
        genres = db_genre_stats()
        json_response(self, {"genres": genres})

    def _handle_genre_get(self):
        status = feeder.status()
        if status:
            json_response(self, {"active": True, **status})
        else:
            json_response(self, {"active": False, "genre": None, "subgenre": None})

    def _handle_genre_set(self):
        body = read_body(self)
        genre = body.get("genre")
        subgenre = body.get("subgenre")

        if not genre:
            json_response(self, {"error": "genre is required"}, 400)
            return

        ok = feeder.start(genre, subgenre)
        if not ok:
            json_response(self, {
                "error": f"no tracks found for genre '{genre}'" +
                         (f" / '{subgenre}'" if subgenre else "")
            }, 404)
            return

        status = feeder.status()
        json_response(self, {"ok": True, "message": f"Genre set to {genre}" +
                             (f" / {subgenre}" if subgenre else ""), **status})

    def _handle_genre_clear(self):
        was_active = feeder.active
        feeder.stop(clear_queue=True)
        json_response(self, {
            "ok": True,
            "message": "Genre override cleared" if was_active else "No genre override was active",
        })

    # --- Queue ---

    def _handle_queue_get(self):
        rids = queue_list()
        json_response(self, {
            "count": len(rids),
            "request_ids": rids,
            "genre_feed": feeder.status(),
        })

    def _handle_queue_add(self):
        body = read_body(self)
        track_id = body.get("track_id")
        search = body.get("search")

        if track_id:
            track = db_get_track_by_id(int(track_id))
            if not track:
                json_response(self, {"error": f"track {track_id} not found"}, 404)
                return
        elif search:
            results = db_search_tracks(search, limit=1)
            if not results:
                json_response(self, {"error": f"no tracks found for '{search}'"}, 404)
                return
            track = results[0]
        else:
            json_response(self, {"error": "track_id or search is required"}, 400)
            return

        filepath = track_filepath(track)
        if not os.path.exists(filepath):
            json_response(self, {"error": f"file not found on disk: {track['path']}"}, 404)
            return

        ok = queue_push(filepath)
        if ok:
            json_response(self, {
                "ok": True,
                "queued": {
                    "id": track["id"],
                    "artist": track.get("artist", ""),
                    "title": track.get("title", ""),
                    "path": track["path"],
                },
            })
        else:
            json_response(self, {"error": "failed to push to liquidsoap queue"}, 500)

    def _handle_queue_clear(self):
        rids = queue_list()
        for rid in rids:
            queue_ignore(rid)
        json_response(self, {"ok": True, "cleared": len(rids)})

    # --- Skip ---

    def _handle_skip(self):
        resp = skip_track()
        json_response(self, {"ok": True, "response": resp})

    # --- Search ---

    def _handle_search(self, params):
        query = params.get("q", [""])[0]
        genre = params.get("genre", [None])[0]
        limit = int(params.get("limit", [20])[0])
        limit = min(limit, 100)

        if not query:
            json_response(self, {"error": "q parameter is required"}, 400)
            return

        results = db_search_tracks(query, genre=genre, limit=limit)
        json_response(self, {"results": results, "count": len(results)})

    # --- Now Playing (proxy + extra state) ---

    def _handle_now_playing(self):
        # Fetch from the existing nowplaying service
        import urllib.request
        try:
            req = urllib.request.Request(
                "http://localhost:8080/api/now-playing",
                headers={"User-Agent": "radio-api"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
        except Exception:
            data = {"error": "could not reach nowplaying service"}

        # Augment with genre/queue state
        data["genre_override"] = feeder.status()
        data["queue_depth"] = len(queue_list())
        json_response(self, data)

    # --- Index ---

    def _handle_index(self):
        info = {
            "service": "KNOB Radio Control API",
            "version": "1.1.0",
            "spec": "/api/spec",
            "stream": "https://nthmost.com/nbradio/stream.ogg",
            "endpoints": {
                "GET /api/genres": "List genres with track counts",
                "GET /api/genre": "Current genre override status",
                "POST /api/genre": "Set genre override: {genre, subgenre?}",
                "DELETE /api/genre": "Clear genre override",
                "GET /api/queue": "Show queued tracks",
                "POST /api/queue": "Queue a track: {track_id} or {search}",
                "DELETE /api/queue": "Clear all queued tracks",
                "POST /api/skip": "Skip current track",
                "GET /api/search?q=&genre=&limit=": "Search tracks",
                "GET /api/now-playing": "Now playing + genre/queue state",
                "GET /api/spec": "OpenAPI 3.0 spec (this API)",
            },
        }
        json_response(self, info)

    # --- Spec ---

    def _handle_spec(self):
        json_response(self, OPENAPI_SPEC)

    def log_message(self, format, *args):
        # Quiet logging — only log errors
        if args and str(args[0]).startswith("4") or str(args[0]).startswith("5"):
            BaseHTTPRequestHandler.log_message(self, format, *args)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="KNOB Radio Control API")
    parser.add_argument("--port", type=int, default=8081, help="HTTP port (default: 8081)")
    parser.add_argument("--bind", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    args = parser.parse_args()

    # Verify DB is accessible
    if not os.path.exists(DB_PATH):
        print(f"WARNING: Genre database not found at {DB_PATH}")
        print("Genre and search endpoints will not work until the DB is available.")

    server = ThreadingHTTPServer((args.bind, args.port), RadioAPIHandler)
    print(f"KNOB Radio API: http://{args.bind}:{args.port}/")
    print(f"Genre DB: {DB_PATH}")
    print(f"Liquidsoap telnet: {TELNET_HOST}:{TELNET_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

    # Clean shutdown
    feeder.stop(clear_queue=False)
    server.server_close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""KNOB - Now Playing Web Dashboard

Zero-dependency HTTP server serving a live dashboard and JSON API.
Reuses data-fetching functions from nowplaying.py.
"""

import argparse
import json
import os
import threading
import time
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from nowplaying import (
    fetch_icecast_status,
    get_telnet_metadata,
    get_remaining,
    get_scheduled_source,
    get_next_change,
    format_duration,
    format_hour,
    SCHEDULE,
)

# --- Response cache -----------------------------------------------------------

_cache_lock = threading.Lock()
_cache = {"data": None, "ts": 0}
CACHE_TTL = 1.5


def get_now_playing():
    """Return now-playing dict, cached for CACHE_TTL seconds."""
    now_ts = time.monotonic()
    with _cache_lock:
        if _cache["data"] is not None and (now_ts - _cache["ts"]) < CACHE_TTL:
            return _cache["data"]

    icecast = fetch_icecast_status()
    telnet_meta = get_telnet_metadata()
    remaining = get_remaining()

    now = datetime.now()
    hour = now.hour
    current_source, _ = get_scheduled_source(hour)
    next_hour, next_source = get_next_change(hour)

    artist = ""
    title = ""
    filename = ""

    if telnet_meta:
        artist = telnet_meta.get("artist", "")
        title = telnet_meta.get("title", "")
        filename = telnet_meta.get("filename", "")

    if icecast and not (artist and title):
        artist = artist or icecast.get("artist", "")
        title = title or icecast.get("title", "")

    # Detect source from filename
    source = current_source
    if filename:
        if "MOBCOIN" in filename:
            source = "Noisefloor"
        elif "pandoras_box" in filename:
            source = "Pandora's Box"
        else:
            source = "AUTODJ"

    listeners = 0
    listener_peak = 0
    if icecast:
        listeners = icecast.get("listeners", 0)
        listener_peak = icecast.get("listener_peak", 0)

    data = {
        "artist": artist,
        "title": title,
        "filename": os.path.basename(filename) if filename else "",
        "remaining": round(remaining, 1) if remaining is not None else None,
        "remaining_fmt": format_duration(remaining),
        "source": source,
        "scheduled_source": current_source,
        "next_source": next_source or "",
        "next_hour_fmt": format_hour(next_hour) if next_hour is not None else "",
        "listeners": listeners,
        "listener_peak": listener_peak,
        "time": now.strftime("%I:%M:%S %p"),
        "icecast_connected": icecast is not None,
    }

    with _cache_lock:
        _cache["data"] = data
        _cache["ts"] = time.monotonic()

    return data


# --- HTML Dashboard -----------------------------------------------------------

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KNOB</title>
<style>
  :root {
    --bg: #0e0e12;
    --card: #16161d;
    --border: #2a2a35;
    --text: #e0e0e0;
    --dim: #7a7a8a;
    --accent: #6ec6ff;
    --green: #66d9a0;
    --yellow: #f0c674;
    --magenta: #c792ea;
    --red: #f07178;
    --cyan: #89ddff;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2rem 1rem;
  }
  h1 {
    font-size: 1.1rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 1.5rem;
    text-align: center;
  }
  .status-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 0.5rem;
    vertical-align: middle;
    background: var(--green);
    box-shadow: 0 0 6px var(--green);
    transition: all 0.3s;
  }
  .status-dot.disconnected {
    background: var(--red);
    box-shadow: 0 0 6px var(--red);
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    width: 100%;
    max-width: 540px;
    margin-bottom: 1rem;
  }
  .card-title {
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--dim);
    margin-bottom: 0.75rem;
  }
  .now-playing .track {
    font-size: 1.15rem;
    line-height: 1.5;
    min-height: 1.8em;
  }
  .now-playing .artist {
    color: var(--cyan);
    font-weight: 600;
  }
  .now-playing .separator {
    color: var(--dim);
    margin: 0 0.3em;
  }
  .now-playing .title-text {
    color: var(--text);
    font-weight: 600;
  }
  .now-playing .filename {
    color: var(--dim);
    font-size: 0.8rem;
    margin-top: 0.25rem;
    word-break: break-all;
  }
  .remaining {
    font-size: 2rem;
    font-weight: 700;
    color: var(--yellow);
    margin-top: 0.5rem;
    font-variant-numeric: tabular-nums;
  }
  .source-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    margin-top: 0.5rem;
  }
  .source-badge.autodj { background: #1a3a2a; color: var(--green); border: 1px solid #2a5a3a; }
  .source-badge.pandora { background: #2a1a3a; color: var(--magenta); border: 1px solid #3a2a5a; }
  .source-badge.mobcoin { background: #3a2a1a; color: var(--yellow); border: 1px solid #5a3a2a; }
  .source-badge.dj { background: #1a2a3a; color: var(--accent); border: 1px solid #2a3a5a; }
  .player-wrap { display: flex; align-items: center; gap: 0.75rem; }
  .play-btn {
    width: 44px; height: 44px;
    border-radius: 50%;
    border: 2px solid var(--accent);
    background: transparent;
    color: var(--accent);
    font-size: 1.2rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background 0.2s, color 0.2s;
  }
  .play-btn:hover { background: var(--accent); color: var(--bg); }
  .play-btn.playing { background: var(--accent); color: var(--bg); }
  .player-status {
    font-size: 0.8rem;
    color: var(--dim);
  }
  .player-status.active { color: var(--green); }
  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.35rem 0;
    border-bottom: 1px solid var(--border);
  }
  .info-row:last-child { border-bottom: none; }
  .info-label {
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--dim);
    flex-shrink: 0;
  }
  .info-value {
    text-align: right;
    font-size: 0.9rem;
  }
  .schedule-current { color: var(--text); }
  .schedule-next { color: var(--magenta); }
  .listeners-count { color: var(--cyan); }
  .clock { color: var(--dim); font-variant-numeric: tabular-nums; }
  .dj-card .info-value { color: var(--green); }
  .dj-card .info-label { min-width: 7em; }
  .footer {
    margin-top: 1rem;
    font-size: 0.7rem;
    color: var(--dim);
    text-align: center;
  }
  @media (max-width: 600px) {
    body { padding: 1rem 0.5rem; }
    .card { padding: 1rem; }
    .now-playing .track { font-size: 1rem; }
    .remaining { font-size: 1.5rem; }
  }
</style>
</head>
<body>

<h1><span class="status-dot" id="statusDot"></span> KNOB</h1>

<div class="card now-playing">
  <div class="card-title">Now Playing</div>
  <div class="track" id="track">--</div>
  <div class="filename" id="filename"></div>
  <div class="remaining" id="remaining">--:--</div>
  <div id="sourceBadge"></div>
</div>

<div class="card">
  <div class="card-title">Listen</div>
  <div class="player-wrap">
    <button class="play-btn" id="playBtn" onclick="togglePlay()" title="Play/Stop">&#9654;</button>
    <span class="player-status" id="playerStatus">Click to listen</span>
  </div>
  <audio id="audioEl" preload="none" src="stream.ogg" type="audio/ogg"></audio>
</div>

<div class="card">
  <div class="card-title">Schedule</div>
  <div class="info-row">
    <span class="info-label">Current</span>
    <span class="info-value schedule-current" id="scheduleCurrent">--</span>
  </div>
  <div class="info-row">
    <span class="info-label">Up Next</span>
    <span class="info-value schedule-next" id="scheduleNext">--</span>
  </div>
  <div class="info-row">
    <span class="info-label">Listeners</span>
    <span class="info-value listeners-count" id="listeners">--</span>
  </div>
  <div class="info-row">
    <span class="info-label">Time</span>
    <span class="info-value clock" id="clock">--</span>
  </div>
</div>

<div class="card dj-card">
  <div class="card-title">Connect as Live DJ</div>
  <div class="info-row">
    <span class="info-label">Protocol</span>
    <span class="info-value">Shoutcast / Icecast</span>
  </div>
  <div class="info-row">
    <span class="info-label">Host</span>
    <span class="info-value">beyla:8005</span>
  </div>
  <div class="info-row">
    <span class="info-label">User</span>
    <span class="info-value">nbradio</span>
  </div>
  <div class="info-row">
    <span class="info-label">Password</span>
    <span class="info-value">nbradio</span>
  </div>
</div>

<div class="footer">KNOB &middot; Broadcasting from the Noisefloor</div>

<script>
(function() {
  var POLL_MS = 2500;
  var remaining_s = null;
  var last_poll = 0;
  var countdown_id = null;

  function $(id) { return document.getElementById(id); }

  function sourceBadgeClass(src) {
    if (!src) return 'autodj';
    var s = src.toLowerCase();
    if (s.indexOf('noisefloor') !== -1) return 'mobcoin';
    if (s.indexOf('pandora') !== -1) return 'pandora';
    if (s.indexOf('dj') !== -1 && s.indexOf('auto') === -1) return 'dj';
    return 'autodj';
  }

  function fmtDuration(sec) {
    if (sec == null || sec < 0) return '--:--';
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  function update(d) {
    // Status dot
    $('statusDot').className = 'status-dot' + (d.icecast_connected ? '' : ' disconnected');

    // Track
    var trackEl = $('track');
    if (d.artist && d.title) {
      trackEl.innerHTML = '<span class="artist">' + esc(d.artist) + '</span>'
        + '<span class="separator"> &mdash; </span>'
        + '<span class="title-text">' + esc(d.title) + '</span>';
    } else if (d.title) {
      trackEl.innerHTML = '<span class="title-text">' + esc(d.title) + '</span>';
    } else if (d.filename) {
      trackEl.innerHTML = '<span class="title-text">' + esc(d.filename) + '</span>';
    } else {
      trackEl.textContent = 'No track info';
    }

    // Filename
    $('filename').textContent = d.filename || '';

    // Remaining
    remaining_s = d.remaining;
    last_poll = Date.now();
    $('remaining').textContent = d.remaining_fmt;

    // Source badge
    var badge = $('sourceBadge');
    badge.innerHTML = '<span class="source-badge ' + sourceBadgeClass(d.source) + '">'
      + esc(d.source) + '</span>';

    // Schedule
    if (d.next_source && d.next_hour_fmt) {
      $('scheduleCurrent').textContent = d.scheduled_source + ' until ' + d.next_hour_fmt;
      $('scheduleNext').textContent = d.next_source + ' at ' + d.next_hour_fmt;
    } else {
      $('scheduleCurrent').textContent = d.scheduled_source;
      $('scheduleNext').textContent = '--';
    }

    // Listeners
    $('listeners').textContent = d.listeners + ' (peak: ' + d.listener_peak + ')';

    // Clock
    $('clock').textContent = d.time;
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function tick() {
    if (remaining_s != null) {
      var elapsed = (Date.now() - last_poll) / 1000;
      var left = remaining_s - elapsed;
      if (left < 0) left = 0;
      $('remaining').textContent = fmtDuration(left);
    }
  }

  function poll() {
    var x = new XMLHttpRequest();
    x.open('GET', 'api/now-playing');
    x.timeout = 5000;
    x.onload = function() {
      if (x.status === 200) {
        try { update(JSON.parse(x.responseText)); } catch(e) {}
      }
    };
    x.send();
  }

  poll();
  setInterval(poll, POLL_MS);
  setInterval(tick, 500);
})();

function togglePlay() {
  var audio = document.getElementById('audioEl');
  var btn = document.getElementById('playBtn');
  var status = document.getElementById('playerStatus');
  if (audio.paused) {
    audio.load();
    audio.play().then(function() {
      btn.innerHTML = '&#9632;';
      btn.classList.add('playing');
      status.textContent = 'Streaming...';
      status.classList.add('active');
    }).catch(function(e) {
      status.textContent = 'Could not play: ' + e.message;
    });
  } else {
    audio.pause();
    btn.innerHTML = '&#9654;';
    btn.classList.remove('playing');
    status.textContent = 'Click to listen';
    status.classList.remove('active');
  }
}
</script>
</body>
</html>"""


# --- HTTP Handler -------------------------------------------------------------

class NowPlayingHandler(BaseHTTPRequestHandler):
    """Handle GET / and GET /api/now-playing."""

    def do_GET(self):
        # Normalize path: strip trailing slash for matching, but keep root as /
        path = self.path.split("?")[0].split("#")[0]

        if path == "/api/now-playing":
            data = get_now_playing()
            payload = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(payload)

        elif path in ("/", ""):
            payload = DASHBOARD_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """Quieter logging — just method + path."""
        pass


# --- Main ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="KNOB - Now Playing Web Dashboard")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")
    parser.add_argument("--bind", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.bind, args.port), NowPlayingHandler)
    print(f"Now Playing dashboard: http://{args.bind}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()

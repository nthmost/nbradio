#!/usr/bin/env python3
"""KNOB - Now Playing HUD

Low-tech terminal display showing current track, schedule, and stream info.
Uses Rich for rendering, polls Icecast JSON + Liquidsoap telnet for data.
"""

import argparse
import json
import socket
import time
import urllib.request
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group


# Schedule definition (must match radio.liq)
SCHEDULE = [
    (22, 2, "Noisefloor", "random"),
    (10, 11, "Pandora's Box", "show"),
    (17, 18, "Pandora's Box", "show"),
    (0, 24, "AUTODJ", "show"),  # default/fallback
]

ICECAST_URL = "http://localhost:8000/status-json.xsl"
TELNET_HOST = "localhost"
TELNET_PORT = 1234


def get_scheduled_source(hour):
    """Return the scheduled source name for a given hour."""
    for start, end, name, fmt in SCHEDULE:
        if start < end:
            if start <= hour < end:
                return name, fmt
        else:  # wraps midnight (e.g. 22-2)
            if hour >= start or hour < end:
                return name, fmt
    return "AUTODJ", "show"


def get_next_change(hour):
    """Return (next_hour, next_source) for the next schedule transition."""
    current_source, _ = get_scheduled_source(hour)
    for h in range(1, 25):
        check = (hour + h) % 24
        source, fmt = get_scheduled_source(check)
        if source != current_source:
            return check, source
    return None, None


def fetch_icecast_status():
    """Fetch stream status from Icecast JSON endpoint."""
    try:
        req = urllib.request.Request(ICECAST_URL, headers={"User-Agent": "nowplaying"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
        source = data.get("icestats", {}).get("source", {})
        if isinstance(source, list):
            source = source[0] if source else {}
        return {
            "artist": source.get("artist", ""),
            "title": source.get("title", ""),
            "listeners": source.get("listeners", 0),
            "listener_peak": source.get("listener_peak", 0),
            "stream_start": source.get("stream_start", ""),
            "bitrate": source.get("audio_bitrate", ""),
            "samplerate": source.get("audio_samplerate", ""),
        }
    except Exception:
        return None


def telnet_command(cmd, timeout=2):
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
        # Strip Liquidsoap telnet trailers (Bye! from quit, END from response)
        lines = text.splitlines()
        while lines and lines[-1].strip() in ("END", "Bye!"):
            lines.pop()
        return "\n".join(lines).strip()
    except Exception:
        return None


def get_remaining():
    """Get seconds remaining on current track from Liquidsoap."""
    resp = telnet_command("/stream_ogg.remaining")
    if resp:
        for line in resp.splitlines():
            line = line.strip()
            try:
                return float(line)
            except ValueError:
                continue
    return None


def parse_meta_block(text):
    """Parse key=value lines from a metadata response block."""
    meta = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, val = line.partition("=")
            meta[key.strip()] = val.strip().strip('"')
    return meta


def get_telnet_metadata():
    """Get current track metadata from Liquidsoap telnet."""
    resp = telnet_command("/stream_ogg.metadata")
    if not resp:
        return None

    # Parse the most recent metadata block (highest --- N --- number)
    blocks = resp.split("--- ")
    if len(blocks) < 2:
        return None

    # Last block is the most recent
    meta = parse_meta_block(blocks[-1])

    # Also get filename from request.on_air + request.metadata
    rid_resp = telnet_command("request.on_air")
    if rid_resp:
        rid = rid_resp.strip()
        req_meta_resp = telnet_command(f"request.metadata {rid}")
        if req_meta_resp:
            req_meta = parse_meta_block(req_meta_resp)
            if "filename" in req_meta:
                meta["filename"] = req_meta["filename"]
            if "initial_uri" in req_meta:
                meta["initial_uri"] = req_meta["initial_uri"]

    return meta if meta else None


def format_duration(seconds):
    """Format seconds as M:SS."""
    if seconds is None or seconds < 0:
        return "--:--"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def format_hour(h):
    """Format hour as 12h time."""
    if h == 0 or h == 24:
        return "12am"
    elif h == 12:
        return "12pm"
    elif h < 12:
        return f"{h}am"
    else:
        return f"{h-12}pm"


def build_display(icecast, telnet_meta, remaining):
    """Build the Rich display."""
    now = datetime.now()
    hour = now.hour
    current_source, current_fmt = get_scheduled_source(hour)
    next_hour, next_source = get_next_change(hour)

    # Track info
    artist = ""
    title = ""
    filename = ""

    if telnet_meta:
        artist = telnet_meta.get("artist", "")
        title = telnet_meta.get("title", "")
        filename = telnet_meta.get("filename", "")

    # Fall back to Icecast data if telnet didn't have it
    if icecast and not (artist and title):
        artist = artist or icecast.get("artist", "")
        title = title or icecast.get("title", "")

    # Build the track display
    if artist and title:
        track_text = Text()
        track_text.append(artist, style="bold cyan")
        track_text.append(" - ", style="dim")
        track_text.append(title, style="bold white")
    elif title:
        track_text = Text(title, style="bold white")
    elif filename:
        # Show just the filename basename if no metadata
        import os
        track_text = Text(os.path.basename(filename), style="bold white")
    else:
        track_text = Text("No track info", style="dim")

    # Remaining time
    remaining_text = format_duration(remaining)

    # Source from filename path
    detected_source = ""
    if filename:
        if "MOBCOIN" in filename:
            detected_source = "Noisefloor"
        elif "pandoras_box" in filename:
            detected_source = "Pandora's Box"
        elif "AUTODJ" in filename:
            detected_source = "AUTODJ"
        else:
            detected_source = "AUTODJ"

    source_display = detected_source or current_source

    # Listeners
    listeners = 0
    peak = 0
    if icecast:
        listeners = icecast.get("listeners", 0)
        peak = icecast.get("listener_peak", 0)

    # Main track panel
    track_table = Table(show_header=False, box=None, padding=(0, 1))
    track_table.add_column("label", style="dim", width=12)
    track_table.add_column("value")

    track_table.add_row("NOW PLAYING", track_text)
    track_table.add_row("REMAINING", Text(remaining_text, style="yellow"))
    track_table.add_row("SOURCE", Text(source_display, style="green bold"))

    track_panel = Panel(
        track_table,
        title="[bold]KNOB[/bold]",
        border_style="blue",
        padding=(1, 2),
    )

    # Schedule + stats panel
    info_table = Table(show_header=False, box=None, padding=(0, 1))
    info_table.add_column("label", style="dim", width=12)
    info_table.add_column("value")

    info_table.add_row(
        "SCHEDULE",
        Text(f"{current_source} until {format_hour(next_hour)}", style="white"),
    )
    if next_source:
        info_table.add_row(
            "UP NEXT",
            Text(f"{next_source} at {format_hour(next_hour)}", style="magenta"),
        )
    info_table.add_row(
        "LISTENERS",
        Text(f"{listeners} (peak: {peak})", style="cyan"),
    )
    info_table.add_row(
        "TIME",
        Text(now.strftime("%I:%M:%S %p"), style="dim"),
    )

    info_panel = Panel(
        info_table,
        border_style="dim",
        padding=(0, 2),
    )

    # DJ connection instructions
    dj_table = Table(show_header=False, box=None, padding=(0, 1))
    dj_table.add_column("label", style="dim", width=12)
    dj_table.add_column("value")

    dj_table.add_row(
        "PROTOCOL",
        Text("Shoutcast / Icecast source client", style="white"),
    )
    dj_table.add_row(
        "HOST:PORT",
        Text("beyla:8005", style="bold green"),
    )
    dj_table.add_row(
        "USER",
        Text("nbradio", style="yellow"),
    )
    dj_table.add_row(
        "PASSWORD",
        Text("nbradio", style="yellow"),
    )
    dj_table.add_row(
        "APPS",
        Text("OBS (recommended), Mixxx, Audio Hijack, or any Shoutcast-compatible source", style="dim"),
    )

    dj_panel = Panel(
        dj_table,
        title="[bold]Connect as Live DJ[/bold]",
        border_style="dim magenta",
        padding=(0, 2),
    )

    return Group(track_panel, info_panel, dj_panel)


def main():
    parser = argparse.ArgumentParser(description="KNOB - Now Playing HUD")
    parser.add_argument(
        "--interval", type=float, default=2.0, help="Refresh interval in seconds"
    )
    args = parser.parse_args()

    console = Console()

    with Live(console=console, refresh_per_second=2, screen=True) as live:
        while True:
            try:
                icecast = fetch_icecast_status()
                telnet_meta = get_telnet_metadata()
                remaining = get_remaining()
                display = build_display(icecast, telnet_meta, remaining)
                live.update(display)
            except KeyboardInterrupt:
                break
            except Exception:
                pass
            time.sleep(args.interval)


if __name__ == "__main__":
    main()

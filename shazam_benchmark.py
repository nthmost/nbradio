#!/usr/bin/env python3
"""KNOB Shazam Accuracy Benchmark

Periodically samples the stream, runs Shazam recognition, and compares
against the known track metadata from Liquidsoap. Logs results to a
CSV file for analysis.
"""

import asyncio
import csv
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime

# Add the nbradio dir to path so we can import nowplaying
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nowplaying import get_telnet_metadata, get_harbor_status
from shazamio import Shazam

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shazam_benchmark.csv")
SAMPLE_DURATION = 15
INTERVAL = 45  # seconds between attempts (15s capture + 30s wait)


def capture_sample(path, duration=SAMPLE_DURATION):
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", "http://localhost:8000/stream.ogg",
             "-t", str(duration), "-ar", "44100", "-ac", "1", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=duration + 10,
        )
        return True
    except Exception as e:
        print(f"  Capture failed: {e}")
        return False


async def recognize(path):
    try:
        shazam = Shazam()
        result = await shazam.recognize(path)
        track = result.get("track")
        if track:
            return {
                "shazam_artist": track.get("subtitle", ""),
                "shazam_title": track.get("title", ""),
                "shazam_url": track.get("url", ""),
                "error": None,
            }
        return {"shazam_artist": "", "shazam_title": "", "shazam_url": "", "error": None}
    except Exception as e:
        return {"shazam_artist": "", "shazam_title": "", "shazam_url": "", "error": str(e)}


def normalize(s):
    """Normalize a string for fuzzy comparison."""
    if not s:
        return ""
    return s.lower().strip()


def is_match(known_artist, known_title, shazam_artist, shazam_title):
    """Check if Shazam result matches known metadata (fuzzy)."""
    if not shazam_title:
        return False
    ka, kt = normalize(known_artist), normalize(known_title)
    sa, st = normalize(shazam_artist), normalize(shazam_title)
    # Title match (exact or substring)
    title_match = kt == st or kt in st or st in kt
    # Artist match (exact or substring)
    artist_match = ka == sa or ka in sa or sa in ka
    return title_match and artist_match


def main():
    # Create CSV with header if it doesn't exist
    write_header = not os.path.exists(LOG_FILE)
    if write_header:
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "source",
                "known_artist", "known_title", "known_file",
                "shazam_artist", "shazam_title", "shazam_url",
                "match", "dj_live",
            ])

    print(f"Shazam Accuracy Benchmark")
    print(f"Logging to: {LOG_FILE}")
    print(f"Sampling every {INTERVAL}s ({SAMPLE_DURATION}s capture)")
    print(f"Press Ctrl+C to stop and show results.\n")

    total = 0
    matches = 0
    identified = 0
    no_match = 0

    try:
        while True:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Get known metadata from Liquidsoap
            meta = get_telnet_metadata()
            harbor = get_harbor_status()
            dj_live = harbor["connected"]

            known_artist = meta.get("artist", "") if meta else ""
            known_title = meta.get("title", "") if meta else ""
            known_file = meta.get("filename", "") if meta else ""
            source = meta.get("source", "") if meta else ""

            if not known_file:
                known_file = meta.get("initial_uri", "") if meta else ""

            print(f"[{timestamp}] Known: {known_artist} - {known_title}")
            print(f"  File: {os.path.basename(known_file) if known_file else '(none)'}")

            # Capture and recognize
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sample_path = f.name

            try:
                if capture_sample(sample_path):
                    result = asyncio.run(recognize(sample_path))
                else:
                    result = {"shazam_artist": "", "shazam_title": "", "shazam_url": ""}
            finally:
                try:
                    os.unlink(sample_path)
                except OSError:
                    pass

            sa = result["shazam_artist"]
            st = result["shazam_title"]
            su = result["shazam_url"]
            err = result.get("error")

            if err:
                print(f"  Shazam: ERROR - {err}")
                print(f"  Result: SKIPPED (network error)")
                time.sleep(INTERVAL)
                continue

            matched = is_match(known_artist, known_title, sa, st)
            total += 1
            if st:
                identified += 1
                if matched:
                    matches += 1
                    status = "MATCH"
                else:
                    status = "WRONG"
            else:
                no_match += 1
                status = "NO MATCH"

            print(f"  Shazam: {sa} - {st}" if st else "  Shazam: (not identified)")
            print(f"  Result: {status}")
            pct = (matches / total * 100) if total else 0
            id_pct = (identified / total * 100) if total else 0
            print(f"  Running: {matches}/{total} correct ({pct:.0f}%), "
                  f"{identified}/{total} identified ({id_pct:.0f}%)\n")

            # Log to CSV
            with open(LOG_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp, source,
                    known_artist, known_title, known_file,
                    sa, st, su,
                    "yes" if matched else ("wrong" if st else "no"),
                    "yes" if dj_live else "no",
                ])

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print(f"\n{'='*60}")
        print(f"RESULTS: {total} samples")
        print(f"  Identified by Shazam: {identified}/{total} ({identified/total*100:.0f}%)" if total else "")
        print(f"  Correct matches:      {matches}/{total} ({matches/total*100:.0f}%)" if total else "")
        print(f"  Wrong matches:        {identified - matches}/{total}" if total else "")
        print(f"  Not identified:       {no_match}/{total} ({no_match/total*100:.0f}%)" if total else "")
        print(f"{'='*60}")
        print(f"Full log: {LOG_FILE}")


if __name__ == "__main__":
    main()

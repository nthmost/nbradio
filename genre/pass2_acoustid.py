"""
Pass 2: AcoustID fingerprint + MusicBrainz lookup.

Requires:
  - chromaprint-tools (apt): provides fpcalc binary
  - pyacoustid (pip): Python wrapper

Fingerprints each track, queries AcoustID for a match, then pulls genre
tags from MusicBrainz recordings.
"""

import subprocess
import time
import json
import os

try:
    import acoustid
    HAS_ACOUSTID = True
except ImportError:
    HAS_ACOUSTID = False

try:
    import urllib.request
    import urllib.parse
except ImportError:
    pass

from .taxonomy import normalize_tag, DISCOGS_TO_KNOB

# MusicBrainz rate limit: 1 req/sec
MB_API = "https://musicbrainz.org/ws/2"
MB_USER_AGENT = "KNOBRadioGenreIndexer/1.0 (nthmost@gmail.com)"
MB_DELAY = 1.1  # seconds between requests

# AcoustID rate limit: 3 req/sec
ACOUSTID_DELAY = 0.35


def check_dependencies():
    """Check if fpcalc and pyacoustid are available."""
    errors = []
    if not HAS_ACOUSTID:
        errors.append("pyacoustid not installed (pip install pyacoustid)")
    try:
        subprocess.run(["fpcalc", "-v"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        errors.append("fpcalc not found (apt install chromaprint-tools)")
    return errors


def get_acoustid_apikey():
    """Get AcoustID API key from environment or config."""
    key = os.environ.get("ACOUSTID_API_KEY")
    if key:
        return key
    # Try reading from a config file
    config_path = os.path.expanduser("~/.config/acoustid/apikey")
    if os.path.exists(config_path):
        with open(config_path) as f:
            return f.read().strip()
    return None


def fingerprint_file(filepath):
    """Get chromaprint fingerprint and duration using fpcalc."""
    try:
        result = subprocess.run(
            ["fpcalc", "-json", filepath],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return None, None
        data = json.loads(result.stdout)
        return data.get("fingerprint"), data.get("duration")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None, None


def lookup_acoustid(api_key, fingerprint, duration):
    """Query AcoustID API for a fingerprint match.

    Returns list of (musicbrainz_recording_id, score) tuples.
    """
    try:
        results = acoustid.lookup(
            api_key, fingerprint, duration,
            meta="recordings",
        )
    except Exception:
        return []

    matches = []
    for result in results.get("results", []):
        score = result.get("score", 0)
        for recording in result.get("recordings", []):
            mb_id = recording.get("id")
            if mb_id:
                matches.append((mb_id, score))
    return matches


def lookup_musicbrainz_tags(mb_recording_id):
    """Query MusicBrainz for genre tags on a recording.

    Returns list of (tag_name, count) tuples.
    """
    url = f"{MB_API}/recording/{mb_recording_id}?inc=tags&fmt=json"
    req = urllib.request.Request(url, headers={"User-Agent": MB_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return []

    tags = []
    for tag in data.get("tags", []):
        name = tag.get("name", "")
        count = tag.get("count", 0)
        if name:
            tags.append((name, count))
    return sorted(tags, key=lambda x: -x[1])


def classify_from_mb_tags(tags):
    """Try to map MusicBrainz tags to our taxonomy.

    Returns (parent, sub, confidence, raw_label) or (None, None, None, None).
    """
    for tag_name, count in tags:
        # Try direct tag normalization
        result = normalize_tag(tag_name)
        if result is not None:
            confidence = min(0.8, 0.5 + count * 0.05)
            return result[0], result[1], confidence, f"mb:{tag_name}"
    return None, None, None, None


def classify_track(db, track, api_key, verbose=False):
    """Classify a single track using AcoustID + MusicBrainz.

    Returns (genre_parent, genre_sub) or (None, None).
    """
    track_id = track["id"]
    filepath = f"/media/radio/{track['path']}"

    # Fingerprint
    fingerprint, duration = fingerprint_file(filepath)
    if not fingerprint:
        db.mark_pass_done(track_id, 2)
        if verbose:
            print(f"  [skip] {track['path']} (no fingerprint)")
        return None, None

    extra_fields = {}
    if duration:
        extra_fields["duration"] = duration

    # AcoustID lookup
    time.sleep(ACOUSTID_DELAY)
    matches = lookup_acoustid(api_key, fingerprint, duration)
    if not matches:
        db.mark_pass_done(track_id, 2)
        if extra_fields:
            db.update_track_fields(track_id, extra_fields)
        if verbose:
            print(f"  [skip] {track['path']} (no AcoustID match)")
        return None, None

    # Take best match
    mb_id, score = matches[0]
    extra_fields["acoustid"] = fingerprint[:32]  # store truncated
    extra_fields["musicbrainz_id"] = mb_id

    # MusicBrainz tag lookup
    time.sleep(MB_DELAY)
    tags = lookup_musicbrainz_tags(mb_id)
    parent, sub, confidence, raw_label = classify_from_mb_tags(tags)

    if parent:
        # Adjust confidence by AcoustID score
        confidence = confidence * score
        db.update_classification(
            track_id, parent, sub,
            "acoustid", confidence, raw_label, pass_num=2,
            extra_fields=extra_fields,
        )
        if verbose:
            print(f"  [acoustid] {track['path']} -> {parent}/{sub} ({confidence:.2f})")
    else:
        db.mark_pass_done(track_id, 2)
        if extra_fields:
            db.update_track_fields(track_id, extra_fields)
        if verbose:
            print(f"  [skip] {track['path']} (AcoustID match but no usable tags)")

    return parent, sub


def run_pass2(db, verbose=False, limit=None):
    """Run Pass 2 on all unclassified tracks that need it.

    Returns (classified_count, skipped_count).
    """
    errors = check_dependencies()
    if errors:
        print("Pass 2 dependency errors:")
        for e in errors:
            print(f"  - {e}")
        return 0, 0

    api_key = get_acoustid_apikey()
    if not api_key:
        print("No AcoustID API key found.")
        print("Set ACOUSTID_API_KEY env var or create ~/.config/acoustid/apikey")
        return 0, 0

    # Only run on tracks that still have no genre after pass 1
    tracks = db.get_tracks_needing_pass(2, limit=limit)
    # Filter to only those without a genre already
    tracks = [t for t in tracks if t["genre_parent"] is None]

    if not tracks:
        print("No unclassified tracks need Pass 2.")
        return 0, 0

    print(f"Pass 2: {len(tracks)} tracks to process")
    classified = 0
    skipped = 0

    for i, track in enumerate(tracks, 1):
        if verbose:
            print(f"  [{i}/{len(tracks)}]", end="")
        parent, sub = classify_track(db, track, api_key, verbose=verbose)
        if parent:
            classified += 1
        else:
            skipped += 1

    return classified, skipped

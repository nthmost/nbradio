"""
Pass 1: Metadata-based genre classification.

Reads ID3/Vorbis/MP4 tags via mutagen, normalizes genre strings using the
mapping table, and falls back to directory name hints.
"""

import mutagen
from .taxonomy import normalize_tag, directory_hint


def classify_track(db, track, verbose=False):
    """Classify a single track using metadata.

    Args:
        db: GenreDB instance
        track: sqlite3.Row from the tracks table
        verbose: print progress

    Returns:
        (genre_parent, genre_sub) or (None, None)
    """
    track_id = track["id"]
    filepath = f"/media/radio/{track['path']}"

    genre_parent = None
    genre_sub = None
    source = None
    confidence = None
    raw_label = None
    extra_fields = {}

    # Try reading tags
    try:
        audio = mutagen.File(filepath, easy=True)
    except Exception:
        audio = None

    if audio:
        # Extract metadata fields
        artist = _first(audio.get("artist"))
        title = _first(audio.get("title"))
        album = _first(audio.get("album"))
        extra_fields = {}
        if artist:
            extra_fields["artist"] = artist
        if title:
            extra_fields["title"] = title
        if album:
            extra_fields["album"] = album

        # Try to get duration
        if hasattr(audio, "info") and audio.info and hasattr(audio.info, "length"):
            extra_fields["duration"] = audio.info.length

        # Try genre tag
        genres = audio.get("genre", [])
        if genres:
            raw_label = genres[0].strip()
            result = normalize_tag(raw_label)
            if result is not None:
                genre_parent, genre_sub = result
                source = "metadata"
                confidence = 0.9

    # Fall back to directory hints if no genre from tags
    if genre_parent is None:
        dir_result = directory_hint(track["directory"])
        if dir_result is not None:
            genre_parent, genre_sub = dir_result
            source = "directory"
            confidence = 0.7
            raw_label = f"dir:{track['directory']}"

    # Always update metadata fields even if no genre found
    if extra_fields:
        db.update_track_fields(track_id, extra_fields)

    if genre_parent:
        db.update_classification(
            track_id, genre_parent, genre_sub,
            source, confidence, raw_label, pass_num=1,
            extra_fields=extra_fields,
        )
        if verbose:
            print(f"  [{source}] {track['path']} -> {genre_parent}/{genre_sub}")
    else:
        db.mark_pass_done(track_id, 1)
        if verbose:
            print(f"  [skip] {track['path']} (no metadata match)")

    return genre_parent, genre_sub


def run_pass1(db, verbose=False, limit=None):
    """Run Pass 1 on all tracks that need it.

    Returns (classified_count, skipped_count).
    """
    tracks = db.get_tracks_needing_pass(1, limit=limit)
    classified = 0
    skipped = 0

    for track in tracks:
        parent, sub = classify_track(db, track, verbose=verbose)
        if parent:
            classified += 1
        else:
            skipped += 1

    return classified, skipped


def _first(lst):
    """Get first element of a list or None."""
    if lst and len(lst) > 0:
        return lst[0]
    return None

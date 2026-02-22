"""
Reporting and export for the genre index.

Provides stats breakdowns and exports to JSON, CSV, and M3U formats.
"""

import json
import csv
import os
import sys
from .taxonomy import TAXONOMY


def report_summary(db):
    """Print a high-level summary of the index."""
    total = db.count_tracks()
    songs = db.count_tracks("content_type = 'song'")
    classified = db.count_tracks("content_type = 'song' AND genre_parent IS NOT NULL")
    unclassified = db.count_tracks("content_type = 'song' AND genre_parent IS NULL")

    print(f"\n{'='*60}")
    print(f"  KNOB Radio Genre Index Summary")
    print(f"{'='*60}")
    print(f"  Total tracks:    {total:,}")
    print(f"  Songs:           {songs:,}")
    print(f"  Classified:      {classified:,} ({classified/songs*100:.1f}%)" if songs else "")
    print(f"  Unclassified:    {unclassified:,}")
    print()

    # Content type breakdown
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT content_type, COUNT(*) as cnt FROM tracks GROUP BY content_type ORDER BY cnt DESC"
        ).fetchall()
    print("  Content types:")
    for row in rows:
        print(f"    {row['content_type']:15s} {row['cnt']:5,}")

    # Source breakdown
    with db.connection() as conn:
        rows = conn.execute(
            """SELECT genre_source, COUNT(*) as cnt FROM tracks
               WHERE genre_parent IS NOT NULL
               GROUP BY genre_source ORDER BY cnt DESC"""
        ).fetchall()
    if rows:
        print("\n  Classification sources:")
        for row in rows:
            src = row['genre_source'] or 'none'
            print(f"    {src:15s} {row['cnt']:5,}")

    # Pass completion
    p1 = db.count_tracks("pass1_done = 1 AND content_type = 'song'")
    p2 = db.count_tracks("pass2_done = 1 AND content_type = 'song'")
    p3 = db.count_tracks("pass3_done = 1 AND content_type = 'song'")
    print(f"\n  Pass completion (songs):")
    print(f"    Pass 1 (metadata):  {p1:,}")
    print(f"    Pass 2 (acoustid):  {p2:,}")
    print(f"    Pass 3 (maest):     {p3:,}")
    print()


def report_by_parent(db):
    """Print genre distribution by parent genre."""
    stats = db.genre_stats("genre_parent")
    unclassified = db.count_tracks("content_type = 'song' AND genre_parent IS NULL")

    print(f"\n{'='*60}")
    print(f"  Genre Distribution (Parent)")
    print(f"{'='*60}")

    total_classified = sum(row["cnt"] for row in stats)
    for row in stats:
        if row["genre_parent"] is None:
            continue
        pct = row["cnt"] / total_classified * 100 if total_classified else 0
        bar = "#" * int(pct / 2)
        print(f"  {row['genre_parent']:15s} {row['cnt']:5,}  {pct:5.1f}%  {bar}")

    if unclassified:
        print(f"  {'(unclassified)':15s} {unclassified:5,}")
    print()


def report_by_sub(db):
    """Print genre distribution by subgenre."""
    stats = db.genre_stats("genre_parent, genre_sub")

    print(f"\n{'='*60}")
    print(f"  Genre Distribution (Subgenre)")
    print(f"{'='*60}")

    current_parent = None
    for row in stats:
        parent = row["genre_parent"]
        if parent is None:
            continue
        sub = row["genre_sub"] or "(none)"
        if parent != current_parent:
            print(f"\n  {parent}:")
            current_parent = parent
        print(f"    {sub:25s} {row['cnt']:5,}")
    print()


def report_unclassified(db):
    """Print details of unclassified tracks."""
    tracks = db.get_unclassified()

    print(f"\n{'='*60}")
    print(f"  Unclassified Tracks ({len(tracks)})")
    print(f"{'='*60}")

    # Group by directory
    by_dir = {}
    for t in tracks:
        d = t["directory"]
        by_dir.setdefault(d, []).append(t)

    for d in sorted(by_dir):
        print(f"\n  {d}/ ({len(by_dir[d])} tracks)")
        for t in by_dir[d][:10]:
            artist = t["artist"] or ""
            title = t["title"] or t["filename"]
            if artist:
                print(f"    {artist} - {title}")
            else:
                print(f"    {title}")
        if len(by_dir[d]) > 10:
            print(f"    ... and {len(by_dir[d]) - 10} more")
    print()


def export_json(db, output_path, genre_parent=None, genre_sub=None):
    """Export tracks to JSON."""
    tracks = db.get_tracks_by_genre(parent=genre_parent, sub=genre_sub)
    data = []
    for t in tracks:
        data.append({
            "path": t["path"],
            "artist": t["artist"],
            "title": t["title"],
            "album": t["album"],
            "genre_parent": t["genre_parent"],
            "genre_sub": t["genre_sub"],
            "genre_source": t["genre_source"],
            "genre_confidence": t["genre_confidence"],
            "duration": t["duration"],
            "content_type": t["content_type"],
        })

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Exported {len(data)} tracks to {output_path}")


def export_csv(db, output_path, genre_parent=None, genre_sub=None):
    """Export tracks to CSV."""
    tracks = db.get_tracks_by_genre(parent=genre_parent, sub=genre_sub)
    fieldnames = [
        "path", "artist", "title", "album", "genre_parent", "genre_sub",
        "genre_source", "genre_confidence", "duration", "content_type",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in tracks:
            writer.writerow({k: t[k] for k in fieldnames})
    print(f"Exported {len(tracks)} tracks to {output_path}")


def export_m3u(db, output_path, genre_parent=None, genre_sub=None,
               media_root="/media/radio/"):
    """Export tracks to M3U playlist."""
    tracks = db.get_tracks_by_genre(parent=genre_parent, sub=genre_sub)

    label = genre_sub or genre_parent or "All Songs"

    with open(output_path, "w") as f:
        f.write("#EXTM3U\n")
        f.write(f"# KNOB Radio - {label}\n")
        f.write(f"# {len(tracks)} tracks\n\n")
        for t in tracks:
            duration = int(t["duration"]) if t["duration"] else -1
            artist = t["artist"] or "Unknown"
            title = t["title"] or t["filename"]
            f.write(f"#EXTINF:{duration},{artist} - {title}\n")
            f.write(f"{media_root}{t['path']}\n")
    print(f"Exported {len(tracks)} tracks to {output_path}")
